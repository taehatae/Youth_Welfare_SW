from types import SimpleNamespace

from app.services import structured_condition_service as structured

SERVICE = SimpleNamespace(serv_id="WLF-TEST", serv_name="테스트 장애인 정책", detail_url="https://example.test",
                          target_details="18세 이상 등록 장애인", selection_criteria="")
USER = SimpleNamespace(age=24, region="서울특별시 관악구", income_level=2_150_000, employment_status="OTHER")
PROFILE = {"gender": "FEMALE", "disability_status": "NO", "student_status": "NO", "owns_home": False,
           "household_size": 1, "additional_conditions": {"employment_detail": "PART_TIME",
                                                          "basic_benefit_status": "NO"}}


def condition(field, operator, value=None, upper=None, values=(), kind="requirement", or_group="", unit=""):
    return {"field": field, "profile_key": "", "kind": kind, "operator": operator, "value": value,
            "upper_value": upper, "unit": unit, "values": list(values), "or_group": or_group}


def seed(monkeypatch, conditions, service=SERVICE):
    policy = {"serv_id": service.serv_id, "source_sha256": structured.source_hash(service), "conditions": conditions}
    monkeypatch.setattr(structured, "load_policies", lambda: {service.serv_id: policy})


def test_disability_requirement_fails_for_non_disabled_user(monkeypatch):
    seed(monkeypatch, [condition("만 나이", "gte", 18, unit="세"), condition("등록 장애인", "is_true")])
    result = structured.analyze(SERVICE, USER, PROFILE)
    assert result["status"] == "ineligible"
    assert result["passed_conditions"] == 1 and result["gap_conditions"][0]["condition_type"] == "등록 장애인"
    assert result["gap_conditions"][0]["current_value"] == "아니오"


def test_or_group_passes_when_any_member_matches(monkeypatch):
    seed(monkeypatch, [condition("기초생활보장 수급자", "is_true", or_group="대상1"),
                       condition("고용 상태", "one_of", values=["아르바이트"], or_group="대상1")])
    result = structured.analyze(SERVICE, USER, PROFILE)
    assert result["status"] == "eligible" and result["passed_conditions"] == 1


def test_unanswered_input_goes_to_review_not_failure(monkeypatch):
    seed(monkeypatch, [condition("차상위계층", "is_true"), condition("가구 소득인정액", "lte", 60, unit="%")])
    result = structured.analyze(SERVICE, USER, PROFILE)
    assert result["status"] == "eligible" and result["evaluated_conditions"] == 0
    assert [r["current_value"] for r in result["review_conditions"]] == ["미입력", "미입력"]


def test_exclusion_and_region_prefix(monkeypatch):
    seed(monkeypatch, [condition("본인 명의 주택 보유", "is_true", kind="exclusion"),
                       condition("거주지", "one_of", values=["서울특별시"])])
    result = structured.analyze(SERVICE, USER, PROFILE)
    assert result["status"] == "eligible" and result["passed_conditions"] == 2


def test_median_ratio_uses_household_income_and_size(monkeypatch):
    seed(monkeypatch, [condition("가구 소득인정액", "lte", 60, unit="%")])
    profile = {**PROFILE, "additional_conditions": {**PROFILE["additional_conditions"],
                                                    "recognized_household_income_won": 10_000_000}}
    assert structured.analyze(SERVICE, USER, profile)["status"] == "ineligible"


def test_changed_source_or_unknown_policy_falls_back(monkeypatch):
    seed(monkeypatch, [condition("등록 장애인", "is_true")])
    changed = SimpleNamespace(**{**vars(SERVICE), "target_details": "원문이 바뀜"})
    assert structured.analyze(changed, USER, PROFILE) is None
    other = SimpleNamespace(**{**vars(SERVICE), "serv_id": "WLF-OTHER"})
    assert structured.analyze(other, USER, PROFILE) is None


def test_seed_covers_every_policy_with_valid_fields():
    policies = structured.load_policies()
    assert len(policies) >= 95
    fields = set(structured.user_values(USER, PROFILE))
    for policy in policies.values():
        for c in policy["conditions"]:
            assert c["field"] in fields and c["operator"] in {"gte", "lte", "between", "one_of", "is_true"}


def test_benefit_types_asset_range_and_homeless(monkeypatch):
    seed(monkeypatch, [condition("생계급여 수급자", "is_true", or_group="대상1"),
                       condition("의료급여 수급자", "is_true", or_group="대상1"),
                       condition("가구 총재산", "lte", 122_000_000, unit="원"),
                       condition("세대원 전원 무주택", "is_true")])
    extra = {**PROFILE["additional_conditions"], "basic_benefit_status": "YES", "basic_benefit_types": ["MEDICAL"],
             "household_homeless": "YES"}
    # 재산 구간(1억~2억)이 기준(1.22억)에 걸치면 판정하지 않는다.
    result = structured.analyze(SERVICE, USER, {**PROFILE, "asset_range": "100M_200M", "additional_conditions": extra})
    assert result["passed_conditions"] == 2 and result["review_conditions"][0]["condition_type"] == "가구 총재산"
    result = structured.analyze(SERVICE, USER, {**PROFILE, "additional_conditions": {**extra, "asset_amount_won": 150_000_000}})
    assert result["gap_conditions"][0]["condition_type"] == "가구 총재산"
    # 수급자가 아니면 급여 종류와 상관없이 미충족, 본인 주택이 있으면 세대 무주택도 아니다.
    result = structured.analyze(SERVICE, USER, {**PROFILE, "owns_home": True, "asset_range": "UNDER_100M"})
    assert {r["condition_type"] for r in result["gap_conditions"]} == {"생계급여 수급자 또는 의료급여 수급자", "세대원 전원 무주택"}


def test_urban_worker_income_ratio(monkeypatch):
    seed(monkeypatch, [condition("도시근로자 월평균소득 대비 가구소득", "lte", 100, unit="%")])
    extra = {**PROFILE["additional_conditions"], "household_monthly_income_won": 4_000_000}
    assert structured.analyze(SERVICE, USER, {**PROFILE, "additional_conditions": extra})["status"] == "ineligible"


def test_personal_asset_falls_back_to_household_asset_only_for_one_person_household():
    user = SimpleNamespace(age=25, region=None, income_level=None, employment_status=None)
    values = lambda profile: structured.user_values(user, profile)["본인 총재산"]
    extra = {"asset_amount_won": 500_000_000}
    assert values({"household_size": 3, "additional_conditions": extra}) is None
    assert values({"household_size": 1, "additional_conditions": extra}) == 500_000_000
    assert values({"household_size": 3, "additional_conditions": {**extra, "personal_asset_amount_won": 30_000_000}}) == 30_000_000
