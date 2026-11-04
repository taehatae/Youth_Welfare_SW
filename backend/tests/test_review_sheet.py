import json
from pathlib import Path

from scripts.make_review_sheet import SNAPSHOT, problems

DATA = Path(__file__).resolve().parents[1] / "data"


def test_batch2_draft_uses_known_fields_and_quotes_source():
    draft = json.loads((DATA / "eligibility_paths_batch2_draft.json").read_text(encoding="utf-8"))
    reviewed = json.loads((DATA / "eligibility_paths_reviewed.json").read_text(encoding="utf-8"))
    services = {s["serv_id"]: s for s in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["data"]["welfare_services"]}

    ids = [p["serv_id"] for p in draft["policies"]]
    assert len(ids) == len(set(ids)) == 10
    assert not set(ids) & {p["serv_id"] for p in reviewed["policies"]}

    for policy in draft["policies"]:
        service = services[policy["serv_id"]]
        source = "\n".join(t for t in (service["target_details"], service["selection_criteria"]) if t and t.strip())
        conditions = policy.get("common", []) + [c for p in policy["paths"] for c in p.get("conditions", [])]
        assert [p for c in conditions for p in problems(c, source)] == [], policy["name"]


def test_problems_flags_unknown_field_and_missing_evidence():
    found = problems({"field": "장애 정도", "op": "is_true", "evidence": "원문에 없는 구절"}, "중증 장애인")
    assert found == ["입력 항목 없음: 장애 정도", "근거 구절이 원문에 없음: 장애 정도"]
