"""간편 찾기 문장 해석: 사전·LLM 답 검증·실패 시 대체·API 비저장을 확인한다(실제 LLM은 부르지 않는다)."""
import json

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.account import Account, AccountSession
from app.models.user import User
from app.services import quick_intent_service as intent
from tests.test_account_flow import setup  # noqa: F401

URL = "/api/v1/quick-finder/interpret"


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self.content}}


def fake_llm(monkeypatch, content=None, error=None):
    calls = []

    def post(url, json=None, timeout=None):  # noqa: A002
        calls.append(json)
        if error:
            raise error
        return FakeResponse(content)

    monkeypatch.setattr(settings, "use_llm_intent", True)
    monkeypatch.setattr(intent.httpx, "post", post)
    return calls


@pytest.mark.parametrize(("text", "category"), [
    ("혹시 자취 관련 정책 없어?", "housing"),
    ("알바 구하는 중이에요", "employment"),
    ("등록금이 걱정돼요", "education"),
    ("요즘 우울해서 상담 받고 싶어", "health"),
    ("전세사기 당했어요", "safety"),
])
def test_dictionary_maps_everyday_words_to_category(text, category):
    assert intent.from_dictionary(text)[0] == category


def test_dictionary_does_not_read_recruiting_as_housing():
    assert intent.from_dictionary("청년 모집 중인 정책 알려줘")[0] != "housing"


def test_busy_llm_falls_back_without_waiting(monkeypatch):
    calls = fake_llm(monkeypatch, json.dumps({"category": "health", "keywords": []}))
    monkeypatch.setattr(intent, "_LLM_SLOTS", intent.threading.BoundedSemaphore(1))
    intent._LLM_SLOTS.acquire()
    try:
        assert intent.interpret("자취 관련 정책 없어?")["source"] == "dictionary"
    finally:
        intent._LLM_SLOTS.release()
    assert calls == []


def test_dictionary_returns_none_for_unrelated_text():
    assert intent.from_dictionary("오늘 날씨 어때?") == (None, [])


def test_dictionary_keywords_skip_word_stems():
    assert intent.from_dictionary("집 구하는데 보증금이 없어") == ("housing", ["보증금"])
    assert intent.from_dictionary("일하고 싶어요") == ("employment", [])


def test_llm_answer_is_used_and_keywords_are_cleaned(monkeypatch):
    calls = fake_llm(monkeypatch, json.dumps({"category": "housing", "keywords": ["월세", "주거", "25세", "월세", "a"]}))
    result = intent.interpret("자취하는데 도움 받을 거 있어?")
    assert result == {"category": "housing", "category_label": "주거", "keywords": ["월세", "주거"], "source": "llm"}
    assert calls[0]["format"]["properties"]["category"]["enum"][-1] == "unknown"


def test_llm_category_outside_list_falls_back_to_dictionary(monkeypatch):
    fake_llm(monkeypatch, json.dumps({"category": "other", "keywords": []}))
    assert intent.interpret("월세가 너무 비싸요")["source"] == "dictionary"
    fake_llm(monkeypatch, json.dumps({"category": "unknown", "keywords": []}))
    assert intent.interpret("오늘 날씨 어때?") == {"category": None, "category_label": None, "keywords": [],
                                                 "source": "none"}


@pytest.mark.parametrize("error", [httpx.ConnectError("off"), httpx.ReadTimeout("slow")])
def test_llm_failure_falls_back_to_dictionary(monkeypatch, error):
    fake_llm(monkeypatch, error=error)
    result = intent.interpret("자취 관련 정책 없어?")
    assert result["category"] == "housing" and result["source"] == "dictionary"


def test_broken_llm_json_falls_back(monkeypatch):
    fake_llm(monkeypatch, "not json")
    assert intent.interpret("등록금 지원 있어?")["source"] == "dictionary"


def test_llm_can_be_turned_off(monkeypatch):
    calls = fake_llm(monkeypatch, json.dumps({"category": "health", "keywords": []}))
    monkeypatch.setattr(settings, "use_llm_intent", False)
    assert intent.interpret("자취 관련 정책 없어?")["source"] == "dictionary"
    assert calls == []


def test_interpret_api_is_public_and_stores_nothing(setup, monkeypatch):  # noqa: F811
    client, db = setup
    fake_llm(monkeypatch, json.dumps({"category": "housing", "keywords": ["월세"]}))
    before = [db.scalar(select(func.count()).select_from(m)) for m in (User, Account, AccountSession)]
    response = client.post(URL, json={"text": "자취 관련 정책 없어?"})
    assert response.status_code == 200
    assert response.json() == {"category": "housing", "category_label": "주거", "keywords": ["월세"], "source": "llm"}
    assert "자취" not in response.text
    assert [db.scalar(select(func.count()).select_from(m)) for m in (User, Account, AccountSession)] == before


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "가" * 201}, {"text": "월세", "age": 25}, {}])
def test_interpret_api_rejects_bad_input(setup, monkeypatch, body):  # noqa: F811
    client, _ = setup
    fake_llm(monkeypatch, error=httpx.ConnectError("off"))
    assert client.post(URL, json=body).status_code == 422
