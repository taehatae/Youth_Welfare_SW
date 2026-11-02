"""정책 원문의 자격 조건을 진단 입력값과 비교할 수 있는 구조로 바꾼 초안을 만든다.

로컬 Ollama 모델(gemma3:12b)에 정해진 칸을 채우는 좁은 질문 세 개(나이·소득 / 고용·재학·국적·주택 / 대상 집단)를
던지고, 답을 조건 목록으로 바꾼다. 결과는 사람이 검수한 뒤 시드 파일로 저장한다. DB는 읽기 전용으로만 연다.

    python scripts/structure_conditions.py --ids-file data/structure_train_ids.txt --out data/structured_train.json
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

PROMPT_VERSION = "2026-11-02-slots-8"  # 칸 채우기 답 캐시 키. 질문을 바꾸면 올린다.
VERIFY_VERSION = "verify-4"
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "structure_cache.json"

COMMON_RULES = """공통 원칙
- 신청자 본인(또는 신청자의 가구)에게 공통으로 적용되는 자격 조건만 적는다.
- 지원 유형(①②③, 사업 유형, 대상자 유형)마다 기준이 다르면, 모든 유형에 똑같이 적용되는 기준만 적고 나머지는 비워둔다.
- 자녀·아동·가구원·보증인·부양의무자 등 다른 사람에 대한 조건, 우대·가점·우선 선발 기준, 신청 방법은 적지 않는다.
- 1순위·2순위처럼 순위를 나누는 기준은 자격 조건이 아니다(낮은 순위로 누구나 신청할 수 있으면 조건이 없는 것).
- 대출 종류·주택 유형·공급 유형마다 붙는 조건은 그 유형에만 해당하므로 적지 않는다.
- 아직 해당하지 않아도 신청할 수 있는 길이 원문에 있으면(신규 등록 예정자, 의사 소견으로 인정 등) 그 조건은 적지 않는다.
- evidence에는 근거 구절을 원문에서 글자 그대로 복사한다. 해당 조건이 없으면 값은 null, evidence는 ""."""

NULLABLE_NUMBER = {"type": ["number", "null"]}
NUMBER_SCHEMA = {
    "type": "object",
    "properties": {
        "age_min": NULLABLE_NUMBER, "age_max": NULLABLE_NUMBER, "age_evidence": {"type": "string"},
        "monthly_income_min": NULLABLE_NUMBER, "monthly_income_max": NULLABLE_NUMBER,
        "annual_income_max": NULLABLE_NUMBER, "income_evidence": {"type": "string"},
        "median_ratio_min": NULLABLE_NUMBER, "median_ratio_max": NULLABLE_NUMBER, "median_evidence": {"type": "string"},
        "urban_ratio_max": NULLABLE_NUMBER, "urban_evidence": {"type": "string"},
        "asset_max": NULLABLE_NUMBER, "asset_evidence": {"type": "string"},
    },
    "required": ["age_min", "age_max", "age_evidence", "monthly_income_min", "monthly_income_max",
                 "annual_income_max", "income_evidence", "median_ratio_min", "median_ratio_max", "median_evidence",
                 "urban_ratio_max", "urban_evidence", "asset_max", "asset_evidence"],
}
NUMBER_PROMPT = f"""복지 정책 원문에서 신청자의 나이·소득 자격 기준을 정해진 칸에 채운다.

- age_min / age_max: 만 나이 하한·상한(포함). "19세 이상 34세 이하" → 19, 34. "65세 미만" → age_max 64.
  '단·다만·예외적으로·관계없이' 같은 예외가 붙은 나이 기준은 비워둔다.
- monthly_income_min / monthly_income_max: 신청자 본인의 월 소득 기준(원). "근로소득 월 10만원 이상" → monthly_income_min 100000.
- annual_income_max: 신청자 본인의 연소득 상한(원). "연소득 3,500만원 이하" → 35000000.
  부부합산·가구 소득, 순자산, 보증금·월세는 적지 않는다.
- median_ratio_min / median_ratio_max: 가구 소득인정액(또는 가구 소득)의 기준 중위소득 비율(%).
  "중위소득 50% 이하" → median_ratio_max 50. "50% 초과 100% 이하" → 50, 100.
  "생계급여 기준 중위소득 32% 이하"처럼 가구원 수별 금액표와 함께 나오면 비율만 적는다.
- urban_ratio_max: "전년도 도시근로자 가구당 월평균소득 100% 이하"처럼 도시근로자 월평균소득 대비 가구 소득 비율(%) 상한.
  가구원 수마다 비율이 다르면(1인 120%, 2인 110% 등) 비워둔다.
- asset_max: 신청자 가구의 총재산(총자산) 상한(원). "총재산가액 1.22억원 이하" → 122000000.
  순자산·재산과표·자동차가액·소득환산액처럼 총재산이 아닌 기준은 적지 않는다.

{COMMON_RULES}"""

EMPLOYMENT_VALUES = ["재직", "중소기업 재직", "아르바이트", "미취업", "자영업", "프리랜서"]
STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "employment_one_of": {"type": "array", "items": {"type": "string", "enum": EMPLOYMENT_VALUES}},
        "employment_evidence": {"type": "string"},
        "student": {"type": "string", "enum": ["required", "excluded", "none"]},
        "student_evidence": {"type": "string"},
        "korean_only": {"type": "boolean"}, "nationality_evidence": {"type": "string"},
        "homeowner_excluded": {"type": "boolean"}, "home_evidence": {"type": "string"},
        "household_homeless": {"type": "boolean"}, "household_home_evidence": {"type": "string"},
        "unemployed_or_no_income": {"type": "boolean"}, "unemployed_or_no_income_evidence": {"type": "string"},
    },
    "required": ["employment_one_of", "employment_evidence", "student", "student_evidence", "korean_only",
                 "nationality_evidence", "homeowner_excluded", "home_evidence", "household_homeless",
                 "household_home_evidence", "unemployed_or_no_income", "unemployed_or_no_income_evidence"],
}
STATUS_PROMPT = f"""복지 정책 원문에서 신청자의 고용·재학·국적·주택 자격 기준을 정해진 칸에 채운다.

- employment_one_of: 신청자가 이 중 하나여야 한다면 그 목록({", ".join(EMPLOYMENT_VALUES)}). 고용 조건이 없으면 [].
  "미취업자", "실업자", "구직자" → ["미취업"]. "중소기업 재직자" → ["중소기업 재직"].
  실업급여 수급자, 국민취업지원제도 참여자처럼 목록으로 나타낼 수 없는 조건은 [].
- student: 재학생이어야 하면 required, 재학생이 제외되면 excluded, 조건이 없으면 none.
  "대학 또는 대학원에 재학 중" → required. "고교·대학 재학생은 참여할 수 없습니다" → excluded.
- korean_only: "대한민국 국민", "국민"으로 대상을 한정하면 true. 문장 끝에 "~하는 대한민국 국민을 대상으로"처럼
  붙어 있어도 true. 외국인·난민도 신청 가능하다고 하면 false.
- homeowner_excluded: "무주택자", "무주택 세대주"처럼 주택을 가진 사람이 제외되면 true.
- household_homeless: "무주택 세대주", "무주택세대구성원", "무주택 가구", "무주택 저소득 한부모가족"처럼
  세대(가구) 전체가 주택이 없어야 하면 true. "무주택 청년", "무주택자"처럼 본인만 말하면 false(homeowner_excluded만 true).
- unemployed_or_no_income: "실업자 또는 정기소득이 없는 경우"처럼 미취업이거나 소득이 없으면 둘 중 하나만 맞아도 되는
  조건이면 true. 이때 employment_one_of는 []로 둔다.

{COMMON_RULES}"""

TARGET_FIELDS = [
    "등록 장애인", "기초생활보장 수급자", "생계급여 수급자", "의료급여 수급자", "주거급여 수급자", "교육급여 수급자",
    "차상위계층", "한부모가족", "국가유공자·보훈대상자", "북한이탈주민", "결혼이민자·다문화가족", "농업인·어업인",
    "자립준비청년",
]
# 근거 구절에 그 대상 집단을 가리키는 말이 실제로 있어야 한다(모델이 지어낸 대상 집단을 걸러낸다).
TARGET_WORDS = {
    "등록 장애인": r"장애", "기초생활보장 수급자": r"수급|생계급여|의료급여", "차상위계층": r"차상위",
    "생계급여 수급자": r"생계", "의료급여 수급자": r"의료급여", "주거급여 수급자": r"주거급여", "교육급여 수급자": r"교육급여",
    "자립준비청년": r"자립준비|보호종료|보호 종료",
    "한부모가족": r"한부모", "국가유공자·보훈대상자": r"유공|보훈|독립|애국|5[.ㆍ·]18|참전",
    "북한이탈주민": r"북한이탈|탈북", "결혼이민자·다문화가족": r"다문화|결혼이민", "농업인·어업인": r"농업|어업|농어|농민|어민",
}
PREFERENCE_WORDS = re.compile(r"가점|우선|우대|가산")
TARGET_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {"type": "array", "items": {"type": "object", "properties": {
            "evidence": {"type": "string"},
            "field": {"type": "string", "enum": TARGET_FIELDS},
            "kind": {"type": "string", "enum": ["requirement", "exclusion"]},
        }, "required": ["evidence", "field", "kind"]}},
        "any_one_is_enough": {"type": "boolean"},
    },
    "required": ["groups", "any_one_is_enough"],
}
TARGET_PROMPT = f"""복지 정책 원문을 읽고, 신청자 본인(또는 신청자의 가구)이 아래 대상 집단에 속해야 하는지 판단한다.
대상 집단: {", ".join(TARGET_FIELDS)}

- groups: 신청자가 해당해야 신청할 수 있는(requirement) 또는 해당하면 제외되는(exclusion) 대상 집단만 고른다.
  evidence에는 근거 구절을 글자 그대로 복사한다. 대상 집단과 상관없는 일반 정책이면 빈 목록.
- 자녀·보호자 등 다른 사람에게만 해당하는 집단, 우대·가점·우선 선발 대상은 고르지 않는다.
- 특정 시설·기관 거주자만 제외하는 경우처럼 집단 전체가 제외되는 것이 아니면 exclusion으로 고르지 않는다.
- any_one_is_enough: requirement 집단이 여러 개 나열되어 그중 하나만 해당하면 되면 true, 모두 해당해야 하면 false.
- 수급자: 생계·의료·주거·교육급여 수급자를 모두 대상으로 하거나 그냥 '기초생활수급자'면 기초생활보장 수급자.
  특정 급여만 대상이면 그 급여 수급자만 고른다("생계급여 수급가구" → 생계급여 수급자).
- 순위(1순위·2순위)로만 나오는 집단, 여러 공급·지원 유형 중 일부 유형의 대상은 고르지 않는다.
- 등록 장애인: "등록장애인", "「장애인복지법」상 등록된 장애인", "장애인을 대상으로"처럼 장애인만 대상이면 반드시 고른다.
  예외는 '신규 장애인 등록이 필요한 사람', '등록되지 않았으나 의사 소견으로 인정'처럼 미등록자도 대상이라고
  원문에 적혀 있을 때뿐이다.
- 자립준비청년: 아동복지시설·가정위탁 보호가 끝난 청년(보호종료아동)만 대상이면 고른다.

예시
- "기초생활수급자, 시각 및 청각 장애인, 일부 국가유공자 등을 대상으로" → 기초생활보장 수급자, 등록 장애인, 국가유공자·보훈대상자 / true
- "「국민기초생활보장법」에 따른 수급자 및 차상위 계층을 지원" → 기초생활보장 수급자, 차상위계층 / true
- "18세 이상 「장애인복지법」상 등록된 미취업 장애인" → 등록 장애인 / false
- "북한이탈주민과 북한이탈주민의 자녀의 교육비를 지원", "탈북민으로 보호결정된 자" → 북한이탈주민
- "생계급여 수급가구 중 임산부 또는 34세 이하 인을 포함하고 있는 가구" → 생계급여 수급자
- "기초생활수급자(생계급여, 의료급여수급자), 시각 및 청각 장애인" → 생계급여 수급자, 의료급여 수급자, 등록 장애인 / true
- "(1순위) 생계급여 수급자 ... (3순위) 소득 70% 이하인 자" → 빈 목록(순위 기준)
- "아동복지시설, 가정위탁 보호종료 5년 이내 자립준비청년" → 자립준비청년
- "저소득층, 장애인, 한부모가족 등 취업취약계층을 우선 선발" → 빈 목록(우선 선발 기준)
- "만 19세 이상 국민 중 월 15회 이상 대중교통 이용자" → 빈 목록"""

EXCEPTION_WORDS = re.compile(r"단[,\s]|다만|예외|관계\s*없이|무관")
# 칸마다 근거 구절에 있어야 하는 말. 없으면 모델이 엉뚱한 구절을 근거로 댄 것이다.
FIELD_WORDS = {
    "만 나이": r"세", "본인 월소득": r"소득|원", "본인 연소득": r"소득", "가구 소득인정액": r"중위|%",
    "고용 상태": r"취업|실업|구직|재직|근로자|근무|직장|사업자|프리랜서|아르바이트",
    "재학 여부": r"재학|학생|대학|학교", "국적": r"국민|내국인|국적", "본인 명의 주택 보유": r"무주택|주택",
    "세대원 전원 무주택": r"무주택", "가구 총재산": r"재산|자산", "자립준비청년": r"자립준비|보호종료|보호 종료", "도시근로자 월평균소득 대비 가구소득": r"도시근로자",
    **TARGET_WORDS,
}

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": ["yes", "no"]}},
    "required": ["reason", "verdict"],
}
VERIFY_PROMPT = """복지 정책 원문과 '주장' 하나가 주어진다. 주장이 원문에 근거한, 이 정책의 신청 자격 조건인지 판단한다.

yes: 원문이 이 조건을 신청자 본인(또는 신청자의 가구)에게 요구하고, 모든 신청자에게 공통으로 적용된다.
해당하면 신청할 수 없는 제외 조건도 자격 조건이다. 제외 조건이 원문에 있으면 yes.
"~인 대한민국 국민을 대상으로 지원", "무주택 세대주를 대상으로"처럼 대상을 한정하면 그 대상이 아닌 사람은 신청할 수 없으므로 yes.
"입학 예정 포함"처럼 대상을 조금 넓히는 표현은 예외가 아니다.
no: 다음 중 하나라도 해당한다.
- 원문에 그런 내용이 없거나, 숫자·대상이 다르다.
- 자녀·아동·가구원·보증인 등 다른 사람에 대한 조건이다.
- 여러 지원 유형 중 일부 유형에만 적용된다.
- 우대·가점·우선 선발 기준이거나, 1순위·2순위 같은 순위 기준이다.
- 예외로 허용되는 경우가 함께 적혀 있다(그 조건에 해당하지 않아도 신청할 수 있는 길이 있다).

reason에 근거를 한두 문장으로 쓰고 verdict를 고른다."""


def claim(conditions: list[dict]) -> str:
    """조건(또는 '또는'으로 묶인 조건들)을 사람이 읽는 주장 문장으로 바꾼다."""
    def manwon(x):
        return f"{x / 10000:,.0f}만원" if x >= 10000 else f"{x:,.0f}원"

    def span(op, v, u, fmt):
        if op == "between":
            return f"{fmt(v)} 이상 {fmt(u)} 이하"
        return f"{fmt(v)} {'이상' if op == 'gte' else '이하'}"

    parts = []
    for c in conditions:
        f, op, v, u = c["input_field"], c["operator"], c["value"], c["upper_value"]
        if f == "만 나이":
            parts.append(f"신청자 본인의 나이가 {span(op, v, u, lambda x: f'만 {x:g}세')}")
        elif f == "본인 월소득":
            parts.append(f"신청자 본인의 월 소득이 {span(op, v, u, manwon)}")
        elif f == "본인 연소득":
            parts.append(f"신청자 본인의 연소득이 {span(op, v, u, manwon)}")
        elif f == "가구 소득인정액":
            parts.append(f"신청자 가구의 소득(소득인정액)이 기준 중위소득 {span(op, v, u, lambda x: f'{x:g}%')}")
        elif f == "고용 상태":
            parts.append(f"신청자가 {' 또는 '.join(c['values'])} 상태")
        elif f == "재학 여부" and c["kind"] == "exclusion":
            return "이 정책은 현재 학교에 재학 중인 학생은 신청할 수 없다."
        elif f == "재학 여부":
            parts.append("신청자가 학교에 재학 중(입학 예정 포함)")
        elif f == "국적":
            parts.append("신청자가 대한민국 국민(외국인 제외)")
        elif f == "가구 총재산":
            parts.append(f"신청자 가구의 총재산이 {span(op, v, u, manwon)}")
        elif f == "도시근로자 월평균소득 대비 가구소득":
            parts.append(f"신청자 가구의 소득이 전년도 도시근로자 가구당 월평균소득의 {span(op, v, u, lambda x: f'{x:g}%')}")
        elif f == "세대원 전원 무주택":
            parts.append("신청자의 세대(가구)가 무주택")
        elif f == "본인 명의 주택 보유":
            return "이 정책은 주택을 소유한 사람은 신청할 수 없다(무주택자만 신청 가능)."
        elif c["kind"] == "exclusion":
            return f"이 정책은 {f}에 해당하는 사람은 신청할 수 없다."
        else:
            parts.append(f"신청자(또는 신청자의 가구)가 {f}에 해당")
    joiner = " 중 하나" if len(parts) > 1 else ""
    return f"이 정책은 {(', '.join(parts))}{joiner}이어야 신청할 수 있다."


def norm(text: str | None) -> str:
    """근거 대조용: 글자와 숫자만 남긴다(모델이 쉼표·가운뎃점·공백을 바꿔 적는 경우가 많다)."""
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text or "")


def source_lines(evidence: str, source: str) -> str:
    target = norm(evidence)
    return " ".join(line for line in source.splitlines() if target and target in norm(line)) or evidence


def condition(field, operator, evidence, *, kind="requirement", value=None, upper=None, unit="", values=(),
              or_group="", summary="") -> dict:
    return {"evidence": evidence, "summary": summary or field, "kind": kind, "applies_to": "applicant",
            "input_field": field, "operator": operator, "value": value, "upper_value": upper, "unit": unit,
            "values": list(values), "or_group": or_group}


def bounds(field, low, high, evidence, unit) -> list[dict]:
    if low is not None and low == high and re.search(r"이하|미만|까지", evidence or ""):
        low = None
    if low is not None and high is not None:
        return [condition(field, "between", evidence, value=low, upper=high, unit=unit)]
    if low is not None:
        return [condition(field, "gte", evidence, value=low, unit=unit)]
    if high is not None:
        return [condition(field, "lte", evidence, value=high, unit=unit)]
    return []


NOT_TOTAL_ASSET = re.compile(r"순자산|과표|환산|자동차")


def number_conditions(a: dict) -> list[dict]:
    return (bounds("만 나이", a["age_min"], a["age_max"], a["age_evidence"], "세")
            + bounds("본인 월소득", a["monthly_income_min"], a["monthly_income_max"], a["income_evidence"], "원")
            + bounds("본인 연소득", None, a["annual_income_max"], a["income_evidence"], "원")
            + bounds("가구 소득인정액", a["median_ratio_min"], a["median_ratio_max"], a["median_evidence"], "%")
            + bounds("도시근로자 월평균소득 대비 가구소득", None, a["urban_ratio_max"], a["urban_evidence"], "%")
            + (bounds("가구 총재산", None, a["asset_max"], a["asset_evidence"], "원")
               if not NOT_TOTAL_ASSET.search(a["asset_evidence"] or "") else []))


def status_conditions(a: dict) -> list[dict]:
    conditions = []
    if a["employment_one_of"]:
        conditions.append(condition("고용 상태", "one_of", a["employment_evidence"], values=a["employment_one_of"]))
    if a["student"] != "none":
        conditions.append(condition("재학 여부", "is_true", a["student_evidence"],
                                    kind="requirement" if a["student"] == "required" else "exclusion"))
    if a["korean_only"]:
        conditions.append(condition("국적", "one_of", a["nationality_evidence"], values=["대한민국"]))
    if a["homeowner_excluded"] or a["household_homeless"]:
        evidence = a["home_evidence"] or a["household_home_evidence"]
        conditions.append(condition("본인 명의 주택 보유", "is_true", evidence, kind="exclusion"))
    if a["household_homeless"]:
        conditions.append(condition("세대원 전원 무주택", "is_true", a["household_home_evidence"]))
    if a["unemployed_or_no_income"]:
        evidence = a["unemployed_or_no_income_evidence"]
        conditions += [condition("고용 상태", "one_of", evidence, values=["미취업"], or_group="미취업또는무소득"),
                       condition("본인 월소득", "lte", evidence, value=0, unit="원", or_group="미취업또는무소득")]
    return conditions


BENEFIT_WORDS = {"생계급여 수급자": "생계", "의료급여 수급자": "의료", "주거급여 수급자": "주거", "교육급여 수급자": "교육"}


def split_benefits(groups: list[dict]) -> list[dict]:
    result = []
    for g in groups:
        named = [field for field, word in BENEFIT_WORDS.items() if re.search(word + r"\s*(급여|·|,|ㆍ)", g["evidence"])]
        if g["field"] == "기초생활보장 수급자" and g["kind"] == "requirement" and 0 < len(named) < 4:
            result += [{**g, "field": field} for field in named]
        else:
            result.append(g)
    return result


def target_conditions(a: dict) -> list[dict]:
    groups, seen = [], set()
    for g in collapse_benefits(split_benefits(a["groups"])):
        if (g["field"], g["kind"]) in seen or not re.search(TARGET_WORDS[g["field"]], g["evidence"]):
            continue
        if PREFERENCE_WORDS.search(g["evidence"]):
            continue
        seen.add((g["field"], g["kind"]))
        groups.append(g)
    requirements = {g["field"] for g in groups if g["kind"] == "requirement"}
    groups = [g for g in groups if g["kind"] == "requirement" or g["field"] not in requirements]
    split = any(g["field"] in BENEFIT_WORDS for g in groups) and len(requirements) > 1
    or_group = "대상집단" if (a["any_one_is_enough"] or split) and len(requirements) > 1 else ""
    return [condition(g["field"], "is_true", g["evidence"], kind=g["kind"],
                      or_group=or_group if g["kind"] == "requirement" else "") for g in groups]


RANK_WORDS = re.compile(r"순위|가점|우선|우대|가산|제외|중복")
# 모델이 대상 집단을 하나도 고르지 않았을 때, 원문 줄에 대상 집단 하나만 뚜렷이 나오면 후보로 올린다.
# 후보는 다른 조건과 똑같이 검증 단계(예/아니오)를 거쳐 통과해야만 진단에 쓰인다.
CANDIDATE_WORDS = {
    "등록 장애인": r"등록\s*장애인|등록된[^.。]{0,15}장애인|장애인\s*등록증", "한부모가족": r"한부모",
    "북한이탈주민": r"북한이탈|탈북", "자립준비청년": r"자립준비청년|보호종료",
    "국가유공자·보훈대상자": r"국가유공자|보훈대상자|독립유공자",
    "세대원 전원 무주택": r"무주택\s*세대|무주택\s*(저소득\s*)?(한부모)?가(구|족)",
}


def candidates(source: str, found: set[str]) -> list[dict]:
    result = []
    for line in source.splitlines()[:6]:
        if RANK_WORDS.search(line):
            continue
        hits = [field for field, words in CANDIDATE_WORDS.items() if re.search(words, line)]
        if len([h for h in hits if h != "세대원 전원 무주택"]) > 1:
            continue
        for field in hits:
            if field not in found and field not in {c["input_field"] for c in result}:
                result.append(condition(field, "is_true", line.strip()))
    return result


OPEN_CATEGORY = re.compile(r"\d\s*순위|일반\s*공급|\(일반\)|일반\s*가구|일반\s*매입|그\s*외\s*(공급|유형)")


# '또는' 묶음은 나열된 대상이 모두 입력 항목이어야 쓸 수 있다. 입력 항목이 아닌 대상(청년·신혼부부·소득 기준 등)이
# 같은 목록에 있으면, 그 대상에 해당하는 사람이 '신청 불가'로 잘못 나온다.
OTHER_CATEGORY = re.compile(r"청년|대학생|신혼|고령자|노인|임산부|저소득|중위소득|근로자|예술인|창업|일반|청소년")


def drop_open_categories(conditions: list[dict], source: str) -> None:
    """대상 집단 '또는' 묶음이 공급 유형·순위 목록이거나, 입력 항목이 아닌 대상과 함께 나열되면 진단에 쓰지 않는다."""
    group = [c for c in conditions if c["or_group"] == "대상집단"]
    if not group:
        return
    lines = " ".join(source_lines(c["evidence"], source) for c in group)
    for word in TARGET_WORDS.values():
        lines = re.sub(word, "", lines)
    if OPEN_CATEGORY.search(source) or OTHER_CATEGORY.search(lines):
        for c in group:
            c["review_reasons"].append("나열된 대상 중 입력 항목이 아닌 대상이 있음(그 대상도 신청 가능)")


def collapse_benefits(groups: list[dict]) -> list[dict]:
    """생계·의료·주거·교육급여 수급자를 모두 고르면 기초생활보장 수급자 하나로 합친다."""
    picked = {g["field"] for g in groups if g["kind"] == "requirement"}
    if set(BENEFIT_WORDS) <= picked:
        evidence = next(g["evidence"] for g in groups if g["field"] in BENEFIT_WORDS)
        groups = [g for g in groups if g["field"] not in BENEFIT_WORDS]
        groups.append({"evidence": evidence, "field": "기초생활보장 수급자", "kind": "requirement"})
    return groups


def review(c: dict, source: str) -> dict:
    """근거가 원문에 없거나 예외 문구가 붙은 조건은 진단에 쓰지 않고 검수 대상으로 남긴다."""
    reasons = []
    c["grounded"] = bool(norm(c["evidence"])) and norm(c["evidence"]) in norm(source)
    if not c["grounded"]:
        reasons.append("근거가 원문과 글자 그대로 일치하지 않음")
    if EXCEPTION_WORDS.search(source_lines(c["evidence"], source)):
        reasons.append("근거에 예외 문구가 있음")
    if not re.search(FIELD_WORDS[c["input_field"]], c["evidence"]):
        reasons.append("근거 구절에 해당 항목을 가리키는 말이 없음")
    c["review_reasons"] = reasons
    return c


def condition_key(c: dict) -> tuple:
    return (c["input_field"], c["kind"], c["operator"], c["value"], c["upper_value"], tuple(c["values"]), c["or_group"])


def dedupe(conditions: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for c in conditions:
        if condition_key(c) not in seen:
            seen.add(condition_key(c))
            unique.append(c)
    return unique


def flag_conflicts(conditions: list[dict]) -> None:
    """검증을 통과한 조건 중 같은 항목에 서로 다른 기준이 남으면 사람이 고르도록 검수 대상으로 돌린다."""
    by_field: dict[tuple, list[dict]] = {}
    for c in conditions:
        if not c["review_reasons"] and not c["or_group"]:
            by_field.setdefault((c["input_field"], c["kind"]), []).append(c)
    for same in by_field.values():
        if len(same) > 1:
            for c in same:
                c["review_reasons"].append("같은 항목에 서로 다른 기준이 뽑힘")


def verify(conditions: list[dict], user: str, model: str, url: str, cache: dict, key: str) -> None:
    """검수 표시가 없는 조건을 하나씩(또는 묶음째) 예/아니오로 다시 확인한다. 아니오면 검수 대상으로 돌린다."""
    units: dict[str, list[dict]] = {}
    for i, c in enumerate(conditions):
        if not c["review_reasons"]:
            units.setdefault(c["or_group"] or f"#{i}", []).append(c)
    for unit in units.values():
        text = claim(unit)
        answer = ask(model, url, VERIFY_PROMPT, VERIFY_SCHEMA, f"{user}\n\n[주장]\n{text}", cache,
                     "verify|" + hashlib.sha256(f"{key}|{VERIFY_VERSION}|{text}".encode()).hexdigest())
        for c in unit:
            c["verification"] = {"claim": text, **answer}
            if answer["verdict"] == "no":
                c["review_reasons"].append("검증 단계에서 아니오")


# 같은 질문을 설정을 바꿔 여러 번 던져 놓친 조건을 줄이고(합집합), 잘못 뽑힌 조건은 검증 단계가 거른다.
SAMPLES = [{}]
EXTRA_SAMPLE = {"temperature": 0.7, "seed": 1}


def ask(model: str, url: str, system: str, schema: dict, user: str, cache: dict, key: str,
        options: dict | None = None) -> dict:
    if options:
        key = f"{key}|{json.dumps(options, sort_keys=True)}"
    if key not in cache:
        response = httpx.post(f"{url}/api/chat", timeout=900, json={
            "model": model, "stream": False, "format": schema,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2000, **(options or {})},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        response.raise_for_status()
        cache[key] = json.loads(response.json()["message"]["content"])
    return cache[key]


def structure(row, model: str, url: str, cache: dict, samples: list[dict] = SAMPLES) -> dict:
    serv_id, name, target, selection = row
    source = "\n".join(t for t in (target, selection) if t and t.strip())
    user = f"[정책 원문: {name}]\n{source}"
    key = hashlib.sha256(f"{model}|{PROMPT_VERSION}|{serv_id}|{source}".encode()).hexdigest()
    started = time.time()
    merged, target_answers = [], []
    for options in samples:
        numbers = ask(model, url, NUMBER_PROMPT, NUMBER_SCHEMA, user, cache, "number|" + key, options)
        status = ask(model, url, STATUS_PROMPT, STATUS_SCHEMA, user, cache, "status|" + key, options)
        merged += number_conditions(numbers) + status_conditions(status)
        target_answers.append(ask(model, url, TARGET_PROMPT, TARGET_SCHEMA, user, cache, "target|" + key, options))
    merged += target_conditions({"groups": [g for a in target_answers for g in a["groups"]],
                                 "any_one_is_enough": any(a["any_one_is_enough"] for a in target_answers)})
    merged = [c for c in merged if not (c["input_field"] in BENEFIT_WORDS
                                        and c["input_field"].removesuffix(" 수급자") in name)]
    conditions = [review(c, source) for c in dedupe(merged)]
    grounded = {c["input_field"] for c in conditions if not c["review_reasons"]}
    conditions += [review(c, source) for c in candidates(source, grounded)]
    drop_open_categories(conditions, source)
    verify(conditions, user, model, url, cache, key)
    flag_conflicts(conditions)
    return {"serv_id": serv_id, "name": name, "prompt_version": PROMPT_VERSION, "model": model,
            "seconds": round(time.time() - started, 1), "source": source, "conditions": conditions}


def report(results: list[dict]) -> str:
    lines = [f"# 조건 구조화 초안 ({len(results)}개, {PROMPT_VERSION})", ""]
    for r in results:
        lines += [f"## {r['name']} ({r['serv_id']})", "", "```", r["source"], "```", ""]
        for i, c in enumerate(r["conditions"]):
            val = c["value"] if c["upper_value"] is None else f"{c['value']}~{c['upper_value']}"
            val = f"{val}{c['unit']}" if val is not None else ""
            group = f" (또는:{c['or_group']})" if c["or_group"] else ""
            extra = f" {c['values']}" if c["values"] else ""
            flag = f" ⚠{', '.join(c['review_reasons'])}" if c["review_reasons"] else ""
            lines.append(f"{i}. [{c['kind']}] **{c['input_field']}** {c['operator']} {val}{extra}{group}{flag}")
            lines.append(f"   - 원문: {c['evidence'][:100]}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="youth_welfare.db")
    parser.add_argument("--ids-file", help="구조화할 serv_id 목록(한 줄에 하나). 없으면 전체")
    parser.add_argument("--exclude-file", help="제외할 serv_id 목록")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="gemma3:12b")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--union", action="store_true", help="같은 질문을 한 번 더 던져 결과를 합친다")
    args = parser.parse_args(argv)

    read_ids = lambda path: {line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()}
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = db.execute("select serv_id, serv_name, target_details, selection_criteria from welfare_services "
                      "order by serv_id").fetchall()
    if args.ids_file:
        wanted = read_ids(args.ids_file)
        rows = [r for r in rows if r[0] in wanted]
    if args.exclude_file:
        skip = read_ids(args.exclude_file)
        rows = [r for r in rows if r[0] not in skip]

    cache = load_cache()
    started = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda row: structure(row, args.model, args.ollama_url, cache,
                                                             SAMPLES + [EXTRA_SAMPLE] if args.union else SAMPLES), rows))
    finally:
        # 중간에 실패해도 이미 받은 모델 답은 남겨 다음 실행에서 다시 묻지 않는다.
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    out = Path(args.out)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    out.with_suffix(".md").write_text(report(results), encoding="utf-8")
    print(f"{len(results)}개 정책 구조화 완료 ({time.time() - started:.0f}초) → {out}", file=sys.stderr)
    return 0


def load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}


if __name__ == "__main__":
    raise SystemExit(main())
