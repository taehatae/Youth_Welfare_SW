"""격리 DB/가상 프로필에서 공개 응답과 로그인 전용 상세 안내의 경계를 검증한다."""
from copy import deepcopy

import pytest

from app.core.config import settings
from app.models.account import AccountWorkspace
from app.models.eligibility_path import EligibilityPath, EligibilityPathCondition, PolicyEligibility
from app.models.welfare_service import WelfareService
from app.services.structured_condition_service import source_hash
from tests.test_account_flow import setup, signup


def prepare(client, db, monkeypatch, field="만 나이", operator="gte", value=26,
            upper=None, values=None, kind="requirement", profile=None):
    monkeypatch.setattr(settings, "use_eligibility_paths", True)
    source = "합성 원문: 판정과 안내의 보안 경계를 검증합니다."
    service = WelfareService(serv_id="guide-test", serv_name="격리 안내 검증", detail_url="", target_details=source)
    db.add(service)
    db.flush()
    record = PolicyEligibility(serv_id=service.serv_id, status="reviewed", source_sha256=source_hash(service),
                               drafted_by="human-test")
    record.paths.append(EligibilityPath(path_key="p", label="검증 경로", kind="기본", sort_order=0, checks=[],
        conditions=[EligibilityPathCondition(field=field, operator=operator, value=value, upper_value=upper,
                                            values=values or [], kind=kind, evidence=source)]))
    db.add(record)
    db.commit()
    account = signup(client)
    p = {"age": 25, "region": "서울특별시", "income_level": 3000000, "employment_status": "UNEMPLOYED",
         "eligibility_conditions": {"housing_type": "MONTHLY", "owns_home": "YES", "student_status": "YES",
                                    "gender": "MALE", "additional_conditions": {"household_homeless": "NO"}}}
    p.update(profile or {})
    response = client.post("/api/v1/welfare/diagnose", json=p)
    assert response.status_code == 200
    state = response.json()
    snap = state["current"]
    request = {"snapshot": "current",
               "profile_key": snap["profileKey"], "checked_at": snap["checkedAt"], "policy_id": service.serv_id}
    return account, state, request


def view(client, request):
    return client.post("/api/v1/users/condition-guides/view", json=request)


def test_session_authenticated_age_guide_without_credentials_preserves_public_and_saved_state(setup, monkeypatch):
    client, db = setup
    account, public, request = prepare(client, db, monkeypatch)
    workspace = db.get(AccountWorkspace, account["account_id"])
    original = deepcopy(workspace.state)
    response = view(client, request)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    text = response.json()["items"][0]["condition_guide"]
    assert "25세" in text and "26세" in text and "1년 뒤" in text
    assert response.json()["items"][0]["gap_index"] == 0
    assert response.json()["items"][0]["guide_kind"] == "state_change"
    db.expire_all()
    assert db.get(AccountWorkspace, account["account_id"]).state == original
    assert client.get("/api/v1/users/state").json() == public
    public_gap = next(a for a in public["current"]["analysis"]["matched"]["analysis_results"]
                      if a["policy_id"] == "guide-test")["eligibility_paths"][0]["conditions"][0]
    assert "25세" not in public_gap["condition_guide"]


@pytest.mark.parametrize("changes,status", [({"profile_key": "0" * 64}, 409),
    ({"checked_at": "2000-01-01T00:00:00Z"}, 409), ({"policy_id": "missing"}, 404)])
def test_private_guide_checks_owned_snapshot_and_policy(setup, monkeypatch, changes, status):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch)
    assert view(client, {**request, **changes}).status_code == status


@pytest.mark.parametrize("field,op,value,values,kind,parts", [
    ("본인 월소득", "lte", 2500000, [], "requirement", ["3,000,000원", "250만원 이하", "500,000원 낮아지면"]),
    ("주거 형태", "one_of", None, ["전세"], "requirement", ["월세", "전세"]),
    ("고용 상태", "one_of", None, ["재직"], "requirement", ["미취업", "재직"]),
    ("성별", "one_of", None, ["여성"], "requirement", ["남성", "여성"]),
    ("재학 여부", "is_true", None, [], "exclusion", ["재학", "재학하지 않는 상태"]),
    ("본인 명의 주택 보유", "is_true", None, [], "exclusion", ["본인 명의 주택", "보유하지 않는 상태"]),
    ("세대원 전원 무주택", "is_true", None, [], "requirement", ["세대원 전원", "본인 명의 주택"]),
])
def test_private_messages_use_exact_compared_field_and_direction(setup, monkeypatch, field, op, value, values, kind, parts):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch, field, op, value, values=values, kind=kind)
    response = view(client, request)
    assert response.status_code == 200
    text = response.json()["items"][0]["condition_guide"]
    assert all(p in text for p in parts)
    assert "퇴사하세요" not in text and "이사하세요" not in text
    if field == "주거 형태":
        assert "무주택" not in text and "주택 보유" not in text
    if field == "재학 여부":
        assert "졸업" not in text


def test_unknown_or_changed_policy_and_old_snapshot_get_no_invented_personal_guide(setup, monkeypatch):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    record = db.get(PolicyEligibility, "guide-test")
    record.source_sha256 = "0" * 64
    db.commit()
    response = view(client, request)
    assert response.status_code == 200 and response.json()["items"] == []
    record.source_sha256 = source_hash(db.get(WelfareService, "guide-test"))
    workspace = db.get(AccountWorkspace, account["account_id"])
    state = deepcopy(workspace.state)
    for a in state["current"]["analysis"]["matched"]["analysis_results"]:
        a.pop("eligibility_paths", None)
    workspace.state = state
    db.commit()
    assert view(client, request).json()["items"] == []


def test_private_endpoint_requires_session_on_every_request(setup, monkeypatch):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch)
    assert view(client, request).status_code == 200
    assert view(client, request).status_code == 200
    client.post("/api/v1/auth/logout")
    assert view(client, request).status_code == 401


def test_expired_session_returns_no_personal_information(setup, monkeypatch):
    from datetime import timedelta
    from app.models.account import AccountSession
    from app.services.auth_service import COOKIE_NAME, token_hash, utcnow
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch)
    session = db.get(AccountSession, token_hash(client.cookies.get(COOKIE_NAME)))
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    response = view(client, request)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert "items" not in response.json() and "25" not in response.text


def test_same_policy_different_input_changes_private_text_and_stale_request_is_rejected(setup, monkeypatch):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    first = view(client, request).json()["items"][0]["condition_guide"]
    stored = deepcopy(db.get(AccountWorkspace, account["account_id"]).state["current"]["profile"])
    stored["age"] = 24
    public = client.post("/api/v1/welfare/diagnose", json=stored).json()
    assert view(client, request).status_code == 409
    new = public["current"]
    second = view(client, {**request, "profile_key": new["profileKey"], "checked_at": new["checkedAt"]}).json()["items"][0]["condition_guide"]
    assert "25세" in first and "1년 뒤" in first
    assert "24세" in second and "2년 뒤" in second
    assert first != second


def test_other_logged_in_account_cannot_view_the_original_accounts_private_guide(setup, monkeypatch):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    signup(client, "account_b")
    assert view(client, request).status_code == 409
    response = client.post("/api/v1/users/condition-guides/view", json=request,
                           headers={"X-Account-ID": account["account_id"]})
    assert response.status_code == 401 and "items" not in response.json()


def test_snapshot_selector_cannot_mix_current_and_diagnosis_records(setup, monkeypatch):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    state = deepcopy(db.get(AccountWorkspace, account["account_id"]).state)
    state["diagnosis"]["checkedAt"] = "2020-01-01T00:00:00Z"
    db.get(AccountWorkspace, account["account_id"]).state = state
    db.commit()
    assert view(client, request).status_code == 200
    assert view(client, {**request, "snapshot": "diagnosis"}).status_code == 409


def test_guide_read_does_not_create_auth_attempts_or_unlock_profile(setup, monkeypatch):
    from sqlalchemy import select, func
    from app.models.account import AuthAttempt
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch)
    before = db.scalar(select(func.count()).select_from(AuthAttempt))
    assert view(client, request).status_code == 200
    assert db.scalar(select(func.count()).select_from(AuthAttempt)) == before
    assert client.get("/api/v1/users/profile").status_code == 403
    assert client.post("/api/v1/users/profile/view", json={"snapshot": "current"}).status_code == 422


def test_guide_uses_snapshot_inputs_not_subsequently_edited_profile(setup, monkeypatch):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch)
    first = view(client, request).json()
    response = client.post("/api/v1/users/profile", json={"age": 24, "region": "부산광역시",
        "income_level": 1000000, "employment_status": "EMPLOYED"})
    assert response.status_code == 200
    assert view(client, request).json() == first


def test_other_accounts_existing_diagnosis_cannot_be_selected_by_supplied_keys(setup, monkeypatch):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    profile = deepcopy(db.get(AccountWorkspace, account["account_id"]).state["current"]["profile"])
    signup(client, "account_b")
    own = client.post("/api/v1/welfare/diagnose", json=profile).json()["current"]
    assert own["profileKey"] != request["profile_key"]
    assert view(client, request).status_code == 409
    own_request = {**request, "profile_key": own["profileKey"], "checked_at": own["checkedAt"]}
    assert view(client, own_request).status_code == 200


def test_age_upper_limit_does_not_suggest_that_time_will_reduce_age(setup, monkeypatch):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch, operator="lte", value=25, profile={"age": 26})
    text = view(client, request).json()["items"][0]["condition_guide"]
    assert "26세" in text and "1세 많고" in text and "시간이 지나도 줄지 않아" in text


@pytest.mark.parametrize("value", [None, "UNKNOWN", ""])
def test_unanswered_gender_is_not_a_failed_condition_or_personal_change(setup, monkeypatch, value):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch, "성별", "one_of", None, values=["여성"],
                            profile={"eligibility_conditions": {"gender": value}})
    assert view(client, request).json()["items"] == []


def test_income_measures_and_unstructured_facts_are_not_interchanged():
    from app.services.personalized_condition_guidance import personalized_guide
    from tests.test_condition_guides import condition
    for field in ("가구 소득인정액", "가구 월소득 중위소득 대비"):
        text = personalized_guide(condition(field, "lte", 50, unit="%"), 70)
        assert "70%" in text and "50%" in text and "20%" in text
        assert "본인 월소득" not in text
        if field == "가구 월소득 중위소득 대비":
            assert "소득인정액" not in text
    assert personalized_guide(condition("가구 총재산", "lte", 100000000, unit="원"), (90000000, 110000000)) is None
    assert personalized_guide(condition("대상 집단", "one_of", values=["등록장애 또는 보호자"]), "일반") is None
    assert personalized_guide(condition("고용 상태", "one_of", values=["재직"]), None) is None
    assert personalized_guide(condition("학적 상태", "one_of", values=["졸업"]), "재학") is None
    assert personalized_guide(condition("본인 월소득", "gte", 0, unit="원"), 0) is None


def test_ambiguous_source_connection_and_changed_target_do_not_personalize(setup, monkeypatch):
    client, db = setup
    _, _, request = prepare(client, db, monkeypatch)
    path = db.get(PolicyEligibility, "guide-test").paths[0]
    path.conditions[0].value = 27
    db.commit()
    assert view(client, request).json()["items"] == []
    path.conditions[0].value = 26
    path.conditions.append(EligibilityPathCondition(field="만 나이", operator="gte", value=26,
        values=[], kind="requirement", evidence=path.conditions[0].evidence))
    db.commit()
    assert view(client, request).json()["items"] == []


@pytest.mark.parametrize("sid,parts", [
    ("WLF00000781", ["남성", "여성"]),
    ("WLF00000078", ["25세", "24세 이하", "시간이 지나도 줄지 않아"]),
    ("WLF00004649", ["본인 명의 주택", "보유하지 않는 상태"]),
    ("WLF00000095", ["3,000,000원", "270만원 미만", "300,001원 낮아지면"]),
])
def test_actual_reviewed_policy_guides_use_synthetic_profile_without_changing_analysis(setup, monkeypatch, tmp_path, sid, parts):
    import json
    from app.services import eligibility_path_service as paths
    from tests.test_condition_guides import REVIEWED, SOURCES
    client, db = setup
    monkeypatch.setattr(settings, "use_eligibility_paths", True)
    raw = SOURCES[sid]
    db.add(WelfareService(serv_id=sid, serv_name=raw["serv_name"], detail_url=raw.get("detail_url", ""),
        target_details=raw["target_details"], selection_criteria=raw["selection_criteria"]))
    db.commit()
    seed = tmp_path / "actual-reviewed-excerpt.json"
    seed.write_text(json.dumps({"policies": [p for p in REVIEWED if p["serv_id"] == sid]}), encoding="utf-8")
    paths.seed_from_file(db, seed)
    account = signup(client)
    state = client.post("/api/v1/welfare/diagnose", json={"age": 25, "region": "서울특별시", "income_level": 3000000,
        "employment_status": "EMPLOYED", "eligibility_conditions": {"gender": "MALE", "owns_home": "YES",
        "household_size": 1, "additional_conditions": {"household_monthly_income_won": 10000000}}}).json()
    snap = state["current"]
    before = deepcopy(db.get(AccountWorkspace, account["account_id"]).state)
    response = view(client, {"snapshot": "current",
        "profile_key": snap["profileKey"], "checked_at": snap["checkedAt"], "policy_id": sid})
    assert response.status_code == 200
    text = " ".join(i["condition_guide"] for i in response.json()["items"])
    assert all(p in text for p in parts)
    db.expire_all()
    assert db.get(AccountWorkspace, account["account_id"]).state == before
    assert client.get("/api/v1/users/state").json() == state
    public = next(a for a in snap["analysis"]["matched"]["analysis_results"] if a["policy_id"] == sid)
    assert public["path_review"] == "reviewed" and public["status"] == "ineligible"


def test_private_guides_cover_every_path_not_only_the_representative_one(setup, monkeypatch, tmp_path):
    import json
    from app.services import eligibility_path_service as paths
    from tests.test_condition_guides import REVIEWED, SOURCES
    client, db = setup
    monkeypatch.setattr(settings, "use_eligibility_paths", True)
    sid = next(p["serv_id"] for p in REVIEWED if p["name"].startswith("행복주택"))
    raw = SOURCES[sid]
    db.add(WelfareService(serv_id=sid, serv_name=raw["serv_name"], detail_url=raw.get("detail_url", ""),
        target_details=raw["target_details"], selection_criteria=raw["selection_criteria"]))
    db.commit()
    seed = tmp_path / "happy-house.json"
    seed.write_text(json.dumps({"policies": [p for p in REVIEWED if p["serv_id"] == sid]}), encoding="utf-8")
    paths.seed_from_file(db, seed)
    signup(client)
    snap = client.post("/api/v1/welfare/diagnose", json={"age": 30, "region": "서울특별시", "income_level": 6500000,
        "employment_status": "EMPLOYED", "eligibility_conditions": {"marital_status": "MARRIED", "household_size": 3,
        "owns_home": "NO", "additional_conditions": {"asset_amount_won": 400000000, "personal_asset_amount_won": 200000000}}}).json()["current"]
    analysis = next(a for a in snap["analysis"]["matched"]["analysis_results"] if a["policy_id"] == sid)
    items = client.post("/api/v1/users/condition-guides/view", json={"snapshot": "current", "profile_key": snap["profileKey"],
        "checked_at": snap["checkedAt"], "policy_id": sid}).json()["items"]
    by_path = {(i["path_id"], i["condition_index"]): i["condition_guide"] for i in items if i.get("path_id")}
    other = [k for k in by_path if k[0] != analysis["matched_path_id"]]
    assert other, "대표 경로가 아닌 경로에도 맞춤 안내가 있어야 한다"
    for (path_id, index), text in by_path.items():
        stored = next(p for p in analysis["eligibility_paths"] if p["path_id"] == path_id)["conditions"][index]
        assert stored["status"] == "failed"
    assert any("400,000,000원" in t or "200,000,000원" in t for t in by_path.values())
