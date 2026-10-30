"""Phase 3-A: public age-target excerpts; profiles/counterexamples are synthetic.

No production DB, external API or network is used by these tests. Service age
boundaries below profile-registration age are tested only through the matcher.
"""
import json
from pathlib import Path

import pytest

from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
from app.services.eligibility_condition_service import EligibilityConditionService as Parser
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher


CASES = json.loads((Path(__file__).parent / "fixtures" /
    "recommendation_age_target_excerpts.json").read_text(encoding="utf-8"))["services"]


def analyze(text, selection="지원대상의 내용을 참고해주시기 바랍니다.", age=22, rows=None):
    service = WelfareService(serv_id="synthetic-not-a-known-id", serv_name="Synthetic",
                             detail_url="", target_details=text, selection_criteria=selection)
    user = User(age=age, region="서울특별시", income_level=0, employment_status="UNEMPLOYED")
    conditions = rows if rows is not None else [Condition(serv_id=service.serv_id, **item)
        for item in Parser.structure_service(text, selection)]
    return Matcher().analyze_service(user, service, conditions)


@pytest.mark.parametrize("case", CASES, ids=[case["service_id"] for case in CASES])
@pytest.mark.parametrize("age,expected", [(8, "excluded"), (9, "candidate"), (24, "candidate"), (25, "excluded")])
def test_public_complete_age_target_reuses_validated_age_comparison(case, age, expected):
    result = analyze(case["target_details"], case["selection_criteria"], age)
    assert result["recommendation_decision"] == expected
    assert result["evaluated_conditions"] == 1
    assert result["passed_conditions"] == int(expected == "candidate")
    assert len(result["gap_conditions"]) == int(expected == "excluded")
    # Existing Policy B and residual review are preserved.
    assert result["status"] == "needs_review"
    assert result["review_conditions"]
    assert result["match_score"] == (100 if expected == "candidate" else 0)
    evidence = next(e for e in result["decision_evidence"] if e["condition_type"] == "age")
    assert evidence["decision_usable"]
    assert evidence["semantics_verified"]
    assert evidence["input_fields"] == ["user.age"]
    assert (evidence["role"], evidence["subject"], evidence["scope"]) == ("requirement", "applicant", "program")
    assert evidence["source_text"] == case["target_details"]


@pytest.mark.parametrize("reference", [
    "지원대상을 참고", "지원대상의 내용을 참고", "지원대상 내용을 참고",
    "지원대상의 내용을 참고해주시기 바랍니다.", "지원대상 내용을 참고하세요.",
    "지원 대상을 참고해 주시기 바랍니다.",
])
def test_synthetic_complete_reference_notice_is_independent(reference):
    assert analyze("9~24세 청소년을 지원합니다.", reference)["recommendation_decision"] == "candidate"


@pytest.mark.parametrize("notice", [
    "신청 방법: 온라인 또는 방문 신청이 가능합니다.",
    "신청 안내: 2026년 기준 온라인 또는 방문 신청이 가능합니다.",
    "추가 서류 확인이 필요합니다.",
])
def test_synthetic_bounded_unrelated_notice_does_not_veto_verified_gate(notice):
    result = analyze("9~24세 청소년을 지원합니다.\n" + notice)
    assert result["recommendation_decision"] == "candidate"
    assert result["review_conditions"]
    assert result["gap_conditions"] == []
    assert result["passed_conditions"] == 1
    assert result["status"] == "needs_review"


@pytest.mark.parametrize("notice", [
    "지원대상의 내용을 참고하되 등록장애인만 신청할 수 있습니다.",
    "지원대상 내용을 참고하세요. 다만 해당 연령은 자녀의 나이입니다.",
    "신청 안내: 온라인 또는 등록장애인만 신청이 가능합니다.",
    "신청 안내: 2026년 기준 만 19세 이상이어야 합니다.",
    "지원대상 내용을 참고하세요.\n위 연령은 의료비 지원에만 적용합니다.",
])
def test_synthetic_reference_or_notice_with_eligibility_is_not_ignored(notice):
    result = analyze("9~24세 청소년을 지원합니다.", notice)
    assert result["recommendation_decision"] == "unverified"
    age = next(e for e in result["decision_evidence"] if e["condition_type"] == "age")
    assert not age["decision_usable"]
    assert "CONTEXT_OTHER_FIELD_UNVERIFIED" in age["reason_codes"]


@pytest.mark.parametrize("qualification", [
    "다만 만 25~34세도 신청할 수 있습니다.",
    "또는 기관의 별도 인정 대상자도 신청할 수 있습니다.",
    "위 연령은 자녀의 나이를 뜻합니다.",
    "위 연령은 세부 의료비 지원에만 적용합니다.",
    "위 조건은 선발 시 가점으로 적용합니다.",
    "장애인 등록 여부는 필수 자격이 아닙니다.",
    "졸업 시점의 연령을 기준으로 합니다.",
])
@pytest.mark.parametrize("age", [22, 25])
def test_synthetic_related_or_unknown_following_qualification_stays_unverified(qualification, age):
    result = analyze("9~24세 청소년을 지원합니다.\n" + qualification, age=age)
    assert result["recommendation_decision"] == "unverified"
    gate = next(e for e in result["decision_evidence"] if e["condition_type"] == "age")
    assert not gate["decision_usable"]


@pytest.mark.parametrize("text", [
    "9~24세 청소년을 지원합니다. 또는 만 25~34세인 경우 신청 가능합니다.",
    "9~24세의 자녀를 둔 보호자를 지원합니다.",
    "보호자 자격\n9~24세 청소년을 지원합니다.",
    "세부 의료비 지원 대상\n9~24세 청소년을 지원합니다.",
    "다른 상품 안내\n9~24세 청소년을 지원합니다.",
    "우대 기준\n9~24세 청소년을 지원합니다.",
    "보호 종료 당시 9~24세 청소년을 지원합니다.",
    "9~24세 청소년", "9~세 청소년을 지원합니다.",
    "24~9세 청소년을 지원합니다.", "24~9세인 청소년을 지원합니다.",
])
def test_synthetic_non_program_age_or_incomplete_source_cannot_certify(text):
    assert analyze(text)["recommendation_decision"] == "unverified"


@pytest.mark.parametrize("change", ["missing_number", "changed_number", "unsupported_operator"])
def test_synthetic_stale_or_incomplete_predicate_cannot_reuse_clear_source(change):
    source = "9~24세 청소년을 지원합니다."
    rows = [Condition(serv_id="synthetic", **c) for c in Parser.parse_text(source, "target_details")]
    age = next(c for c in rows if c.condition_type == "age")
    if change == "missing_number":
        age.value_number = None
    elif change == "changed_number":
        age.upper_value_number = 99
    else:
        age.operator = "unsupported"
    result = analyze(source, rows=rows)
    assert result["recommendation_decision"] == "unverified"
    evidence = next(e for e in result["decision_evidence"] if e["condition_type"] == "age")
    assert "SOURCE_PREDICATE_NOT_VERIFIED" in evidence["reason_codes"]


def test_synthetic_rule_does_not_depend_on_service_id_or_fixed_age_numbers():
    result = analyze("10~23세 청소년을 지원합니다.", age=22)
    assert result["recommendation_decision"] == "candidate"
    assert result["policy_id"] == "synthetic-not-a-known-id"
