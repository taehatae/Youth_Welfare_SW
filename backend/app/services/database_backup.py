"""Explicit SQLite backup and restore helpers.

Both operations create a new destination file and refuse to overwrite an
existing path. They are deliberately separate from welfare synchronization.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    counts: dict[str, int] = {}
    for (name,) in tables:
        escaped_name = name.replace('"', '""')
        counts[name] = connection.execute(f'SELECT COUNT(*) FROM "{escaped_name}"').fetchone()[0]
    return counts


def _integrity_check(connection: sqlite3.Connection) -> str:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise sqlite3.DatabaseError(f"SQLite integrity check failed: {result}")
    return result


def _copy_and_verify(source: Path, destination: Path) -> dict:
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve(strict=False)
    if source == destination:
        raise ValueError("Source and destination must be different files.")
    if not source.is_file():
        raise ValueError("Source must be a regular SQLite database file.")
    if not destination.parent.is_dir():
        raise FileNotFoundError("Destination directory does not exist.")

    created = False
    try:
        # Exclusive creation prevents accidentally replacing any existing DB.
        with destination.open("xb"):
            created = True
        source_uri = source.as_uri() + "?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as source_connection:
            expected_counts = _table_counts(source_connection)
            _integrity_check(source_connection)
            with sqlite3.connect(destination) as destination_connection:
                source_connection.backup(destination_connection)
                actual_integrity = _integrity_check(destination_connection)
                actual_counts = _table_counts(destination_connection)
                if actual_counts != expected_counts:
                    raise sqlite3.DatabaseError("Copied database table counts do not match the source.")
        return {"integrity_check": actual_integrity, "table_counts": actual_counts}
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def backup_database(source: str | Path, destination: str | Path) -> dict:
    """Create a verified SQLite online backup at a new path."""
    return _copy_and_verify(Path(source), Path(destination))


def restore_database(backup: str | Path, destination: str | Path) -> dict:
    """Restore a backup into a new file without modifying the backup or source."""
    return _copy_and_verify(Path(backup), Path(destination))
