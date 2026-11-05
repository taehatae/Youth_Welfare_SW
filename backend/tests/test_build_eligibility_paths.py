import json

from scripts.build_eligibility_paths import REVIEWED, build, load_services, source_hash
from scripts.merge_reviewed import merge

PATH = {"id": "기본", "label": "기본", "kind": "기본", "conditions": []}


def test_reviewed_policy_is_dropped_when_source_changed_after_review():
    services = {"A": ("정책", "만 19세 이상", "소득 기준")}
    reviewed = {"A": {"serv_id": "A", "name": "정책", "source_sha256": source_hash("만 19세 이상", "소득 기준"), "paths": [PATH]}}

    policies, stale = build(services, reviewed, {})
    assert [p["serv_id"] for p in policies] == ["A"] and stale == []

    # API 원문이 바뀌면 검수본을 새 원문에 붙이지 않고 재검수 목록에 올린다.
    services["A"] = ("정책", "만 19세 이상", "소득 기준 변경")
    policies, stale = build(services, reviewed, {})
    assert policies == [] and stale == ["A"]


def test_reviewed_policy_without_hash_is_not_used():
    services = {"A": ("정책", "원문", None)}
    policies, stale = build(services, {"A": {"serv_id": "A", "name": "정책", "paths": [PATH]}}, {})
    assert policies == [] and stale == ["A"]


def test_merge_stamps_hash_and_keeps_batch_of_existing_policy():
    services = {"A": ("정책A", "원문A", None), "B": ("정책B", "원문B", None)}
    reviewed = {"version": 2, "policies": [{"serv_id": "A", "name": "정책A", "batch": 1, "paths": []}]}
    draft = {"batch": 3, "policies": [{"serv_id": "A", "name": "정책A", "status": "draft", "paths": [PATH]},
                                      {"serv_id": "B", "name": "정책B", "paths": [PATH]}]}

    merge(reviewed, draft, services, "2026-11-05")
    a, b = reviewed["policies"]
    assert (a["batch"], a["paths"], a["source_sha256"], a["reviewed_at"]) == (1, [PATH], source_hash("원문A", None), "2026-11-05")
    assert "status" not in a
    assert (b["batch"], b["source_sha256"]) == (3, source_hash("원문B", None))


def test_every_reviewed_policy_matches_current_source():
    services = load_services()
    for policy in json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"]:
        _, target, selection = services[policy["serv_id"]]
        assert policy.get("source_sha256") == source_hash(target, selection), policy["name"]
