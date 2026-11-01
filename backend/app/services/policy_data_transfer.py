"""Explicit policy-only snapshots; no app initialization, credentials or network IO."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3

from app.services.database_backup import backup_database


SERVICE_TABLE = "welfare_services"
CONDITION_TABLE = "welfare_eligibility_conditions"
JSON_FIELDS = ("application_methods", "contact_numbers", "related_websites", "application_forms", "related_laws")
SERVICE_FIELDS = (
    "serv_id", "serv_name", "department", "organization", "summary", "detail_url",
    "support_cycle", "support_type", "online_application", "target_details", "selection_criteria",
    "support_content", "reference_year", "life_stages", "target_groups", "interest_categories",
    *JSON_FIELDS, "created_at", "synced_at",
)
CONDITION_FIELDS = (
    "serv_id", "condition_type", "operator", "value_text", "value_number", "upper_value_number",
    "unit", "source_field", "source_text", "comparison_ready", "parse_status", "confidence", "created_at",
)
TABLE_FIELDS = {SERVICE_TABLE: SERVICE_FIELDS, CONDITION_TABLE: CONDITION_FIELDS}
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
NUMERIC_FIELDS = ("value_number", "upper_value_number", "confidence")


def _safe_output(database, destination):
    """Never create an exchange/backup file at a SQLite-managed sidecar path."""
    database = Path(database).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination == database or (
        destination.parent == database.parent and
        (destination in {database.with_name(database.name + suffix) for suffix in ("-journal", "-wal", "-shm")}
         or os.path.normcase(destination.name).startswith(os.path.normcase(database.name + "-mj")))
    ):
        raise ValueError("Output must not be the database or a SQLite sidecar path.")


def _normalized_records(records, table):
    normalized = []
    for record in records:
        record = dict(record)
        if table == CONDITION_TABLE:
            for field in NUMERIC_FIELDS:
                if record[field] is not None:
                    record[field] = float(record[field])
        normalized.append(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return sorted(normalized)


def data_checksum(data: dict) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")
        result[key] = value
    return result


def _invalid_number(_value):
    raise ValueError("Non-finite JSON number.")


def _decode(text):
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_number)


def _validate(document):
    expected = {"format_version", "exported_at", "service_count", "condition_count", "sha256", "data"}
    if not isinstance(document, dict) or set(document) != expected:
        raise ValueError("Invalid snapshot envelope.")
    if type(document["format_version"]) is not int or document["format_version"] != 1:
        raise ValueError("Unsupported snapshot format version.")
    _date(document["exported_at"])
    data = document["data"]
    if not isinstance(data, dict) or set(data) != set(TABLE_FIELDS):
        raise ValueError("Snapshot must contain only the two policy tables.")
    ids = set()
    for table, fields in TABLE_FIELDS.items():
        records = data[table]
        count_key = "service_count" if table == SERVICE_TABLE else "condition_count"
        if not isinstance(records, list) or type(document[count_key]) is not int or document[count_key] != len(records):
            raise ValueError("Snapshot count mismatch.")
        for record in records:
            if not isinstance(record, dict) or set(record) != set(fields):
                raise ValueError("Invalid policy record fields.")
            for field in fields:
                value = record[field]
                if table == SERVICE_TABLE and field in JSON_FIELDS:
                    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                        raise ValueError("Policy JSON field must be a list of objects.")
                elif table == CONDITION_TABLE and field == "comparison_ready":
                    if type(value) is not bool:
                        raise ValueError("comparison_ready must be a JSON boolean.")
                elif table == CONDITION_TABLE and field in NUMERIC_FIELDS:
                    if value is None and field != "confidence":
                        continue
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError("Invalid policy numeric field.")
                elif not isinstance(value, str):
                    raise ValueError("Policy text field must be a string.")
            _date(record["created_at"])
            if table == SERVICE_TABLE:
                _date(record["synced_at"])
                if not record["serv_id"].strip() or record["serv_id"] in ids:
                    raise ValueError("Empty or duplicate service ID.")
                ids.add(record["serv_id"])
            elif record["serv_id"] not in ids:
                raise ValueError("Condition references a service absent from the snapshot.")
    if not isinstance(document["sha256"], str) or data_checksum(data) != document["sha256"]:
        raise ValueError("Snapshot checksum mismatch.")
    return document


def _date(value):
    if not isinstance(value, str):
        raise ValueError("Invalid policy timestamp.")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid policy timestamp.") from None


def _read_snapshot(source):
    path = Path(source).resolve(strict=True)
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("Snapshot exceeds 64 MiB limit.")
    return _validate(_decode(path.read_text(encoding="utf-8")))


def _connect(path, *, writable=False):
    path = Path(path).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if writable else "?mode=ro"), uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    if not writable:
        connection.execute("PRAGMA query_only=ON")
    return connection


def _schema(connection):
    for table, fields in TABLE_FIELDS.items():
        columns = {row["name"]: row for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if not set(fields).issubset(columns):
            raise ValueError("Required policy schema is missing; initialize the matching app version first.")
        if table == SERVICE_TABLE and columns["serv_id"]["pk"] != 1:
            raise ValueError("Unsupported service primary key.")
        if table == CONDITION_TABLE and ("id" not in columns or columns["id"]["pk"] != 1):
            raise ValueError("Unsupported condition primary key.")
        for name, info in columns.items():
            if name not in fields and name != "id" and info["notnull"] and info["dflt_value"] is None:
                raise ValueError("Destination schema requires unsupported fields.")


def _health(connection):
    if [tuple(row) for row in connection.execute("PRAGMA integrity_check")] != [("ok",)]:
        raise sqlite3.DatabaseError("SQLite integrity check failed.")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise sqlite3.DatabaseError("SQLite foreign key check failed.")


def _records(connection, table):
    fields = TABLE_FIELDS[table]
    selected = ",".join(f'"{field}"' for field in fields)
    order = "serv_id" if table == SERVICE_TABLE else "id"
    records = [dict(row) for row in connection.execute(f'SELECT {selected} FROM "{table}" ORDER BY "{order}"')]
    for record in records:
        if table == SERVICE_TABLE:
            for field in JSON_FIELDS:
                record[field] = _decode(record[field])
        else:
            if record["comparison_ready"] not in (0, 1):
                raise ValueError("Invalid stored boolean.")
            record["comparison_ready"] = bool(record["comparison_ready"])
    return records


def _report(document):
    return {key: document[key] for key in ("format_version", "exported_at", "service_count", "condition_count", "sha256")}


def export_policies(database, output):
    """Read a consistent policy snapshot and exclusively create a JSON file."""
    output = Path(output).resolve()
    _safe_output(database, output)
    if output.exists():
        raise FileExistsError("Output already exists.")
    with closing(_connect(database)) as connection:
        connection.execute("BEGIN")
        _schema(connection)
        _health(connection)
        data = {table: _records(connection, table) for table in TABLE_FIELDS}
        document = {
            "format_version": 1, "exported_at": datetime.now(timezone.utc).isoformat(),
            "service_count": len(data[SERVICE_TABLE]), "condition_count": len(data[CONDITION_TABLE]),
            "sha256": data_checksum(data), "data": data,
        }
        _validate(document)
    text = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(text.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Snapshot exceeds 64 MiB limit.")
    created = False
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(text)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return _report(document)


def inspect_policies(source):
    """Validate a snapshot without opening any database or printing its records."""
    return _report(_read_snapshot(source))


def import_policies(database, source, *, apply=False, backup=None):
    """Preview by default; apply atomically only after making a new verified backup."""
    document = _read_snapshot(source)
    database = Path(database).resolve(strict=True)
    if database == Path(source).resolve():
        raise ValueError("Snapshot and database must be different files.")
    if apply and backup is None:
        raise ValueError("Applying requires a new --backup path.")
    if backup is not None:
        backup = Path(backup).resolve()
        _safe_output(database, backup)
        if backup in (database, Path(source).resolve()) or backup.exists():
            raise FileExistsError("Backup must be a new, separate file.")
    data = document["data"]
    with closing(_connect(database, writable=apply)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
            _schema(connection)
            _health(connection)
            existing = {row[0] for row in connection.execute("SELECT serv_id FROM welfare_services")}
            incoming = {row["serv_id"] for row in data[SERVICE_TABLE]}
            report = {**_report(document), "applied": apply,
                      "new_services": len(incoming - existing), "updated_services": len(incoming & existing)}
            if not apply:
                return report
            # A separate read-only connection can back up while this connection
            # reserves the writer lock, before any policy changes are made.
            backup_database(database, backup)
            service_columns = ",".join(f'"{field}"' for field in SERVICE_FIELDS)
            assignments = ",".join(f'"{field}"=excluded."{field}"' for field in SERVICE_FIELDS if field != "serv_id")
            upsert = (f'INSERT INTO "{SERVICE_TABLE}" ({service_columns}) VALUES '
                      f'({",".join("?" for _ in SERVICE_FIELDS)}) ON CONFLICT(serv_id) DO UPDATE SET {assignments}')
            for record in data[SERVICE_TABLE]:
                connection.execute(upsert, [json.dumps(record[field], ensure_ascii=False, allow_nan=False)
                                           if field in JSON_FIELDS else record[field] for field in SERVICE_FIELDS])
                connection.execute("DELETE FROM welfare_eligibility_conditions WHERE serv_id=?", (record["serv_id"],))
            condition_columns = ",".join(f'"{field}"' for field in CONDITION_FIELDS)
            insert = (f'INSERT INTO "{CONDITION_TABLE}" ({condition_columns}) '
                      f'VALUES ({",".join("?" for _ in CONDITION_FIELDS)})')
            connection.executemany(insert, [[record[field] for field in CONDITION_FIELDS]
                                            for record in data[CONDITION_TABLE]])
            _health(connection)
            # Verify the transferred records, including JSON types and nulls,
            # before committing. Unmentioned policies remain untouched.
            for table in TABLE_FIELDS:
                actual = [row for row in _records(connection, table) if row["serv_id"] in incoming]
                expected = data[table]
                if _normalized_records(actual, table) != _normalized_records(expected, table):
                    raise sqlite3.DatabaseError("Imported policy verification failed.")
            connection.commit()
            report["backup"] = str(backup)
            return report
        finally:
            if connection.in_transaction:
                connection.rollback()
