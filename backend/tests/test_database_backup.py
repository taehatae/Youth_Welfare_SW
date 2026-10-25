import sqlite3

import pytest

from app.services.database_backup import backup_database, restore_database


def _create_source(path):
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    connection.executemany("INSERT INTO records(value) VALUES (?)", [("one",), ("two",)])
    connection.commit()
    connection.close()


def test_backup_verifies_integrity_and_table_counts_without_changing_source(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    _create_source(source)
    original = source.read_bytes()

    report = backup_database(source, backup)

    assert report["integrity_check"] == "ok"
    assert report["table_counts"] == {"records": 2}
    assert source.read_bytes() == original
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM records ORDER BY id").fetchall() == [("one",), ("two",)]


def test_backup_refuses_to_overwrite_existing_destination(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "existing.db"
    _create_source(source)
    destination.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        backup_database(source, destination)

    assert destination.read_bytes() == b"keep"


def test_restore_writes_new_destination_and_verifies_representative_rows(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    _create_source(source)
    backup_database(source, backup)

    report = restore_database(backup, restored)

    assert report["integrity_check"] == "ok"
    assert report["table_counts"] == {"records": 2}
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM records ORDER BY id").fetchall() == [("one",), ("two",)]
    assert source.exists()
    assert backup.exists()


def test_restore_refuses_to_overwrite_destination(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    destination = tmp_path / "restored.db"
    _create_source(source)
    backup_database(source, backup)
    destination.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        restore_database(backup, destination)

    assert destination.read_bytes() == b"keep"
