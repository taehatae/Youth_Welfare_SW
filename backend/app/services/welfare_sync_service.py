import xml.etree.ElementTree as ET
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.welfare_api_client import WelfareApiClient, WelfareApiError
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.models.welfare_service import WelfareService
from app.models.welfare_sync import WelfareSyncBatch, WelfareSyncItem, utcnow
from app.repositories.welfare_sync_repository import (
    ActiveSyncLease,
    QuotaWindowUnavailable,
    WelfareSyncRepository,
)
from app.services.eligibility_condition_service import EligibilityConditionService


class WelfareSyncService:
    PAGE_SIZE = 100
    YOUTH_LIFE_ARRAY = "004"
    MAX_DETAIL_ATTEMPTS = 100
    LEASE_SECONDS = 90

    SERVICE_FIELDS = (
        "serv_name",
        "department",
        "organization",
        "summary",
        "detail_url",
        "support_cycle",
        "support_type",
        "online_application",
        "target_details",
        "selection_criteria",
        "support_content",
        "reference_year",
        "life_stages",
        "target_groups",
        "interest_categories",
        "application_methods",
        "contact_numbers",
        "related_websites",
        "application_forms",
        "related_laws",
    )

    def __init__(self, client: WelfareApiClient | None = None, repository: WelfareSyncRepository | None = None):
        self.client = client or WelfareApiClient()
        self.repository = repository or WelfareSyncRepository()

    async def sync_welfare_services(
        self,
        db: Session,
        max_services: int | None = None,
        *,
        batch_id: str | None = None,
        list_window_id: str | None = None,
        detail_window_id: str | None = None,
        start_new_batch: bool = False,
        retry_failed: bool = False,
        max_detail_attempts: int = MAX_DETAIL_ATTEMPTS,
    ) -> dict:
        if max_services is not None and max_services < 1:
            raise ValueError("max_services must be at least 1")
        if not 1 <= max_detail_attempts <= self.MAX_DETAIL_ATTEMPTS:
            raise ValueError("max_detail_attempts must be between 1 and 100")
        if batch_id and start_new_batch:
            raise ValueError("batch_id and start_new_batch cannot be used together")

        batch = self._resolve_batch(db, batch_id, start_new_batch, retry_failed)
        if batch is None:
            batch = self.repository.create_batch(
                db, life_array=self.YOUTH_LIFE_ARRAY, start_new_batch=start_new_batch
            )
        db.refresh(batch)
        if batch.status == "completed":
            items = self.repository.list_items(db, batch.batch_id)
            return {
                "life_array": batch.life_array,
                "listed_count": len(items),
                "synced_count": 0,
                "failed_count": 0,
                "failed_services": [],
                "batch_id": batch.batch_id,
                "batch_status": "completed",
                "api_total_count": batch.total_count or 0,
                "detail_attempt_count": 0,
                "detail_success_count": 0,
                "detail_failure_count": 0,
                "detail_quota_blocked_count": 0,
                "detail_unprocessed_count": 0,
                "condition_persistence_success_count": 0,
                "condition_rows_saved": 0,
                "condition_rows_total": 0,
                "quota": {},
                "errors": [],
            }

        worker_token = uuid4().hex
        if not self.repository.acquire_batch(
            db,
            batch.batch_id,
            worker_token,
            lease_seconds=self.LEASE_SECONDS,
            retry_failed=retry_failed,
        ):
            raise ActiveSyncLease("Another synchronization worker owns this batch.")
        if list_window_id or detail_window_id:
            self.repository.set_batch_windows(
                db,
                batch.batch_id,
                worker_token=worker_token,
                list_window_id=list_window_id,
                detail_window_id=detail_window_id,
            )

        errors: list[dict] = []
        failed_services: list[dict] = []
        detail_attempts = 0
        detail_successes = 0
        detail_failures = 0
        quota_blocked = 0
        condition_rows_saved = 0
        stopped_for_quota = False
        stop_after_error = False

        try:
            db.refresh(batch)
            if batch.status == "paused" and batch.listing_complete and detail_window_id:
                self.repository.prepare_quota_resume(db, batch.batch_id, detail_window_id)
                db.refresh(batch)

            if not batch.listing_complete:
                list_error = await self._collect_listing(db, batch, worker_token)
                if list_error:
                    errors.append(list_error)
                    stopped_for_quota = list_error["category"] in {
                        "quota_exhausted",
                        "quota_window_exhausted",
                    }
                    if stopped_for_quota:
                        batch.status = "paused"
                        db.commit()

            db.refresh(batch)
            if batch.status in {"ready", "running", "paused"} and not stopped_for_quota:
                detail_id = detail_window_id or batch.detail_window_id
                while True:
                    item = self.repository.claim_received_item(
                        db,
                        batch.batch_id,
                        worker_token,
                        lease_seconds=self.LEASE_SECONDS,
                    )
                    if item is None:
                        break
                    rows, item_error = self._persist_received(db, item, worker_token)
                    if item_error:
                        detail_failures += 1
                        failed_services.append(item_error)
                    else:
                        detail_successes += 1
                        condition_rows_saved += rows

                has_pending = any(
                    item.status == "pending"
                    for item in self.repository.list_items(db, batch.batch_id)
                )
                if not detail_id and has_pending:
                    errors.append({
                        "category": "quota_window_required",
                        "message": "A separately verified detail quota window is required.",
                    })
                elif detail_id:
                    while detail_attempts < min(max_detail_attempts, max_services or self.MAX_DETAIL_ATTEMPTS):
                        if not self.repository.renew_batch(
                            db, batch.batch_id, worker_token, lease_seconds=self.LEASE_SECONDS
                        ):
                            raise ActiveSyncLease("The batch lease expired before the next detail request.")
                        item = self.repository.claim_next_item(
                            db,
                            batch.batch_id,
                            worker_token,
                            lease_seconds=self.LEASE_SECONDS,
                        )
                        if item is None:
                            break
                        try:
                            self.repository.reserve_quota_call(db, detail_id, "detail")
                        except QuotaWindowUnavailable as exc:
                            self.repository.release_item_without_attempt(db, item.id, worker_token)
                            if self._quota_is_exhausted(db, detail_id, "detail"):
                                batch.status = "paused"
                                db.commit()
                                stopped_for_quota = True
                                errors.append({"category": "quota_window_exhausted", "message": str(exc)})
                            else:
                                errors.append({"category": "quota_window_required", "message": str(exc)})
                            break

                        detail_attempts += 1
                        try:
                            detail_xml = await self.client.get_welfare_service_detail(item.serv_id)
                            detail_data = self.client.parse_welfare_service_detail(detail_xml)
                        except WelfareApiError as exc:
                            is_quota = exc.category == "quota_exhausted"
                            if is_quota:
                                self.repository.block_quota_window(db, detail_id, "detail")
                                stopped_for_quota = True
                                quota_blocked += 1
                            else:
                                detail_failures += 1
                            self.repository.mark_item_failed(
                                db,
                                item.id,
                                worker_token,
                                category=exc.category,
                                message=str(exc),
                                quota_blocked=is_quota,
                            )
                            issue = {"serv_id": item.serv_id, "category": exc.category, "reason": str(exc)}
                            failed_services.append(issue)
                            if not is_quota:
                                stop_after_error = True
                            if is_quota or stop_after_error:
                                break
                            continue
                        except (ET.ParseError, ValueError) as exc:
                            detail_failures += 1
                            message = self._safe_exception_message(exc)
                            self.repository.mark_item_failed(
                                db, item.id, worker_token, category="invalid_response", message=message
                            )
                            failed_services.append({
                                "serv_id": item.serv_id,
                                "category": "invalid_response",
                                "reason": message,
                            })
                            continue

                        response_serv_id = str(detail_data.get("serv_id") or "").strip()
                        if response_serv_id != item.serv_id:
                            detail_failures += 1
                            self.repository.mark_item_failed(
                                db,
                                item.id,
                                worker_token,
                                category="service_id_mismatch",
                                message="Detail response service ID did not match the requested service.",
                            )
                            failed_services.append({
                                "serv_id": item.serv_id,
                                "category": "service_id_mismatch",
                                "reason": "Detail response service ID did not match the requested service.",
                            })
                            continue

                        if not self.repository.save_received_payload(
                            db, item.id, worker_token, detail_data
                        ):
                            raise ActiveSyncLease("The item lease expired before the response was persisted.")
                        item = db.get(WelfareSyncItem, item.id)
                        rows, item_error = self._persist_received(db, item, worker_token)
                        if item_error:
                            detail_failures += 1
                            failed_services.append(item_error)
                        else:
                            detail_successes += 1
                            condition_rows_saved += rows
        finally:
            batch_status = self.repository.finalize_batch(db, batch.batch_id, worker_token)

        items = self.repository.list_items(db, batch.batch_id)
        list_snapshot = self.repository.quota_snapshot(
            db,
            list_window_id or batch.list_window_id or "",
            "list",
        )
        detail_snapshot = self.repository.quota_snapshot(
            db,
            detail_window_id or batch.detail_window_id or "",
            "detail",
        )
        condition_total = db.scalar(
            select(func.count())
            .select_from(WelfareEligibilityCondition)
            .where(
                WelfareEligibilityCondition.serv_id.in_(
                    select(WelfareSyncItem.serv_id).where(WelfareSyncItem.batch_id == batch.batch_id)
                )
            )
        ) or 0
        detail_unprocessed = sum(item.status in {"pending", "processing", "received"} for item in items)
        total_count = batch.total_count or 0
        return {
            "life_array": batch.life_array,
            "listed_count": len(items),
            "synced_count": detail_successes,
            "failed_count": detail_failures + quota_blocked,
            "failed_services": failed_services,
            "batch_id": batch.batch_id,
            "batch_status": batch_status,
            "api_total_count": total_count,
            "list_pages_completed": max(batch.next_page - 1, 0) if batch.status != "listing" else max(batch.next_page - 1, 0),
            "detail_attempt_count": detail_attempts,
            "detail_success_count": detail_successes,
            "detail_failure_count": detail_failures,
            "detail_quota_blocked_count": quota_blocked,
            "detail_unprocessed_count": detail_unprocessed,
            "condition_persistence_success_count": detail_successes,
            "condition_rows_saved": condition_rows_saved,
            "condition_rows_total": condition_total,
            "quota": {
                "list": list_snapshot,
                "detail": detail_snapshot,
            },
            "errors": errors,
        }

    def _resolve_batch(
        self,
        db: Session,
        batch_id: str | None,
        start_new_batch: bool,
        retry_failed: bool,
    ) -> WelfareSyncBatch | None:
        if batch_id:
            batch = self.repository.get_batch(db, batch_id)
            if batch is None or batch.life_array != self.YOUTH_LIFE_ARRAY:
                raise ValueError("Sync batch was not found.")
            if batch.status == "partial" and not retry_failed:
                raise ValueError("A partial batch requires retry_failed=true or a new batch.")
            if retry_failed and batch.status != "partial":
                raise ValueError("retry_failed is only valid for a partial batch.")
            return batch

        latest = self.repository.latest_batch(db, self.YOUTH_LIFE_ARRAY)
        if latest and latest.status in {"completed", "partial"} and not start_new_batch:
            raise ValueError("A completed/partial batch requires an explicit batch ID or start_new_batch.")
        if latest and start_new_batch and latest.active_key:
            raise ActiveSyncLease("An active synchronization batch already exists.")
        return None

    async def _collect_listing(
        self,
        db: Session,
        batch: WelfareSyncBatch,
        worker_token: str,
    ) -> dict | None:
        list_window_id = batch.list_window_id
        if not list_window_id:
            return {"category": "quota_window_required", "message": "A separately verified list quota window is required."}

        while not batch.listing_complete:
            if batch.status == "paused":
                batch.status = "listing"
                db.commit()
            if not self.repository.renew_batch(
                db, batch.batch_id, worker_token, lease_seconds=self.LEASE_SECONDS
            ):
                raise ActiveSyncLease("The batch lease expired before the next list request.")
            try:
                self.repository.reserve_quota_call(db, list_window_id, "list")
            except QuotaWindowUnavailable as exc:
                if self._quota_is_exhausted(db, list_window_id, "list"):
                    batch.status = "paused"
                    db.commit()
                    return {"category": "quota_window_exhausted", "message": str(exc)}
                return {"category": "quota_window_required", "message": str(exc)}
            try:
                xml_text = await self.client.get_welfare_services(
                    page_no=batch.next_page,
                    num_of_rows=self.PAGE_SIZE,
                    life_array=batch.life_array,
                )
                root = ET.fromstring(xml_text)
                total_text = root.findtext(".//totalCount")
                if total_text is None or not total_text.isdigit():
                    raise ValueError("List response did not contain a valid totalCount.")
                total_count = int(total_text)
                summaries = self.client.parse_welfare_services(xml_text)
                if self.repository.save_list_page(
                    db,
                    batch.batch_id,
                    worker_token=worker_token,
                    page_no=batch.next_page,
                    total_count=total_count,
                    summaries=summaries,
                ) == 0 and total_count > 0:
                    raise ValueError("List page contained no new service IDs.")
            except WelfareApiError as exc:
                if exc.category == "quota_exhausted":
                    self.repository.block_quota_window(db, list_window_id, "list")
                return {"category": exc.category, "message": str(exc)}
            except (ET.ParseError, ValueError) as exc:
                return {"category": "invalid_list_response", "message": self._safe_exception_message(exc)}
            db.refresh(batch)
        return None

    def _persist_received(
        self,
        db: Session,
        item: WelfareSyncItem,
        worker_token: str,
    ) -> tuple[int, dict | None]:
        payload = item.detail_payload or {}
        if str(payload.get("serv_id") or "").strip() != item.serv_id:
            self.repository.mark_item_failed(
                db,
                item.id,
                worker_token,
                category="service_id_mismatch",
                message="Detail response service ID did not match the requested service.",
            )
            return 0, {
                "serv_id": item.serv_id,
                "category": "service_id_mismatch",
                "reason": "Detail response service ID did not match the requested service.",
            }

        try:
            summary = item.summary or {}
            data = {**summary, **payload}
            service = db.get(WelfareService, item.serv_id)
            if service is None:
                service = WelfareService(serv_id=item.serv_id)
                db.add(service)
            for field in self.SERVICE_FIELDS:
                if field in data:
                    setattr(service, field, data[field])
            db.flush()
            if "target_details" in data or "selection_criteria" in data:
                condition_count = EligibilityConditionService.replace_conditions(
                    db,
                    serv_id=item.serv_id,
                    target_details=service.target_details,
                    selection_criteria=service.selection_criteria,
                )
            else:
                condition_count = 0
            service.synced_at = utcnow()
            if not self.repository.complete_item_in_transaction(db, item.id, worker_token):
                raise ActiveSyncLease("The item lease expired before persistence completed.")
            db.commit()
            return condition_count, None
        except Exception as exc:
            db.rollback()
            message = self._safe_exception_message(exc)
            self.repository.mark_item_failed(
                db,
                item.id,
                worker_token,
                category="persistence_error",
                message=message,
            )
            return 0, {"serv_id": item.serv_id, "category": "persistence_error", "reason": message}

    @staticmethod
    def _safe_exception_message(exc: Exception) -> str:
        if isinstance(exc, WelfareApiError):
            return str(exc)[:300]
        return f"{type(exc).__name__}: response or persistence validation failed"[:300]

    def _quota_is_exhausted(self, db: Session, window_id: str, operation: str) -> bool:
        snapshot = self.repository.quota_snapshot(db, window_id, operation)
        return snapshot["confirmed"] and (snapshot["blocked"] or snapshot["remaining"] == 0)
