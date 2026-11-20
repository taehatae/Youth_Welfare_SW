"""간편 정책 찾기 공개 API: 격리 메모리 DB에서 비로그인 접근, 미입력 처리, 기존 판정과의 일치, 비저장·비노출을 검증한다."""
import json

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.account import Account, AccountSession, AccountWorkspace
from app.models.eligibility_path import EligibilityPath, EligibilityPathCondition, PolicyEligibility
from app.models.user import User, UserEligibilityConditions
from app.models.welfare_service import WelfareService
from app.services.structured_condition_service import source_hash
from tests.test_account_flow import setup, signup  # noqa: F401

URL = "/api/v1/quick-finder"


def cond(field, op, value=None, upper=None, values=None, kind="requirement"):
    return EligibilityPathCondition(field=field, operator=op, value=value, upper_value=upper, values=values or [],
                                    kind=kind, evidence="합성 원문 근거")


def add_policy(db, serv_id, interest, paths, common=()):
    service = WelfareService(serv_id=serv_id, serv_name=f"합성 {serv_id}", detail_url=f"https://example.test/{serv_id}",
                             interest_categories=interest, target_details=f"합성 원문 {serv_id}")
    db.add(service)
    db.flush()
    record = PolicyEligibility(serv_id=serv_id, status="reviewed", source_sha256=source_hash(service),
                               drafted_by="human-test")
    record.paths.append(EligibilityPath(path_key="_common", label="공통 조건", kind="공통", sort_order=0, checks=[],
                                        conditions=list(common)))
    for order, (key, conditions, checks) in enumerate(paths, start=1):
        record.paths.append(EligibilityPath(path_key=key, label=f"경로 {key}", kind="기본", sort_order=order,
                                            checks=checks, conditions=conditions))
    db.add(record)


@pytest.fixture
def quick(setup, monkeypatch):  # noqa: F811
    client, db = setup
    monkeypatch.setattr(settings, "use_eligibility_paths", True)
    add_policy(db, "house", "주거", [
        ("a", [cond("가구 소득인정액", "lte", 50)], ["임대차 계약서 확인"]),
        ("b", [cond("세대원 전원 무주택", "is_true"), cond("본인 월소득", "lte", 2_500_000),
               cond("고용 상태", "one_of", values=["미취업"])], []),
    ], common=[cond("만 나이", "between", 19, 34), cond("거주지", "one_of", values=["서울특별시"])])
    add_policy(db, "house-target", "주거", [
        ("v", [cond("국가유공자·보훈대상자", "is_true")], []),
        ("x", [cond("원문에만 있는 항목", "is_true")], []),
    ])
    add_policy(db, "job", "일자리", [("j", [cond("고용 상태", "one_of", values=["미취업"])], [])])
    db.commit()
    return client, db


def evaluate(client, answers, category="housing"):
    return client.post(f"{URL}/evaluate", json={"category": category, "answers": answers})


def results(response):
    assert response.status_code == 200, response.text
    return {a["policy_id"]: a for a in response.json()["matched"]["analysis_results"]}


def stored_rows(db):
    return [db.scalar(select(func.count()).select_from(model))
            for model in (User, UserEligibilityConditions, Account, AccountSession, AccountWorkspace)]


def test_public_category_and_fields_without_login(quick):
    client, _ = quick
    listed = client.get(f"{URL}/categories")
    assert listed.status_code == 200
    counts = {c["id"]: c["policy_count"] for c in listed.json()["categories"]}
    assert counts["housing"] == 2 and counts["employment"] == 1
    detail = client.get(f"{URL}/categories/housing").json()
    assert detail["questions"] == ["age", "region", "income", "employment", "household", "recognized_income",
                                   "home_ownership", "special_targets"]
    assert detail["unsupported_fields"] == ["원문에만 있는 항목"]
    assert detail["path_policy_count"] == 2 and detail["check_count"] == 1
    assert client.get(f"{URL}/categories/employment").json()["questions"] == ["age", "employment"]
    assert client.get(f"{URL}/categories/unknown").status_code == 422


def test_missing_answers_stay_unanswered_and_are_not_defaulted(quick):
    client, db = quick
    before = stored_rows(db)
    response = evaluate(client, {"age": 25})
    rows = results(response)
    assert set(rows) == {"house", "house-target"}  # 선택 분야만
    house = {p["path_id"]: p for p in rows["house"]["eligibility_paths"]}
    statuses = {c["condition_type"]: c["status"] for c in house["b"]["conditions"]}
    assert statuses == {"만 나이": "passed", "거주지": "needs_review", "세대원 전원 무주택": "needs_review",
                        "본인 월소득": "needs_review", "고용 상태": "needs_review"}
    target = {p["path_id"]: p for p in rows["house-target"]["eligibility_paths"]}
    # 대상자 질문에 답하지 않았으면 '해당 없음'으로 보지 않는다.
    assert target["v"]["conditions"][0]["status"] == "needs_review"
    assert rows["house-target"]["status"] == "needs_review"
    # '해당 없음'을 고른 경우에만 미충족이 된다.
    chosen = results(evaluate(client, {"age": 25, "special_targets": []}))
    assert {p["path_id"]: p for p in chosen["house-target"]["eligibility_paths"]}["v"]["status"] == "ineligible"
    assert response.headers["cache-control"] == "no-store" and "set-cookie" not in response.headers
    assert stored_rows(db) == before == [0, 0, 0, 0, 0]


def test_quick_result_matches_logged_in_diagnosis_for_same_input(quick):
    client, db = quick
    answers = {"age": 25, "region": "서울특별시 관악구", "income_monthly_won": 2_000_000, "employment": "UNEMPLOYED",
               "household_size": 1, "recognized_household_income_won": 3_000_000, "household_homeless": "YES",
               "owns_home": "NO"}
    quick_rows = results(evaluate(client, answers))
    signup(client)
    diagnosis = client.post("/api/v1/welfare/diagnose", json={
        "age": 25, "region": "서울특별시 관악구", "income_level": 2_000_000, "employment_status": "UNEMPLOYED",
        "eligibility_conditions": {"household_size": 1, "owns_home": False, "additional_conditions": {
            "profile_schema_version": 3, "employment_detail": "UNEMPLOYED", "household_homeless": "YES",
            "household_income_recognition_known": "YES", "recognized_household_income_won": 3_000_000}}})
    assert diagnosis.status_code == 200
    diagnosed = {a["policy_id"]: a for a in diagnosis.json()["current"]["analysis"]["matched"]["analysis_results"]}
    for policy_id, row in quick_rows.items():
        assert row == diagnosed[policy_id]
    assert quick_rows["house"]["status"] == "eligible"
    assert quick_rows["house"]["matched_path_id"] == "b"


def test_logged_in_user_can_use_it_without_touching_saved_state(quick):
    client, db = quick
    account = signup(client)
    before = db.get(AccountWorkspace, account["account_id"])
    before = json.dumps(before.state if before else None, sort_keys=True)
    rows = stored_rows(db)
    assert evaluate(client, {"age": 30, "employment": "EMPLOYED"}, "employment").status_code == 200
    db.expire_all()
    after = db.get(AccountWorkspace, account["account_id"])
    assert json.dumps(after.state if after else None, sort_keys=True) == before
    assert stored_rows(db) == rows


def test_public_response_hides_exact_difficulty_context_and_inputs(quick):
    client, _ = quick
    response = evaluate(client, {"age": 25, "region": "부산광역시 해운대구", "income_monthly_won": 3_456_000,
                                 "employment": "EMPLOYED", "household_size": 2,
                                 "recognized_household_income_won": 9_876_000})
    rows = results(response)
    assert rows["house"]["status"] == "ineligible"
    text = response.text
    for raw in ("3456000", "3,456,000", "345만", "9876000", "9,876,000", "부산", "해운대"):
        assert raw not in text
    for row in rows.values():
        assert row["evaluation_context"] is None
        for path in row["eligibility_paths"]:
            assert path["difficulty"] is None
            assert all(c["difficulty"] is None for c in path["conditions"])
    assert "difficulties" not in text


@pytest.mark.parametrize("payload", [
    {"category": "housing", "answers": {}},  # 나이는 필수
    {"category": "housing", "answers": {"age": 18}},
    {"category": "nowhere", "answers": {"age": 25}},
    {"category": "housing", "answers": {"age": 25, "unknown": 1}},
    {"category": "housing", "answers": {"age": 25, "region": "어딘가"}},
    {"category": "employment", "answers": {"age": 25, "income_monthly_won": 100}},  # 분야에서 쓰지 않는 항목
    {"category": "housing", "answers": {"age": 25, "income_monthly_won": -1}},
    {"category": "housing", "answers": {"age": 25, "special_targets": ["VETERAN", "VETERAN"]}},
    {"category": "employment", "answers": {"age": 25, "employment": "STUDENT"}},
])
def test_server_validates_category_and_answers(quick, payload):
    client, db = quick
    assert client.post(f"{URL}/evaluate", json=payload).status_code == 422
    assert stored_rows(db) == [0, 0, 0, 0, 0]


def test_contradictory_answers_are_rejected(quick):
    client, _ = quick
    from app.schemas.quick_finder import QuickAnswers
    from pydantic import ValidationError
    for answers in ({"school_level": "COLLEGE"}, {"severe_disability": "YES", "disability_status": "NO"},
                    {"youngest_child_age": 3, "children_count": 0}, {"marriage_years": 2, "marital_status": "SINGLE"},
                    {"credit_score": 700}, {"basic_benefit_types": ["MEDICAL"]}, {"protection_ended": "YES"},
                    {"housing_type": "OWNED", "owns_home": "NO"}):
        with pytest.raises(ValidationError):
            QuickAnswers(age=25, **answers)


def test_requires_path_engine(quick, monkeypatch):
    client, _ = quick
    monkeypatch.setattr(settings, "use_eligibility_paths", False)
    assert client.get(f"{URL}/categories").status_code == 503
    assert evaluate(client, {"age": 25}).status_code == 503


# ---- 공개 API는 읽기 전용: 경로 데이터가 비었거나 일부만 적재되면 503, DB 무변경 ----
PATH_TABLES = (PolicyEligibility, EligibilityPath, EligibilityPathCondition)


def path_rows(db):
    return [db.scalar(select(func.count()).select_from(model)) for model in PATH_TABLES]


def all_endpoints(client):
    return [client.get(f"{URL}/categories").status_code, client.get(f"{URL}/categories/housing").status_code,
            evaluate(client, {"age": 25}).status_code]


def write_seed(tmp_path, db, monkeypatch, extra=()):
    """픽스처 정책과 같은 구조의 임시 시드. seed_from_file 형식과 같다."""
    from app.services import quick_finder_service
    item = lambda sid, common, paths, common_checks=(): {
        "serv_id": sid, "status": "reviewed", "source_sha256": db.get(PolicyEligibility, sid).source_sha256,
        "common": [{}] * common, "common_checks": list(common_checks),
        "paths": [{"id": key, "conditions": [{}] * n, "checks": list(c)} for key, n, c in paths]}
    policies = [item("house", 2, [("a", 1, ["임대차 계약서 확인"]), ("b", 3, [])]),
                item("house-target", 0, [("v", 1, []), ("x", 1, [])]),
                item("job", 0, [("j", 1, [])]), *extra]
    seed = tmp_path / "eligibility_paths.json"
    seed.write_text(json.dumps({"version": 2, "policies": policies}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(quick_finder_service, "SEED_PATH", seed)


def test_empty_path_tables_return_503_without_auto_seeding(setup, monkeypatch):  # noqa: F811
    client, db = setup  # 정책 원문만 있고 경로 테이블은 비어 있다.
    monkeypatch.setattr(settings, "use_eligibility_paths", True)
    before = stored_rows(db)
    assert all_endpoints(client) == [503, 503, 503]
    db.expire_all()
    # 엔진 load()가 시드를 자동 적재했다면 행이 생겼을 것이다.
    assert path_rows(db) == [0, 0, 0] and stored_rows(db) == before


def test_complete_load_matching_seed_keeps_results(quick, tmp_path, monkeypatch):
    client, db = quick
    write_seed(tmp_path, db, monkeypatch)
    assert all_endpoints(client) == [200, 200, 200]
    assert results(evaluate(client, {"age": 25}))["house"]["status"] == "eligible"


@pytest.mark.parametrize("break_db", ["missing_record", "missing_condition", "missing_path", "missing_check",
                                      "missing_common", "not_reviewed"])
def test_partial_load_returns_503_and_does_not_change_db(quick, tmp_path, monkeypatch, break_db):
    client, db = quick
    extra = ()
    if break_db == "missing_record":  # 시드에 있고 원문도 있는데 경로 기록이 없다.
        db.add(WelfareService(serv_id="seed-only", serv_name="합성 seed-only", detail_url="", target_details="원문"))
        db.commit()
        extra = [{"serv_id": "seed-only", "status": "reviewed", "source_sha256": "0" * 64, "common": [],
                  "paths": [{"id": "p", "conditions": [{}]}]}]
    write_seed(tmp_path, db, monkeypatch, extra)
    record = db.get(PolicyEligibility, "house")
    path = next(p for p in record.paths if p.path_key == "b")
    if break_db == "missing_condition":
        path.conditions.pop()
    if break_db == "missing_path":
        record.paths.remove(path)
    if break_db == "missing_check":
        next(p for p in record.paths if p.path_key == "a").checks = []
    if break_db == "missing_common":
        record.paths.remove(next(p for p in record.paths if p.path_key == "_common"))
    if break_db == "not_reviewed":
        record.status = "draft"
    db.commit()
    before = (path_rows(db), stored_rows(db))
    assert all_endpoints(client) == [503, 503, 503]
    db.expire_all()
    assert (path_rows(db), stored_rows(db)) == before


def test_other_seed_version_is_not_compared_by_count(quick, tmp_path, monkeypatch):
    client, db = quick
    write_seed(tmp_path, db, monkeypatch)
    from app.services import quick_finder_service
    seed = json.loads(quick_finder_service.SEED_PATH.read_text(encoding="utf-8"))
    seed["policies"][0]["source_sha256"] = "f" * 64  # 다른 원문 버전의 시드: 개수 차이는 부분 적재로 보지 않는다.
    seed["policies"][0]["common"] = []
    quick_finder_service.SEED_PATH.write_text(json.dumps(seed), encoding="utf-8")
    assert all_endpoints(client) == [200, 200, 200]
