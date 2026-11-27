import pytest
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.welfare_sync import WelfareApiQuotaWindow
from app.repositories.welfare_sync_repository import (
    QuotaWindowUnavailable,
    ActiveSyncLease,
    WelfareSyncRepository,
)


@pytest.fixture
def database():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()


def test_list_and_detail_quota_windows_reserve_calls_independently(database):
    repository = WelfareSyncRepository()
    repository.open_quota_window(
        database,
        window_id="verified-day-1",
        operation="list",
        verified_available_calls=2,
        operator_name="local-operator",
    )
    repository.open_quota_window(
        database,
        window_id="verified-day-1",
        operation="detail",
        verified_available_calls=100,
        operator_name="local-operator",
    )

    assert repository.reserve_quota_call(database, "verified-day-1", "list") == 1
    assert repository.reserve_quota_call(database, "verified-day-1", "list") == 0
    assert repository.reserve_quota_call(database, "verified-day-1", "detail") == 99
    assert database.query(WelfareApiQuotaWindow).filter_by(operation="list").one().used_count == 2
    assert database.query(WelfareApiQuotaWindow).filter_by(operation="detail").one().used_count == 1


def test_unverified_or_missing_quota_window_is_rejected_before_reservation(database):
    repository = WelfareSyncRepository()

    with pytest.raises(QuotaWindowUnavailable):
        repository.open_quota_window(
            database,
            window_id="unverified",
            operation="detail",
            verified_available_calls=None,
            operator_name="local-operator",
        )

    with pytest.raises(QuotaWindowUnavailable):
        repository.reserve_quota_call(database, "not-open", "detail")

    assert database.query(WelfareApiQuotaWindow).count() == 0


def test_quota_window_rejects_unconfirmed_and_blocks_after_quota_error(database):
    repository = WelfareSyncRepository()
    repository.open_quota_window(
        database,
        window_id="verified-day-2",
        operation="detail",
        verified_available_calls=3,
        operator_name="local-operator",
    )
    repository.block_quota_window(database, "verified-day-2", "detail")

    with pytest.raises(QuotaWindowUnavailable):
        repository.reserve_quota_call(database, "verified-day-2", "detail")


def test_provider_xml_error_does_not_infer_quota_from_message():
    from app.clients.welfare_api_client import WelfareApiClient, WelfareApiError

    with pytest.raises(WelfareApiError) as error:
        WelfareApiClient().parse_welfare_services(
            "<root><resultCode>999</resultCode><resultMessage>quota limit reached</resultMessage></root>"
        )

    assert error.value.category == "provider_error"
    assert error.value.category != "quota_exhausted"
    assert "quota limit reached" not in str(error.value)


def test_detail_parser_preserves_absent_fields_as_absent_not_empty():
    from app.clients.welfare_api_client import WelfareApiClient

    parsed = WelfareApiClient().parse_welfare_service_detail(
        "<root><resultCode>0</resultCode><servId>policy-1</servId><servNm>New name</servNm></root>"
    )

    assert parsed["serv_id"] == "policy-1"
    assert parsed["serv_name"] == "New name"
    assert "selection_criteria" not in parsed
    assert "target_details" not in parsed
    assert "support_content" not in parsed


def test_operator_confirmation_is_required_to_open_quota_window(database):
    from app.services.welfare_sync_operator import confirm_quota_window

    with pytest.raises(QuotaWindowUnavailable):
        confirm_quota_window(
            database,
            window_id="day-1",
            operation="list",
            verified_available_calls=2,
            operator_name="operator",
            confirm_provider_quota=False,
        )

    assert database.query(WelfareApiQuotaWindow).count() == 0
    window = confirm_quota_window(
        database,
        window_id="day-1",
        operation="list",
        verified_available_calls=2,
        operator_name="operator",
        confirm_provider_quota=True,
    )
    assert window.confirmed is True
    assert window.confirmed_available_calls == 2


def test_batch_quota_windows_can_only_be_bound_by_the_live_lease_owner(database):
    repository = WelfareSyncRepository()
    batch = repository.create_batch(database, life_array="004")
    assert repository.acquire_batch(database, batch.batch_id, "worker-a")

    with pytest.raises(ActiveSyncLease):
        repository.set_batch_windows(
            database,
            batch.batch_id,
            worker_token="worker-b",
            detail_window_id="unowned-window",
        )
    database.refresh(batch)
    assert batch.detail_window_id is None

    repository.set_batch_windows(
        database,
        batch.batch_id,
        worker_token="worker-a",
        detail_window_id="owned-window",
    )
    database.refresh(batch)
    assert batch.detail_window_id == "owned-window"
