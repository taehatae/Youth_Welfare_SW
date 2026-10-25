import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.models.welfare_service import WelfareService
from app.models.welfare_sync import (
    WelfareApiQuotaWindow,
    WelfareSyncBatch,
    WelfareSyncItem,
)


def test_sync_models_add_tables_without_changing_existing_welfare_data():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            service = WelfareService(serv_id="existing", serv_name="Existing policy")
            db.add(service)
            db.flush()
            condition = WelfareEligibilityCondition(
                serv_id="existing",
                condition_type="age",
                operator="gte",
                value_text="18+",
                value_number=18,
                unit="years",
                source_field="selection_criteria",
                source_text="18+",
                comparison_ready=True,
                parse_status="parsed",
                confidence=1.0,
            )
            db.add(condition)
            db.commit()

            Base.metadata.create_all(engine)

            assert db.get(WelfareService, "existing").serv_name == "Existing policy"
            assert db.query(WelfareEligibilityCondition).filter_by(serv_id="existing").count() == 1
            table_names = set(inspect(engine).get_table_names())
            assert {"welfare_sync_batches", "welfare_sync_items", "welfare_api_quota_windows"} <= table_names
    finally:
        engine.dispose()


def test_sync_item_is_unique_per_batch_and_service():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            batch = WelfareSyncBatch(batch_id="batch-1", life_array="004", status="listing")
            db.add(batch)
            db.flush()
            db.add_all([
                WelfareSyncItem(batch_id=batch.batch_id, serv_id="service-1", status="pending"),
                WelfareSyncItem(batch_id=batch.batch_id, serv_id="service-1", status="pending"),
            ])
            with pytest.raises(IntegrityError):
                db.commit()
    finally:
        engine.dispose()


def test_quota_windows_are_independent_by_operation():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.add_all([
                WelfareApiQuotaWindow(
                    window_id="provider-window-day-1",
                    operation="list",
                    used_count=2,
                    limit_count=100,
                    confirmed_available_calls=98,
                    confirmed=True,
                ),
                WelfareApiQuotaWindow(
                    window_id="provider-window-day-1",
                    operation="detail",
                    used_count=100,
                    limit_count=100,
                    confirmed_available_calls=100,
                    confirmed=True,
                ),
            ])
            db.commit()

            rows = {row.operation: row for row in db.query(WelfareApiQuotaWindow).all()}
            assert rows["list"].used_count == 2
            assert rows["detail"].used_count == 100
    finally:
        engine.dispose()


def test_pytest_application_engine_uses_memory_database():
    from app.main import engine as app_engine

    assert app_engine.url.drivername == "sqlite"
    assert app_engine.url.database is None
    assert "welfare_sync_batches" in inspect(app_engine).get_table_names()
