"""Public policy fixtures and explicitly synthetic safety regressions."""
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.services.eligibility_condition_service import EligibilityConditionService as Parser
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher


def policy(name):
    data = json.loads((Path(__file__).parent / "fixtures/eligibility_policy_excerpts.json").read_text(encoding="utf-8"))
    return next(row for row in data["policies"] if row["serv_name"] == name)


def analyze(text, profile=None):
    # Synthetic input unless called with the public fixture's source text.
    service = WelfareService(serv_id="synthetic", serv_name="Synthetic", detail_url="")
    user = User(age=25, region="서울특별시 관악구", income_level=0, employment_status="UNEMPLOYED")
    rows = [WelfareEligibilityCondition(serv_id=service.serv_id, **c) for c in Parser.parse_text(text, "selection_criteria")]
    return Matcher().analyze_service(user, service, rows, profile)


@pytest.mark.parametrize("punctuation", [".", "。", "!!!", "() · ;"])
def test_punctuation_only_residual_is_not_a_condition(punctuation):
    assert Parser._unrecognized_residual(punctuation, []) == ""


def test_actual_reference_notice_keeps_note_without_phantom_review():
    source = policy("장애인자립자금대여")["selection_criteria"]
    rows = Parser.parse_text(source, "selection_criteria")
    assert [r["condition_type"] for r in rows] == ["informational"]
    assert rows[0]["source_text"] == source


@pytest.mark.parametrize(("source", "field", "value"), [
    ("여성을 지원합니다.", "gender", "FEMALE"),
    ("등록 장애인을 지원합니다.", "disability_status", "YES"),
    ("재학생을 지원합니다.", "student_status", "YES"),
    ("재학생은 지원 대상에서 제외합니다.", "student_status", "NO"),
])
def test_synthetic_single_profile_fact_keeps_direction_and_compares(source, field, value):
    result = analyze(source, {field: value})
    assert result["evaluated_conditions"] == result["passed_conditions"] == 1
    assert result["status"] == "eligible"
    assert result["review_conditions"] == []
    assert result["confirmed_conditions"][0]["source_text"] == source


@pytest.mark.parametrize("value", [None, "", "UNKNOWN", False, 0])
def test_profile_unknown_or_wrong_type_does_not_pass(value):
    result = analyze("등록 장애인을 지원합니다.", {"disability_status": value})
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0


@pytest.mark.parametrize(("source", "profile"), [
    ("여성을 지원합니다.", {"gender": "MALE"}),
    ("등록 장애인을 지원합니다.", {"disability_status": "NO"}),
    ("재학생을 지원합니다.", {"student_status": "NO"}),
])
def test_clear_personal_fact_mismatch_is_a_gap(source, profile):
    result = analyze(source, profile)
    assert result["status"] == "ineligible"
    assert len(result["gap_conditions"]) == 1
    assert result["review_conditions"] == []
    assert result["match_score"] == 0


@pytest.mark.parametrize("source", [
    "여성을 지원합니다.",
    "실업급여 수급액을 소득에 포함합니다.",
    "주민등록상 1인 가구를 지원합니다.",
])
def test_missing_profile_or_non_requirement_keyword_is_not_a_pass(source):
    result = analyze(source)
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0
    assert result["gap_conditions"] == []


def test_explicit_student_exclusion_failure_and_policy_b_with_residual():
    result = analyze("재학생은 지원 대상에서 제외합니다.", {"student_status": "YES"})
    assert result["status"] == "ineligible"
    assert len(result["gap_conditions"]) == 1
    result = analyze("재학생은 지원 대상에서 제외합니다.\n기관별 추가 심사가 필요합니다.", {"student_status": "YES"})
    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == len(result["review_conditions"]) == 1
    assert result["match_score"] == 0


@pytest.mark.parametrize("source", [
    "여성 또는 등록 장애인을 지원합니다.",
    "재학생 중 일부를 지원합니다.",
    "등록 장애인이 아닌 경우도 지원할 수 있습니다.",
    "다만 재학생을 지원합니다.",
])
def test_synthetic_ambiguous_facts_stay_review(source):
    result = analyze(source, {"gender": "FEMALE", "disability_status": "YES", "student_status": "YES"})
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0
    assert result["gap_conditions"] == []


@pytest.mark.parametrize("separator", ["\n", "\n또는\n"])
def test_separate_profile_groups_are_not_assumed_to_be_required_together(separator):
    result = analyze("등록 장애인을 지원합니다." + separator + "재학생을 지원합니다.",
                     {"disability_status": "YES", "student_status": "NO"})
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0
    assert result["gap_conditions"] == []


def test_exception_in_income_footnote_prevents_embedded_fact_comparison():
    source = policy("장애인자립자금대여")["target_details"].splitlines()[0]
    source += " 다만 등록 장애인이 아닌 경우에도 참여 가능"
    rows = Parser.parse_text(source, "target_details")
    assert not any(r["comparison_ready"] for r in rows if r["condition_type"] == "target_group")


@pytest.mark.parametrize("heading", ["지원 제외 대상:", "우대 대상:"])
def test_personal_fact_under_scoped_heading_is_not_a_positive_requirement(heading):
    result = analyze(heading + "\n등록 장애인", {"disability_status": "NO"})
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0
    assert result["gap_conditions"] == []
    rows = Parser.parse_text(heading + "\n등록 장애인", "selection_criteria")
    expected_role = "preference" if heading.startswith("우대") else "exclusion"
    assert any(r["unit"] == expected_role for r in rows)


def test_actual_forest_preserves_exclusions_and_unresolved_or_but_separates_notices():
    data = policy("공공산림가꾸기")
    rows = Parser.structure_service(data["target_details"], data["selection_criteria"])
    notices = [r for r in rows if r["condition_type"] == "informational"]
    assert any(r["unit"] == "procedure" for r in notices)
    assert any(r["unit"] == "preference" for r in notices)
    conditional_skill = next(r for r in rows if "특별한 기술" in r["source_text"])
    assert conditional_skill["condition_type"] == "other"
    assert conditional_skill["parse_status"] == "manual_review"
    # The student field cannot identify the listed institution types. Preserve
    # the negative heading's scope, but do not assume all students are excluded.
    student = next(r for r in rows if "재학생" in r["source_text"])
    assert student["unit"] == "exclusion"
    assert student["comparison_ready"] is False
    assert not any(r["comparison_ready"] for r in rows if r["condition_type"] == "employment")
    assert any("사업별 자격" in r["source_text"] and r["condition_type"] == "other" for r in rows)
    result = analyze(data["target_details"], {"student_status": "NO"})
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 1


def test_actual_loan_extracts_registered_disability_but_not_income_or_other_product():
    data = policy("장애인자립자금대여")
    rows = Parser.structure_service(data["target_details"], data["selection_criteria"])
    facts = [r for r in rows if r["condition_type"] == "target_group" and r["comparison_ready"]]
    assert [(r["unit"], r["value_text"]) for r in facts] == [("disability_status", "YES")]
    assert not any(r["comparison_ready"] for r in rows if r["condition_type"] == "income_ratio")
    other_product = [r for r in rows if "미소금융재단" in r["source_text"]]
    assert other_product and all(not r["comparison_ready"] for r in other_product)
    result = analyze(data["target_details"], {"disability_status": "YES"})
    assert result["evaluated_conditions"] == result["passed_conditions"] == 2
    assert result["status"] == "needs_review"


def test_actual_disability_job_requires_unemployment_without_dropping_other_criteria():
    source = policy("장애인일자리지원")["target_details"]
    rows = Parser.parse_text(source, "target_details")
    employment = [r for r in rows if r["condition_type"] == "employment"]
    assert len(employment) == 1 and employment[0]["comparison_ready"]
    assert employment[0]["value_text"] == "UNEMPLOYED"
    assert employment[0]["source_text"] == source
    assert any(r["condition_type"] == "other" for r in rows)
    result = analyze(source)
    assert result["evaluated_conditions"] == result["passed_conditions"] == 2
    assert result["status"] == "needs_review"


def test_employment_exception_footnote_is_not_removed_for_comparison():
    source = policy("장애인일자리지원")["target_details"] + " 다만 재직자도 참여 가능"
    rows = Parser.parse_text(source, "target_details")
    assert not any(r["comparison_ready"] for r in rows if r["condition_type"] == "employment")


@pytest.mark.parametrize("source", ["미취업 청년을 지원합니다.", "실업자를 지원합니다.", "중소기업 재직 청년을 지원합니다."])
def test_synthetic_clear_employment_wording_is_normalized(source):
    rows = Parser.parse_text(source, "selection_criteria")
    assert any(r["condition_type"] == "employment" and r["comparison_ready"] for r in rows)
    assert not any(r["condition_type"] == "other" for r in rows)


def test_clear_region_suffix_is_supported_but_address_proof_is_not():
    assert analyze("서울시에 거주하는 청년을 지원합니다.")["status"] == "eligible"
    for source in ["서울시에 주민등록을 둔 청년을 지원합니다.", "서울시에 3년 이상 거주한 청년을 지원합니다."]:
        result = analyze(source)
        assert result["status"] == "needs_review"
        assert result["evaluated_conditions"] == 0


def test_runtime_reparsing_uses_raw_policy_without_replacing_stored_conditions():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.add(WelfareService(serv_id="live", serv_name="Synthetic", target_details="", selection_criteria="등록 장애인을 지원합니다."))
            db.flush()
            db.add(WelfareEligibilityCondition(serv_id="live", condition_type="other", operator="unknown", value_text="legacy", source_field="selection_criteria", source_text="legacy", comparison_ready=False, parse_status="manual_review", confidence=0))
            db.commit()
            user = User(age=25, region="서울특별시", income_level=0, employment_status="OTHER")
            result = Matcher().analyze_user(db, user, {"disability_status": "YES"})
            assert result["analysis_results"][0]["evaluated_conditions"] == 1
            assert result["policies"][0]["policy_id"] == "live"
            assert db.query(WelfareEligibilityCondition).one().value_text == "legacy"
            assert not db.new and not db.dirty and not db.deleted
            db.get(WelfareService, "live").selection_criteria = " "
            db.flush()
            fallback = Matcher().analyze_user(db, user, None)["analysis_results"][0]
            assert fallback["evaluated_conditions"] == 0
            assert fallback["review_conditions"][0]["required_value"] == "legacy"
    finally:
        engine.dispose()
