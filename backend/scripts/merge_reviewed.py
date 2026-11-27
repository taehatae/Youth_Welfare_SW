"""채점을 마치고 고친 초안을 검수본(data/eligibility_paths_reviewed.json)에 합친다.

정책마다 지금 원문의 해시(source_sha256)와 검수일을 함께 기록한다. 나중에 원문이 바뀌면
build_eligibility_paths.py가 해시를 비교해 그 정책을 시드에서 빼고 재검수 목록에 올린다.

    python scripts/merge_reviewed.py data/eligibility_paths_batchN_draft.json
    python scripts/merge_reviewed.py --stamp-existing      # 해시가 없는 기존 검수본에 지금 원문 해시 기록

이미 검수본에 있는 정책은 새 내용으로 바꾸고 차수(batch)는 그대로 둔다.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_eligibility_paths import REVIEWED, load_services, source_hash  # noqa: E402

DRAFT_ONLY_KEYS = ("status", "note")


def merge(reviewed: dict, draft: dict, services: dict, today: str) -> list[str]:
    by_id = {p["serv_id"]: i for i, p in enumerate(reviewed["policies"])}
    changed = []
    for policy in draft["policies"]:
        serv_id = policy["serv_id"]
        _, target, selection = services[serv_id]
        old = reviewed["policies"][by_id[serv_id]] if serv_id in by_id else None
        batch = old.get("batch", 1) if old else draft["batch"]
        item = {k: v for k, v in policy.items() if k not in DRAFT_ONLY_KEYS + ("batch", "source_sha256", "reviewed_at")}
        if draft.get("drafted_by"):
            item.setdefault("drafted_by", draft["drafted_by"])
        item.update({"batch": batch, "source_sha256": source_hash(target, selection), "reviewed_at": today})
        if old:
            reviewed["policies"][by_id[serv_id]] = item
        else:
            reviewed["policies"].append(item)
        changed.append(f"{'바꿈' if old else '추가'} {serv_id} {policy['name']}")
    return changed


def stamp_existing(reviewed: dict, services: dict) -> list[str]:
    stamped = []
    for policy in reviewed["policies"]:
        if not policy.get("source_sha256"):
            _, target, selection = services[policy["serv_id"]]
            policy["source_sha256"] = source_hash(target, selection)
            stamped.append(f"해시 기록 {policy['serv_id']} {policy['name']}")
    return stamped


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    reviewed = json.loads(REVIEWED.read_text(encoding="utf-8"))
    services = load_services()
    if argv[0] == "--stamp-existing":
        lines = stamp_existing(reviewed, services)
    else:
        draft = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        lines = merge(reviewed, draft, services, date.today().isoformat())
    REVIEWED.write_text(json.dumps(reviewed, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines) or "바뀐 것 없음")
    print(f"검수본 {len(reviewed['policies'])}개 → {REVIEWED.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
