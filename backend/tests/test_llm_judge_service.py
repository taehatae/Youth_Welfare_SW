from types import SimpleNamespace

from app.services import llm_judge_service as judge

SERVICE = SimpleNamespace(
    serv_id="WLF-TEST", serv_name="테스트 정책", detail_url="https://example.test",
    target_details="만 19세 이상 34세 이하 청년", selection_criteria="고교·대학 재학생은 제외",
)
USER = SimpleNamespace(age=24, region="서울특별시 관악구", income_level=600_000, employment_status="OTHER")
FIELDS = judge.profile_fields(USER, {"student_status": "YES", "additional_conditions": {
    "employment_detail": "PART_TIME", "nationality": "KOREAN", "special_targets": ["FARMER"]}})
AGE = {"evidence": "만 19세 이상 34세 이하 청년", "name": "나이", "category": "age",
       "requirement": "19~34세", "kind": "requirement", "applies_to": "applicant"}
STUDENT = {"evidence": "고교·대학 재학생은 제외", "name": "재학생 제외", "category": "education",
           "requirement": "재학생 제외", "kind": "exclusion", "applies_to": "applicant"}


def verdict(index, field, matches):
    return {"index": index, "profile_field": field, "reasoning": "", "matches": matches}


def test_judgment_maps_to_existing_analysis_shape_with_real_user_values():
    judgment = {"summary": "재학생이라 제외", "results": [
        verdict(0, "만 나이", "yes"), verdict(1, "현재 학생(고교·대학 재학 중)", "yes")]}
    result = judge.to_analysis(SERVICE, [AGE, STUDENT], judgment, FIELDS)
    assert result["status"] == "ineligible" and result["passed_conditions"] == 1
    assert result["confirmed_conditions"][0]["current_value"] == "24세"
    assert result["gap_conditions"][0]["current_value"] == "예"
    assert result["recommendation_reason"] == "재학생이라 제외"


def test_exclusion_not_matched_is_met():
    judgment = {"summary": "", "results": [verdict(0, "현재 학생(고교·대학 재학 중)", "no")]}
    result = judge.to_analysis(SERVICE, [STUDENT], judgment, FIELDS)
    assert result["status"] == "eligible" and result["passed_conditions"] == 1


def test_verdict_without_matching_profile_field_goes_to_review():
    judgment = {"summary": "", "results": [verdict(0, judge.NO_FIELD, "yes")]}
    result = judge.to_analysis(SERVICE, [AGE], judgment, FIELDS)
    assert result["status"] == "eligible" and not result["confirmed_conditions"] and result["review_conditions"]


def test_verdict_on_unanswered_field_goes_to_review():
    judgment = {"summary": "", "results": [verdict(0, "등록 장애인", "no")]}
    result = judge.to_analysis(SERVICE, [AGE], judgment, FIELDS)
    assert not result["gap_conditions"] and result["review_conditions"][0]["current_value"] == "미입력"


def test_conditions_for_other_people_are_skipped():
    other = AGE | {"applies_to": "other_person"}
    result = judge.to_analysis(SERVICE, [other], {"summary": "", "results": [verdict(0, "만 나이", "no")]}, FIELDS)
    assert result["status"] == "eligible" and not result["review_conditions"]


def test_failed_llm_call_is_reported_without_verdict():
    result = judge.to_analysis(SERVICE, [], None, FIELDS, "connection refused")
    assert result["status"] == "eligible" and result["evaluated_conditions"] == 0
    assert "실패" in result["recommendation_reason"]


def test_profile_fields_use_manwon_and_explicit_yes_no():
    assert FIELDS["본인 월평균 소득"] == "60만원 (연 환산 720만원)"
    assert FIELDS["고용 상태"] == "아르바이트" and FIELDS["국적"] == "대한민국 국민(내국인)"
    assert FIELDS["농업인·어업인"] == "예" and FIELDS["북한이탈주민"] == "아니오"
    assert FIELDS["등록 장애인"] == "미입력"
