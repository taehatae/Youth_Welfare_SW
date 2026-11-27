"""격리된 메모리 DB에서 계정 흐름과 개인정보 경계를 검증한다."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.connection import Base, create_database_engine, get_db
from app.models.account import Account, AccountSession, AccountWorkspace
from app.models.user import User, UserEligibilityConditions
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.services.auth_service import COOKIE_NAME, token_hash, utcnow, verify_password
from app.services.eligibility_matching_service import EligibilityMatchingService

PASSWORD = "AccountCheck123!"
PROFILE = {"age": 25, "region": "서울특별시 관악구", "income_level": 2130000,
           "employment_status": "OTHER", "eligibility_conditions": {
               "household_size": 2, "owns_home": False, "student_status": "NO",
               "additional_conditions": {"employment_detail": "PART_TIME", "near_poverty_status": "NO"}}}


@pytest.fixture
def setup():
    engine = create_database_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        def dependency():
            yield db
        app.dependency_overrides[get_db] = dependency
        # 테스트 전용 DB 안에서만 생성하며 실제 공공 정책 DB는 사용하거나 수정하지 않는다.
        db.add(WelfareService(serv_id="unit-policy", serv_name="격리 테스트 정책", detail_url="https://example.com/policy"))
        db.flush()
        db.add(WelfareEligibilityCondition(serv_id="unit-policy", condition_type="age", operator="gte",
            value_text="만 30세 이상", value_number=30, upper_value_number=None, unit="세",
            source_field="selection_criteria", source_text="만 30세 이상", comparison_ready=True,
            parse_status="parsed", confidence=1.0))
        db.commit()
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, db
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def signup(client, name="account_a"):
    response = client.post("/api/v1/auth/signup", json={"username": name, "password": PASSWORD, "display_name": "검증 계정"})
    assert response.status_code == 201, response.text
    return response.json()


def reauth(client, **changes):
    return client.post("/api/v1/users/profile/view", json={"username": "account_a", "password": PASSWORD, **changes})


def assert_locked(state):
    assert state["profile"] is None
    for name in ("diagnosis", "previousDiagnosis", "current", "previous"):
        snapshot = state.get(name)
        if snapshot:
            assert snapshot["profile"] is None
            assert len(snapshot["profileKey"]) == 64
            for row in snapshot["analysis"]["matched"]["analysis_results"]:
                for field in ("gap_conditions", "review_conditions"):
                    assert all(item["current_value"] == "프로필 보호 중" for item in row[field])
    for item in state["savedPolicies"]:
        assert item["profile"] is None
        assert len(item["profileKey"]) == 64
        assert all(c["current"] == "프로필 보호 중" for c in item["policy"]["conditions"])


def test_signup_login_diagnose_refresh_restore_and_favorites(setup):
    client, db = setup
    account = signup(client)
    stored = db.get(Account, account["account_id"])
    assert stored.password_hash != PASSWORD and verify_password(PASSWORD, stored.password_hash)
    raw_token = client.cookies.get(COOKIE_NAME)
    assert db.get(AccountSession, token_hash(raw_token))
    assert db.get(AccountSession, raw_token) is None
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    login = client.post("/api/v1/auth/login", json={"username": "ACCOUNT_A", "password": PASSWORD})
    assert login.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=lax" in login.headers["set-cookie"].lower()
    response = client.post("/api/v1/welfare/diagnose", json=PROFILE)
    assert response.status_code == 200, response.text
    state = response.json()
    assert_locked(state)
    first = state["diagnosis"]
    assert first["analysis"]["matched"]["evaluated_count"] == 1
    user_id = first["analysis"]["userId"]
    user = db.get(User, user_id)
    assert user.income_level == PROFILE["income_level"]
    assert db.get(UserEligibilityConditions, user_id).conditions == PROFILE["eligibility_conditions"]
    original = EligibilityMatchingService().analyze_user(db, user, PROFILE["eligibility_conditions"])
    assert first["analysis"]["matched"]["analysis_results"][0]["match_score"] == original["analysis_results"][0]["match_score"]
    saved = client.post("/api/v1/users/saved/toggle", json={"profileKey": first["profileKey"], "policyId": "unit-policy"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["items"][0]["profile"] is None
    refreshed = client.post("/api/v1/welfare/refresh").json()
    assert_locked(refreshed)
    assert refreshed["diagnosis"] == first
    assert refreshed["previous"] == state["current"]
    assert refreshed["current"]["checkedAt"] != first["checkedAt"]
    assert refreshed["current"]["profileKey"] == first["profileKey"]
    assert len(refreshed["savedPolicies"]) == 1
    assert client.get("/api/v1/users/state").json() == refreshed
    assert reauth(client).json() == PROFILE
    # 한 번 조회해도 쿠키에 프로필 조회 권한이 남지 않는다.
    assert client.get("/api/v1/users/profile").status_code == 403
    assert_locked(client.get("/api/v1/users/state").json())
    second = client.post("/api/v1/welfare/diagnose", json={**PROFILE, "age": 31}).json()
    assert second["previousDiagnosis"] == first
    assert second["current"]["analysis"]["userId"] == user_id
    assert second["current"]["analysis"]["matched"]["matched_count"] == 1
    assert db.query(User).count() == 1
    assert reauth(client).json()["age"] == 31
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.post("/api/v1/auth/login", json={"username": "account_a", "password": PASSWORD})
    restored = client.get("/api/v1/users/state").json()
    assert restored == second
    assert len(restored["savedPolicies"]) == 1
    removed = client.post("/api/v1/users/saved/toggle", json={"profileKey": first["profileKey"], "policyId": "unit-policy"})
    assert removed.json() == {"items": []}


def test_reauthentication_rejects_wrong_password_and_other_account(setup):
    client, db = setup
    a = signup(client)
    client.post("/api/v1/welfare/diagnose", json=PROFILE)
    assert reauth(client, password="incorrect-password").status_code == 403
    assert reauth(client, username="account_b").status_code == 403
    token_a = client.cookies.get(COOKIE_NAME)
    b = signup(client, "account_b")
    assert reauth(client).status_code == 403  # 유효한 A 비밀번호라도 B 세션에서 사용할 수 없다.
    assert client.get("/api/v1/users/state").json()["current"] is None
    profile_a = db.get(Account, a["account_id"]).profile_id
    for endpoint in ("matched", "reverse-engineering"):
        assert client.get(f"/api/v1/welfare/{endpoint}", params={"user_id": profile_a}).status_code == 404
    assert client.get("/api/v1/users/state", headers={"X-Account-ID": a["account_id"]}).status_code == 401
    assert client.post("/api/v1/auth/logout", headers={"X-Account-ID": a["account_id"]}).status_code == 401
    assert client.get("/api/v1/auth/me").json()["account_id"] == b["account_id"]
    assert client.post("/api/v1/users/profile/view", headers={"X-Account-ID": a["account_id"]}, json={"username": "account_b", "password": PASSWORD}).status_code == 401
    assert db.get(AccountSession, token_hash(token_a)) is None
    session = db.scalar(select(AccountSession).where(AccountSession.account_id == b["account_id"]))
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/users/state").status_code == 401
    assert reauth(client, username="account_b").status_code == 401


@pytest.mark.parametrize("endpoint,method,payload", [
    ("/users/state", "get", None), ("/users/profile", "get", None),
    ("/welfare/diagnose", "post", PROFILE), ("/welfare/refresh", "post", None),
    ("/users/profile/view", "post", {"username": "account_a", "password": PASSWORD}),
])
def test_anonymous_access_is_blocked(setup, endpoint, method, payload):
    client, _ = setup
    response = client.request(method, "/api/v1" + endpoint, json=payload)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("changes", [{"username": "a"}, {"username": "한글아이디"}, {"password": "short"}, {"display_name": "   "}])
def test_signup_validation(setup, changes):
    client, _ = setup
    data = {"username": "account_a", "password": PASSWORD, "display_name": "검증", **changes}
    assert client.post("/api/v1/auth/signup", json=data).status_code == 422


def test_duplicate_invalid_login_and_throttle(setup):
    client, _ = setup
    signup(client)
    assert client.post("/api/v1/auth/signup", json={"username": "ACCOUNT_A", "password": PASSWORD, "display_name": "검증"}).status_code == 409
    for username in ("account_a", "missing_user"):
        response = client.post("/api/v1/auth/login", json={"username": username, "password": "wrong-password"})
        assert response.status_code == 401
        assert response.json()["detail"] == "아이디 또는 비밀번호가 일치하지 않아요."
    from app.models.account import AuthAttempt
    _, db = setup
    for _ in range(40):
        db.add(AuthAttempt(bucket=token_hash("testclient"), created_at=utcnow()))
    db.commit()
    assert reauth(client).status_code == 429


def test_cross_origin_requests_are_rejected(setup):
    client, _ = setup
    signup(client)
    for headers in ({"Origin": "https://untrusted.example"}, {"Sec-Fetch-Site": "cross-site"}):
        assert client.post("/api/v1/welfare/diagnose", json=PROFILE, headers=headers).status_code == 403


def test_failed_diagnosis_is_atomic_and_foreign_favorite_is_rejected(setup, monkeypatch):
    client, db = setup
    signup(client)
    before = client.post("/api/v1/welfare/diagnose", json=PROFILE).json()
    def fail(*args, **kwargs):
        raise RuntimeError("isolated test failure")
    monkeypatch.setattr(EligibilityMatchingService, "analyze_user", fail)
    assert client.post("/api/v1/welfare/diagnose", json={**PROFILE, "age": 32}).status_code == 500
    assert reauth(client).json() == PROFILE
    assert client.get("/api/v1/users/state").json() == before
    assert client.post("/api/v1/users/saved/toggle", json={"profileKey": "a" * 64, "policyId": "unit-policy"}).status_code == 404
    assert client.put("/api/v1/users/saved", json={"items": []}).status_code == 410
