from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes import welfare as welfare_routes
from app.core.config import settings
from app.database.connection import Base, create_database_engine, get_db
from app.models.account import Account


@pytest.fixture
def client(monkeypatch):
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    app = FastAPI()
    app.include_router(welfare_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    account = Account(
        account_id="account-test",
        username="sync-test",
        display_name="Sync Test",
        password_hash="unused",
    )
    app.dependency_overrides[welfare_routes.current_account] = lambda: account
    monkeypatch.setattr(settings, "welfare_sync_operator_token", "operator-secret-test", raising=False)
    sync = AsyncMock(return_value={
        "life_array": "004",
        "listed_count": 0,
        "synced_count": 0,
        "failed_count": 0,
        "failed_services": [],
    })
    monkeypatch.setattr(welfare_routes.welfare_sync_service, "sync_welfare_services", sync)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, sync
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_sync_route_requires_operator_token_before_service_call(client):
    test_client, sync = client

    response = test_client.post("/api/v1/welfare/sync")

    assert response.status_code == 403
    sync.assert_not_awaited()


def test_sync_route_preserves_path_and_response_with_operator_token(client):
    test_client, sync = client

    response = test_client.post(
        "/api/v1/welfare/sync?start_new_batch=true&list_window_id=list-1&detail_window_id=detail-1",
        headers={"X-Welfare-Sync-Token": "operator-secret-test"},
    )

    assert response.status_code == 200
    assert response.json()["life_array"] == "004"
    assert response.json()["listed_count"] == 0
    sync.assert_awaited_once()
    assert sync.await_args.kwargs["start_new_batch"] is True
    assert sync.await_args.kwargs["list_window_id"] == "list-1"
    assert sync.await_args.kwargs["detail_window_id"] == "detail-1"


def test_empty_operator_token_disables_http_sync(client, monkeypatch):
    test_client, sync = client
    monkeypatch.setattr(settings, "welfare_sync_operator_token", "", raising=False)

    response = test_client.post(
        "/api/v1/welfare/sync",
        headers={"X-Welfare-Sync-Token": "operator-secret-test"},
    )

    assert response.status_code == 503
    sync.assert_not_awaited()
