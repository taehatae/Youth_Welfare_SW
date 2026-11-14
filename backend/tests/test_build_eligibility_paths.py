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


def test_data_files_have_no_duplicate_policies():
    from collections import Counter
    from scripts.build_eligibility_paths import DATA, GOLD_FILES, OUT

    gold = Counter(k for name in GOLD_FILES for k in json.loads((DATA / name).read_text(encoding="utf-8")) if not k.startswith("_"))
    assert [k for k, n in gold.items() if n > 1] == []  # 한 정책은 정답지 파일 하나에만 있다
    reviewed = Counter(p["serv_id"] for p in json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"])
    assert [k for k, n in reviewed.items() if n > 1] == []
    seed = [p["serv_id"] for p in json.loads(OUT.read_text(encoding="utf-8"))["policies"]]
    services = load_services()
    assert len(seed) == len(set(seed)) and set(seed) == set(services)  # 152개 정책이 시드에 정확히 한 번씩
    assert set(gold) == set(services)  # 모든 정책에 정답지가 있다(검수본이 있으면 검수본이 우선)


def test_every_reviewed_policy_matches_current_source():
    services = load_services()
    for policy in json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"]:
        _, target, selection = services[policy["serv_id"]]
        assert policy.get("source_sha256") == source_hash(target, selection), policy["name"]


def test_merge_preserves_explicit_draft_author_in_generated_seed():
    services = {"A": ("정책A", "원문A", None)}
    reviewed = {"version": 2, "policies": []}
    draft = {"batch": 3, "drafted_by": "Codex",
             "policies": [{"serv_id": "A", "name": "정책A", "paths": [PATH]}]}

    merge(reviewed, draft, services, "2026-11-06")

    assert reviewed["policies"][0]["drafted_by"] == "Codex"
    policies, stale = build(services, {p["serv_id"]: p for p in reviewed["policies"]}, {})
    assert stale == []
    assert policies[0]["drafted_by"] == "Codex"
    assert policies[0]["reviewed_by"] == "human(3차)"
    assert policies[0]["reviewed_at"] == "2026-11-06"


def test_batch3_review_date_falls_back_to_registered_batch_date():
    services = {"A": ("정책A", "원문A", None)}
    reviewed = {"A": {"serv_id": "A", "name": "정책A", "batch": 3,
                      "source_sha256": source_hash("원문A", None), "paths": [PATH]}}

    policies, stale = build(services, reviewed, {})

    assert stale == []
    assert policies[0]["reviewed_at"] == "2026-11-11"


def test_seed_distinguishes_60_human_reviewed_and_92_converted_policies():
    from scripts.build_eligibility_paths import OUT

    reviewed = {p["serv_id"]: p for p in json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"]}
    seed = json.loads(OUT.read_text(encoding="utf-8"))["policies"]
    assert len(seed) == len({p["serv_id"] for p in seed}) == 152
    human = [p for p in seed if p["serv_id"] in reviewed]
    converted = [p for p in seed if p["serv_id"] not in reviewed]
    assert len(human) == 60 and len(converted) == 92
    assert all(p["drafted_by"] == "converted" and p["reviewed_by"] == "claude" for p in converted)
    for policy in human:
        original = reviewed[policy["serv_id"]]
        batch = original.get("batch", 1)
        assert policy["reviewed_by"] == ("claude+human(1차)" if batch == 1 else f"human({batch}차)")
        assert policy.get("common", []) == original.get("common", [])
        assert policy["paths"] == original["paths"]
        if batch in (3, 4):
            assert policy["drafted_by"] == "Codex"
            assert policy["reviewed_at"] == original["reviewed_at"]  # 재검수일(2026-11-11)


def test_batch4_review_date_falls_back_to_registered_batch_date():
    services = {"A": ("정책A", "원문A", None)}
    reviewed = {"A": {"serv_id": "A", "name": "정책A", "batch": 4,
                      "source_sha256": source_hash("원문A", None), "paths": [PATH]}}

    policies, stale = build(services, reviewed, {})

    assert stale == []
    assert policies[0]["reviewed_at"] == "2026-11-11"
    assert policies[0]["reviewed_by"] == "human(4차)"


def test_batch4_merge_keeps_existing_reviewed_policies_unchanged():
    from copy import deepcopy

    existing = [{"serv_id": f"OLD-{n}", "name": f"기존 정책 {n}", "batch": n // 10 + 1,
                 "source_sha256": "unchanged", "reviewed_at": "2026-11-02", "paths": [PATH]}
                for n in range(30)]
    reviewed = {"version": 2, "policies": deepcopy(existing)}
    draft = {"batch": 4, "drafted_by": "Codex", "policies": [
        {"serv_id": "NEW", "name": "신규 정책", "paths": [PATH]}]}

    merge(reviewed, draft, {"NEW": ("신규 정책", "원문", None)}, "2026-11-06")

    assert reviewed["policies"][:30] == existing
    assert len(reviewed["policies"]) == 31
    assert reviewed["policies"][-1]["batch"] == 4
    assert reviewed["policies"][-1]["source_sha256"] == source_hash("원문", None)


def test_batch3_4_reviewed_content_matches_rechecked_draft():
    # 3·4차 20개는 2026-11-11 재검수(eligibility_paths_recheck34_draft.json)를 반영한 내용이다.
    from scripts.build_eligibility_paths import DATA

    draft = json.loads((DATA / "eligibility_paths_recheck34_draft.json").read_text(encoding="utf-8"))
    reviewed = json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"]
    actual = {p["serv_id"]: p for p in reviewed if p.get("batch") in (3, 4)}
    assert len(actual) == len(draft["policies"]) == 20
    assert set(actual) == {p["serv_id"] for p in draft["policies"]}
    for policy in draft["policies"]:
        saved = actual[policy["serv_id"]]
        assert all(saved[key] == value for key, value in policy.items())
        assert saved["drafted_by"] == "Codex"
