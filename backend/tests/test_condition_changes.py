"""상태 변화 설명 테스트. 실제 검수 경로와 합성 사용자/조건을 구분한다."""
import json
from decimal import Decimal
from types import SimpleNamespace as N

import pytest

from app.schemas.welfare import EligibilityAnalysis, PathConditionResult
from app.services import structured_condition_service as base
from app.services.profile_privacy import hide_input_values
from tests.test_condition_guides import REVIEWED, actual_analysis, condition
from tests.test_account_flow import setup, signup


def explain(c, value):
    return base.condition_guide(c, value, base.matches(c, value))


@pytest.mark.parametrize("c,current,direction,target,difference", [
    (condition("만 나이", "gte", 26, unit="세"), 25, "increase", "26", "1"),
    (condition("만 나이", "lte", 25, unit="세"), 26, "decrease", "25", "1"),
    (condition("본인 월소득", "lte", 2_699_999, unit="원"), 3_000_000, "decrease", "2699999", "300001"),
    (condition("본인 월소득", "gte", 2_500_000, unit="원"), 0, "increase", "2500000", "2500000"),
    (condition("가구 월소득 중위소득 대비", "between", 50, 100, unit="%"), 120.1, "decrease", "100", "20.1"),
    (condition("가구 소득인정액", "between", 50, 100, unit="%"), 40.1, "increase", "50", "9.9"),
])
def test_synthetic_numeric_change_is_calculated_exactly_internally(c, current, direction, target, difference):
    assert base._numeric_change(c, current) == (direction, Decimal(target), Decimal(difference))


@pytest.mark.parametrize("c,current,parts,code", [
    (condition("만 나이", "gte", 26, unit="세"), 25, ["시간이 지나", "만 26세 이상"], "age_below_minimum"),
    (condition("만 나이", "lte", 25, unit="세"), 26, ["기준을 넘었", "시간이 지나도", "충족할 수 없습니다"], "age_above_maximum"),
    (condition("만 나이", "between", 18, 20, unit="세"), 17, ["시간이 지나", "만 18세 이상 20세 이하"], "age_below_minimum"),
    (condition("만 나이", "between", 18, 20, unit="세"), 21, ["기준을 넘었", "충족할 수 없습니다"], "age_above_maximum"),
    (condition("본인 월소득", "lte", 2_699_999, unit="원"), 3_000_000, ["본인 월소득이", "기준보다 높", "270만원 미만"], "requirement_not_met"),
    (condition("가구 소득인정액", "lte", 50, unit="%"), 70, ["가구 소득인정액이", "기준 중위소득 50% 이하", "기준보다 높"], "requirement_not_met"),
    (condition("거주지", "one_of", values=["부산광역시"]), "서울특별시", ["거주지가", "부산광역시로", "바뀌면"], "requirement_not_met"),
    (condition("고용 상태", "one_of", values=["재직", "중소기업 재직"]), "미취업", ["고용 상태가", "재직 또는 중소기업 재직으로", "바뀌면"], "requirement_not_met"),
    (condition("학교 구분", "one_of", values=["대학"]), "고등학교", ["학교 구분이", "대학으로", "바뀌면"], "requirement_not_met"),
    (condition("재학 여부", "is_true"), False, ["재학 중", "충족합니다"], "requirement_not_met"),
    (condition("재학 여부", "is_true", kind="exclusion"), True, ["재학하지 않는 상태", "제외됩니다"], "exclusion_applies"),
    (condition("만 나이", "lte", 18, kind="exclusion", unit="세"), 18, ["만 18세 초과", "제외 조건에 해당하지 않습니다"], "exclusion_applies"),
    (condition("본인 월소득", "gte", 2_500_000, kind="exclusion", unit="원"), 3_000_000, ["2,500,000원 미만", "제외 조건에 해당하지 않습니다"], "exclusion_applies"),
])
def test_synthetic_failed_condition_explains_cause_and_changed_state(c, current, parts, code):
    result = explain(c, current)
    assert result.get("guide_kind") == "state_change"
    assert result["reason_code"] == code
    assert all(part in result["condition_guide"] for part in parts)
    assert "조건" in result["condition_guide"]


@pytest.mark.parametrize("current", [18, 20])
def test_synthetic_age_boundaries_have_no_unnecessary_change_suggestion(current):
    result = explain(condition("만 나이", "between", 18, 20, unit="세"), current)
    assert result.get("guide_kind") is None


@pytest.mark.parametrize("c,current", [
    (condition("대상 집단", "one_of", values=["장애인이거나 가족이며 소득 심사를 거친 자"]), "일반"),
    (condition("고용 상태", "one_of", values=["정기소득이 없거나 기관이 인정하는 자"]), "재직"),
    (condition("거주지", "one_of", values=["부산광역시에 3년간 주민등록"]), "서울특별시"),
    (condition("학적 상태", "one_of", values=["졸업"]), "재학"),
    (condition("자유 텍스트", "is_true"), False),
])
def test_synthetic_unstructured_or_unavailable_semantics_do_not_get_fake_changes(c, current):
    result = explain(c, current)
    assert not result.get("condition_guide") and result.get("guide_kind") is None


def test_not_enrolled_is_not_a_verified_graduate():
    result = explain(condition("재학 여부", "is_true", kind="exclusion"), True)
    assert "졸업" not in result["condition_guide"]


def test_excluded_age_lower_bound_does_not_promise_that_time_reverses_age():
    result = explain(condition("만 나이", "gte", 19, unit="세", kind="exclusion"), 26)
    assert "만 19세 미만" in result["condition_guide"]
    assert "시간이 지나도 줄지 않는 값이라 이 제외 조건을 벗어날 수 없습니다" in result["condition_guide"]


def test_excluded_numeric_interval_preserves_both_strict_exit_alternatives():
    c = condition("본인 월소득", "between", 2_000_001, 2_699_999, kind="exclusion", unit="원")
    text = explain(c, 2_500_000)["condition_guide"]
    # 저장값(2,000,001·2,699,999)은 원문 표현(200만원 초과·270만원 미만)으로 되돌려 반대 구간을 안내한다.
    assert "본인 월소득 2,000,000원 이하 또는 본인 월소득 2,700,000원 이상" in text
    assert base.matches(c, 2_000_000) is True and base.matches(c, 2_700_000) is True
    assert base.matches(c, 2_000_001) is False and base.matches(c, 2_699_999) is False


def test_excluded_recognized_income_keeps_its_ratio_indicator_and_unit():
    c = condition("가구 소득인정액", "lte", 50, kind="exclusion", unit="%")
    text = explain(c, 40)["condition_guide"]
    assert "가구 소득인정액 기준 중위소득 50% 초과" in text
    assert "본인 월소득" not in text and "원" not in text


@pytest.mark.parametrize("value", [None, (100_000_000, 199_999_999)])
def test_missing_or_interval_only_values_do_not_generate_changes(value):
    result = explain(condition("가구 총재산", "lte", 122_000_000, unit="원"), value)
    assert result.get("guide_kind") is None
    assert result["reason_code"] in ("input_missing", "comparison_uncertain")


def test_private_input_and_exact_difference_never_enter_response_or_snapshot():
    c = condition("본인 월소득", "lte", 2_699_999, unit="원")
    result = explain(c, 3_456_789)
    assert base._numeric_change(c, 3_456_789)[2] == Decimal(756_790)
    response = PathConditionResult(condition_type=c["field"], status="failed", current_value="3,456,789원",
                                   required_value="2,699,999원 이하", **result).model_dump()
    public = json.dumps(hide_input_values(response), ensure_ascii=False)
    assert "2,699,999원" in public
    for secret in ("3,456,789", "3456789", "756,790", "756790"):
        assert secret not in public
    assert set(result) <= {"condition_guide", "reason_code", "guide_kind"}
    assert "프로필 보호 중" in public


def test_actual_durunuri_policy_uses_private_income_to_compute_public_change():
    policy = next(p for p in REVIEWED if p["serv_id"] == "WLF00000095")
    user = N(age=25, region="개인 상세 주소", income_level=3_456_789, employment_status="EMPLOYED")
    result = EligibilityAnalysis.model_validate(actual_analysis(policy, user)).model_dump()
    income_rows = [c for p in result["eligibility_paths"] for c in p["conditions"] if c["condition_type"] == "본인 월소득"]
    assert income_rows and all(c["status"] == "failed" and c.get("guide_kind") == "state_change" for c in income_rows)
    assert all("기준보다 높" in c["condition_guide"] and "270만원 미만" in c["condition_guide"] for c in income_rows)
    public = json.dumps(hide_input_values(result), ensure_ascii=False)
    assert "3,456,789" not in public and "756,790" not in public and "개인 상세 주소" not in public


def test_old_snapshot_default_does_not_claim_a_state_change():
    old = PathConditionResult(condition_type="나이", status="failed", current_value="보호", required_value="18~20세")
    assert old.guide_kind is None


def test_isolated_api_and_saved_snapshot_keep_changes_without_private_values(setup, monkeypatch):
    from app.core.config import settings
    from app.models.account import Account, AccountWorkspace
    from app.models.eligibility_path import COMMON_PATH, EligibilityPath, EligibilityPathCondition, PolicyEligibility
    from app.models.welfare_service import WelfareService

    client, db = setup
    monkeypatch.setattr(settings, "use_eligibility_paths", True)
    service = db.get(WelfareService, "unit-policy")
    record = PolicyEligibility(serv_id=service.serv_id, source_sha256=base.source_hash(service), status="reviewed", preferences=[])
    def c(field, op, value=None, values=()):
        return EligibilityPathCondition(field=field, operator=op, value=value, values=list(values),
                                        kind="requirement", evidence=field + " 합성 정책 근거")
    record.paths = [
        EligibilityPath(path_key=COMMON_PATH, label="공통", kind="공통", checks=[], conditions=[c("만 나이", "gte", 26)]),
        EligibilityPath(path_key="first", label="첫 경로", kind="기본", checks=["공식 심사"], conditions=[
            c("본인 월소득", "lte", 2_699_999), c("거주지", "one_of", values=["부산광역시"]),
            c("고용 상태", "one_of", values=["재직"])]),
        EligibilityPath(path_key="second", label="다른 경로", kind="기본", checks=[], conditions=[c("등록 장애인", "is_true")]),
    ]
    db.add(record)
    db.commit()  # setup이 제공하는 격리 메모리 DB에만 쓴다.
    account = signup(client)
    response = client.post("/api/v1/welfare/diagnose", json={
        "age": 25, "region": "서울특별시 관악구", "income_level": 3_456_789,
        "employment_status": "UNEMPLOYED", "eligibility_conditions": {"disability_status": "NO"}})
    assert response.status_code == 200
    public = response.json()
    account_row = db.get(Account, account["account_id"])
    matched = client.get("/api/v1/welfare/matched", params={"user_id": account_row.profile_id})
    assert matched.status_code == 200
    analysis = public["current"]["analysis"]["matched"]["analysis_results"][0]
    assert matched.json()["analysis_results"][0]["eligibility_paths"] == analysis["eligibility_paths"]
    assert len(analysis["eligibility_paths"]) == 2
    first = analysis["eligibility_paths"][0]
    assert len(first["conditions"]) == 4 and all(c["guide_kind"] == "state_change" for c in first["conditions"])
    assert first["conditions"][0]["common"] is True and first["checks"] == ["공식 심사"]
    stored = db.get(AccountWorkspace, account["account_id"]).state["current"]["analysis"]["matched"]["analysis_results"][0]
    for path in stored["eligibility_paths"]:
        for row in path["conditions"]:
            assert row["guide_kind"] == "state_change"
            for secret in ("3,456,789", "3456789", "756,790", "756790", "서울특별시 관악구"):
                assert secret not in row["condition_guide"]
    assert client.get("/api/v1/users/state").json() == public
    for payload in (public, matched.json()):
        text = json.dumps(payload, ensure_ascii=False)
        for secret in ("3,456,789", "3456789", "756,790", "756790", "서울특별시 관악구"):
            assert secret not in text
