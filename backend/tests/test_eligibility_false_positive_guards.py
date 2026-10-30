"""Public DB excerpts (2026-10-30); profiles/counterexamples are synthetic.

No production DB, account state, API client or network is used by these tests.
"""
import pytest

from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition as Condition
from app.schemas.welfare import EligibilityAnalysis
from app.services.eligibility_condition_service import EligibilityConditionService as Parser
from app.services.eligibility_matching_service import EligibilityMatchingService as Matcher


# WLF00006286, selection_criteria: a ranking table, not eligibility ages.
SCORE = "1. 연령(30점) : 청년 30점(34세 이하), 비청년 20점(35세), 19점(36세) … 1점(54세 이상)"
# WLF00000047, target_details: program age and medical-cost component age.
MEDICAL = (
    "주민등록상 사업지역(19개 시군구)에 거주하는 30세 이상 고혈압·당뇨병 환자를 대상으로 합니다. "
    "※ 의료비(진료비 및 약제비) 지원 대상 : 65세 이상 고혈압, 당뇨병 환자"
)
# WLF00003199, target_details: the first excluded category in an explicit list.
ART_EXCLUSION = (
    "만 19세 미만, 격년제 예술활동준비금 지원사업 운영에 따른 전년도 사업 수혜 예술인, "
    "당해연도 우리 재단 <예술인 파견 지원사업-예술로>, "
    "<청년예술인 예술활동 적립계좌> 참여 예술인 등은 참여가 불가합니다. * 사업 공고문 참조"
)
# WLF00000025, target_details.
DISABILITY_JOB = (
    "18세 이상 「장애인복지법」상 등록된 미취업 장애인을 대상으로 합니다."
    "* 일자리 지원 주요직무 : 행정도우미, 전담지원 행정도우미, 복지서비스 지원요원 등"
)


def parse(text, field="target_details"):
    return [Condition(serv_id="public-excerpt", **c) for c in Parser.parse_text(text, field)]


def analyze(text, age=25, profile=None, rows=None):
    user = User(age=age, region="서울특별시 관악구", income_level=0, employment_status="UNEMPLOYED")
    service = WelfareService(serv_id="public-excerpt", serv_name="Public excerpt", detail_url="", target_details=text)
    return Matcher().analyze_service(user, service, parse(text) if rows is None else rows, profile)


def legacy_age(source, age, operator="gte"):
    return Condition(serv_id="public-excerpt", condition_type="age", operator=operator,
                     value_text=f"{age}세 {'이상' if operator == 'gte' else '미만'}",
                     value_number=age, unit="세", source_field="target_details",
                     source_text=source, comparison_ready=True, parse_status="parsed")


@pytest.mark.parametrize("age", [19, 34, 35, 54, 60])
def test_actual_ranking_age_is_note_not_a_required_age(age):
    rows = parse(SCORE, "selection_criteria")
    assert not any(c.condition_type == "age" and c.comparison_ready for c in rows)
    assert any(c.condition_type == "informational" and c.source_text == SCORE for c in rows)
    result = analyze(SCORE, age, rows=rows)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0
    assert SCORE in result["notes"]
    assert result["status"] == "needs_review"


def test_legacy_ranking_age_is_not_automatically_compared():
    rows = [legacy_age(SCORE, 54)]
    result = analyze(SCORE, 25, rows=rows)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0
    assert SCORE in result["notes"]


def test_synthetic_ranking_notice_does_not_remove_other_required_age():
    # Synthetic combination of a real table and a separate required clause.
    text = "만 19세 이상\n" + SCORE
    result = analyze(text, 18)
    assert result["evaluated_conditions"] == 1
    assert len(result["gap_conditions"]) == 1
    assert result["gap_conditions"][0]["source_text"] == "만 19세 이상"


@pytest.mark.parametrize("age, gaps", [(29, 1), (30, 0), (64, 0), (65, 0)])
def test_actual_component_age_cannot_fail_whole_program(age, gaps):
    rows = parse(MEDICAL)
    component = next(c for c in rows if c.condition_type == "age" and c.value_number == 65)
    assert not component.comparison_ready
    assert component.parse_status == "manual_review"
    assert component.source_text == MEDICAL
    result = analyze(MEDICAL, age, rows=rows)
    assert result["evaluated_conditions"] == 1
    assert len(result["gap_conditions"]) == gaps
    assert any(c["condition_type"] == "age" for c in result["review_conditions"])
    assert result["status"] == "needs_review"
    assert result["match_score"] == (0 if gaps else 100)


def test_legacy_component_age_is_revalidated_without_changing_rows():
    rows = [legacy_age(MEDICAL, 30), legacy_age(MEDICAL, 65)]
    result = analyze(MEDICAL, 40, rows=rows)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == result["passed_conditions"] == 1
    assert len(result["review_conditions"]) == 1
    assert rows[1].comparison_ready is True  # No mutation of persisted objects.


@pytest.mark.parametrize("age, passed", [(18, False), (19, True), (20, True)])
def test_actual_art_exclusion_direction_and_policy_b(age, passed):
    result = analyze(ART_EXCLUSION, age)
    assert result["evaluated_conditions"] == 1
    assert result["passed_conditions"] == int(passed)
    assert len(result["gap_conditions"]) == int(not passed)
    assert result["review_conditions"]  # Other excluded categories are unknown.
    assert result["status"] == "needs_review"
    assert result["match_score"] == (100 if passed else 0)
    assert "제외" in (result["confirmed_conditions"] + result["gap_conditions"])[0]["message"]


def test_legacy_art_exclusion_is_inverted_only_with_exact_source_and_value():
    row = legacy_age(ART_EXCLUSION, 19, "lt")
    row.value_text = "만 19세 미만"
    result = analyze(ART_EXCLUSION, 25, rows=[row])
    assert result["passed_conditions"] == 1
    assert result["gap_conditions"] == []
    assert row.operator == "lt"


@pytest.mark.parametrize("source", [
    "만 19세 미만은 참여가 불가합니다. 다만 별도 심사를 통해 참여할 수 있습니다.",
    "만 19세 미만 또는 학생은 참여가 불가합니다.",
    "만 19세 미만 자녀를 둔 보호자는 참여가 불가합니다.",
    ART_EXCLUSION + " 다만 위원회가 인정하는 경우 참여할 수 있습니다.",
])
def test_synthetic_uncertain_age_exclusion_is_review_not_a_positive_requirement(source):
    result = analyze(source, 25)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0
    assert result["review_conditions"]


@pytest.mark.parametrize("value, expected", [("YES", "passed"), ("NO", "failed"), ("UNKNOWN", "needs_review"), (None, "needs_review")])
def test_actual_job_registered_disability_is_a_separate_required_fact(value, expected):
    result = analyze(DISABILITY_JOB, profile={"disability_status": value})
    facts = [c for c in result["confirmed_conditions"] + result["gap_conditions"] + result["review_conditions"]
             if c["condition_type"] == "target_group"]
    assert len(facts) == 1
    assert facts[0]["status"] == expected
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == (3 if value in {"YES", "NO"} else 2)


@pytest.mark.parametrize("source", [
    "18세 이상 등록장애인의 가족을 지원합니다.",
    "등록장애인 보호자를 지원합니다.",
    "등록장애인은 선발 시 우대합니다.",
    "등록장애인 또는 의사의 소견으로 인정된 사람을 지원합니다.",
    DISABILITY_JOB + "\n다만 장애 등록이 없어도 별도 인정 시 참여할 수 있습니다.",
])
def test_synthetic_family_preference_alternative_is_not_applicant_disability_failure(source):
    result = analyze(source, profile={"disability_status": "NO"})
    assert not any(c["condition_type"] == "target_group" for c in result["gap_conditions"])
    assert result["review_conditions"]


def test_synthetic_or_alternative_remains_review():
    result = analyze("만 19~24세 또는 만 25~34세", age=27)
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0
    assert result["gap_conditions"] == []


def test_api_shape_and_existing_gender_employment_policy_b_are_unchanged():
    result = analyze("여성을 지원합니다.\n추가 기관 심사가 필요합니다.", profile={"gender": "MALE"})
    assert result["status"] == "needs_review"
    assert len(result["gap_conditions"]) == 1
    assert result["review_conditions"]
    assert result["match_score"] == 0
    assert EligibilityAnalysis.model_validate(result).model_dump() == result
    assert "candidate" not in result


def test_legacy_ranking_does_not_make_a_separate_required_age_ambiguous():
    rows = [legacy_age("만 19세 이상", 19), legacy_age(SCORE, 54)]
    result = analyze("만 19세 이상\n" + SCORE, 18, rows=rows)
    assert result["evaluated_conditions"] == 1
    assert len(result["gap_conditions"]) == 1
    assert result["gap_conditions"][0]["source_text"] == "만 19세 이상"


def test_actual_child_age_is_not_compared_with_applicant_age():
    # WLF00005856 target_details. The synthetic applicant is 25, not the child.
    source = (
        "양육비 채권을 보유하고 있으나 양육비 채무자로부터 양육비를 지급받지 못하는 "
        "만 18세 이하 자녀를 양육하고 있는 양육비 채권자를 지원합니다."
    )
    result = analyze(source, 25)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0
    assert result["review_conditions"]


def test_synthetic_guardian_age_is_not_the_applicant_age():
    result = analyze("만 65세 이상 보호자의 자녀를 지원합니다.", 25)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0


def test_legacy_job_fact_with_separate_registration_alternative_stays_review():
    row = Condition(serv_id="public-excerpt", condition_type="target_group", operator="equals",
                    value_text="YES", unit="disability_status", source_field="target_details",
                    source_text=DISABILITY_JOB, comparison_ready=True, parse_status="parsed")
    source = DISABILITY_JOB + "\n다만 장애 등록이 없어도 별도 인정 시 참여할 수 있습니다."
    result = analyze(source, profile={"disability_status": "NO"}, rows=[row])
    assert result["gap_conditions"] == []
    assert result["review_conditions"]


def test_synthetic_exclusion_exception_in_separate_sentence_is_not_lost():
    source = "만 19세 미만은 참여가 불가합니다.\n다만 위원회가 인정하면 참여할 수 있습니다."
    row = legacy_age("만 19세 미만은 참여가 불가합니다.", 19, "lt")
    row.value_text = "만 19세 미만"
    result = analyze(source, 25, rows=[row])
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0
    assert result["review_conditions"]


@pytest.mark.parametrize("age", [18, 19])
def test_synthetic_unconditional_single_age_exclusion_boundary(age):
    result = analyze("만 19세 미만은 참여가 불가합니다.", age)
    assert result["evaluated_conditions"] == 1
    assert result["status"] == ("ineligible" if age < 19 else "eligible")


def test_synthetic_ranking_with_appended_requirement_is_not_discarded_as_note():
    source = SCORE + " 단, 만 19세 이상만 신청 가능합니다."
    result = analyze(source, 18)
    assert result["evaluated_conditions"] == 0
    assert result["review_conditions"]


@pytest.mark.parametrize("separator", [" ", "\n"])
def test_synthetic_dan_exception_outside_age_sentence_prevents_a_gap(separator):
    text = "만 19세 미만은 참여가 불가합니다." + separator + "단, 학교장이 추천하면 참여할 수 있습니다."
    result = analyze(text, 18)
    assert result["gap_conditions"] == []
    assert result["evaluated_conditions"] == 0


def test_synthetic_dan_exception_to_registered_job_stays_review_for_new_and_legacy_rows():
    text = DISABILITY_JOB + "\n단, 기관 추천자는 진단서만으로 신청할 수 있습니다."
    legacy = Condition(serv_id="public-excerpt", condition_type="target_group", operator="equals",
                       value_text="YES", unit="disability_status", source_field="target_details",
                       source_text=DISABILITY_JOB, comparison_ready=True, parse_status="parsed")
    for rows in [None, [legacy]]:
        result = analyze(text, profile={"disability_status": "NO"}, rows=rows)
        assert not any(c["condition_type"] == "target_group" for c in result["gap_conditions"])
        assert any(c["condition_type"] == "target_group" for c in result["review_conditions"])


def test_legacy_sentence_split_medical_keeps_program_age_comparable():
    first, second = MEDICAL.split(" ※ ")
    rows = [legacy_age(first, 30), legacy_age("※ " + second, 65)]
    result = analyze(MEDICAL, 29, rows=rows)
    assert result["evaluated_conditions"] == 1
    assert len(result["gap_conditions"]) == 1
    assert result["gap_conditions"][0]["source_text"] == first
    assert len(result["review_conditions"]) == 1


def test_legacy_ranking_without_number_keeps_separate_required_age_comparable():
    legacy_source = SCORE.split(". ", 1)[1]
    rows = [legacy_age("만 19세 이상", 19), legacy_age(legacy_source, 54)]
    for row in rows:
        row.source_field = "selection_criteria"
    result = analyze("", 18, rows=rows)
    assert result["evaluated_conditions"] == 1
    assert len(result["gap_conditions"]) == 1
    assert legacy_source in result["notes"]
