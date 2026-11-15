"""조건 안내는 판정이 아닌 설명이다. 합성 조건과 저장된 검수 원문을 구분해 검증한다."""

import json
from copy import deepcopy
from types import SimpleNamespace as N

import pytest

from app.schemas.welfare import EligibilityAnalysis, PathConditionResult
from app.services import eligibility_path_service as paths
from app.services import structured_condition_service as base
from app.services.profile_privacy import hide_input_values


def condition(field, operator, value=None, upper=None, values=(), kind="requirement", unit=""):
    return {"field": field, "operator": operator, "value": value, "upper_value": upper,
            "values": list(values), "kind": kind, "unit": unit, "or_group": ""}


def guide(c, current):
    return base.condition_guide(c, current, base.matches(c, current))


@pytest.mark.parametrize("c,current,code,text", [
    (condition("만 나이", "gte", 26, unit="세"), 25, "age_below_minimum", "만 26세 이상"),
    (condition("만 나이", "lte", 25, unit="세"), 26, "age_above_maximum", "나이 증가"),
    (condition("만 나이", "between", 19, 34, unit="세"), 18, "age_below_minimum", "만 19세 이상 34세 이하"),
    (condition("만 나이", "between", 19, 34, unit="세"), 35, "age_above_maximum", "상한"),
    (condition("본인 월소득", "lte", 2_500_000, unit="원"), 3_000_000, "requirement_not_met", "2,500,000원 이하"),
    (condition("본인 연소득", "lte", 42_999_999, unit="원"), 43_000_000, "requirement_not_met", "42,999,999원 이하"),
    (condition("가구 월소득 중위소득 대비", "lte", 100, unit="%"), 120, "requirement_not_met", "기준 중위소득 100% 이하"),
    (condition("가구 소득인정액", "lte", 50, unit="%"), 60, "requirement_not_met", "가구 소득인정액"),
    (condition("거주지", "one_of", values=["부산광역시"]), "서울특별시", "requirement_not_met", "부산광역시로 변경되면"),
    (condition("고용 상태", "one_of", values=["재직"]), "미취업", "requirement_not_met", "재직"),
    (condition("학교 구분", "one_of", values=["대학", "대학원"]), "고등학교", "requirement_not_met", "대학 또는 대학원"),
    (condition("재학 여부", "is_true"), False, "requirement_not_met", "재학"),
    (condition("등록 장애인", "is_true"), False, "requirement_not_met", "등록 장애인"),
])
def test_synthetic_requirement_guides(c, current, code, text):
    result = guide(c, current)
    assert result["reason_code"] == code
    assert text in result["condition_guide"]


@pytest.mark.parametrize("operator,lower,upper,cases", [
    ("gte", 26, None, [(25, False), (26, True), (27, True)]),
    ("lte", 25, None, [(24, True), (25, True), (26, False)]),
    ("between", 19, 34, [(18, False), (19, True), (34, True), (35, False)]),
])
def test_synthetic_age_boundaries_keep_comparison_direction(operator, lower, upper, cases):
    c = condition("만 나이", operator, lower, upper, unit="세")
    for age, passed in cases:
        assert base.matches(c, age) is passed
        result = guide(c, age)
        assert result["reason_code"] == ("condition_met" if passed else
                                           "age_above_maximum" if operator == "lte" or age > (upper or age)
                                           else "age_below_minimum")


@pytest.mark.parametrize("value,expected", [(2_699_998, True), (2_699_999, True), (2_700_000, False)])
def test_actual_durunuri_threshold_excerpt_is_not_rounded(value, expected):
    # WLF00000095 검수본: 270만원 미만을 원 단위 lte로 저장한 값이다.
    c = condition("본인 월소득", "lte", 2_699_999, unit="원")
    assert base.matches(c, value) is expected
    assert "2,699,999원" in base.describe(c)
    assert "2,699,999원 이하" in guide(c, value)["condition_guide"]


def test_synthetic_one_of_preserves_every_option():
    options = ["재직", "중소기업 재직", "아르바이트", "미취업", "자영업", "프리랜서"]
    c = condition("고용 상태", "one_of", values=options)
    before = deepcopy(c)
    for option in options:
        assert option in guide(c, "기타")["condition_guide"]
        assert option in base.describe(c)
    assert c == before


@pytest.mark.parametrize("value,text", [(2_699_999.0, "2,699,999"), (99.999999, "99.999999"),
                                        (1.25e20, "125,000,000,000,000,000,000")])
def test_synthetic_number_format_does_not_round_or_drop_integer_zeroes(value, text):
    assert base._exact_number(value) == text


@pytest.mark.parametrize("c,hit,miss", [
    (condition("재학 여부", "is_true", kind="exclusion"), True, False),
    (condition("본인 명의 주택 보유", "is_true", kind="exclusion"), True, False),
    (condition("만 나이", "lte", 18, kind="exclusion", unit="세"), 18, 19),
    (condition("만 나이", "between", 19, 24, kind="exclusion", unit="세"), 22, 25),
    (condition("고용 상태", "one_of", values=["재직"], kind="exclusion"), "재직", "미취업"),
])
def test_synthetic_exclusion_guides_do_not_reverse_direction(c, hit, miss):
    assert base.matches(c, hit) is False and base.matches(c, miss) is True
    applied, clear = guide(c, hit), guide(c, miss)
    assert applied["reason_code"] == "exclusion_applies"
    assert clear["reason_code"] == "exclusion_not_applicable"
    assert "해당하면 제외" in applied["condition_guide"]
    assert "제외 기준에 해당하지" in clear["condition_guide"]


def test_synthetic_missing_and_imprecise_values_are_not_failures():
    c = condition("가구 총재산", "lte", 122_000_000, unit="원")
    assert base.matches(c, None) is None
    assert guide(c, None)["reason_code"] == "input_missing"
    assert base.matches(c, (100_000_000, 199_999_999)) is None
    result = guide(c, (100_000_000, 199_999_999))
    assert result["reason_code"] == "comparison_uncertain"
    assert "확정할 수 없습니다" in result["condition_guide"]
    assert "122,000,000원" in result["condition_guide"]


def test_synthetic_false_and_zero_are_real_values():
    assert guide(condition("재학 여부", "is_true"), False)["reason_code"] == "requirement_not_met"
    assert guide(condition("본인 월소득", "gte", 0, unit="원"), 0)["reason_code"] == "condition_met"


@pytest.mark.parametrize("c", [
    condition("나이", "regex", values=["unknown"]),
    condition("만 나이", "gte", None, unit="세"),
    condition("만 나이", "between", 34, 19, unit="세"),
    condition("고용 상태", "one_of", values=[]),
    condition("본인 월소득", "lte", float("inf"), unit="원"),
    condition("만 나이", "gte", 19, kind="unknown", unit="세"),
])
def test_synthetic_unsupported_structure_does_not_invent_an_explanation(c):
    before = deepcopy(c)
    assert base.condition_guide(c, None, None) == {"condition_guide": "", "reason_code": "unsupported_condition"}
    assert c == before


def test_previous_response_defaults_are_compatible():
    old = {"condition_type": "만 나이", "status": "failed", "current_value": "25세",
           "required_value": "만 나이 26세 이상", "evidence": "만 26세 이상"}
    result = PathConditionResult.model_validate(old)
    assert result.condition_guide == "" and result.reason_code is None
    assert all(result.model_dump()[key] == value for key, value in old.items())


def path_condition(c, evidence="합성 조건 원문"):
    return N(field=c["field"], operator=c["operator"], value=c["value"], upper_value=c["upper_value"],
             values=c["values"], kind=c["kind"], evidence=evidence)


def test_synthetic_all_failures_common_and_other_or_paths_keep_guides():
    common = N(conditions=[path_condition(condition("만 나이", "gte", 26))], checks=["공통 심사"])
    path = N(path_key="first", label="첫 경로", kind="기본", priority=None, checks=["경로 심사"], conditions=[
        path_condition(condition("고용 상태", "one_of", values=["재직"])),
        path_condition(condition("등록 장애인", "is_true")),
        path_condition(condition("학교 구분", "one_of", values=["대학"])),
    ])
    values = {"만 나이": 25, "고용 상태": "미취업", "등록 장애인": False, "학교 구분": "고등학교"}
    result = paths._evaluate_path(path, common, values)
    assert result["status"] == "ineligible" and len(result["conditions"]) == 4
    assert all(c["status"] == "failed" and c["condition_guide"] for c in result["conditions"])
    assert [c["common"] for c in result["conditions"]] == [True, False, False, False]
    assert result["checks"] == ["공통 심사", "경로 심사"]


def test_synthetic_partial_unknown_checks_and_empty_path_rules_are_unchanged():
    p = N(path_key="p", label="경로", kind="기본", priority=None, checks=["필수 기관 확인"], conditions=[
        path_condition(condition("만 나이", "gte", 19)), path_condition(condition("등록 장애인", "is_true"))])
    result = paths._evaluate_path(p, None, {"만 나이": 25})
    assert result["status"] == "eligible"
    assert result["conditions"][1]["reason_code"] == "input_missing"
    p.conditions = []
    assert paths._evaluate_path(p, None, {})["status"] == "needs_review"


def test_synthetic_every_or_path_keeps_its_own_conditions_and_guides():
    common = N(conditions=[path_condition(condition("만 나이", "gte", 19))], checks=["공통 확인"])
    def branch(key, employment):
        return N(path_key=key, label=key, kind="기본", priority=None, checks=[key + " 확인"],
                 conditions=[path_condition(condition("고용 상태", "one_of", values=[employment]))])
    values = {"만 나이": 25, "고용 상태": "재직"}
    results = [paths._evaluate_path(p, common, values) for p in (branch("재직 경로", "재직"), branch("미취업 경로", "미취업"))]
    assert [p["status"] for p in results] == ["eligible", "ineligible"]
    assert [r["common"] for r in results[0]["conditions"]] == [True, False]
    assert all(r["condition_guide"] for p in results for r in p["conditions"])
    assert "재직" in results[0]["conditions"][1]["condition_guide"]
    assert "미취업" in results[1]["conditions"][1]["condition_guide"]
    assert results[0]["checks"] == ["공통 확인", "재직 경로 확인"]
    assert results[1]["checks"] == ["공통 확인", "미취업 경로 확인"]


REVIEWED = json.loads((paths.SEED_PATH.parent / "eligibility_paths_reviewed.json").read_text(encoding="utf-8"))["policies"]
SOURCES = {s["serv_id"]: s for s in json.loads((paths.SEED_PATH.parent / "welfare-policies.json").read_text(encoding="utf-8"))["data"]["welfare_services"]}


def actual_analysis(policy, user=None, profile=None):
    """실제 저장 원문 및 검수 경로, 사용자 값은 합성 입력만 사용한다."""
    raw = SOURCES[policy["serv_id"]]
    service = N(serv_id=policy["serv_id"], serv_name=policy["name"], detail_url=raw.get("detail_url", ""),
                target_details=raw["target_details"], selection_criteria=raw["selection_criteria"])
    specs = [{"id": paths.COMMON_PATH, "label": "공통", "conditions": policy.get("common", []),
              "checks": policy.get("common_checks", [])}] + policy["paths"]
    rec = N(source_sha256=base.source_hash(service), drafted_by=policy.get("drafted_by", "claude"),
            preferences=policy.get("preferences", []), paths=[])
    for spec in specs:
        rec.paths.append(N(path_key=spec["id"], label=spec["label"], kind=spec.get("kind", "기본"),
                           priority=spec.get("priority"), checks=spec.get("checks", []), conditions=[
                               path_condition(condition(c["field"], c["op"], c.get("value"), c.get("upper"),
                                                        c.get("values", []), c.get("kind", "requirement")),
                                              c["evidence"]) for c in spec.get("conditions", [])]))
    user = user or N(age=25, region=None, income_level=None, employment_status=None)
    return paths.analyze(service, user, profile or {}, rec)


@pytest.mark.parametrize("policy", REVIEWED, ids=lambda p: p["serv_id"])
def test_actual_reviewed_policy_guides_preserve_evidence_and_api_fields(policy):
    before = deepcopy(policy)
    result = actual_analysis(policy)
    parsed = EligibilityAnalysis.model_validate(result).model_dump()
    for path in parsed["eligibility_paths"]:
        for row in path["conditions"]:
            assert row["condition_guide"] and row["reason_code"] != "unsupported_condition"
            assert row["evidence"]
            assert all(word not in row["condition_guide"] for word in ("퇴사하세요", "이사하세요", "소득을 줄이세요"))
    assert policy == before


def test_actual_durunuri_guides_and_masking_do_not_replicate_private_income():
    policy = next(p for p in REVIEWED if p["serv_id"] == "WLF00000095")
    result = actual_analysis(policy, N(age=25, region="개인 거주지", income_level=3_456_789, employment_status="EMPLOYED"))
    masked = hide_input_values(EligibilityAnalysis.model_validate(result).model_dump())
    rows = [c for p in masked["eligibility_paths"] for c in p["conditions"]]
    assert any("2,699,999원" in row["condition_guide"] for row in rows)
    for row in rows:
        assert row["current_value"] == "프로필 보호 중"
        assert "3456789" not in row["condition_guide"] and "3,456,789" not in row["condition_guide"]
        assert "개인 거주지" not in row["condition_guide"]


def test_actual_policy_summary_state_and_score_are_independent_of_guides(monkeypatch):
    policy = next(p for p in REVIEWED if p["serv_id"] == "WLF00000781")
    guided = actual_analysis(policy)
    monkeypatch.setattr(base, "condition_guide", lambda *_: {"condition_guide": "", "reason_code": None})
    plain = actual_analysis(policy)
    for key in ("status", "match_score", "evaluated_conditions", "passed_conditions", "matched_path_id", "blocked_by_common"):
        assert guided[key] == plain[key]
    for first, second in zip(guided["eligibility_paths"], plain["eligibility_paths"]):
        assert first["status"] == second["status"]
        assert [r["status"] for r in first["conditions"]] == [r["status"] for r in second["conditions"]]
