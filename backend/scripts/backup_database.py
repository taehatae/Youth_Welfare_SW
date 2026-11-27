import argparse
import json

from app.services.database_backup import backup_database, restore_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or verify a SQLite backup using a new destination file.")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("backup", "restore"):
        operation = commands.add_parser(command)
        operation.add_argument("--source", required=True, help="Source SQLite file (backup file for restore).")
        operation.add_argument("--destination", required=True, help="New destination path; existing files are refused.")
    args = parser.parse_args(argv)
    operation = backup_database if args.command == "backup" else restore_database
    result = operation(args.source, args.destination)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
