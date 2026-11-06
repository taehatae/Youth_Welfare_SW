"""검수를 마친 구조화 조건(data/structured_conditions.json)으로 진단 입력값과 정책 자격을 비교한다.

정책마다 '신청자 본인에게 반드시 적용되는 조건'만 입력값과 비교한다. 입력하지 않은 값은 판정하지 않고
추가 확인으로 남긴다. 원문이 검수 이후 바뀐 정책(해시 불일치)이나 시드에 없는 정책은 None을 돌려줘
기존 분석을 그대로 쓰게 한다.
"""
import hashlib
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.median_income_reference import median_income_amount
from app.services.urban_worker_income_reference import urban_worker_income_amount

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "structured_conditions.json"

EMPLOYMENT_LABELS = {
    "EMPLOYED": "재직", "EMPLOYED_SME": "중소기업 재직", "PART_TIME": "아르바이트", "UNEMPLOYED": "미취업",
    "SELF_EMPLOYED": "자영업", "FREELANCER": "프리랜서",
}
SPECIAL_TARGETS = {
    "국가유공자·보훈대상자": "VETERAN", "북한이탈주민": "NK_DEFECTOR",
    "결혼이민자·다문화가족": "MULTICULTURAL", "농업인·어업인": "FARMER",
}
BENEFIT_TYPES = {"생계급여 수급자": "LIVELIHOOD", "의료급여 수급자": "MEDICAL", "주거급여 수급자": "HOUSING",
                 "교육급여 수급자": "EDUCATION"}
HOUSING_LABELS = {"OWNED": "자가", "JEONSE": "전세", "MONTHLY": "월세", "FREE": "무상 거주", "OTHER": "기타"}
MARRIAGE_LABELS = {"SINGLE": "미혼", "MARRIED": "기혼", "DIVORCED": "이혼", "WIDOWED": "사별"}
# 예전 입력의 재산 구간(원). 금액을 모를 때 구간 전체가 기준 안/밖인지로만 판정한다.
ASSET_RANGES = {"UNDER_100M": (0, 99_999_999), "100M_200M": (100_000_000, 199_999_999),
                "200M_300M": (200_000_000, 299_999_999), "300M_500M": (300_000_000, 499_999_999),
                "OVER_500M": (500_000_000, None)}
# 기존 분석에서 가져와 추가 확인으로 보여줄 원문 조건. 나이는 시드가 대신하므로 뺀다.
LEGACY_REVIEW_TYPES = {"other", "target_group", "employment", "income_ratio", "income_amount", "region",
                       "external_review"}


@lru_cache(maxsize=1)
def load_policies() -> dict[str, dict]:
    if not SEED_PATH.exists():
        return {}
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return {policy["serv_id"]: policy for policy in data.get("policies", [])}


def source_hash(service) -> str:
    source = "\n".join(t for t in (service.target_details, service.selection_criteria) if t and t.strip())
    return hashlib.sha256(source.encode()).hexdigest()


def _yes_no(value) -> bool | None:
    return True if value in ("YES", True) else False if value in ("NO", False) else None


def user_values(user, profile: dict | None) -> dict[str, Any]:
    """조건 항목 이름 → 사용자 값. 입력하지 않았거나 알 수 없으면 None."""
    p = profile if isinstance(profile, dict) else {}
    extra = p.get("additional_conditions") if isinstance(p.get("additional_conditions"), dict) else {}
    monthly = user.income_level if user.income_level is not None else None
    employment = extra.get("employment_detail") or user.employment_status
    household_size = p.get("household_size")
    recognized = extra.get("recognized_household_income_won")
    median = median_income_amount(date.today().year, household_size) if household_size else None
    targets = extra.get("special_targets")
    nationality = extra.get("nationality")
    benefit = _yes_no(extra.get("basic_benefit_status"))
    benefit_types = extra.get("basic_benefit_types") if isinstance(extra.get("basic_benefit_types"), list) else []
    asset = extra.get("asset_amount_won")
    household_asset = int(asset) if asset not in (None, "") else ASSET_RANGES.get(p.get("asset_range"))
    own_asset = extra.get("personal_asset_amount_won")
    household_income = extra.get("household_monthly_income_won")
    urban = urban_worker_income_amount(date.today().year, household_size)
    owns_home = _yes_no(p.get("owns_home"))
    homeless = _yes_no(extra.get("household_homeless"))
    protected, ended = _yes_no(extra.get("child_welfare_protection_experience")), _yes_no(extra.get("protection_ended"))
    values = {
        "만 나이": user.age,
        "거주지": user.region or None,
        "성별": {"MALE": "남성", "FEMALE": "여성"}.get(p.get("gender")),
        "본인 월소득": monthly,
        "본인 연소득": monthly * 12 if monthly is not None else None,
        # 중위소득 비율은 가구 소득인정액과 가구원 수를 모두 입력했을 때만 계산한다.
        "가구 소득인정액": round(int(recognized) / median * 100, 1) if recognized not in (None, "") and median else None,
        "가구원 수": household_size,
        "자녀 수": p.get("children_count"),
        "고용 상태": EMPLOYMENT_LABELS.get(employment),
        "재학 여부": _yes_no(p.get("student_status")),
        "등록 장애인": _yes_no(p.get("disability_status")),
        "본인 명의 주택 보유": _yes_no(p.get("owns_home")),
        "국적": {"KOREAN": "대한민국", "FOREIGN": "외국인"}.get(nationality),
        "기초생활보장 수급자": _yes_no(extra.get("basic_benefit_status")),
        "차상위계층": _yes_no(extra.get("near_poverty_status")),
        "한부모가족": _yes_no(extra.get("single_parent_support_status")),
        "가구 총재산": household_asset,
        # 본인 명의 재산. 1인 가구면 가구 총재산과 같고, 가구원이 더 있는데 입력하지 않았으면 알 수 없다.
        "본인 총재산": int(own_asset) if own_asset not in (None, "") else household_asset if household_size == 1 else None,
        # 도시근로자 비율은 가구 월소득과 가구원 수를 모두 입력했을 때만 계산한다.
        "도시근로자 월평균소득 대비 가구소득": round(int(household_income) / urban * 100, 1)
        if household_income not in (None, "") and urban else None,
        "혼인 상태": MARRIAGE_LABELS.get(p.get("marital_status")),
        "주거 형태": HOUSING_LABELS.get(p.get("housing_type")),
        # 1인 가구면 부모와 따로 산다. 가구원이 더 있으면 배우자·자녀일 수도 있어 알 수 없다.
        "부모와 따로 거주": True if household_size == 1 else None,
        # 본인 명의 주택이 있으면 세대 전원 무주택일 수 없다.
        "세대원 전원 무주택": False if owns_home is True else homeless,
        "자립준비청년": False if protected is False or ended is False else True if protected and ended else None,
    }
    for field, code in BENEFIT_TYPES.items():
        # 수급자가 아니면 모든 급여에 해당하지 않고, 수급자라도 급여 종류를 고르지 않았으면 알 수 없다.
        values[field] = False if benefit is False else (code in benefit_types) if benefit and benefit_types else None
    for field, code in SPECIAL_TARGETS.items():
        values[field] = (code in targets) if isinstance(targets, list) else None
    return values


def matches(condition: dict, value: Any) -> bool | None:
    """조건을 충족하면 True, 충족하지 않으면 False, 값이 없으면 None."""
    if value is None:
        return None
    operator = condition["operator"]
    if isinstance(value, tuple):
        return _matches_range(condition, value)
    if operator == "is_true":
        hit = bool(value)
    elif operator == "one_of":
        # 거주지는 '서울특별시 성동구'처럼 시도만 적힌 기준도 있어 앞부분이 같으면 해당한다.
        hit = any(value == option or str(value).startswith(option + " ") for option in condition["values"])
    elif operator == "gte":
        hit = value >= condition["value"]
    elif operator == "lte":
        hit = value <= condition["value"]
    else:
        hit = condition["value"] <= value <= condition["upper_value"]
    return not hit if condition["kind"] == "exclusion" else hit


def _matches_range(condition: dict, value: tuple) -> bool | None:
    """값을 (최소, 최대) 구간으로만 아는 경우: 구간 전체가 기준 안이면 충족, 전체가 밖이면 미충족."""
    low, high = value
    lower = condition["value"] if condition["operator"] in ("gte", "between") else None
    upper = condition["upper_value"] if condition["operator"] == "between" else condition["value"]         if condition["operator"] == "lte" else None
    inside = (lower is None or low >= lower) and (upper is None or (high is not None and high <= upper))
    outside = (lower is not None and high is not None and high < lower) or (upper is not None and low > upper)
    hit = True if inside else False if outside else None
    if hit is None:
        return None
    return not hit if condition["kind"] == "exclusion" else hit


def describe(condition: dict) -> str:
    field, operator, unit = condition["field"], condition["operator"], condition["unit"]
    value, upper = condition["value"], condition["upper_value"]
    number = lambda x: f"{x / 10000:,.0f}만원" if unit == "원" else f"{x:g}{unit}"
    if field == "가구 소득인정액":
        number = lambda x: f"기준 중위소득 {x:g}%"
    if field == "도시근로자 월평균소득 대비 가구소득":
        number = lambda x: f"{x:g}%"
    if operator == "gte":
        return f"{field} {number(value)} 이상"
    if operator == "lte":
        return f"{field} {number(value)} 이하"
    if operator == "between":
        return f"{field} {number(value)} ~ {number(upper)}"
    if operator == "one_of":
        return f"{field}: {', '.join(condition['values'][:5])}{' 등' if len(condition['values']) > 5 else ''}"
    return f"{field} 해당자 제외" if condition["kind"] == "exclusion" else f"{field} 해당"


def show(field: str, value: Any) -> str:
    if value is None:
        return "미입력"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, tuple):
        low, high = value
        return f"{low / 10000:,.0f}만원 이상" if high is None else f"{low / 10000:,.0f}만~{(high + 1) / 10000:,.0f}만원 미만"
    if field in ("가구 총재산", "본인 총재산"):
        return f"{value / 10000:,.0f}만원"
    if field == "도시근로자 월평균소득 대비 가구소득":
        return f"{value:g}%"
    if field == "만 나이":
        return f"{value}세"
    if field in ("본인 월소득", "본인 연소득"):
        return f"{value / 10000:,.0f}만원"
    if field == "가구 소득인정액":
        return f"기준 중위소득 {value:g}%"
    if field in ("가구원 수", "자녀 수"):
        return f"{value}명"
    return str(value)


def _row(field: str, status: str, current: str, required: str, message: str, guide: str) -> dict:
    return {"condition_type": field, "status": status, "current_value": current, "required_value": required,
            "message": message, "action_guide": guide, "source_field": "structured", "source_text": required}


def analyze(service, user, profile: dict | None, legacy: dict | None = None) -> dict | None:
    policy = load_policies().get(service.serv_id)
    if policy is None or policy.get("source_sha256") != source_hash(service):
        return None
    values = user_values(user, profile)
    met, unmet, review = [], [], []
    units: dict[str, list[dict]] = {}
    for index, condition in enumerate(policy["conditions"]):
        units.setdefault(condition["or_group"] or f"#{index}", []).append(condition)
    for unit in units.values():
        results = [matches(c, values.get(c["field"])) for c in unit]
        # '또는' 묶음은 하나라도 충족하면 충족, 모두 충족하지 않으면 미충족, 그 밖에는 확인이 필요하다.
        result = True if True in results else False if all(r is False for r in results) else None
        fields = list(dict.fromkeys(c["field"] for c in unit))
        field = " 또는 ".join(fields)
        required = " 또는 ".join(describe(c) for c in unit)
        current = ", ".join(f"{f} {show(f, values.get(f))}" if len(fields) > 1 else show(f, values.get(f)) for f in fields)
        if result is True:
            met.append(_row(field, "passed", current, required, "입력한 정보로 조건을 충족합니다.", "별도 조치가 필요하지 않습니다."))
        elif result is False:
            unmet.append(_row(field, "failed", current, required, "입력한 정보로는 조건을 충족하지 않습니다.",
                              "입력 정보가 맞는지 확인하고, 다른 지원 정책을 살펴보세요."))
        else:
            review.append(_row(field, "needs_review", current, required, "입력하지 않은 정보라 비교하지 못했습니다.",
                               "관련 정보를 입력하고 다시 진단하거나 공식 안내에서 확인하세요."))
    # 입력값으로 비교할 수 없는 원문 조건은 기존 분석의 추가 확인 항목을 그대로 보여준다.
    for item in (legacy or {}).get("review_conditions", []):
        if item.get("condition_type") in LEGACY_REVIEW_TYPES:
            review.append({**item, "status": "needs_review"})
    evaluated = len(met) + len(unmet)
    if unmet:
        reason = f"입력한 정보로 비교한 조건 중 {len(unmet)}개를 충족하지 않습니다."
    elif met:
        reason = f"입력한 정보로 비교한 조건 {len(met)}개를 모두 충족합니다. 나머지 조건은 공식 안내에서 확인하세요."
    else:
        reason = "입력한 정보로 비교할 수 있는 조건이 없는 정책입니다. 공식 안내에서 세부 자격을 확인하세요."
    return {
        **(legacy or {}),
        "policy_id": service.serv_id,
        "title": service.serv_name,
        "status": "ineligible" if unmet else "eligible",
        "match_score": round(len(met) / evaluated * 100, 1) if evaluated else 0.0,
        "evaluated_conditions": evaluated,
        "passed_conditions": len(met),
        "gap_conditions": unmet,
        "review_conditions": review,
        "confirmed_conditions": met,
        "recommendation_status": "condition_mismatch" if unmet else "priority_recommendation" if met else "additional_review",
        "recommendation_reason": reason,
        "recommendation_uncertainty": None,
        "detail_url": service.detail_url,
    }
