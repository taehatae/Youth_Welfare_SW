"""Transfer policy records without sharing a user's SQLite database."""

import argparse
import json
import sqlite3
import sys

from app.services.policy_data_transfer import export_policies, import_policies, inspect_policies


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Export only policy services and conditions")
    export.add_argument("--database", required=True)
    export.add_argument("--output", required=True)
    inspect = commands.add_parser("inspect", help="Validate snapshot and show counts")
    inspect.add_argument("--source", required=True)
    load = commands.add_parser("import", help="Preview import; --apply requires a new backup path")
    load.add_argument("--database", required=True)
    load.add_argument("--source", required=True)
    load.add_argument("--apply", action="store_true")
    load.add_argument("--backup")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            report = export_policies(args.database, args.output)
        elif args.command == "inspect":
            report = inspect_policies(args.source)
        else:
            report = import_policies(args.database, args.source, apply=args.apply, backup=args.backup)
    except (ValueError, OSError, sqlite3.Error, RecursionError) as error:
        # Do not echo raw SQLite/JSON errors: they may contain data or paths.
        print(f"Policy transfer failed ({type(error).__name__}). Check paths, snapshot validity, schema and database locks.", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
