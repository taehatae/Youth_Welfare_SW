"""실제 정책 원문 + 합성 프로필을 격리 DB에서 재현한다. 운영 DB는 사용하지 않는다."""
import pytest

from app.core.config import settings
from app.models.account import Account
from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.schemas.welfare import EligibilityAnalysis
from app.services.eligibility_condition_service import EligibilityConditionService as Parser
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher
from app.services.profile_privacy import hide_input_values
from tests.test_account_flow import setup, signup
from tests.test_condition_guides import SOURCES

SERVICE_ID = "WLF00000781"


def actual_service():
    raw = SOURCES[SERVICE_ID]
    return WelfareService(serv_id=SERVICE_ID, serv_name=raw["serv_name"], detail_url=raw.get("detail_url", ""),
                          target_details=raw["target_details"], selection_criteria=raw["selection_criteria"])


def actual_conditions(service):
    return [WelfareEligibilityCondition(serv_id=service.serv_id, **dict(c)) for c in
            Parser.cached_structure_service(Parser.PARSER_RULESET_VERSION, service.target_details, service.selection_criteria)]


def test_actual_headline_is_verified_gender_comparison_not_a_free_text_target_check():
    service = actual_service()
    c = next(c for c in actual_conditions(service) if c.condition_type == "target_group" and c.unit == "gender")
    assert (c.operator, c.value_text, c.parse_status, c.comparison_ready) == ("equals", "FEMALE", "parsed", True)
    user = User(age=20, region="합성 지역", income_level=0, employment_status="UNEMPLOYED")
    assert Matcher._compare_profile_condition(user, c, {"gender": "MALE"}) is False
    assert Matcher._compare_profile_condition(user, c, {"gender": "FEMALE"}) is True
    assert Matcher._compare_profile_condition(user, c, {"gender": "UNKNOWN"}) is None


def test_actual_reported_counts_keep_policy_b_and_gain_gender_only_guidance(monkeypatch):
    service = actual_service()
    user = User(age=20, region="개인 상세 주소", income_level=0, employment_status="UNEMPLOYED")
    result = Matcher().analyze_service(user, service, actual_conditions(service), {"gender": "MALE"})
    assert (result["passed_conditions"], len(result["gap_conditions"]), len(result["review_conditions"])) == (2, 1, 9)
    assert result["status"] == "needs_review"  # 화면의 '신청 불가' 분류와 백엔드 Policy B는 별개다.
    assert result["match_score"] == 66.7 and result["eligibility_paths"] == []
    gap = result["gap_conditions"][0]
    assert gap.get("guide_kind") == "state_change"
    assert gap.get("reason_code") == "requirement_not_met"
    assert "성별" in gap["condition_guide"] and "여성" in gap["condition_guide"]
    assert "남성" not in gap["condition_guide"] and "개인 상세 주소" not in gap["condition_guide"]
    assert "다른 요건" in gap["condition_guide"]  # 취약계층·연령 전체를 성별 하나로 판단하지 않는다.
    public = EligibilityAnalysis.model_validate(hide_input_values(result)).model_dump()
    assert public["gap_conditions"][0]["condition_guide"] == gap["condition_guide"]
    assert public["gap_conditions"][0]["current_value"] == "프로필 보호 중"
    monkeypatch.setattr(Matcher, "_profile_condition_guidance", staticmethod(lambda *_: {}))
    original = Matcher().analyze_service(user, service, actual_conditions(service), {"gender": "MALE"})
    for key in ("status", "match_score", "passed_conditions", "evaluated_conditions", "recommendation_status", "recommendation_decision"):
        assert original[key] == result[key]
    for key in ("gap_conditions", "review_conditions", "confirmed_conditions"):
        assert [(c["condition_type"], c["status"], c["required_value"], c["source_text"]) for c in original[key]] == [
            (c["condition_type"], c["status"], c["required_value"], c["source_text"]) for c in result[key]]


@pytest.mark.parametrize("gender", [None, "UNKNOWN", "", False])
def test_actual_missing_gender_stays_review_and_does_not_invent_a_change(gender):
    service = actual_service()
    result = Matcher().analyze_service(User(age=20, region="합성", income_level=0, employment_status="UNEMPLOYED"),
                                       service, actual_conditions(service), {"gender": gender})
    assert result["gap_conditions"] == []
    assert not any(c.get("guide_kind") == "state_change" for c in result["review_conditions"])


@pytest.mark.parametrize("changes", [
    {"comparison_ready": False}, {"parse_status": "manual_review"}, {"value_text": "MALE"},
    {"source_text": "여성 또는 가족을 지원합니다."}, {"unit": "unknown"}, {"operator": "contains"},
])
def test_unverified_old_records_cannot_gain_a_guide(changes):
    service = actual_service()
    c = next(c for c in actual_conditions(service) if c.condition_type == "target_group" and c.unit == "gender")
    for name, value in changes.items():
        setattr(c, name, value)
    assert Matcher._profile_condition_guidance(c, {"gender": "MALE"}, False) == {}


def test_isolated_actual_policy_api_serializes_legacy_guide_without_paths(setup, monkeypatch):
    client, db = setup
    for flag in ("use_llm_judge", "use_structured_conditions", "use_eligibility_paths"):
        monkeypatch.setattr(settings, flag, False)
    service = actual_service()
    db.add(service)
    db.commit()
    account = signup(client)
    response = client.post("/api/v1/welfare/diagnose", json={
        "age": 20, "region": "개인 상세 주소", "income_level": 0, "employment_status": "UNEMPLOYED",
        "eligibility_conditions": {"gender": "MALE"}})
    assert response.status_code == 200
    state = response.json()
    analysis = next(a for a in state["current"]["analysis"]["matched"]["analysis_results"] if a["policy_id"] == SERVICE_ID)
    assert (analysis["passed_conditions"], len(analysis["gap_conditions"]), len(analysis["review_conditions"])) == (2, 1, 9)
    assert analysis["status"] == "needs_review" and analysis["match_score"] == 66.7
    gap = analysis["gap_conditions"][0]
    assert gap.get("guide_kind") == "state_change" and "성별" in gap["condition_guide"]
    assert gap.get("reason_code") == "requirement_not_met"
    assert gap["current_value"] == "프로필 보호 중" and analysis["eligibility_paths"] == []
    user_id = db.get(Account, account["account_id"]).profile_id
    matched = client.get("/api/v1/welfare/matched", params={"user_id": user_id})
    assert matched.status_code == 200
    again = next(a for a in matched.json()["analysis_results"] if a["policy_id"] == SERVICE_ID)
    assert again["gap_conditions"] == analysis["gap_conditions"]
    assert client.get("/api/v1/users/state").json() == state


@pytest.mark.parametrize("source,field,current", [
    ("등록 장애인 또는 보호자를 지원합니다.", "disability_status", "NO"),
    ("등록 장애인을 지원합니다.", "disability_status", "NO"),
    ("재학생은 지원 대상에서 제외합니다.", "student_status", "YES"),
])
def test_bounded_personal_fact_and_exclusion_keep_direction(source, field, current):
    service = WelfareService(serv_id="synthetic", serv_name="합성 정책", detail_url="")
    conditions = [WelfareEligibilityCondition(serv_id=service.serv_id, **c) for c in Parser.parse_text(source, "selection_criteria")]
    user = User(age=20, region="합성", income_level=0, employment_status="UNEMPLOYED")
    result = Matcher().analyze_service(user, service, conditions, {field: current})
    if "또는" in source:
        assert not any(c.get("guide_kind") for c in result["gap_conditions"])
    else:
        assert len(result["gap_conditions"]) == 1
        gap = result["gap_conditions"][0]
        assert gap.get("guide_kind") == "state_change"
        assert "재학하지 않는 상태" in gap["condition_guide"] if field == "student_status" else "등록 장애인" in gap["condition_guide"]
