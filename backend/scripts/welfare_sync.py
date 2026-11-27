import argparse
import asyncio
import json
import sys

from app.database.connection import SessionLocal
from app.services.welfare_sync_operator import confirm_quota_window
from app.services.welfare_sync_service import WelfareSyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate resumable welfare service synchronization.")
    commands = parser.add_subparsers(dest="command", required=True)

    window = commands.add_parser("confirm-window", help="Record externally verified quota for one API operation.")
    window.add_argument("--window-id", required=True)
    window.add_argument("--operation", choices=("list", "detail"), required=True)
    window.add_argument("--verified-available-calls", type=int, choices=range(0, 101), required=True)
    window.add_argument("--operator-name", required=True)
    window.add_argument("--confirm-provider-quota", action="store_true", required=True)

    sync = commands.add_parser("run", help="Resume or start a synchronization batch.")
    sync.add_argument("--batch-id")
    sync.add_argument("--list-window-id")
    sync.add_argument("--detail-window-id")
    sync.add_argument("--start-new-batch", action="store_true")
    sync.add_argument("--retry-failed", action="store_true")
    sync.add_argument("--max-services", type=int)
    sync.add_argument("--max-detail-attempts", type=int, default=100, choices=range(1, 101))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Importing the application registers all ORM models before additive create_all.
    from app.main import Base, engine  # noqa: PLC0415

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if args.command == "confirm-window":
            try:
                window = confirm_quota_window(
                    db,
                    window_id=args.window_id,
                    operation=args.operation,
                    verified_available_calls=args.verified_available_calls,
                    operator_name=args.operator_name,
                    confirm_provider_quota=args.confirm_provider_quota,
                )
            except (ValueError, RuntimeError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
            print(json.dumps({
                "window_id": window.window_id,
                "operation": window.operation,
                "verified_available_calls": window.confirmed_available_calls,
                "used_calls": window.used_count,
                "confirmed": window.confirmed,
            }, ensure_ascii=False))
            return 0

        try:
            result = asyncio.run(WelfareSyncService().sync_welfare_services(
                db,
                max_services=args.max_services,
                batch_id=args.batch_id,
                list_window_id=args.list_window_id,
                detail_window_id=args.detail_window_id,
                start_new_batch=args.start_new_batch,
                retry_failed=args.retry_failed,
                max_detail_attempts=args.max_detail_attempts,
            ))
        except (ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["batch_status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
