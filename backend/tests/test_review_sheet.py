import json
from pathlib import Path

from scripts.make_review_sheet import SNAPSHOT, problems

DATA = Path(__file__).resolve().parents[1] / "data"


def test_reviewed_paths_use_known_fields_and_quote_source():
    reviewed = json.loads((DATA / "eligibility_paths_reviewed.json").read_text(encoding="utf-8"))
    services = {s["serv_id"]: s for s in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["data"]["welfare_services"]}

    ids = [p["serv_id"] for p in reviewed["policies"]]
    assert len(ids) == len(set(ids)) == 60  # 1·2·3·4차 각 10개, 5차 20개, 겹치지 않음
    assert sum(p.get("batch", 1) == 1 for p in reviewed["policies"]) == 10
    assert sum(p.get("batch") == 2 for p in reviewed["policies"]) == 10
    assert sum(p.get("batch") == 3 for p in reviewed["policies"]) == 10
    assert sum(p.get("batch") == 4 for p in reviewed["policies"]) == 10
    assert sum(p.get("batch") == 5 for p in reviewed["policies"]) == 20

    for policy in (p for p in reviewed["policies"] if p.get("batch") in (2, 3, 4, 5)):  # 1차는 근거를 요약해 적은 곳이 있어 제외
        service = services[policy["serv_id"]]
        source = "\n".join(t for t in (service["target_details"], service["selection_criteria"]) if t and t.strip())
        conditions = policy.get("common", []) + [c for p in policy["paths"] for c in p.get("conditions", [])]
        assert [p for c in conditions for p in problems(c, source)] == [], policy["name"]


def test_problems_flags_unknown_field_and_missing_evidence():
    found = problems({"field": "장애 정도", "op": "is_true", "evidence": "원문에 없는 구절"}, "중증 장애인")
    assert found == ["입력 항목 없음: 장애 정도", "근거 구절이 원문에 없음: 장애 정도"]
