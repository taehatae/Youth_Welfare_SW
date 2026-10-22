import asyncio
from unittest.mock import AsyncMock

from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.services.eligibility_condition_service import EligibilityConditionService
from app.services.welfare_sync_service import WelfareSyncService


def make_sync():
    service = WelfareSyncService()
    service.client.get_welfare_services = AsyncMock(return_value="<root><totalCount>1</totalCount></root>")
    service.client.parse_welfare_services = lambda _: [{"serv_id": "test-sync"}]
    service.client.get_welfare_service_detail = AsyncMock(return_value="<root/>")
    service.client.parse_welfare_service_detail = lambda _: {
        "serv_name": "합성 정책", "target_details": "만 19세 이상 34세 이하",
        "selection_criteria": "",
    }
    return service


def test_new_policy_sync_and_resync_preserve_foreign_keys():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, autoflush=False) as db:
            service = make_sync()
            first = asyncio.run(service.sync_welfare_services(db, max_services=5))
            assert first["synced_count"] == 1
            assert first["failed_count"] == 0
            assert db.get(WelfareService, "test-sync") is not None
            condition_count = db.query(WelfareEligibilityCondition).count()
            assert condition_count > 0
            second = asyncio.run(service.sync_welfare_services(db, max_services=5))
            assert second["synced_count"] == 1
            assert db.query(WelfareService).count() == 1
            assert db.query(WelfareEligibilityCondition).count() == condition_count
    finally:
        engine.dispose()


def test_condition_failure_rolls_back_new_parent(monkeypatch):
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    def fail(**kwargs):
        assert kwargs["db"].get(WelfareService, "test-sync") is not None
        raise RuntimeError("synthetic failure after parent flush")
    monkeypatch.setattr(EligibilityConditionService, "replace_conditions", fail)
    try:
        with Session(engine, autoflush=False) as db:
            result = asyncio.run(make_sync().sync_welfare_services(db, max_services=5))
            assert result["synced_count"] == 0
            assert result["failed_count"] == 1
            assert db.get(WelfareService, "test-sync") is None
            assert db.query(WelfareEligibilityCondition).count() == 0
    finally:
        engine.dispose()
