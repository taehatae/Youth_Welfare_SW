"""격리 계정/메모리 DB에서 난이도 전달 경계와 진단 당시 조건 연결을 검증한다."""
from copy import deepcopy

import pytest

from app.models.account import AccountWorkspace
from app.models.eligibility_path import PolicyEligibility
from app.models.welfare_service import WelfareService
from app.services import structured_condition_service as base
from tests.test_account_flow import setup
from tests.test_personalized_condition_guides import prepare, view


def analysis(state):
    return next(a for a in state["current"]["analysis"]["matched"]["analysis_results"]
                if a["policy_id"] == "guide-test")


def test_exact_difficulty_is_private_and_not_persisted(setup, monkeypatch):
    client, db = setup
    account, public, request = prepare(client, db, monkeypatch, "본인 월소득", "lte", 2500000)
    stored = deepcopy(db.get(AccountWorkspace, account["account_id"]).state)
    for state in (public, stored, client.get("/api/v1/users/state").json()):
        a = analysis(state)
        assert a["eligibility_paths"][0]["difficulty"] is None
        assert a["eligibility_paths"][0]["conditions"][0]["difficulty"] is None
    assert analysis(public).get("evaluation_context") is None
    context = analysis(stored)["evaluation_context"]
    assert context["version"] == 1
    assert "3000000" not in str(context) and "current_value" not in str(context)
    response = view(client, request)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["difficulties"] == [{"path_id": "p", "condition_index": 0,
                                               "difficulty": 4.0, "difficulty_group": "money"}]
    assert db.get(AccountWorkspace, account["account_id"]).state == stored


@pytest.mark.parametrize("change", ["evidence", "value", "operator", "kind", "count", "source", "checks", "path_id"])
def test_all_personalization_requires_the_original_policy_graph(setup, monkeypatch, change):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    before = deepcopy(db.get(AccountWorkspace, account["account_id"]).state)
    record = db.get(PolicyEligibility, "guide-test")
    path = record.paths[0]
    c = path.conditions[0]
    if change == "evidence": c.evidence += " changed"
    if change == "value": c.value = 27
    if change == "operator": c.operator = "lte"
    if change == "kind": c.kind = "exclusion"
    if change == "count": path.conditions.clear()
    if change == "checks": path.checks = ["새 예외 확인"]
    if change == "path_id": path.path_key = "other"
    if change == "source":
        service = db.get(WelfareService, "guide-test")
        service.target_details += " changed"
        record.source_sha256 = base.source_hash(service)
    db.commit()
    response = view(client, request)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["difficulties"] == []
    assert response.json()["unavailable_reason"]
    assert db.get(AccountWorkspace, account["account_id"]).state == before


def test_legacy_snapshot_is_not_backfilled_or_rejudged(setup, monkeypatch):
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch)
    workspace = db.get(AccountWorkspace, account["account_id"])
    state = deepcopy(workspace.state)
    analysis(state).pop("evaluation_context", None)
    workspace.state = state
    db.commit()
    before = deepcopy(state)
    response = view(client, request).json()
    assert response["items"] == [] and response["difficulties"] == []
    assert response["unavailable_reason"] == "legacy_context_missing"
    assert workspace.state == before


def test_old_stored_scores_are_redacted_without_rewriting_the_snapshot(setup, monkeypatch):
    client, db = setup
    account, _, _ = prepare(client, db, monkeypatch)
    workspace = db.get(AccountWorkspace, account["account_id"])
    state = deepcopy(workspace.state)
    a = analysis(state)
    a["eligibility_paths"][0]["difficulty"] = 4.0
    a["eligibility_paths"][0]["conditions"][0]["difficulty"] = 4.0
    workspace.state = state
    db.commit()
    response = client.get("/api/v1/users/state").json()
    assert analysis(response)["eligibility_paths"][0]["difficulty"] is None
    assert analysis(response)["eligibility_paths"][0]["conditions"][0]["difficulty"] is None
    assert workspace.state == state


def test_matched_and_refresh_protect_scores_and_preserve_the_original_diagnosis(setup, monkeypatch):
    client, db = setup
    account, public, request = prepare(client, db, monkeypatch, "본인 월소득", "lte", 2500000)
    workspace = db.get(AccountWorkspace, account["account_id"])
    before = deepcopy(workspace.state["diagnosis"])
    response = client.get("/api/v1/welfare/matched", params={"user_id": public["current"]["analysis"]["userId"]})
    assert response.status_code == 200
    row = next(a for a in response.json()["analysis_results"] if a["policy_id"] == "guide-test")
    assert row["eligibility_paths"][0]["difficulty"] is None
    assert row["eligibility_paths"][0]["conditions"][0]["difficulty"] is None
    refreshed = client.post("/api/v1/welfare/refresh")
    assert refreshed.status_code == 200
    assert workspace.state["diagnosis"] == before
    private = view(client, {**request, "snapshot": "diagnosis"})
    assert private.status_code == 200 and private.json()["difficulties"][0]["difficulty"] == 4
    client.post("/api/v1/auth/logout")
    denied = view(client, request)
    assert denied.status_code == 401 and "difficulties" not in denied.json()


@pytest.mark.parametrize("change", ["year", "reference"])
def test_changed_income_calculation_context_never_reinterprets_the_saved_profile(setup, monkeypatch, change):
    from datetime import datetime
    from app.services.median_income_reference import MONTHLY_MEDIAN_INCOME_WON
    client, db = setup
    account, _, request = prepare(client, db, monkeypatch, "가구 소득인정액", "lte", 50,
        profile={"eligibility_conditions": {"household_size": 1,
                 "additional_conditions": {"recognized_household_income_won": 3000000}}})
    workspace = db.get(AccountWorkspace, account["account_id"])
    if change == "reference":
        table = MONTHLY_MEDIAN_INCOME_WON[datetime.now().year]
        monkeypatch.setitem(table, 1, table[1] + 1)
    else:
        state = deepcopy(workspace.state)
        state["current"]["checkedAt"] = f"{datetime.now().year-1}-01-01T00:00:00Z"
        workspace.state = state
        db.commit()
        request = {**request, "checked_at": state["current"]["checkedAt"]}
    before = deepcopy(workspace.state)
    result = view(client, request).json()
    assert result["items"] == [] and result["difficulties"] == []
    assert result["unavailable_reason"] == "calculation_changed"
    assert workspace.state == before


@pytest.mark.parametrize("change", ["order", "passed_value", "passed_evidence"])
def test_passed_conditions_and_their_order_are_also_verified(setup, monkeypatch, change):
    from app.models.eligibility_path import EligibilityPathCondition
    client, db = setup
    account, _, _ = prepare(client, db, monkeypatch)
    record = db.get(PolicyEligibility, "guide-test")
    path = record.paths[0]
    path.conditions.append(EligibilityPathCondition(field="만 나이", operator="lte", value=40,
                                                  kind="requirement", values=[], evidence="upper"))
    db.commit()
    profile = db.get(AccountWorkspace, account["account_id"]).state["current"]["profile"]
    state = client.post("/api/v1/welfare/diagnose", json=profile).json()["current"]
    request = {"snapshot": "current", "profile_key": state["profileKey"],
               "checked_at": state["checkedAt"], "policy_id": "guide-test"}
    assert view(client, request).json()["difficulties"]
    before = deepcopy(db.get(AccountWorkspace, account["account_id"]).state)
    if change == "order":
        # DB 정렬 키 교환 없이 정책 조건 자체의 순서를 교환한다.
        a, b = path.conditions
        a.operator, b.operator = b.operator, a.operator
        a.value, b.value = b.value, a.value
        a.evidence, b.evidence = b.evidence, a.evidence
    elif change == "passed_value":
        path.conditions[-1].value = 50
    else:
        path.conditions[-1].evidence = "changed upper evidence"
    db.commit()
    result = view(client, request).json()
    assert result["items"] == [] and result["difficulties"] == []
    assert db.get(AccountWorkspace, account["account_id"]).state == before


def test_fingerprints_normalize_numbers_but_preserve_meaning_and_contain_no_input(setup, monkeypatch):
    from app.services.eligibility_snapshot_context import create_context
    client, db = setup
    _, _, _ = prepare(client, db, monkeypatch)
    record = db.get(PolicyEligibility, "guide-test")
    service = db.get(WelfareService, "guide-test")
    original = create_context(service, record)
    record.paths[0].conditions[0].value = 26.0
    assert create_context(service, record) == original
    record.paths[0].conditions[0].kind = "exclusion"
    assert create_context(service, record) != original


def test_calculation_fingerprint_ignores_line_endings(tmp_path):
    from app.services.eligibility_snapshot_context import code_hash
    lf, crlf = tmp_path / "lf.py", tmp_path / "crlf.py"
    lf.write_bytes(b"a = 1\nb = 2\n")
    crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert code_hash(lf) == code_hash(crlf)
    lf.write_bytes(b"a = 1\nb = 3\n")
    assert code_hash(lf) != code_hash(crlf)
