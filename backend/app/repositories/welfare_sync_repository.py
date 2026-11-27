from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, case, exists, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.welfare_sync import WelfareApiQuotaWindow, WelfareSyncBatch, WelfareSyncItem, utcnow


class QuotaWindowUnavailable(RuntimeError):
    """A call cannot be made without verified, unspent provider quota."""


class ActiveSyncLease(RuntimeError):
    """A batch or service item is currently owned by another worker."""


class WelfareSyncRepository:
    MAX_CALLS_PER_WINDOW = 100

    @staticmethod
    def _owns_live_batch(worker_token: str, now: datetime):
        return exists(
            select(WelfareSyncBatch.batch_id).where(
                WelfareSyncBatch.batch_id == WelfareSyncItem.batch_id,
                WelfareSyncBatch.worker_token == worker_token,
                WelfareSyncBatch.lease_expires_at > now,
            )
        )

    @staticmethod
    def create_batch(db: Session, *, life_array: str, start_new_batch: bool = False) -> WelfareSyncBatch:
        active = db.scalar(
            select(WelfareSyncBatch).where(WelfareSyncBatch.active_key == life_array)
        )
        if active is not None:
            if start_new_batch:
                raise ActiveSyncLease("An active synchronization batch already exists.")
            return active
        batch = WelfareSyncBatch(
            batch_id=str(uuid4()),
            life_array=life_array,
            active_key=life_array,
            status="listing",
            next_page=1,
        )
        db.add(batch)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ActiveSyncLease("An active synchronization batch already exists.") from None
        db.refresh(batch)
        return batch

    @staticmethod
    def get_batch(db: Session, batch_id: str) -> WelfareSyncBatch | None:
        return db.get(WelfareSyncBatch, batch_id)

    @staticmethod
    def latest_batch(db: Session, life_array: str) -> WelfareSyncBatch | None:
        return db.scalar(
            select(WelfareSyncBatch)
            .where(WelfareSyncBatch.life_array == life_array)
            .order_by(WelfareSyncBatch.started_at.desc())
            .limit(1)
        )

    @staticmethod
    def set_batch_windows(
        db: Session,
        batch_id: str,
        *,
        worker_token: str,
        list_window_id: str | None = None,
        detail_window_id: str | None = None,
        now: datetime | None = None,
    ) -> None:
        now = now or utcnow()
        values = {"updated_at": now}
        if list_window_id:
            values["list_window_id"] = list_window_id
            values["status"] = case(
                (
                    and_(WelfareSyncBatch.status == "paused", WelfareSyncBatch.listing_complete.is_(False)),
                    "listing",
                ),
                else_=WelfareSyncBatch.status,
            )
        if detail_window_id:
            values["detail_window_id"] = detail_window_id
        updated = db.execute(
            update(WelfareSyncBatch)
            .where(
                WelfareSyncBatch.batch_id == batch_id,
                WelfareSyncBatch.worker_token == worker_token,
                WelfareSyncBatch.lease_expires_at > now,
                WelfareSyncBatch.status.in_(("listing", "ready", "running", "paused")),
            )
            .values(**values)
        )
        if updated.rowcount != 1:
            db.rollback()
            raise ActiveSyncLease("Only the live batch lease owner can bind quota windows.")
        db.commit()

    @staticmethod
    def retry_failed_items(db: Session, batch_id: str) -> int:
        batch = db.get(WelfareSyncBatch, batch_id)
        if batch is None or batch.status != "partial":
            raise ValueError("Only a partial batch can retry failed items.")
        # Use a set-based transition so no failed item is selected twice.
        result = db.execute(
            update(WelfareSyncItem)
            .where(WelfareSyncItem.batch_id == batch_id, WelfareSyncItem.status == "failed")
            .values(
                status="pending",
                last_error_category=None,
                last_error_message=None,
                worker_token=None,
                lease_expires_at=None,
                updated_at=utcnow(),
            )
        )
        count = result.rowcount
        if count:
            batch.status = "running"
            batch.active_key = batch.life_array
            batch.completed_at = None
            db.commit()
        else:
            db.rollback()
        return count

    @staticmethod
    def prepare_quota_resume(db: Session, batch_id: str, detail_window_id: str) -> int:
        window = db.scalar(
            select(WelfareApiQuotaWindow).where(
                WelfareApiQuotaWindow.window_id == detail_window_id,
                WelfareApiQuotaWindow.operation == "detail",
            )
        )
        if window is None or not window.confirmed or window.blocked:
            raise QuotaWindowUnavailable("A new verified detail quota window is required.")
        capacity = min(window.limit_count, window.confirmed_available_calls)
        if capacity <= window.used_count:
            raise QuotaWindowUnavailable("No confirmed detail quota remains.")
        batch = db.get(WelfareSyncBatch, batch_id)
        if batch is None:
            raise ValueError("Sync batch was not found.")
        count = db.execute(
            update(WelfareSyncItem)
            .where(WelfareSyncItem.batch_id == batch_id, WelfareSyncItem.status == "quota_blocked")
            .values(
                status="pending",
                last_error_category=None,
                last_error_message=None,
                worker_token=None,
                lease_expires_at=None,
                updated_at=utcnow(),
            )
        ).rowcount
        batch.detail_window_id = detail_window_id
        batch.status = "running"
        batch.active_key = batch.life_array
        batch.completed_at = None
        db.commit()
        return count

    @staticmethod
    def save_list_page(
        db: Session,
        batch_id: str,
        *,
        worker_token: str,
        page_no: int,
        total_count: int,
        summaries: list[dict],
        now: datetime | None = None,
    ) -> int:
        now = now or utcnow()
        batch = db.get(WelfareSyncBatch, batch_id)
        if (
            batch is None
            or batch.status != "listing"
            or batch.worker_token != worker_token
            or batch.lease_expires_at is None
            or batch.lease_expires_at <= now
        ):
            raise ValueError("Batch is not accepting list pages.")
        if batch.next_page != page_no:
            raise ValueError("Unexpected list page number.")
        if batch.total_count is not None and batch.total_count != total_count:
            raise ValueError("Catalog totalCount changed during listing.")

        existing_ids = set(
            db.scalars(
                select(WelfareSyncItem.serv_id).where(WelfareSyncItem.batch_id == batch_id)
            )
        )
        pending_summaries = []
        for summary in summaries:
            serv_id = str(summary.get("serv_id") or "").strip()
            if not serv_id or serv_id in existing_ids:
                continue
            pending_summaries.append((serv_id, summary))
            existing_ids.add(serv_id)

        listing_complete = len(existing_ids) >= total_count
        updated = db.execute(
            update(WelfareSyncBatch)
            .where(
                WelfareSyncBatch.batch_id == batch_id,
                WelfareSyncBatch.status == "listing",
                WelfareSyncBatch.next_page == page_no,
                WelfareSyncBatch.worker_token == worker_token,
                WelfareSyncBatch.lease_expires_at > now,
                or_(WelfareSyncBatch.total_count.is_(None), WelfareSyncBatch.total_count == total_count),
            )
            .values(
                total_count=total_count,
                next_page=page_no + 1,
                listing_complete=listing_complete,
                status="ready" if listing_complete else "listing",
                updated_at=now,
            )
        )
        if updated.rowcount != 1:
            db.rollback()
            raise ActiveSyncLease("Only the live batch lease owner can persist list pages.")
        for serv_id, summary in pending_summaries:
            db.add(WelfareSyncItem(
                batch_id=batch_id,
                serv_id=serv_id,
                summary=summary,
                status="pending",
                attempt_count=0,
            ))
        db.commit()
        return len(pending_summaries)

    @staticmethod
    def list_items(db: Session, batch_id: str) -> list[WelfareSyncItem]:
        return list(db.scalars(
            select(WelfareSyncItem)
            .where(WelfareSyncItem.batch_id == batch_id)
            .order_by(WelfareSyncItem.id)
        ))

    @staticmethod
    def acquire_batch(
        db: Session,
        batch_id: str,
        worker_token: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 90,
        retry_failed: bool = False,
    ) -> bool:
        now = now or utcnow()
        statuses = ("listing", "ready", "running", "paused", "partial") if retry_failed else (
            "listing", "ready", "running", "paused"
        )
        try:
            acquired = db.execute(
                update(WelfareSyncBatch)
                .where(
                    WelfareSyncBatch.batch_id == batch_id,
                    WelfareSyncBatch.status.in_(statuses),
                    or_(
                        WelfareSyncBatch.worker_token.is_(None),
                        WelfareSyncBatch.lease_expires_at <= now,
                        WelfareSyncBatch.worker_token == worker_token,
                    ),
                )
                .values(
                    status=case(
                        (WelfareSyncBatch.status == "partial", "running"),
                        else_=WelfareSyncBatch.status,
                    ),
                    active_key=case(
                        (WelfareSyncBatch.status == "partial", WelfareSyncBatch.life_array),
                        else_=WelfareSyncBatch.active_key,
                    ),
                    completed_at=case(
                        (WelfareSyncBatch.status == "partial", None),
                        else_=WelfareSyncBatch.completed_at,
                    ),
                    worker_token=worker_token,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    updated_at=now,
                )
            )
            if acquired.rowcount == 1 and retry_failed:
                db.execute(
                    update(WelfareSyncItem)
                    .where(
                        WelfareSyncItem.batch_id == batch_id,
                        WelfareSyncItem.status == "failed",
                    )
                    .values(
                        status="pending",
                        last_error_category=None,
                        last_error_message=None,
                        worker_token=None,
                        lease_expires_at=None,
                        updated_at=now,
                    )
                )
            db.commit()
            return acquired.rowcount == 1
        except IntegrityError:
            db.rollback()
            return False

    @staticmethod
    def renew_batch(
        db: Session,
        batch_id: str,
        worker_token: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 90,
    ) -> bool:
        now = now or utcnow()
        renewed = db.execute(
            update(WelfareSyncBatch)
            .where(
                WelfareSyncBatch.batch_id == batch_id,
                WelfareSyncBatch.worker_token == worker_token,
                WelfareSyncBatch.lease_expires_at > now,
            )
            .values(lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now)
        )
        db.commit()
        return renewed.rowcount == 1

    @staticmethod
    def release_batch(db: Session, batch_id: str, worker_token: str) -> None:
        db.execute(
            update(WelfareSyncBatch)
            .where(
                WelfareSyncBatch.batch_id == batch_id,
                WelfareSyncBatch.worker_token == worker_token,
            )
            .values(worker_token=None, lease_expires_at=None, updated_at=utcnow())
        )
        db.commit()

    @staticmethod
    def claim_next_item(
        db: Session,
        batch_id: str,
        worker_token: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 90,
    ) -> WelfareSyncItem | None:
        now = now or utcnow()
        batch = db.get(WelfareSyncBatch, batch_id)
        if batch is None or batch.worker_token != worker_token or not batch.lease_expires_at or batch.lease_expires_at <= now:
            raise ActiveSyncLease("The batch lease is not held by this worker.")
        candidate = db.scalar(
            select(WelfareSyncItem)
            .where(
                WelfareSyncItem.batch_id == batch_id,
                or_(
                    WelfareSyncItem.status == "pending",
                    and_(
                        WelfareSyncItem.status == "processing",
                        WelfareSyncItem.lease_expires_at <= now,
                    ),
                ),
                WelfareSyncRepository._owns_live_batch(worker_token, now),
            )
            .order_by(WelfareSyncItem.id)
            .limit(1)
        )
        if candidate is None:
            return None
        item_id = candidate.id
        claimed = db.execute(
            update(WelfareSyncItem)
            .where(
                WelfareSyncItem.id == item_id,
                or_(
                    WelfareSyncItem.status == "pending",
                    and_(
                        WelfareSyncItem.status == "processing",
                        WelfareSyncItem.lease_expires_at <= now,
                    ),
                ),
                WelfareSyncRepository._owns_live_batch(worker_token, now),
            )
            .values(
                status="processing",
                attempt_count=WelfareSyncItem.attempt_count + 1,
                worker_token=worker_token,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                updated_at=now,
            )
        )
        db.commit()
        if claimed.rowcount != 1:
            return None
        return db.get(WelfareSyncItem, item_id)

    @staticmethod
    def save_received_payload(
        db: Session,
        item_id: int,
        worker_token: str,
        payload: dict,
        *,
        now: datetime | None = None,
    ) -> bool:
        now = now or utcnow()
        updated = db.execute(
            update(WelfareSyncItem)
            .where(
                WelfareSyncItem.id == item_id,
                WelfareSyncItem.status == "processing",
                WelfareSyncItem.worker_token == worker_token,
                WelfareSyncItem.lease_expires_at > now,
                WelfareSyncRepository._owns_live_batch(worker_token, now),
            )
            .values(
                status="received",
                detail_payload=payload,
                lease_expires_at=now + timedelta(seconds=90),
                updated_at=now,
            )
        )
        db.commit()
        return updated.rowcount == 1

    @staticmethod
    def release_item_without_attempt(db: Session, item_id: int, worker_token: str) -> None:
        db.execute(
            update(WelfareSyncItem)
            .where(
                WelfareSyncItem.id == item_id,
                WelfareSyncItem.status == "processing",
                WelfareSyncItem.worker_token == worker_token,
            )
            .values(
                status="pending",
                attempt_count=case(
                    (WelfareSyncItem.attempt_count > 0, WelfareSyncItem.attempt_count - 1),
                    else_=0,
                ),
                worker_token=None,
                lease_expires_at=None,
                updated_at=utcnow(),
            )
        )
        db.commit()

    @staticmethod
    def mark_item_failed(
        db: Session,
        item_id: int,
        worker_token: str,
        *,
        category: str,
        message: str,
        quota_blocked: bool = False,
        now: datetime | None = None,
    ) -> bool:
        now = now or utcnow()
        updated = db.execute(
            update(WelfareSyncItem)
            .where(
                WelfareSyncItem.id == item_id,
                WelfareSyncItem.worker_token == worker_token,
                WelfareSyncItem.lease_expires_at > now,
                WelfareSyncItem.status.in_(("processing", "received")),
                WelfareSyncRepository._owns_live_batch(worker_token, now),
            )
            .values(
                status="quota_blocked" if quota_blocked else "failed",
                last_error_category=category[:40],
                last_error_message=message[:300],
                worker_token=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        db.commit()
        return updated.rowcount == 1

    @staticmethod
    def complete_item_in_transaction(
        db: Session,
        item_id: int,
        worker_token: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        now = now or utcnow()
        updated = db.execute(
            update(WelfareSyncItem)
            .where(
                WelfareSyncItem.id == item_id,
                WelfareSyncItem.status == "received",
                WelfareSyncItem.worker_token == worker_token,
                WelfareSyncItem.lease_expires_at > now,
                WelfareSyncRepository._owns_live_batch(worker_token, now),
            )
            .values(
                status="succeeded",
                detail_payload=None,
                last_error_category=None,
                last_error_message=None,
                worker_token=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        return updated.rowcount == 1

    @staticmethod
    def finalize_batch(
        db: Session,
        batch_id: str,
        worker_token: str,
        *,
        now: datetime | None = None,
    ) -> str:
        now = now or utcnow()
        batch = db.get(WelfareSyncBatch, batch_id)
        if (
            batch is None
            or batch.worker_token != worker_token
            or batch.lease_expires_at is None
            or batch.lease_expires_at <= now
        ):
            raise ActiveSyncLease("The batch lease is not held by this worker.")
        items = WelfareSyncRepository.list_items(db, batch_id)
        statuses = [item.status for item in items]
        completed_at = batch.completed_at
        if not batch.listing_complete:
            status = "paused" if batch.status == "paused" else "listing"
            active_key = batch.life_array
        elif batch.status == "listing":
            status = "listing"
            active_key = batch.life_array
        elif all(status == "succeeded" for status in statuses):
            status = "completed"
            active_key = None
            completed_at = now
        elif "quota_blocked" in statuses:
            status = "paused"
            active_key = batch.life_array
        elif batch.status == "paused":
            status = "paused"
            active_key = batch.life_array
        elif any(value in statuses for value in ("pending", "processing", "received")):
            status = "running"
            active_key = batch.life_array
        elif "failed" in statuses:
            status = "partial"
            active_key = None
        else:
            status = "completed"
            active_key = None
            completed_at = now
        finalized = db.execute(
            update(WelfareSyncBatch)
            .where(
                WelfareSyncBatch.batch_id == batch_id,
                WelfareSyncBatch.worker_token == worker_token,
                WelfareSyncBatch.lease_expires_at > now,
            )
            .values(
                status=status,
                active_key=active_key,
                completed_at=completed_at,
                worker_token=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        if finalized.rowcount != 1:
            db.rollback()
            raise ActiveSyncLease("The batch lease changed before finalization.")
        db.commit()
        return status

    @staticmethod
    def claim_received_item(
        db: Session,
        batch_id: str,
        worker_token: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 90,
    ) -> WelfareSyncItem | None:
        now = now or utcnow()
        batch = db.get(WelfareSyncBatch, batch_id)
        if batch is None or batch.worker_token != worker_token or not batch.lease_expires_at or batch.lease_expires_at <= now:
            raise ActiveSyncLease("The batch lease is not held by this worker.")
        item = db.scalar(
            select(WelfareSyncItem)
            .where(WelfareSyncItem.batch_id == batch_id, WelfareSyncItem.status == "received")
            .order_by(WelfareSyncItem.id)
            .limit(1)
        )
        if item is None:
            return None
        claimed = db.execute(
            update(WelfareSyncItem)
            .where(
                WelfareSyncItem.id == item.id,
                WelfareSyncItem.status == "received",
                WelfareSyncRepository._owns_live_batch(worker_token, now),
            )
            .values(worker_token=worker_token, lease_expires_at=now + timedelta(seconds=lease_seconds))
        )
        db.commit()
        if claimed.rowcount != 1:
            return None
        return db.get(WelfareSyncItem, item.id)

    @staticmethod
    def open_quota_window(
        db: Session,
        *,
        window_id: str,
        operation: str,
        verified_available_calls: int | None,
        operator_name: str,
    ) -> WelfareApiQuotaWindow:
        if operation not in {"list", "detail"}:
            raise ValueError("operation must be 'list' or 'detail'")
        if not window_id.strip() or not operator_name.strip():
            raise QuotaWindowUnavailable("A window ID and operator identity are required.")
        if verified_available_calls is None or not 0 <= verified_available_calls <= 100:
            raise QuotaWindowUnavailable("Provider quota availability is not verified.")

        existing = db.scalar(
            select(WelfareApiQuotaWindow).where(
                WelfareApiQuotaWindow.window_id == window_id,
                WelfareApiQuotaWindow.operation == operation,
            )
        )
        if existing is not None:
            if (
                existing.confirmed_available_calls != verified_available_calls
                or not existing.confirmed
                or existing.operator_name != operator_name
            ):
                raise QuotaWindowUnavailable("This quota window already exists with different confirmation data.")
            return existing

        window = WelfareApiQuotaWindow(
            window_id=window_id,
            operation=operation,
            used_count=0,
            limit_count=WelfareSyncRepository.MAX_CALLS_PER_WINDOW,
            confirmed_available_calls=verified_available_calls,
            confirmed=True,
            blocked=False,
            operator_name=operator_name,
            confirmed_at=utcnow(),
        )
        db.add(window)
        db.commit()
        db.refresh(window)
        return window

    @staticmethod
    def reserve_quota_call(db: Session, window_id: str, operation: str) -> int:
        capacity = case(
            (
                WelfareApiQuotaWindow.limit_count < WelfareApiQuotaWindow.confirmed_available_calls,
                WelfareApiQuotaWindow.limit_count,
            ),
            else_=WelfareApiQuotaWindow.confirmed_available_calls,
        )
        reservation = db.execute(
            update(WelfareApiQuotaWindow)
            .where(
                WelfareApiQuotaWindow.window_id == window_id,
                WelfareApiQuotaWindow.operation == operation,
                WelfareApiQuotaWindow.confirmed.is_(True),
                WelfareApiQuotaWindow.blocked.is_(False),
                WelfareApiQuotaWindow.used_count < capacity,
            )
            .values(used_count=WelfareApiQuotaWindow.used_count + 1)
        )
        if reservation.rowcount != 1:
            db.rollback()
            raise QuotaWindowUnavailable("No confirmed quota remains for this operation.")

        row = db.scalar(
            select(WelfareApiQuotaWindow).where(
                WelfareApiQuotaWindow.window_id == window_id,
                WelfareApiQuotaWindow.operation == operation,
            )
        )
        assert row is not None
        remaining = min(row.limit_count, row.confirmed_available_calls) - row.used_count
        db.commit()
        return remaining

    @staticmethod
    def block_quota_window(db: Session, window_id: str, operation: str) -> None:
        db.execute(
            update(WelfareApiQuotaWindow)
            .where(
                WelfareApiQuotaWindow.window_id == window_id,
                WelfareApiQuotaWindow.operation == operation,
            )
            .values(blocked=True)
        )
        db.commit()

    @staticmethod
    def quota_snapshot(db: Session, window_id: str, operation: str) -> dict:
        row = db.scalar(
            select(WelfareApiQuotaWindow).where(
                WelfareApiQuotaWindow.window_id == window_id,
                WelfareApiQuotaWindow.operation == operation,
            )
        )
        if row is None:
            return {"used": 0, "remaining": 0, "confirmed": False, "blocked": False}
        capacity = min(row.limit_count, row.confirmed_available_calls)
        return {
            "used": row.used_count,
            "remaining": max(capacity - row.used_count, 0),
            "confirmed": row.confirmed,
            "blocked": row.blocked,
        }
