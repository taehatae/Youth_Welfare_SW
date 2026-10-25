"""Public-source regressions; isolated synthetic counterexamples are labelled."""
import json
from pathlib import Path
from collections import Counter

import pytest

from app.models.user import User
from app.models.welfare_service import WelfareService
from app.models.welfare_eligibility_condition import WelfareEligibilityCondition
from app.services.eligibility_condition_service import EligibilityConditionService as P
from app.services.eligibility_matching_service import EligibilityMatchingService as M


def fixture():
    return json.loads((Path(__file__).parent / "fixtures/employment_region_public_excerpts.json").read_text(encoding="utf-8"))


def analyze(text, status="UNEMPLOYED", region="서울특별시 관악구"):
    user = User(age=25, region=region, income_level=0, employment_status=status)
    service = WelfareService(serv_id="synthetic", serv_name="Synthetic", detail_url="")
    rows = [WelfareEligibilityCondition(serv_id="synthetic", **r) for r in P.parse_text(text, "target_details")]
    return M().analyze_service(user, service, rows)


def test_public_snippets_cover_all_original_employment_and_region_rows():
    assert Counter(r["condition_type"] for r in fixture()["conditions"]) == {"employment": 60, "region": 37}


@pytest.mark.parametrize(("status", "decision"), [
    ("UNEMPLOYED", "passed"), ("EMPLOYED", "failed"), ("EMPLOYED_SME", "failed"),
    ("STUDENT", "needs_review"), ("OTHER", "needs_review"),
    ("SELF_EMPLOYED", "needs_review"), ("FREELANCER", "needs_review"),
])
def test_actual_excluded_employee_item_is_not_a_positive_employment_requirement(status, decision):
    source = next(c["target_details"] for c in fixture()["contexts"] if c["serv_name"].startswith("출소"))
    rows = P.parse_text(source, "target_details")
    excluded = [r for r in rows if r["condition_type"] == "employment" and r["unit"] == "employment_exclusion"]
    assert len(excluded) == 1
    assert excluded[0]["operator"] == "not_equals"
    assert excluded[0]["source_text"] in source
    assert excluded[0]["source_text"].splitlines()[-1].strip() == "취업자"
    result = analyze(source, status)
    decisions = result["confirmed_conditions"] + result["gap_conditions"] + result["review_conditions"]
    actual = [r for r in decisions if r["condition_type"] == "employment"]
    assert len(actual) == 1 and actual[0]["status"] == decision
    assert result["status"] == "needs_review"  # unresolved other qualifications, Policy B
    assert any("영세자영업자" in r["source_text"] for r in result["review_conditions"])


@pytest.mark.parametrize("source", [
    "취업자",  # synthetic standalone item has no exclusion scope
    "제외 대상:\n취업자 또는 사업자",
    "제외 대상:\n다만 예외 인정\n취업자",
    "제외 대상:\n지원 대상:\n취업자",
    "우대 대상:\n취업자",
])
def test_synthetic_uncertain_employee_scope_is_never_automatically_failed(source):
    result = analyze(source, "EMPLOYED")
    assert result["status"] == "needs_review"
    assert result["evaluated_conditions"] == 0
    assert not result["gap_conditions"]


@pytest.mark.parametrize(("status", "expected"), [
    ("EMPLOYED", "eligible"), ("EMPLOYED_SME", "eligible"),
    ("UNEMPLOYED", "ineligible"), ("STUDENT", "needs_review"),
    ("SELF_EMPLOYED", "needs_review"), ("FREELANCER", "needs_review"),
])
def test_synthetic_explicit_salaried_worker_requirement_includes_sme_subset(status, expected):
    assert analyze("재직 중인 근로자를 지원합니다.", status)["status"] == expected


def test_intervening_unknown_heading_cannot_leak_exclusion_scope():
    source = "제외 대상:\n프로그램 내용은 다음과 같습니다.\n취업자"
    result = analyze(source, "EMPLOYED")
    assert result["evaluated_conditions"] == 0
    assert not result["gap_conditions"]


def test_actual_pilot_area_and_workplace_alternatives_are_not_residence_matches():
    source = next(c["target_details"] for c in fixture()["contexts"] if c["serv_name"].startswith("한국형"))
    result = analyze(source, "EMPLOYED", "서울특별시 종로구")
    assert not any(c["condition_type"] in {"region", "employment"} for c in result["confirmed_conditions"])
    assert result["status"] == "needs_review"
    assert result["review_conditions"]


@pytest.mark.parametrize(("needle", "kind"), [
    ("도시근로자", "income_reference"),
    ("실업급여 수급자격", "benefit_entitlement"),
    ("근로자 10명 미만에 대한", "employer_workforce"),
])
def test_real_non_employment_keywords_are_preserved_as_review_not_job_status(needle, kind):
    source = next(r["source_text"] for r in fixture()["conditions"] if needle in r["source_text"])
    rows = P.parse_text(source, "selection_criteria")
    assert not any(r["condition_type"] == "employment" for r in rows)
    assert any(r["condition_type"] == "other" and r["unit"] == kind and r["source_text"] == source for r in rows)
    result = analyze(source)
    assert result["evaluated_conditions"] == 0
    assert result["status"] == "needs_review"


def test_real_household_definition_is_not_a_geographic_requirement():
    source = next(r["source_text"] for r in fixture()["conditions"] if "(청년가구)" in r["source_text"])
    rows = P.parse_text(source, "target_details")
    assert not any(r["condition_type"] == "region" for r in rows)
    assert any(r["condition_type"] == "other" and r["unit"] == "household_or_address" for r in rows)


@pytest.mark.parametrize(("source", "region", "expected"), [
    ("서울 거주자", "서울특별시 관악구", "eligible"),
    ("경기 거주자", "경기도 성남시", "eligible"),
    ("서울 거주자", "부산광역시 해운대구", "ineligible"),
    ("서울 거주자", "서울 관악구", "eligible"),
    ("서울 거주자", "UNKNOWN", "needs_review"),
])
def test_synthetic_exact_short_sido_residence_is_compared(source, region, expected):
    assert analyze(source, region=region)["status"] == expected


@pytest.mark.parametrize("source", [
    "서울에 주민등록을 둔 청년", "서울에서 3년 이상 거주자",
    "서울 소재 사업장 근로자", "서울 거주자 또는 경기 소재 근로자",
    "사업 수행 지역은 서울", "서울에 주소를 둔 보호자의 자녀",
])
def test_synthetic_region_scope_and_proof_are_not_inferred_from_region_string(source):
    result = analyze(source, region="서울특별시 관악구")
    assert not any(c["condition_type"] == "region" for c in result["confirmed_conditions"])
    assert result["status"] == "needs_review"


def test_all_real_region_clauses_remain_non_comparable_without_missing_scope_information():
    for row in fixture()["conditions"]:
        if row["condition_type"] == "region":
            assert P.normalize_simple_sido_requirement(row["source_text"]) is None


def test_real_employment_clauses_do_not_gain_unjustified_keyword_matches():
    for row in fixture()["conditions"]:
        if row["condition_type"] == "employment":
            expected = "UNEMPLOYED" if "등록된 미취업 장애인" in row["source_text"] else None
            assert P.normalize_simple_employment_requirement(row["source_text"]) == expected


def test_templates_are_immutable_and_invalidated_by_content_and_rule_version():
    P.cached_structure_service.cache_clear()
    try:
        first = P.cached_structure_service(P.PARSER_RULESET_VERSION, "서울 거주자", "")
        again = P.cached_structure_service(P.PARSER_RULESET_VERSION, "서울 거주자", "")
        assert first is again
        assert isinstance(first, tuple) and all(isinstance(row, tuple) for row in first)
        rows = [dict(row) for row in first]
        rows[0]["value_text"] = "modified"
        assert dict(first[0])["value_text"] != "modified"
        different = P.cached_structure_service(P.PARSER_RULESET_VERSION, "경기 거주자", "")
        assert different != first
        before = P.cached_structure_service.cache_info().misses
        P.cached_structure_service("another-rule-version", "서울 거주자", "")
        assert P.cached_structure_service.cache_info().misses == before + 1
        assert P.cached_structure_service.cache_info().maxsize == 256
    finally:
        P.cached_structure_service.cache_clear()


def test_cached_templates_do_not_cache_user_decisions():
    # Synthetic policies share immutable source templates, never user values.
    P.cached_structure_service.cache_clear()
    try:
        template = P.cached_structure_service(P.PARSER_RULESET_VERSION, "서울 거주자", "")
        service = WelfareService(serv_id="synthetic", serv_name="Synthetic", detail_url="")
        statuses = []
        for region in ["서울특별시", "경기도"]:
            rows = [WelfareEligibilityCondition(serv_id=service.serv_id, **dict(row)) for row in template]
            user = User(age=25, region=region, income_level=0, employment_status="OTHER")
            statuses.append(M().analyze_service(user, service, rows)["status"])
        assert statuses == ["eligible", "ineligible"]
    finally:
        P.cached_structure_service.cache_clear()


def test_full_requests_share_templates_but_react_to_user_and_source_changes():
    # Synthetic session: no disk database or network, and original text makes
    # loading obsolete saved condition rows unnecessary.
    service = WelfareService(serv_id="synthetic", serv_name="Synthetic", target_details="서울 거주자", selection_criteria="")

    class Query:
        def order_by(self, *_args):
            return self

        def all(self):
            return [service]

    class Session:
        def query(self, model):
            assert model is WelfareService, "Do not load all saved rows when every policy has original text"
            return Query()

    P.cached_structure_service.cache_clear()
    try:
        user = User(age=25, region="서울특별시", income_level=0, employment_status="OTHER")
        cold = M().analyze_user(Session(), user)
        assert M().analyze_user(Session(), user) == cold
        assert P.cached_structure_service.cache_info().hits >= 1
        user.region = "경기도"
        assert M().analyze_user(Session(), user)["analysis_results"][0]["status"] == "ineligible"
        service.target_details = "경기 거주자"
        assert M().analyze_user(Session(), user)["analysis_results"][0]["status"] == "eligible"
        assert cold["analysis_results"][0]["status"] == "eligible"
    finally:
        P.cached_structure_service.cache_clear()


def test_public_source_cache_evicts_old_entries_at_its_limit():
    P.cached_structure_service.cache_clear()
    try:
        for number in range(260):
            P.cached_structure_service(P.PARSER_RULESET_VERSION, f"synthetic text {number}", "")
        assert P.cached_structure_service.cache_info().currsize == 256
        misses = P.cached_structure_service.cache_info().misses
        P.cached_structure_service(P.PARSER_RULESET_VERSION, "synthetic text 0", "")
        assert P.cached_structure_service.cache_info().misses == misses + 1
    finally:
        P.cached_structure_service.cache_clear()
