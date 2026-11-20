"""검수를 마친 구조화 조건(data/structured_conditions.json)으로 진단 입력값과 정책 자격을 비교한다.

정책마다 '신청자 본인에게 반드시 적용되는 조건'만 입력값과 비교한다. 입력하지 않은 값은 판정하지 않고
추가 확인으로 남긴다. 원문이 검수 이후 바뀐 정책(해시 불일치)이나 시드에 없는 정책은 None을 돌려줘
기존 분석을 그대로 쓰게 한다.
"""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
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
    values.update(_extended_values(p, extra, values, household_size, median, monthly, household_asset))
    return values


SCHOOL_LABELS = {"HIGH": "고등학교", "COLLEGE": "대학", "GRADUATE": "대학원"}
MONEY_FIELDS = {"가구 총재산", "본인 총재산", "가구 순자산", "본인 순자산", "부부합산 연소득", "자동차가액"}


def _won(value) -> int | None:
    return int(value) if value not in (None, "") else None


def _extended_values(p: dict, extra: dict, values: dict, household_size, median, monthly, household_asset) -> dict:
    """여러 정책에서 자주 쓰는 기준을 비교할 수 있게 추가한 항목. 모르면 None(확인 필요)으로 둔다."""
    out: dict[str, Any] = {}
    married = values["혼인 상태"]
    # 가구 월소득을 중위소득으로 나눈 비율. '소득인정액'(재산 환산 포함)과 다른 '가구 소득' 기준에 쓴다.
    household_income = _won(extra.get("household_monthly_income_won"))
    out["가구 월소득 중위소득 대비"] = round(household_income / median * 100, 1) if household_income is not None and median else None
    # 본인 또는 가구 안에 기초생활보장 수급자가 있으면 '수급 가구'다.
    own, house = values["기초생활보장 수급자"], _yes_no(extra.get("household_basic_benefit_status"))
    out["기초생활보장 수급 가구"] = True if own or house else False if own is False and house is False else None
    out["구직 등록"] = _yes_no(extra.get("job_seek_registration"))
    # 학교 구분은 재학 중일 때만 의미가 있다.
    out["학교 구분"] = SCHOOL_LABELS.get(extra.get("school_level")) if values["재학 여부"] else None
    # 등록 장애인이 아니면 중증 장애인도 아니다.
    severe = _yes_no(extra.get("severe_disability"))
    out["중증 장애인"] = False if values["등록 장애인"] is False else severe
    # 자녀 나이는 막내 나이로 받는다. '6세 이하', '미성년' 등 자녀 나이 기준은 모두 막내 기준으로 판단할 수 있다.
    children = values["자녀 수"]
    youngest = extra.get("youngest_child_age")
    youngest = int(youngest) if children != 0 and youngest not in (None, "") else None
    out["막내 자녀 나이"] = youngest
    under7 = youngest <= 6 if youngest is not None else _yes_no(extra.get("has_child_under_7"))  # 예전 저장본은 예/아니오
    out["6세 이하 자녀"] = False if children == 0 else under7
    out["임신 중"] = _yes_no(extra.get("pregnancy"))
    # 배우자 소득: 기혼이면 입력값, 미혼·이혼·사별이면 0으로 본다.
    spouse = _won(extra.get("spouse_monthly_income_won"))
    if married in ("미혼", "이혼", "사별"):
        spouse = 0
    out["부부합산 연소득"] = (monthly + spouse) * 12 if monthly is not None and spouse is not None else None
    out["맞벌이"] = (monthly > 0 and spouse > 0) if married == "기혼" and monthly is not None and spouse is not None else (
        False if married in ("미혼", "이혼", "사별") else None)
    years = extra.get("marriage_years")
    out["혼인 기간"] = int(years) if married == "기혼" and years not in (None, "") else None
    # 순자산 = 재산 − 부채. 부채를 입력하지 않았으면 알 수 없다(재산 그대로 쓰면 빚이 있는 사람이 잘못 불가가 됨).
    debt, own_debt = _won(extra.get("household_debt_won")), _won(extra.get("personal_debt_won"))
    asset = household_asset if isinstance(household_asset, int) else None
    out["가구 순자산"] = asset - debt if asset is not None and debt is not None else None
    own_asset = values["본인 총재산"] if isinstance(values["본인 총재산"], int) else None
    if own_debt is None and household_size == 1:
        own_debt = debt
    out["본인 순자산"] = own_asset - own_debt if own_asset is not None and own_debt is not None else None
    out["자동차가액"] = _won(extra.get("car_value_won"))
    score, bureau = extra.get("credit_score"), extra.get("credit_bureau")
    out["신용점수(KCB)"] = int(score) if bureau == "KCB" and score not in (None, "") else None
    out["신용점수(NICE)"] = int(score) if bureau == "NICE" and score not in (None, "") else None
    return out


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
    number = lambda x: _won_text(x) if unit == "원" else f"{_exact_number(x)}{unit}"
    if field == "가구 소득인정액":
        number = lambda x: f"기준 중위소득 {_exact_number(x)}%"
    if field == "가구 월소득 중위소득 대비":
        number = lambda x: f"기준 중위소득 {_exact_number(x)}%"
    if field == "도시근로자 월평균소득 대비 가구소득":
        number = lambda x: f"{_exact_number(x)}%"
    if operator in ("gte", "lte", "between"):
        bounds = _bounds(condition)
        if bounds is None:
            return f"{field} {number(value)} {'이상' if operator == 'gte' else '이하'}" if operator != "between" \
                else f"{field} {number(value)} ~ {number(upper)}"
        if operator == "between" and [word for _, word in bounds] == ["이상", "이하"]:
            return f"{field} {number(bounds[0][0])} ~ {number(bounds[1][0])}"
        text = " ".join(f"{number(n)} {word}" for n, word in bounds)
        if text.count("기준 중위소득 ") > 1:  # 범위는 앞에만 붙인다
            head, _, rest = text.partition("기준 중위소득 ")
            text = head + "기준 중위소득 " + rest.replace("기준 중위소득 ", "")
        return f"{field} {text}"
    if operator == "one_of":
        return f"{field}: {', '.join(condition['values'])}"
    return f"{field} 해당자 제외" if condition["kind"] == "exclusion" else f"{field} 해당"


def _won_text(value) -> str:
    """만원 단위로 떨어지는 금액은 억·만원으로 읽기 쉽게 쓴다. 예: 122,000,000 → 1억 2,200만원."""
    amount = Decimal(str(value))
    if not amount or amount != amount.to_integral() or amount % 10000:
        return f"{_exact_number(amount)}원"
    eok, man = divmod(int(amount) // 10000, 10000)
    if not eok:
        return f"{man:,}만원"
    return f"{eok:,}억원" if not man else f"{eok:,}억 {man:,}만원"


def _exact_number(value: int | float) -> str:
    """정책 기준값은 반올림하거나 유효 숫자를 줄이지 않는다."""
    text = format(Decimal(str(value)), ",f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _bounds(c: dict) -> list[tuple[Decimal, str]] | None:
    """저장값을 원문 표현으로 되돌린다. '미만'은 원 단위에서 1을 빼고, '초과'는 %에서 0.1을 더해 저장했다.

    예: 270만원 미만 → lte 2,699,999 → (2,700,000, 미만), 중위소득 50% 초과 → gte 50.1 → (50, 초과).
    입력값도 같은 단위(원은 정수, %는 소수 첫째 자리)라 판정 의미는 같다.
    """
    op, unit = c.get("operator"), c.get("unit", "")
    try:
        lower = Decimal(str(c["value"])) if op in ("gte", "between") else None
        upper = Decimal(str(c["upper_value"] if op == "between" else c["value"])) if op in ("lte", "between") else None
    except (InvalidOperation, KeyError, TypeError):
        return None
    if any(n is not None and not n.is_finite() for n in (lower, upper)):
        return None
    out = []
    if lower is not None:
        if unit == "원" and lower == lower.to_integral() and lower % 10000 == 1:
            out.append((lower - 1, "초과"))
        elif unit == "%" and lower * 10 == (lower * 10).to_integral() and lower * 10 % 10 == 1:
            out.append((lower - Decimal("0.1"), "초과"))
        else:
            out.append((lower, "이상"))
    if upper is not None:
        if unit == "원" and upper == upper.to_integral() and (upper + 1) % 10000 == 0:
            out.append((upper + 1, "미만"))
        else:
            out.append((upper, "이하"))
    return out


_FINAL_DIGIT = {"0": 1, "1": 8, "2": 0, "3": 16, "4": 0, "5": 0, "6": 1, "7": 8, "8": 8, "9": 0}


def _josa(word: str, pair: str) -> str:
    """받침에 맞는 조사를 붙인다. pair: '이/가', '을/를', '은/는', '으로/로'."""
    last = next((ch for ch in reversed(word) if "가" <= ch <= "힣" or ch.isdigit() or ch == "%"), "")
    jong = _FINAL_DIGIT.get(last, 0) if not ("가" <= last <= "힣") else (ord(last) - 0xAC00) % 28
    if pair == "으로/로":
        return word + ("으로" if jong not in (0, 8) else "로")
    first, second = pair.split("/")
    return word + (first if jong else second)


# 대상자 조건. '바꾸면 충족'이라고 하지 않고 '해당하면 이 조건을 충족한다'는 정보로 안내한다.
# 경로 순위에는 쓰지 않는다(어느 조건이 더 쉬운지는 사람마다 달라 판단하지 않는다).
FIXED_FIELDS = {"성별", "국적", "등록 장애인", "중증 장애인", "국가유공자·보훈대상자", "북한이탈주민",
                "자립준비청년", "결혼이민자·다문화가족"}
# 소득·가족 상황으로 정해지는 지위. 바꾸라고 권하지 않고 대상 여부만 알린다.
STATUS_FIELDS = {"기초생활보장 수급자", "기초생활보장 수급 가구", *BENEFIT_TYPES, "차상위계층", "한부모가족",
                 "임신 중", "6세 이하 자녀", "맞벌이", "농업인·어업인", "혼인 상태"}
# 시간이 지나면 늘기만 하는 값. 상한을 넘으면 다시 충족할 수 없다.
TIME_FIELDS = {"만 나이", "막내 자녀 나이", "혼인 기간"}


# 추천 경로용 개선 난이도 표(낮을수록 맞추기 쉬움). 추천은 판단이 들어가는 영역이라 기준을 한 곳에 공개한다.
# 화면의 '추천 기준 보기'도 이 표와 같은 내용을 보여준다(frontend/src/services/conditionGuidance.ts DIFFICULTY_RULES).
DIFFICULTY_APPLY = {"구직 등록", "재학 여부", "학교 구분"}  # 신청·등록만으로 바뀜
DIFFICULTY_LIFE = {"고용 상태", "주거 형태", "부모와 따로 거주", "거주지", "세대원 전원 무주택", "본인 명의 주택 보유"}  # 이직·이사 등 생활 변화
DIFFICULTY_FAMILY = {"혼인 상태", "자녀 수", "6세 이하 자녀", "임신 중", "맞벌이", "가구원 수", "한부모가족",
                     "기초생활보장 수급자", "기초생활보장 수급 가구", *BENEFIT_TYPES, "차상위계층",
                     "등록 장애인", "중증 장애인", "농업인·어업인"}  # 가족 구성·소득 지위 변화
DIFFICULTY_IDENTITY = {"성별", "국적", "국가유공자·보훈대상자", "북한이탈주민", "자립준비청년", "결혼이민자·다문화가족"}
DIFFICULTY_POINTS = {"apply": 1.0, "life": 4.0, "family": 8.0, "identity": 20.0, "number_unknown": 4.0}


def difficulty(c: dict, current: Any) -> float | None:
    """미충족 조건 하나의 개선 난이도. 다시 충족할 수 없는 조건은 None(경로를 숨긴다)."""
    field = c.get("field")
    if impossible_failure(c, current):
        return None
    if field in TIME_FIELDS and c.get("operator") in ("gte", "lte", "between"):
        change = _numeric_change(c, current)
        return max(1.0, float(change[2])) if change else DIFFICULTY_POINTS["number_unknown"]  # 남은 햇수
    if c.get("operator") in ("gte", "lte", "between"):
        ratio = gap_ratio(c, current)  # 기준 대비 차이가 클수록 어렵다: 2점 + 차이 10%마다 1점(최대 8점)
        return round(2.0 + min(ratio * 10, 6.0), 2) if ratio is not None else DIFFICULTY_POINTS["number_unknown"]
    for group, fields in (("apply", DIFFICULTY_APPLY), ("life", DIFFICULTY_LIFE),
                          ("family", DIFFICULTY_FAMILY), ("identity", DIFFICULTY_IDENTITY)):
        if field in fields:
            return DIFFICULTY_POINTS[group]
    return DIFFICULTY_POINTS["number_unknown"]


def difficulty_group(c: dict) -> str:
    """난이도 종류. 사용자가 화면에서 종류별 가중치를 바꿀 수 있게 점수와 함께 내려보낸다."""
    field = c.get("field")
    for group, fields in (("apply", DIFFICULTY_APPLY), ("life", DIFFICULTY_LIFE),
                          ("family", DIFFICULTY_FAMILY), ("identity", DIFFICULTY_IDENTITY)):
        if field in fields:
            return group
    if field in TIME_FIELDS:
        return "time"
    return "money" if c.get("operator") in ("gte", "lte", "between") else "other"


def impossible_failure(c: dict, current: Any) -> bool:
    """정의상 다시 충족할 수 없는 미충족: 시간이 지나면 늘기만 하는 값(나이·혼인 기간·막내 자녀 나이)이 상한을 넘은 경우."""
    change = _numeric_change(c, current) if c.get("field") in TIME_FIELDS else None
    return bool(change and change[0] == "decrease")


def gap_ratio(c: dict, current: Any) -> float | None:
    """금액·비율 같은 수치 조건의 기준 대비 차이 비율. 수치 조건이 아니면 None(다른 조건과 비교하지 않는다)."""
    if c.get("field") in TIME_FIELDS:
        return None
    change = _numeric_change(c, current)
    if not change:
        return None
    _, target, delta = change
    return float(delta / abs(target)) if target else None


def _choices(field: str, options: list[str]) -> str:
    if field == "거주지" and len(options) > 5:
        return f"{'·'.join(options[:2])} 등 {len(options)}곳 중 한 곳"
    return " 또는 ".join(options)


def _guide_bounds(c: dict) -> str | None:
    bounds = _bounds(c)
    if bounds is None:
        return None
    field, unit = c.get("field"), c.get("unit", "")
    def number(n):
        if field == "만 나이":
            return f"만 {_exact_number(n)}세"
        if unit == "원":
            return _won_text(n)
        prefix = "기준 중위소득 " if field in ("가구 소득인정액", "가구 월소득 중위소득 대비") and unit == "%" else ""
        return f"{prefix}{_exact_number(n)}{unit}"
    if len(bounds) == 2:
        # 범위는 앞에만 단위 설명을 붙인다. 예: 기준 중위소득 50% 초과 100% 이하
        (a, wa), (b, wb) = bounds
        tail = f"{_exact_number(b)}세" if field == "만 나이" else _won_text(b) if unit == "원" else f"{_exact_number(b)}{unit}"
        return f"{number(a)} {wa} {tail} {wb}"
    return " ".join(f"{number(n)} {word}" for n, word in bounds)


def _guide_requirement(c: dict) -> str | None:
    """구조를 확인할 수 있는 조건만 설명한다. 비교나 정책 해석은 수행하지 않는다."""
    field, op = c.get("field"), c.get("operator")
    if not isinstance(field, str) or not field or c.get("kind") not in ("requirement", "exclusion"):
        return None
    if op == "is_true":
        return "재학 상태" if field == "재학 여부" else f"'{field}' 해당 상태"
    if op == "one_of":
        options = c.get("values")
        if not isinstance(options, list) or not options or not all(isinstance(v, str) and v.strip() for v in options):
            return None
        choices = _choices(field, options)
        return f"{choices} 거주 요건" if field == "거주지" else f"{field}: {choices}"
    if op not in ("gte", "lte", "between"):
        return None
    numbers = [c.get("value")] + ([c.get("upper_value")] if op == "between" else [])
    try:
        if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not Decimal(str(n)).is_finite() for n in numbers):
            return None
    except InvalidOperation:
        return None
    if op == "between" and numbers[0] > numbers[1]:
        return None
    if not isinstance(c.get("unit", ""), str):
        return None
    bounds = _guide_bounds(c)
    if bounds is None:
        return None
    return bounds if field == "만 나이" else f"{field} {bounds}"


_CHANGE_UNITS = {
    "만 나이": "세", "막내 자녀 나이": "세", "본인 월소득": "원", "본인 연소득": "원",
    **{field: "원" for field in MONEY_FIELDS},
    "가구 소득인정액": "%", "가구 월소득 중위소득 대비": "%", "도시근로자 월평균소득 대비 가구소득": "%",
    "가구원 수": "명", "자녀 수": "명", "혼인 기간": "년", "신용점수(KCB)": "점", "신용점수(NICE)": "점",
}
_CHANGE_BOOLEANS = {
    "재학 여부", "등록 장애인", "중증 장애인", "본인 명의 주택 보유", "세대원 전원 무주택", "부모와 따로 거주",
    "기초생활보장 수급자", "기초생활보장 수급 가구", "차상위계층", "한부모가족", "자립준비청년", "구직 등록",
    "6세 이하 자녀", "임신 중", "맞벌이", *BENEFIT_TYPES, *SPECIAL_TARGETS,
}
_CHANGE_CHOICES = {
    "고용 상태": set(EMPLOYMENT_LABELS.values()), "학교 구분": set(SCHOOL_LABELS.values()),
    "주거 형태": set(HOUSING_LABELS.values()), "혼인 상태": set(MARRIAGE_LABELS.values()),
    "국적": {"대한민국", "외국인"}, "성별": {"남성", "여성"},
}
_CHANGE_REGION = re.compile(
    r"(?:서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|"
    r"경기도|강원특별자치도|충청북도|충청남도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도)"
    r"(?: [가-힣]+[시군구]){0,2}"
)


def _numeric_change(c: dict, current: Any) -> tuple[str, Decimal, Decimal] | None:
    """내부 계산 전용 (방향, 경계 목표값, 차이). 차이와 현재 값은 응답/스냅샷에 넣지 않는다."""
    if c.get("kind") != "requirement" or c.get("operator") not in ("gte", "lte", "between"):
        return None
    if _CHANGE_UNITS.get(c.get("field")) != c.get("unit") or _guide_requirement(c) is None:
        return None
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    value = Decimal(str(current))
    if not value.is_finite():
        return None
    lower = Decimal(str(c["value"]))
    upper = Decimal(str(c["upper_value"])) if c["operator"] == "between" else lower
    if c["operator"] in ("gte", "between") and value < lower:
        return "increase", lower, lower - value
    if c["operator"] in ("lte", "between") and value > upper:
        return "decrease", upper, value - upper
    return None


def _state_change_guide(c: dict, current: Any, required: str) -> str | None:
    """검증된 단일 조건의 미충족 원인과 목표 상태. 자유 텍스트를 재파싱하지 않는다."""
    field, op, exclusion = c["field"], c["operator"], c["kind"] == "exclusion"
    if op in ("gte", "lte", "between"):
        if _CHANGE_UNITS.get(field) != c.get("unit") or isinstance(current, bool) or not isinstance(current, (int, float)):
            return None
        if not Decimal(str(current)).is_finite():
            return None
        bounds = _bounds(c)
        if exclusion:
            outside_word = {"이상": "미만", "초과": "이하", "이하": "초과", "미만": "이상"}
            prefix = "" if field == "만 나이" else f"{field} "
            def number(n):
                if field == "만 나이":
                    return f"만 {_exact_number(n)}세"
                ratio = "기준 중위소득 " if field in ("가구 소득인정액", "가구 월소득 중위소득 대비") and c["unit"] == "%" else ""
                return f"{ratio}{_exact_number(n)}{c['unit']}"
            outside = " 또는 ".join(f"{prefix}{number(n)} {outside_word[word]}" for n, word in bounds)
            text = f"{required}에 해당하면 제외됩니다. {outside}이면 이 제외 조건에 해당하지 않습니다."
            if field in TIME_FIELDS and op == "gte":
                text += " 시간이 지나도 줄지 않는 값이라 이 제외 조건을 벗어날 수 없습니다."
            return text
        change = _numeric_change(c, current)
        if change is None:
            return None
        direction, _, _ = change  # 차액을 노출하면 목표값으로 현재 입력을 역산할 수 있다.
        target = _guide_bounds(c)
        if field in TIME_FIELDS:
            name = "나이" if field == "만 나이" else field
            if direction == "decrease":
                return (f"{_josa(name, '이/가')} {target} 기준을 넘었습니다. "
                        "시간이 지나도 줄지 않아 이 조건은 충족할 수 없습니다.")
            return f"시간이 지나 {_josa(name, '이/가')} {_josa(target, '이/가')} 되면 이 조건을 충족합니다."
        count = c.get("unit") == "명"
        state = ("적습니다" if count else "낮습니다") if direction == "increase" else ("많습니다" if count else "높습니다")
        return f"{_josa(field, '이/가')} 기준보다 {state}. {_josa(target, '이/가')} 되면 이 조건을 충족합니다."
    if op == "is_true" and field in _CHANGE_BOOLEANS and isinstance(current, bool):
        name = f"'{field}'"
        # 대상자 조건(장애·한부모·수급 등)은 바꾸라고 하지 않고, 해당하면 받을 수 있다는 정보로 알린다.
        if field in FIXED_FIELDS | STATUS_FIELDS:
            return (f"{name}에 해당하면 이 경로에서는 제외됩니다." if exclusion
                    else f"이 경로는 {name}에 해당하는 사람이 대상입니다. 해당하면 이 조건을 충족합니다.")
        if field == "재학 여부":
            return ("재학 중이면 제외됩니다. 재학하지 않는 상태여야 이 조건을 충족합니다." if exclusion
                    else "재학 중(입학·복학 예정 포함)이면 이 조건을 충족합니다.")
        return (f"{name}에 해당하면 제외됩니다. 해당하지 않게 되면 이 조건을 충족합니다." if exclusion
                else f"{name}에 해당하게 되면 이 조건을 충족합니다.")
    if op == "one_of" and isinstance(current, str) and current.strip() and current != "UNKNOWN":
        options = c["values"]
        known = field in _CHANGE_CHOICES and all(option in _CHANGE_CHOICES[field] for option in options)
        known = known or field == "거주지" and all(_CHANGE_REGION.fullmatch(option) for option in options)
        if not known:
            return None
        choices = _choices(field, options)
        if exclusion:
            return f"{field} {choices}에 해당하면 제외됩니다. 다른 {_josa(field, '으로/로')} 바뀌면 이 조건을 충족합니다." \
                if field not in FIXED_FIELDS | STATUS_FIELDS else f"{field} {choices}에 해당하면 이 경로에서는 제외됩니다."
        if field in FIXED_FIELDS:  # 성별·국적은 사실만 알린다
            return f"이 경로는 {_josa(field, '이/가')} {choices}인 경우 대상입니다."
        if field in STATUS_FIELDS:
            return f"이 경로는 {_josa(field, '이/가')} {choices}인 경우 대상입니다. 해당하면 이 조건을 충족합니다."
        return f"{_josa(field, '이/가')} {_josa(choices, '으로/로')} 바뀌면 이 조건을 충족합니다."
    return None


def condition_guide(condition: dict, current: Any, result: bool | None) -> dict:
    """현재 비교값으로 미충족 원인과 상태 변화를 계산하고 기존 비교 결과에 덧붙인다.

    reason_code는 조건 단위의 설명이며, 정책 전체의 자격이나 신청 결과를 뜻하지 않는다.
    현재 값·정확한 차액은 반환하지 않는다. 미지원 변화는 기존 required_value/evidence를 보존한다.
    """
    required = _guide_requirement(condition)
    if required is None:
        return {"condition_guide": "", "reason_code": "unsupported_condition"}
    if result is False:
        text = _state_change_guide(condition, current, required)
        if text is None:
            return {"condition_guide": "", "reason_code": "change_unavailable"}
        code = "exclusion_applies" if condition["kind"] == "exclusion" else "requirement_not_met"
        if condition["field"] == "만 나이" and condition["kind"] == "requirement":
            code = "age_above_maximum" if _numeric_change(condition, current)[0] == "decrease" else "age_below_minimum"
        return {"condition_guide": text, "reason_code": code, "guide_kind": "state_change"}
    exclusion = condition["kind"] == "exclusion"
    requirement = f"{required}에 해당하면 제외됩니다." if exclusion else f"{required} 기준을 만족해야 합니다."
    if result is None:
        code = "input_missing" if current is None else "comparison_uncertain"
        detail = "정보가 입력되지 않아 비교하지 않았습니다." if current is None else "현재 입력 범위만으로 충족 여부를 확정할 수 없습니다."
        return {"condition_guide": f"{requirement} {detail}", "reason_code": code}
    if exclusion:
        detail = "입력 정보가 제외 기준에 해당합니다." if result is False else "입력 정보는 해당 제외 기준에 해당하지 않습니다."
        return {"condition_guide": f"{requirement} {detail}",
                "reason_code": "exclusion_applies" if result is False else "exclusion_not_applicable"}
    code = "condition_met" if result is True else "requirement_not_met"
    if condition["field"] == "만 나이":
        text = f"{required}이면 연령 요건을 충족합니다."
        if result is False:
            above = condition["operator"] == "lte" or (condition["operator"] == "between" and current > condition["upper_value"])
            code = "age_above_maximum" if above else "age_below_minimum"
            if above:
                text += " 현재 연령이 상한을 초과하며, 나이 증가만으로는 해당 연령 요건을 충족할 수 없습니다."
    else:
        text = f"{required}이 필요합니다." if condition["field"] == "거주지" else requirement
        if result is True:
            text += " 입력 정보 기준으로 이 조건을 충족합니다."
    return {"condition_guide": text, "reason_code": code}


def show(field: str, value: Any) -> str:
    if value is None:
        return "미입력"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, tuple):
        low, high = value
        return f"{low / 10000:,.0f}만원 이상" if high is None else f"{low / 10000:,.0f}만~{(high + 1) / 10000:,.0f}만원 미만"
    if field in MONEY_FIELDS:
        return f"{value / 10000:,.0f}만원"
    if field in ("도시근로자 월평균소득 대비 가구소득", "가구 월소득 중위소득 대비"):
        return f"{value:g}%"
    if field == "혼인 기간":
        return f"{value}년"
    if field.startswith("신용점수"):
        return f"{value}점"
    if field in ("만 나이", "막내 자녀 나이"):
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
