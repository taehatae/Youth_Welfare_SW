"""진단할 때 LLM(로컬 Ollama)이 정책 원문과 사용자 입력을 직접 비교한다 (실험 기능).

작은 모델도 정확히 답하도록 일을 두 단계로 나눈다.
1. 조건 찾기: 정책 원문에서 자격 조건만 뽑는다. 사용자와 무관하므로 정책별로 한 번만 묻고 저장한다.
2. 판정: 뽑은 조건마다 어느 사용자 정보 항목과 비교했는지 고르고 충족 / 미충족 / 확인 필요를 답한다.
   화면에 보여줄 사용자 값은 모델이 쓴 글이 아니라 고른 항목의 실제 값을 쓴다 (지어낸 사실 차단).
근거 구절이 원문에 그대로 없으면 충족·미충족으로 인정하지 않는다.
"""
import hashlib
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

PROMPT_VERSION = "2026-10-31-two-step-2"
CATEGORIES = ["age", "income", "region", "employment", "nationality", "target_group", "household", "education", "other"]
NO_FIELD = "해당 항목 없음"

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "evidence": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "requirement": {"type": "string"},
                    "kind": {"type": "string", "enum": ["requirement", "exclusion"]},
                    "applies_to": {"type": "string", "enum": ["applicant", "other_person"]},
                },
                "required": ["evidence", "name", "category", "requirement", "kind", "applies_to"],
            },
        }
    },
    "required": ["conditions"],
}
EXTRACT_PROMPT = """너는 복지 정책 원문에서 '지원 자격 조건'만 골라내는 도구다.
- 누가 지원받을 수 있는지(또는 누가 제외되는지)를 정하는 조건만 최대 6개 고른다.
- 신청 방법, 제출 서류, 홈페이지·회원가입 안내, 지원 내용·금액, 우대·가점, 선정 순위, 사업 운영 기준은 조건이 아니다.
- '또는'으로 이어진 대상 목록은 하나의 조건으로 묶는다.
- evidence에는 원문 구절을 글자 그대로 복사한다.
- kind: 해당해야 지원받는 조건은 requirement, 해당하면 제외되는 조건은 exclusion.
- applies_to: 신청자 본인에 대한 조건은 applicant, 외국인·자녀·보호자처럼 일부 다른 사람에게만 붙는 안내나 세부 조건은 other_person.
예시
- "만 19세 이상 34세 이하 청년" → requirement, applicant
- "고교·대학 재학생은 참여 대상에서 제외" → exclusion, applicant
- "※ 외국인 등록번호가 있는 외국인에 한해 회원가입 가능" → 가입 안내이므로 넣지 않는다
- "북한이탈주민 또는 그 자녀" → requirement, applicant"""

JUDGE_PROMPT = """너는 사용자가 복지 정책 조건 문구에 '해당하는지'만 확인하는 도구다.
가장 중요한 규칙: [사용자 정보]에 적힌 값만 쓴다. 적혀 있지 않은 사실은 절대 추측하지 않는다.
조건마다 다음 순서로 답한다.
1. profile_field: 이 문구와 직접 같은 내용을 담은 [사용자 정보] 항목 이름을 목록에서 그대로 고른다.
   직접 같은 내용이 아니면(예: 대중교통 이용 횟수, 건강 상태, 사업 참여 이력) "해당 항목 없음"을 고른다.
2. reasoning: 그 항목의 값과 문구를 비교하는 과정을 한 문장으로 쓴다. 숫자는 두 값을 나란히 적고 어느 쪽이 큰지 먼저 밝힌다.
3. matches: 사용자가 이 문구에 해당하면 yes, 확실히 해당하지 않으면 no,
   항목 값이 '미입력'이거나 맞는 항목이 없거나 '다만·예외적으로·관계없이' 같은 예외가 붙으면 unknown.
   문구가 '제외'를 말하더라도 판단은 똑같이 '사용자가 그 문구가 가리키는 사람인가'만 본다.
주의
- 국적과 특정 대상은 다르다. '대한민국 국민'이라는 사실만으로 북한이탈주민·국가유공자·결혼이민자·장애인이 되지 않는다.
- 가구 소득·소득인정액·중위소득 기준은 가구 소득 항목으로만 비교한다. 본인 소득으로 대신하지 않는다.
예시 (사용자: 만 나이 22세, 본인 연 환산 720만원, 현재 학생 예, 등록 장애인 아니오)
- "연소득 3,500만원 이하" → 본인 월평균 소득, "720만원은 3,500만원보다 작다", yes
- "연소득 500만원 이하" → 본인 월평균 소득, "720만원은 500만원보다 크다", no
- "고교·대학 재학생" (제외 문구) → 현재 학생(고교·대학 재학 중), "사용자는 재학생이다", yes
- "등록 장애인" → 등록 장애인, "사용자는 등록 장애인이 아니다", no
- "월 15회 이상 대중교통 이용자" → 해당 항목 없음, "이용 횟수 정보가 없다", unknown"""

CODE_LABELS = {
    "gender": {"MALE": "남성", "FEMALE": "여성"},
    "income_type": {"LABOR": "근로소득", "BUSINESS": "사업소득", "FREELANCE": "프리랜서 소득", "NONE": "소득 없음"},
    "housing_type": {"OWNED": "자가", "JEONSE": "전세", "MONTHLY": "월세", "FREE": "무상 거주", "OTHER": "기타"},
    "asset_range": {"UNDER_100M": "1억원 미만", "100M_200M": "1억~2억원", "200M_300M": "2억~3억원",
                    "300M_500M": "3억~5억원", "OVER_500M": "5억원 이상"},
    "employment": {"EMPLOYED": "재직(대기업·공공기관 등)", "EMPLOYED_SME": "중소기업 재직", "PART_TIME": "아르바이트",
                   "UNEMPLOYED": "미취업(구직 중)", "SELF_EMPLOYED": "자영업", "FREELANCER": "프리랜서",
                   "STUDENT": "학생", "OTHER": "기타"},
    "marital_status": {"SINGLE": "미혼", "MARRIED": "기혼", "DIVORCED": "이혼", "WIDOWED": "사별"},
    "nationality": {"KOREAN": "대한민국 국민(내국인)", "FOREIGN": "외국인(외국인등록번호 보유)"},
}
SPECIAL_TARGETS = {
    "VETERAN": "국가유공자·보훈대상자", "NK_DEFECTOR": "북한이탈주민",
    "MULTICULTURAL": "결혼이민자·다문화가족", "FARMER": "농업인·어업인",
}
YES_NO_LABEL = {"YES": "예", "NO": "아니오"}
DISPLAY_FIELD = {"income": "income_level", "household": "household", "education": "education"}

_cache_lock = threading.Lock()


def _manwon(won: int) -> str:
    return f"{won // 10_000:,}만원" if won % 10_000 == 0 else f"{won:,}원"


def _yes_no(value: Any) -> str:
    return YES_NO_LABEL.get(value, "미입력")


def _won(value: Any) -> str:
    return _manwon(int(value)) if isinstance(value, (int, float)) else "미입력"


def profile_fields(user, profile: dict | None) -> dict[str, str]:
    """LLM에 넘길 사용자 정보 (항목 이름 → 값). 입력하지 않은 항목은 '미입력'."""
    p = profile if isinstance(profile, dict) else {}
    extra = p.get("additional_conditions") if isinstance(p.get("additional_conditions"), dict) else {}
    monthly = int(user.income_level or 0)
    employment = extra.get("employment_detail") or user.employment_status
    fields = {
        "만 나이": f"{user.age}세",
        "거주지(주민등록)": user.region or "미입력",
        # 정책 원문이 대부분 만원 단위라 같은 단위로 적어 작은 모델의 비교 실수를 줄인다.
        "본인 월평균 소득": f"{_manwon(monthly)} (연 환산 {_manwon(monthly * 12)})",
        "주된 소득 종류": CODE_LABELS["income_type"].get(p.get("income_type"), "미입력"),
        "고용 상태": CODE_LABELS["employment"].get(employment, "미입력"),
        "성별": CODE_LABELS["gender"].get(p.get("gender"), "미입력"),
        "국적": CODE_LABELS["nationality"].get(extra.get("nationality"), "미입력"),
        "가구원 수": f"{p['household_size']}명" if p.get("household_size") else "미입력",
        "주거 형태": CODE_LABELS["housing_type"].get(p.get("housing_type"), "미입력"),
        "본인 명의 주택 보유": "보유" if p.get("owns_home") is True else "미보유" if p.get("owns_home") is False else "미입력",
        "본인 재산": CODE_LABELS["asset_range"].get(p.get("asset_range"), "미입력"),
        "현재 학생(고교·대학 재학 중)": _yes_no(p.get("student_status")),
        "등록 장애인": _yes_no(p.get("disability_status")),
        "혼인 상태": CODE_LABELS["marital_status"].get(p.get("marital_status"), "미입력"),
        "자녀 수": f"{p['children_count']}명" if p.get("children_count") is not None else "미입력",
        "기초생활보장 수급자": _yes_no(extra.get("basic_benefit_status")),
        "차상위계층": _yes_no(extra.get("near_poverty_status")),
        "한부모가족 지원 대상": _yes_no(extra.get("single_parent_support_status")),
        "가구 월소득": _won(extra.get("household_monthly_income_won")),
        "가구 소득인정액": _won(extra.get("recognized_household_income_won")),
        "아동복지시설·가정위탁 보호 경험": _yes_no(extra.get("child_welfare_protection_experience")),
        "구직 등록": _yes_no(extra.get("job_seek_registration")),
    }
    targets = extra.get("special_targets")
    for code, label in SPECIAL_TARGETS.items():
        fields[label] = ("예" if code in targets else "아니오") if isinstance(targets, list) else "미입력"
    return fields


def profile_text(user, profile: dict | None) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in profile_fields(user, profile).items())


def _source(service) -> str:
    return "\n".join(t.strip() for t in (service.target_details, service.selection_criteria) if t and t.strip())


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _cache_path() -> Path:
    path = Path(settings.llm_judgments_path)
    return path if path.is_absolute() else Path.cwd() / path


def _load_cache() -> dict:
    path = _cache_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if "extract" in data and "judge" in data else {"extract": {}, "judge": {}}


def _save(section: str, key: str, value: Any) -> None:
    with _cache_lock:
        data = _load_cache()
        data[section][key] = value
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join((settings.llm_model, PROMPT_VERSION, *parts)).encode("utf-8")).hexdigest()


def _chat(system: str, user_message: str, schema: dict) -> dict:
    last_error = None
    for _ in range(2):
        try:
            response = httpx.post(
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.llm_model,
                    "stream": False,
                    "format": schema,
                    "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3000},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_message}],
                },
                timeout=600,
            )
            response.raise_for_status()
            return json.loads(response.json()["message"]["content"])
        except (ValueError, KeyError) as exc:
            last_error = exc
    raise ValueError(f"LLM 응답을 해석하지 못했습니다: {last_error}")


def extract_conditions(service) -> list[dict]:
    """1단계: 정책 원문에서 자격 조건만 뽑는다. 원문에 근거가 없는 조건은 버린다."""
    source = _source(service)
    result = _chat(EXTRACT_PROMPT, f"[정책 원문: {service.serv_name}]\n{source}", EXTRACT_SCHEMA)
    normalized = _normalize(source)
    return [
        c for c in result.get("conditions", [])
        if _normalize(c.get("evidence")) and _normalize(c.get("evidence")) in normalized
    ]


def judge_conditions(conditions: list[dict], fields: dict[str, str]) -> dict:
    """2단계: 조건마다 비교할 사용자 정보 항목을 고르고 판정한다."""
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "profile_field": {"type": "string", "enum": [*fields, NO_FIELD]},
                        "reasoning": {"type": "string"},
                        "matches": {"type": "string", "enum": ["yes", "no", "unknown"]},
                    },
                    "required": ["index", "profile_field", "reasoning", "matches"],
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["results", "summary"],
    }
    listed = "\n".join(
        f"{i}. \"{c.get('evidence')}\"{' (제외 문구)' if c.get('kind') == 'exclusion' else ''}" for i, c in enumerate(conditions)
    )
    profile = "\n".join(f"- {key}: {value}" for key, value in fields.items())
    return _chat(JUDGE_PROMPT, f"[사용자 정보]\n{profile}\n\n[조건 목록]\n{listed}", schema)


def _condition(item: dict, user_value: str, status: str, message: str, guide: str) -> dict:
    return {
        "condition_type": DISPLAY_FIELD.get(item.get("category"), item.get("category") or "other"),
        "status": status,
        "current_value": user_value,
        "required_value": item.get("evidence", ""),
        "message": message,
        "action_guide": guide,
        "source_field": "llm",
        "source_text": item.get("evidence", ""),
    }


def to_analysis(service, conditions: list[dict], judgment: dict | None, fields: dict[str, str],
                error: str | None = None) -> dict:
    """두 단계 결과를 기존 진단 결과 형식으로 바꾼다."""
    verdicts = {r.get("index"): r for r in (judgment or {}).get("results", [])}
    met, unmet, review = [], [], []
    for index, item in enumerate(conditions):
        if item.get("applies_to") == "other_person":
            continue
        verdict = verdicts.get(index, {})
        field = verdict.get("profile_field")
        user_value = fields.get(field, "미입력")
        # 모델은 '사용자가 문구에 해당하는지'만 답하고, 필수·제외에 따른 충족 여부는 여기서 정한다.
        matches = verdict.get("matches")
        if field not in fields or user_value == "미입력" or matches not in ("yes", "no"):
            status = "unknown"
        elif item.get("kind") == "exclusion":
            status = "unmet" if matches == "yes" else "met"
        else:
            status = "met" if matches == "yes" else "unmet"
        name = item.get("name") or "조건"
        if status == "met":
            met.append(_condition(item, user_value, "passed", f"{name}을(를) 충족합니다.", "별도 조치가 필요하지 않습니다."))
        elif status == "unmet":
            unmet.append(_condition(item, user_value, "failed", f"{name}을(를) 충족하지 않습니다.", "조건과 입력 정보를 다시 확인하세요."))
        else:
            review.append(_condition(item, user_value, "needs_review", "입력한 정보만으로는 확인할 수 없습니다.",
                                     "공식 안내에서 세부 자격을 확인하세요."))
    evaluated = len(met) + len(unmet)
    summary = f"LLM 판정에 실패해 확인하지 못했습니다. ({error[:80]})" if error else (judgment or {}).get("summary", "")
    return {
        "policy_id": service.serv_id,
        "title": service.serv_name,
        "status": "ineligible" if unmet else "eligible",
        "match_score": round(len(met) / evaluated * 100, 1) if evaluated else 0.0,
        "evaluated_conditions": evaluated,
        "passed_conditions": len(met),
        "gap_conditions": unmet,
        "review_conditions": review,
        "recommendation_status": "condition_mismatch" if unmet else "priority_recommendation",
        "recommendation_reason": summary,
        "recommendation_uncertainty": None,
        "confirmed_conditions": met,
        "notes": [],
        "detail_url": service.detail_url,
    }


def analyze_all(services: list, user, eligibility_conditions: dict | None) -> list[dict]:
    """모든 정책을 병렬로 두 단계 판정한다. 이미 묻고 답한 결과는 저장된 것을 쓴다."""
    fields = profile_fields(user, eligibility_conditions)
    profile_key = json.dumps(fields, ensure_ascii=False, sort_keys=True)
    cache = _load_cache()

    def run(service):
        source = _source(service)
        if not source:
            return service, [], {"results": [], "summary": "정책 원문에 자격 조건이 없습니다."}, None
        try:
            extract_key = _hash(service.serv_id, source)
            conditions = cache["extract"].get(extract_key)
            if conditions is None:
                conditions = extract_conditions(service)
                _save("extract", extract_key, conditions)
            if not conditions:
                return service, [], {"results": [], "summary": "원문에서 자격 조건을 찾지 못했습니다."}, None
            judge_key = _hash(extract_key, profile_key)
            judgment = cache["judge"].get(judge_key)
            if judgment is None:
                judgment = judge_conditions(conditions, fields)
                _save("judge", judge_key, judgment)
            return service, conditions, judgment, None
        except (httpx.HTTPError, ValueError) as exc:
            return service, [], None, str(exc)

    with ThreadPoolExecutor(max_workers=max(1, settings.llm_concurrency)) as pool:
        results = list(pool.map(run, services))
    return [to_analysis(service, conditions, judgment, fields, error)
            for service, conditions, judgment, error in results]
