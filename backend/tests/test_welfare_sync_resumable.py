from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.clients.welfare_api_client import WelfareApiError, WelfareApiClient
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.models.welfare_service import WelfareService
from app.models.welfare_sync import WelfareSyncItem
from app.repositories.welfare_sync_repository import (
    ActiveSyncLease,
    WelfareSyncRepository,
    utcnow,
)
from app.services.welfare_sync_service import WelfareSyncService


@pytest.fixture
def database(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'welfare-sync.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()


def test_batch_resumes_listing_and_deduplicates_service_ids(database):
    repository = WelfareSyncRepository()
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "listing-worker")
    first_count = repository.save_list_page(
        database,
        batch.batch_id,
        worker_token="listing-worker",
        page_no=1,
        total_count=3,
        summaries=[{"serv_id": "one"}, {"serv_id": "two"}],
    )
    resumed = repository.create_batch(database, life_array="004")
    second_count = repository.save_list_page(
        database,
        resumed.batch_id,
        worker_token="listing-worker",
        page_no=2,
        total_count=3,
        summaries=[{"serv_id": "two"}, {"serv_id": "three"}],
    )

    assert resumed.batch_id == batch.batch_id
    assert first_count == 2
    assert second_count == 1
    assert repository.list_items(database, batch.batch_id)[-1].serv_id == "three"
    assert resumed.next_page == 3


def test_batch_and_item_leases_are_exclusive_and_expired_owner_is_fenced(database):
    repository = WelfareSyncRepository()
    now = datetime(2026, 10, 25, 0, 0, 0)
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now)
    repository.save_list_page(
        database,
        batch.batch_id,
        worker_token="worker-a",
        page_no=1,
        total_count=1,
        summaries=[{"serv_id": "one"}],
    )

    assert not repository.acquire_batch(database, batch.batch_id, "worker-b", now=now)
    item = repository.claim_next_item(
        database, batch.batch_id, "worker-a", now=now, lease_seconds=90
    )
    assert item is not None and item.status == "processing"
    with pytest.raises(ActiveSyncLease):
        repository.claim_next_item(
            database, batch.batch_id, "worker-b", now=now, lease_seconds=90
        )

    later = now + timedelta(seconds=91)
    assert repository.acquire_batch(database, batch.batch_id, "worker-b", now=later)
    reclaimed = repository.claim_next_item(
        database, batch.batch_id, "worker-b", now=later, lease_seconds=90
    )
    assert reclaimed is not None and reclaimed.worker_token == "worker-b"
    assert not repository.save_received_payload(
        database, item.id, "worker-a", {"serv_id": "one"}, now=later
    )


def test_expired_batch_owner_cannot_persist_while_its_item_lease_remains(database):
    repository = WelfareSyncRepository()
    now = datetime(2026, 10, 25, 0, 0, 0)
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now, lease_seconds=90)
    repository.save_list_page(
        database,
        batch.batch_id,
        worker_token="worker-a",
        page_no=1,
        total_count=1,
        summaries=[{"serv_id": "one"}],
    )
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now, lease_seconds=90)
    item = repository.claim_next_item(
        database, batch.batch_id, "worker-a", now=now, lease_seconds=120
    )

    batch_expired = now + timedelta(seconds=91)
    assert repository.acquire_batch(database, batch.batch_id, "worker-b", now=batch_expired)
    assert not repository.save_received_payload(
        database, item.id, "worker-a", {"serv_id": "one"}, now=batch_expired
    )

    database.refresh(item)
    assert item.status == "processing"
    assert item.detail_payload is None


def test_expired_batch_lease_owner_cannot_finalize_batch(database):
    repository = WelfareSyncRepository()
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", lease_seconds=90)
    batch.lease_expires_at = utcnow() - timedelta(seconds=1)
    database.commit()

    with pytest.raises(ActiveSyncLease):
        repository.finalize_batch(database, batch.batch_id, "worker-a")


def test_finalize_batch_is_fenced_atomically_if_batch_owner_changes(database):
    repository = WelfareSyncRepository()
    now = datetime(2026, 10, 25, 0, 0, 0)
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now)
    engine = database.get_bind()
    changed = False

    def transfer_owner(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if not changed and statement.lstrip().upper().startswith("UPDATE WELFARE_SYNC_BATCHES"):
            changed = True
            with Session(engine) as other_session:
                other_session.execute(
                    text("UPDATE welfare_sync_batches SET worker_token = :token, lease_expires_at = :expiry WHERE batch_id = :batch_id"),
                    {"token": "worker-b", "expiry": now + timedelta(seconds=180), "batch_id": batch.batch_id},
                )
                other_session.commit()

    event.listen(engine, "before_cursor_execute", transfer_owner)
    try:
        with pytest.raises(ActiveSyncLease):
            repository.finalize_batch(database, batch.batch_id, "worker-a", now=now)
    finally:
        event.remove(engine, "before_cursor_execute", transfer_owner)

    database.expire_all()
    batch = repository.get_batch(database, batch.batch_id)
    assert batch.worker_token == "worker-b"
    assert batch.status == "listing"


def test_list_page_persistence_is_fenced_atomically_if_batch_owner_changes(database):
    repository = WelfareSyncRepository()
    now = datetime(2026, 10, 25, 0, 0, 0)
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now)
    engine = database.get_bind()
    changed = False

    def transfer_owner(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if not changed and statement.lstrip().upper().startswith("UPDATE WELFARE_SYNC_BATCHES"):
            changed = True
            with Session(engine) as other_session:
                other_session.execute(
                    text("UPDATE welfare_sync_batches SET worker_token = :token, lease_expires_at = :expiry WHERE batch_id = :batch_id"),
                    {"token": "worker-b", "expiry": now + timedelta(seconds=180), "batch_id": batch.batch_id},
                )
                other_session.commit()

    event.listen(engine, "before_cursor_execute", transfer_owner)
    try:
        with pytest.raises(ActiveSyncLease):
            repository.save_list_page(
                database,
                batch.batch_id,
                worker_token="worker-a",
                page_no=1,
                total_count=1,
                summaries=[{"serv_id": "one"}],
                now=now,
            )
    finally:
        event.remove(engine, "before_cursor_execute", transfer_owner)

    database.expire_all()
    batch = repository.get_batch(database, batch.batch_id)
    assert batch.worker_token == "worker-b"
    assert batch.next_page == 1
    assert repository.list_items(database, batch.batch_id) == []


def test_item_claim_is_fenced_atomically_if_batch_ownership_changes(database):
    repository = WelfareSyncRepository()
    now = datetime(2026, 10, 25, 0, 0, 0)
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now)
    repository.save_list_page(
        database,
        batch.batch_id,
        worker_token="worker-a",
        page_no=1,
        total_count=1,
        summaries=[{"serv_id": "one"}],
    )
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now)
    engine = database.get_bind()
    changed = False

    def transfer_owner(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if not changed and statement.lstrip().upper().startswith("UPDATE WELFARE_SYNC_ITEMS"):
            changed = True
            with Session(engine) as other_session:
                other_session.execute(
                    text("UPDATE welfare_sync_batches SET worker_token = :token, lease_expires_at = :expiry WHERE batch_id = :batch_id"),
                    {"token": "worker-b", "expiry": now + timedelta(seconds=180), "batch_id": batch.batch_id},
                )
                other_session.commit()

    event.listen(engine, "before_cursor_execute", transfer_owner)
    try:
        item = repository.claim_next_item(database, batch.batch_id, "worker-a", now=now)
    finally:
        event.remove(engine, "before_cursor_execute", transfer_owner)

    assert item is None
    assert database.query(WelfareSyncItem).one().status == "pending"


def test_received_payload_is_durable_and_claimed_without_detail_request(database):
    repository = WelfareSyncRepository()
    now = datetime(2026, 10, 25, 0, 0, 0)
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a", now=now)
    repository.save_list_page(
        database,
        batch.batch_id,
        worker_token="worker-a",
        page_no=1,
        total_count=1,
        summaries=[{"serv_id": "one"}],
    )
    item = repository.claim_next_item(database, batch.batch_id, "worker-a", now=now)
    assert repository.save_received_payload(
        database, item.id, "worker-a", {"serv_id": "one", "serv_name": "received"}, now=now
    )

    received = repository.claim_received_item(database, batch.batch_id, "worker-a")

    assert received.id == item.id
    assert received.detail_payload["serv_name"] == "received"


class FakeWelfareClient:
    def __init__(self, service_count=152, fail_details=None, fail_list_pages=None, detail_ids=None):
        self.service_count = service_count
        self.fail_details = fail_details or {}
        self.fail_list_pages = dict(fail_list_pages or {})
        self.detail_ids = detail_ids or {}
        self.detail_calls = []
        self.list_calls = []

    async def get_welfare_services(self, *, page_no, num_of_rows, life_array):
        self.list_calls.append(page_no)
        error = self.fail_list_pages.get(page_no)
        if error:
            raise error
        start = (page_no - 1) * num_of_rows
        ids = [f"service-{n:03}" for n in range(start, min(start + num_of_rows, self.service_count))]
        records = "".join(f"<servList><servId>{serv_id}</servId><servNm>{serv_id}</servNm></servList>" for serv_id in ids)
        return f"<root><resultCode>0</resultCode><totalCount>{self.service_count}</totalCount>{records}</root>"

    def parse_welfare_services(self, xml_text):
        return WelfareApiClient().parse_welfare_services(xml_text)

    async def get_welfare_service_detail(self, serv_id):
        self.detail_calls.append(serv_id)
        if serv_id in self.fail_details:
            error = self.fail_details[serv_id]
            raise error if isinstance(error, Exception) else WelfareApiError("network_error")
        response_id = self.detail_ids.get(serv_id, serv_id)
        return (
            f"<root><resultCode>0</resultCode><servId>{response_id}</servId>"
            f"<servNm>Detail {response_id}</servNm><tgtrDtlCn></tgtrDtlCn>"
            f"<slctCritCn></slctCritCn><alwServCn></alwServCn></root>"
        )

    def parse_welfare_service_detail(self, xml_text):
        return WelfareApiClient().parse_welfare_service_detail(xml_text)


def open_window(db, window_id, operation, available):
    WelfareSyncRepository.open_quota_window(
        db,
        window_id=window_id,
        operation=operation,
        verified_available_calls=available,
        operator_name="test-operator",
    )


def test_152_services_resume_after_100_detail_attempts_without_relisting(database):
    client = FakeWelfareClient()
    service = WelfareSyncService()
    service.client = client
    open_window(database, "day-1", "list", 2)
    open_window(database, "day-1", "detail", 100)

    first = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="day-1",
        detail_window_id="day-1",
        start_new_batch=True,
    ))

    assert first["listed_count"] == 152
    assert first["synced_count"] == 100
    assert first["detail_unprocessed_count"] == 52
    assert len(client.detail_calls) == 100
    assert client.list_calls == [1, 2]
    batch_id = first["batch_id"]

    open_window(database, "day-2", "detail", 52)
    second = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=batch_id,
        detail_window_id="day-2",
    ))

    assert second["synced_count"] == 52
    assert second["batch_status"] == "completed"
    assert client.list_calls == [1, 2]
    assert len(client.detail_calls) == 152
    assert database.query(WelfareService).count() == 152


def test_failed_detail_does_not_replace_existing_service_or_conditions(database):
    existing = WelfareService(
        serv_id="service-000",
        serv_name="previous name",
        target_details="previous target",
        selection_criteria="previous criteria",
        support_content="previous support",
    )
    database.add(existing)
    database.flush()
    database.add(WelfareEligibilityCondition(
        serv_id="service-000",
        condition_type="age",
        operator="gte",
        value_text="old source",
        value_number=20,
        unit="age",
        source_field="selection_criteria",
        source_text="old source",
        comparison_ready=True,
        parse_status="parsed",
        confidence=1,
    ))
    database.commit()
    service = WelfareSyncService()
    service.client = FakeWelfareClient(
        service_count=1,
        fail_details={"service-000": WelfareApiError("network_error")},
    )
    open_window(database, "one", "list", 1)
    open_window(database, "one", "detail", 1)

    result = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="one",
        detail_window_id="one",
        start_new_batch=True,
    ))

    database.expire_all()
    assert result["failed_count"] == 1
    assert database.get(WelfareService, "service-000").serv_name == "previous name"
    assert database.get(WelfareService, "service-000").selection_criteria == "previous criteria"
    old_condition = database.query(WelfareEligibilityCondition).one()
    assert old_condition.value_text == "old source"


def test_quota_limit_stops_detail_requests_and_new_window_resumes_blocked_item(database):
    client = FakeWelfareClient(
        service_count=3,
        fail_details={"service-000": WelfareApiError("quota_exhausted", "429")},
    )
    service = WelfareSyncService(client=client)
    open_window(database, "list-window", "list", 1)
    open_window(database, "detail-window-1", "detail", 3)

    first = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="list-window",
        detail_window_id="detail-window-1",
        start_new_batch=True,
    ))

    assert first["batch_status"] == "paused"
    assert first["detail_quota_blocked_count"] == 1
    assert first["detail_unprocessed_count"] == 2
    assert len(client.detail_calls) == 1
    client.fail_details.clear()
    open_window(database, "detail-window-2", "detail", 3)

    resumed = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=first["batch_id"],
        detail_window_id="detail-window-2",
    ))

    assert resumed["batch_status"] == "completed"
    assert resumed["synced_count"] == 3
    assert len(client.detail_calls) == 4


def test_partial_listing_resumes_from_saved_page_without_refetching_page_one(database):
    client = FakeWelfareClient(
        fail_list_pages={2: WelfareApiError("network_error")},
    )
    service = WelfareSyncService(client=client)
    open_window(database, "list-day-1", "list", 2)
    open_window(database, "detail-window", "detail", 1)

    first = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="list-day-1",
        detail_window_id="detail-window",
        start_new_batch=True,
        max_detail_attempts=1,
    ))

    assert first["batch_status"] == "listing"
    assert first["listed_count"] == 100
    assert first["detail_attempt_count"] == 0
    client.fail_list_pages.clear()
    open_window(database, "list-day-2", "list", 1)

    resumed = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=first["batch_id"],
        list_window_id="list-day-2",
        detail_window_id="detail-window",
        max_detail_attempts=1,
    ))

    assert resumed["listed_count"] == 152
    assert client.list_calls == [1, 2, 2]
    assert len(client.detail_calls) == 1


def test_detail_response_with_wrong_service_id_keeps_previous_rows(database):
    previous = WelfareService(
        serv_id="service-000",
        serv_name="saved name",
        target_details="saved target",
        selection_criteria="saved criteria",
    )
    database.add(previous)
    database.flush()
    database.add(WelfareEligibilityCondition(
        serv_id="service-000",
        condition_type="other",
        operator="unknown",
        value_text="saved condition",
        source_field="selection_criteria",
        source_text="saved condition",
        comparison_ready=False,
        parse_status="manual_review",
        confidence=0,
    ))
    database.commit()
    service = WelfareSyncService(client=FakeWelfareClient(
        service_count=1,
        detail_ids={"service-000": "other-id"},
    ))
    open_window(database, "list", "list", 1)
    open_window(database, "detail", "detail", 1)

    result = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="list",
        detail_window_id="detail",
        start_new_batch=True,
    ))

    database.expire_all()
    assert result["detail_failure_count"] == 1
    assert database.get(WelfareService, "service-000").serv_name == "saved name"
    assert database.query(WelfareEligibilityCondition).one().value_text == "saved condition"


def test_durable_received_payload_completes_without_detail_api_call(database):
    client = FakeWelfareClient(service_count=1)
    service = WelfareSyncService(client=client)
    repository = WelfareSyncRepository()
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "crashed-worker")
    repository.save_list_page(
        database,
        batch.batch_id,
        worker_token="crashed-worker",
        page_no=1,
        total_count=1,
        summaries=[{"serv_id": "service-000", "serv_name": "summary"}],
    )
    item = repository.claim_next_item(database, batch.batch_id, "crashed-worker")
    payload = client.parse_welfare_service_detail(
        "<root><resultCode>0</resultCode><servId>service-000</servId><servNm>received detail</servNm></root>"
    )
    repository.save_received_payload(database, item.id, "crashed-worker", payload)
    repository.release_batch(database, batch.batch_id, "crashed-worker")

    result = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=batch.batch_id,
    ))

    assert result["batch_status"] == "completed"
    assert database.get(WelfareService, "service-000").serv_name == "received detail"
    assert client.detail_calls == []


def test_explicit_retry_reprocesses_failed_items_and_skips_succeeded_items(database):
    client = FakeWelfareClient(
        service_count=2,
        fail_details={"service-000": WelfareApiError("network_error")},
    )
    service = WelfareSyncService(client=client)
    open_window(database, "list-retry", "list", 1)
    open_window(database, "detail-retry", "detail", 3)

    first = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="list-retry",
        detail_window_id="detail-retry",
        start_new_batch=True,
    ))
    assert first["detail_failure_count"] == 1

    continued = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=first["batch_id"],
        detail_window_id="detail-retry",
    ))
    assert continued["batch_status"] == "partial"
    assert continued["detail_success_count"] == 1

    client.fail_details.clear()
    retried = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=first["batch_id"],
        detail_window_id="detail-retry",
        retry_failed=True,
    ))

    assert retried["batch_status"] == "completed"
    assert retried["detail_success_count"] == 1
    assert client.detail_calls == ["service-000", "service-001", "service-000"]


def test_successful_sparse_detail_does_not_erase_saved_criteria_or_conditions(database):
    saved_service = WelfareService(
        serv_id="service-000",
        serv_name="old name",
        target_details="old target detail",
        selection_criteria="old selection criteria",
        support_content="old support",
    )
    database.add(saved_service)
    database.flush()
    database.add(WelfareEligibilityCondition(
        serv_id="service-000",
        condition_type="other",
        operator="unknown",
        value_text="old condition",
        source_field="selection_criteria",
        source_text="old selection criteria",
        comparison_ready=False,
        parse_status="manual_review",
        confidence=0,
    ))
    database.commit()

    class SparseDetailClient(FakeWelfareClient):
        async def get_welfare_service_detail(self, serv_id):
            self.detail_calls.append(serv_id)
            return (
                "<root><resultCode>0</resultCode><servId>service-000</servId>"
                "<servNm>updated name</servNm></root>"
            )

    client = SparseDetailClient(service_count=1)
    service = WelfareSyncService(client=client)
    open_window(database, "sparse-list", "list", 1)
    open_window(database, "sparse-detail", "detail", 1)

    result = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="sparse-list",
        detail_window_id="sparse-detail",
        start_new_batch=True,
    ))

    database.expire_all()
    assert result["detail_success_count"] == 1
    assert database.get(WelfareService, "service-000").serv_name == "updated name"
    assert database.get(WelfareService, "service-000").target_details == "old target detail"
    assert database.get(WelfareService, "service-000").selection_criteria == "old selection criteria"
    assert database.query(WelfareEligibilityCondition).one().value_text == "old condition"


def test_verified_zero_detail_quota_pauses_without_request_and_resumes_with_new_window(database):
    client = FakeWelfareClient(service_count=1)
    service = WelfareSyncService(client=client)
    open_window(database, "zero-list", "list", 1)
    open_window(database, "zero-detail", "detail", 0)

    paused = __import__("asyncio").run(service.sync_welfare_services(
        database,
        list_window_id="zero-list",
        detail_window_id="zero-detail",
        start_new_batch=True,
    ))

    assert paused["batch_status"] == "paused"
    assert paused["detail_attempt_count"] == 0
    assert paused["detail_unprocessed_count"] == 1
    assert client.detail_calls == []

    open_window(database, "new-detail", "detail", 1)
    resumed = __import__("asyncio").run(service.sync_welfare_services(
        database,
        batch_id=paused["batch_id"],
        detail_window_id="new-detail",
    ))
    assert resumed["batch_status"] == "completed"
    assert client.detail_calls == ["service-000"]
