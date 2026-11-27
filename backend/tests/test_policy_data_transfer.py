"""Policy-only exchange; every database and snapshot here is temporary."""

import json
import os
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.services.database_backup import restore_database
from app.services.policy_data_transfer import export_policies, import_policies, inspect_policies


def make_db(path, name="original", service_id="S1"):
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    WelfareService.__table__.create(engine)
    WelfareEligibilityCondition.__table__.create(engine)
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        session.add(WelfareService(serv_id=service_id, serv_name=name,
                                  application_methods=[{"enabled": False, "count": 0, "empty": [], "missing": None}]))
        session.flush()
        session.add(WelfareEligibilityCondition(serv_id=service_id, condition_type="age",
                    operator="gte", value_number=19, source_field="target_details",
                    source_text="synthetic age", comparison_ready=True, parse_status="parsed"))
        session.commit()
    engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, private_value TEXT);
            INSERT INTO users VALUES (1, 'PRIVATE_USER_SENTINEL');
            CREATE TABLE accounts (id INTEGER PRIMARY KEY, private_value TEXT);
            INSERT INTO accounts VALUES (1, 'PRIVATE_ACCOUNT_SENTINEL');
            CREATE TABLE sync_state (id INTEGER PRIMARY KEY, state TEXT);
            INSERT INTO sync_state VALUES (1, 'local progress only');
            CREATE TABLE policy_reference (serv_id TEXT REFERENCES welfare_services(serv_id));
        """)
        connection.execute("INSERT INTO policy_reference VALUES (?)", (service_id,))


def rows(path, table):
    with sqlite3.connect(path) as connection:
        return connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()


@pytest.fixture
def exchange(tmp_path):
    source, target, snapshot, backup = [tmp_path / name for name in
                                      ("source.db", "target.db", "policies.json", "backup.db")]
    make_db(source, "incoming")
    make_db(target)
    export_policies(source, snapshot)
    return source, target, snapshot, backup


def test_export_allowlist_types_and_source_unchanged(tmp_path):
    database, snapshot = tmp_path / "source.db", tmp_path / "data.json"
    make_db(database)
    before = database.read_bytes()
    report = export_policies(database, snapshot)
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert report["service_count"] == 1
    assert set(data["data"]) == {"welfare_services", "welfare_eligibility_conditions"}
    assert "PRIVATE_" not in snapshot.read_text(encoding="utf-8")
    condition = data["data"]["welfare_eligibility_conditions"][0]
    assert "id" not in condition
    assert condition["comparison_ready"] is True
    assert condition["upper_value_number"] is None
    assert data["data"]["welfare_services"][0]["application_methods"] == [
        {"enabled": False, "count": 0, "empty": [], "missing": None}]
    assert database.read_bytes() == before
    assert inspect_policies(snapshot)["condition_count"] == 1
    with pytest.raises(FileExistsError):
        export_policies(database, snapshot)


def test_preview_does_not_write_and_apply_requires_backup(exchange):
    _, target, snapshot, _ = exchange
    before = target.read_bytes()
    report = import_policies(target, snapshot)
    assert report["applied"] is False
    assert report["updated_services"] == 1
    assert target.read_bytes() == before
    with pytest.raises(ValueError):
        import_policies(target, snapshot, apply=True)
    assert target.read_bytes() == before


def test_import_upserts_preserves_private_data_and_other_policies(exchange, tmp_path):
    source, target, snapshot, backup = exchange
    with sqlite3.connect(target) as connection:
        connection.execute("INSERT INTO welfare_services SELECT " +
                           ",".join("'KEEP'" if column == "serv_id" else f'"{column}"'
                                    for column in [r[1] for r in connection.execute("PRAGMA table_info(welfare_services)")]) +
                           " FROM welfare_services WHERE serv_id='S1'")
    private = {table: rows(target, table) for table in ("users", "accounts", "policy_reference", "sync_state")}
    report = import_policies(target, snapshot, apply=True, backup=backup)
    assert report["applied"] is True
    assert {table: rows(target, table) for table in private} == private
    assert rows(target, "welfare_services")[1][1] == "incoming"
    assert len(rows(target, "welfare_eligibility_conditions")) == 1
    assert len(rows(target, "welfare_services")) == 2
    assert rows(target, "welfare_eligibility_conditions")[0][1:] == rows(source, "welfare_eligibility_conditions")[0][1:]
    restored = tmp_path / "restored.db"
    restore_database(backup, restored)
    assert rows(restored, "welfare_services")[1][1] == "original"
    assert rows(restored, "users") == private["users"]
    with sqlite3.connect(restored) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(FileExistsError):
        import_policies(target, snapshot, apply=True, backup=backup)
    import_policies(target, snapshot, apply=True, backup=tmp_path / "second.db")
    assert len(rows(target, "welfare_eligibility_conditions")) == 1


def test_failed_condition_insert_rolls_back_parent_and_children(exchange):
    _, target, snapshot, backup = exchange
    with sqlite3.connect(target) as connection:
        connection.executescript("""CREATE TRIGGER fail_import BEFORE INSERT ON welfare_eligibility_conditions
            BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END;""")
    tables = ("welfare_services", "welfare_eligibility_conditions", "users", "accounts")
    before = {table: rows(target, table) for table in tables}
    with pytest.raises(sqlite3.IntegrityError):
        import_policies(target, snapshot, apply=True, backup=backup)
    assert {table: rows(target, table) for table in tables} == before
    assert backup.exists()
    with sqlite3.connect(target) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()


@pytest.mark.parametrize("damage", ["checksum", "version", "extra_table", "condition_id", "duplicate", "orphan", "bool", "nan"])
def test_invalid_snapshot_rejected_before_writes(exchange, damage):
    from app.services.policy_data_transfer import data_checksum
    _, target, snapshot, backup = exchange
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    data = document["data"]
    if damage == "checksum":
        document["sha256"] = "0" * 64
    elif damage == "version":
        document["format_version"] = 999
    elif damage == "extra_table":
        data["users"] = []
    elif damage == "condition_id":
        data["welfare_eligibility_conditions"][0]["id"] = 1
    elif damage == "duplicate":
        data["welfare_services"].append(data["welfare_services"][0])
        document["service_count"] = 2
    elif damage == "orphan":
        data["welfare_eligibility_conditions"][0]["serv_id"] = "absent"
    elif damage == "bool":
        data["welfare_eligibility_conditions"][0]["comparison_ready"] = "false"
    elif damage == "nan":
        data["welfare_eligibility_conditions"][0]["value_number"] = float("nan")
    if damage not in {"checksum", "nan"}:
        document["sha256"] = data_checksum(data)
    snapshot.write_text(json.dumps(document), encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        import_policies(target, snapshot, apply=True, backup=backup)
    assert target.read_bytes() == before
    assert not backup.exists()


def test_missing_database_is_not_created(exchange, tmp_path):
    _, _, snapshot, _ = exchange
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        import_policies(missing, snapshot)
    assert not missing.exists()


def test_cli_preview_and_safe_error_output(exchange, capsys):
    from scripts.policy_data import main
    source, target, snapshot, backup = exchange
    assert main(["export", "--database", str(source), "--output", str(snapshot.with_name("cli.json"))]) == 0
    assert main(["inspect", "--source", str(snapshot)]) == 0
    assert main(["import", "--database", str(target), "--source", str(snapshot)]) == 0
    assert '"applied": false' in capsys.readouterr().out
    assert main(["import", "--database", str(target), "--source", str(snapshot), "--apply"]) == 1
    output = capsys.readouterr()
    assert "PRIVATE_" not in output.out + output.err
    assert main(["import", "--database", str(target), "--source", str(snapshot),
                 "--apply", "--backup", str(backup)]) == 0
    assert '"applied": true' in capsys.readouterr().out


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm", "-mj123"])
def test_sqlite_sidecar_paths_cannot_be_used_for_backup_or_export(exchange, suffix):
    _, target, snapshot, _ = exchange
    sidecar = target.with_name(target.name + suffix)
    before = target.read_bytes()
    with pytest.raises(ValueError):
        import_policies(target, snapshot, apply=True, backup=sidecar)
    with pytest.raises(ValueError):
        export_policies(target, sidecar)
    assert target.read_bytes() == before
    assert not sidecar.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows filenames are case insensitive")
@pytest.mark.parametrize("suffix", ["-JOURNAL", "-WAL", "-SHM", "-MJ123"])
def test_mixed_case_windows_sidecar_is_also_rejected(exchange, suffix):
    _, target, snapshot, _ = exchange
    sidecar = target.with_name(target.name.upper() + suffix)
    with pytest.raises(ValueError):
        import_policies(target, snapshot, apply=True, backup=sidecar)
    with pytest.raises(ValueError):
        export_policies(target, sidecar)
    assert not sidecar.exists()


def test_new_policy_is_added_and_unmentioned_conditions_are_preserved(exchange, tmp_path):
    _, target, _, backup = exchange
    source, snapshot = tmp_path / "new-source.db", tmp_path / "new.json"
    make_db(source, "new policy", service_id="NEW")
    export_policies(source, snapshot)
    old_conditions = rows(target, "welfare_eligibility_conditions")
    report = import_policies(target, snapshot, apply=True, backup=backup)
    assert report["new_services"] == 1
    assert report["updated_services"] == 0
    assert len(rows(target, "welfare_services")) == 2
    assert rows(target, "welfare_eligibility_conditions")[:1] == old_conditions
    assert len(rows(target, "welfare_eligibility_conditions")) == 2


def test_duplicate_json_fields_and_incompatible_schema_rejected(exchange, tmp_path):
    _, target, snapshot, _ = exchange
    snapshot.write_text('{"format_version":1,"format_version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        inspect_policies(snapshot)
    empty = tmp_path / "empty.db"
    with sqlite3.connect(empty):
        pass
    with pytest.raises(ValueError, match="schema"):
        export_policies(empty, tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()


def test_integer_numeric_fields_are_accepted_by_sqlite_real_columns(exchange):
    from app.services.policy_data_transfer import data_checksum
    _, target, snapshot, backup = exchange
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    condition = document["data"]["welfare_eligibility_conditions"][0]
    condition["value_number"] = 19
    condition["confidence"] = 0
    document["sha256"] = data_checksum(document["data"])
    snapshot.write_text(json.dumps(document), encoding="utf-8")
    assert inspect_policies(snapshot)["condition_count"] == 1
    assert import_policies(target, snapshot, apply=True, backup=backup)["applied"] is True


def test_backup_failure_prevents_policy_mutation(exchange, monkeypatch):
    _, target, snapshot, backup = exchange
    before = target.read_bytes()

    def fail_backup(*args):
        raise sqlite3.DatabaseError("synthetic backup verification failure")

    monkeypatch.setattr("app.services.policy_data_transfer.backup_database", fail_backup)
    with pytest.raises(sqlite3.DatabaseError):
        import_policies(target, snapshot, apply=True, backup=backup)
    assert target.read_bytes() == before
    assert not backup.exists()


def test_wal_mode_online_backup_and_restore(exchange, tmp_path):
    source, target, snapshot, backup = exchange
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    export_policies(source, tmp_path / "wal.json")
    import_policies(target, snapshot, apply=True, backup=backup)
    restored = tmp_path / "wal-restored.db"
    restore_database(backup, restored)
    assert rows(restored, "welfare_services")[0][1] == "original"
    assert rows(target, "welfare_services")[0][1] == "incoming"
    assert rows(restored, "users") == rows(target, "users")


def test_bundled_policy_snapshot_roundtrip_in_isolated_database(tmp_path):
    """Real public policy snapshot, never the operating DB or user records."""
    snapshot = Path(__file__).resolve().parents[1] / "data" / "welfare-policies.json"
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    assert document["service_count"] == 152
    assert document["condition_count"] == 1749
    target, backup = tmp_path / "receiver.db", tmp_path / "receiver-before.db"
    make_db(target, service_id=document["data"]["welfare_services"][0]["serv_id"])
    private_before = {table: rows(target, table) for table in ("users", "accounts", "sync_state")}
    result = import_policies(target, snapshot, apply=True, backup=backup)
    assert result["new_services"] == 151
    assert result["updated_services"] == 1
    assert len(rows(target, "welfare_services")) == 152
    assert len(rows(target, "welfare_eligibility_conditions")) == 1749
    assert {table: rows(target, table) for table in private_before} == private_before
    reexported = tmp_path / "roundtrip.json"
    assert export_policies(target, reexported)["sha256"] == document["sha256"]
