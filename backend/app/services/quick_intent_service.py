"""간편 정책 찾기: 사용자가 쓴 문장을 정책 분야로 바꾼다.

예: "자취 관련 정책 없어?" → 주거. 판정은 하지 않고 분야만 고른다(판정은 기존 엔진이 한다).
1. 로컬 LLM(Ollama)에 분야 하나와 검색어 몇 개를 고르게 한다. 정해진 분야 밖의 답은 버린다.
2. LLM이 꺼져 있거나 모르겠다고 하면 단어 사전으로 고른다.
입력 문장은 저장하거나 기록하지 않는다.
"""
import json
import re
import threading

import httpx

from app.core.config import settings
from app.services.policy_catalog_service import CATEGORIES

# 분야 → 사람들이 흔히 쓰는 말. 원문에 없는 말(자취·알바 등)을 분야로 잇는 데만 쓴다.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "housing": ("자취", "월세", "전세", "보증금", "원룸", "투룸", "오피스텔", "이사", "집 구", "살 집", "집값", "내 집", "방 구", "주거", "주택",
                "임대", "무주택", "독립", "기숙사", "셰어하우스", "청약", "관리비"),
    "employment": ("취업", "취직", "일자리", "구직", "알바", "아르바이트", "인턴", "직장", "회사", "면접", "이력서",
                   "창업", "실업", "퇴사", "실직", "구인", "채용", "일하"),
    "finance": ("대출", "적금", "저축", "통장", "자산", "빚", "부채", "금융", "이자", "신용", "목돈", "돈 모", "재테크"),
    "education": ("학비", "등록금", "장학", "학자금", "공부", "학교", "대학", "자격증", "교육", "강의", "수강", "학원"),
    "health": ("건강", "병원", "치료", "의료", "검진", "우울", "마음", "정신", "심리", "약값", "수술", "아프"),
    "living": ("생활비", "돌봄", "육아", "임신", "출산", "아기", "양육", "식비", "생계", "공과금", "끼니"),
    "culture": ("문화", "여가", "공연", "영화", "여행", "운동", "체육", "예술", "취미", "전시"),
    "safety": ("전세사기", "법률", "소송", "사기", "폭력", "위기", "안전", "피해", "변호사", "범죄"),
}
# 문장 일부를 찾는 데만 쓰고 검색어로는 내보내지 않는 말
STEMS = {"방 구", "집 구", "살 집", "내 집", "일하", "돈 모", "아프"}
CHOICES = [key for key in CATEGORIES if key != "other"]
UNKNOWN = "unknown"
PROMPT_VERSION = "intent-1"
MAX_KEYWORDS = 5

SYSTEM = (
    "청년 복지 정책 안내 챗봇이다. 사용자가 쓴 문장을 읽고, 찾고 싶은 정책 분야를 아래에서 하나만 고른다.\n"
    + "\n".join(f"- {key}: {CATEGORIES[key][0]}" for key in CHOICES)
    + "\n어느 분야인지 알 수 없거나 복지 정책과 무관하면 unknown을 고른다.\n"
    "keywords에는 정책 목록에서 검색할 짧은 단어(2~6자)를 최대 5개 적는다. 사용자의 말을 정책에서 쓰는 말로 바꾼다"
    "(예: 자취 → 월세, 전세, 주거, 무주택). 사용자의 개인정보(나이·소득·이름)는 적지 않는다."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": [*CHOICES, UNKNOWN]},
        "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_KEYWORDS},
    },
    "required": ["category", "keywords"],
}
# 공개 API라 동시에 LLM을 부르는 수를 제한한다. 넘치면 기다리지 않고 사전으로 답한다.
_LLM_SLOTS = threading.BoundedSemaphore(2)
KEYWORD_PATTERN = re.compile(r"^[가-힣A-Za-z·]{2,10}$")


def _clean_keywords(words) -> list[str]:
    out: list[str] = []
    for word in words if isinstance(words, list) else []:
        word = str(word).strip()
        if KEYWORD_PATTERN.match(word) and word not in out:
            out.append(word)
    return out[:MAX_KEYWORDS]


def from_dictionary(text: str) -> tuple[str | None, list[str]]:
    """사전에 있는 말이 가장 많이(길게) 나온 분야. 없으면 None."""
    compact = re.sub(r"\s+", " ", text)
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for key, words in KEYWORDS.items():
        found = [w for w in words if w in compact]
        if found:
            scores[key] = sum(len(w) for w in found)
            hits[key] = found
    if not scores:
        return None, []
    best = max(scores, key=lambda k: (scores[k], -CHOICES.index(k)))
    return best, _clean_keywords([w for w in hits[best] if w not in STEMS])


def from_llm(text: str) -> tuple[str | None, list[str]]:
    """LLM 답. 연결 실패·형식 오류·동시 요청 초과는 None으로 돌려 사전으로 넘긴다."""
    if not _LLM_SLOTS.acquire(blocking=False):
        return None, []
    try:
        response = httpx.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.intent_model,
                "stream": False,
                "keep_alive": "30m",
                "format": SCHEMA,
                "options": {"temperature": 0, "num_predict": 200},
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
            },
            timeout=settings.intent_timeout_seconds,
        )
        response.raise_for_status()
        answer = json.loads(response.json()["message"]["content"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None, []
    finally:
        _LLM_SLOTS.release()
    category = answer.get("category") if isinstance(answer, dict) else None
    if category not in CHOICES:
        return None, []
    return category, _clean_keywords(answer.get("keywords"))


def interpret(text: str) -> dict:
    text = text.strip()
    category, keywords, source = None, [], "none"
    if settings.use_llm_intent:
        category, keywords = from_llm(text)
        source = "llm" if category else "none"
    if not category:
        category, keywords = from_dictionary(text)
        source = "dictionary" if category else "none"
    return {
        "category": category,
        "category_label": CATEGORIES[category][0] if category else None,
        "keywords": keywords,
        "source": source,
    }
