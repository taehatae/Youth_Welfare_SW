"""자격 경로 시드(data/eligibility_paths.json)를 만든다.

- 원문을 다시 읽고 경로로 정리한 정책(data/eligibility_paths_reviewed.json)은 그대로 쓴다.
- 나머지는 기존 정답지(structure_gold_*.json)를 경로로 옮긴다: 필수 조건은 공통 조건, '또는' 묶음은 경로 하나씩.
  (여러 묶음이면 조합마다 경로) 이렇게 옮긴 정책은 drafted_by='converted'로 표시해 경로 재검수 대상임을 남긴다.

    python scripts/build_eligibility_paths.py
"""
import hashlib
import itertools
import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
GOLD_FILES = ["structure_gold_train.json", "structure_gold_val.json", "structure_gold_rest.json"]
REVIEWED = DATA / "eligibility_paths_reviewed.json"
OUT = DATA / "eligibility_paths.json"
OPS = {"min": "gte", "max": "lte", "range": "between", "one_of": "one_of", "is_true": "is_true"}


def convert(item: dict) -> dict:
    return {k: v for k, v in {"field": item["field"], "op": OPS[item["op"]], "value": item.get("value"),
                              "upper": item.get("upper"), "values": item.get("values"),
                              "kind": item.get("kind")}.items() if v is not None}


def from_gold(entry: dict) -> dict:
    groups = entry.get("or", [])
    paths = []
    for combo in itertools.product(*groups) if groups else [()]:
        label = " · ".join(c["field"] + (f" {c['values'][0]}" if c.get("values") else "") for c in combo) or "기본"
        paths.append({"id": label, "label": label, "kind": "기본", "conditions": [convert(c) for c in combo]})
    return {"common": [convert(c) for c in entry.get("required", [])], "paths": paths}


def main() -> int:
    gold = {}
    for name in GOLD_FILES:
        gold.update({k: v for k, v in json.loads((DATA / name).read_text(encoding="utf-8")).items()
                     if not k.startswith("_")})
    reviewed = {p["serv_id"]: p for p in json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"]}
    db = sqlite3.connect(f"file:{DATA.parent / 'youth_welfare.db'}?mode=ro", uri=True)
    services = {r[0]: r[1:] for r in db.execute(
        "select serv_id, serv_name, target_details, selection_criteria from welfare_services")}
    missing = sorted(set(services) - set(gold) - set(reviewed))
    if missing:
        raise SystemExit(f"경로가 없는 정책이 있어요: {', '.join(missing)}")

    policies = []
    for serv_id in sorted(services):
        name, target, selection = services[serv_id]
        source = "\n".join(t for t in (target, selection) if t and t.strip())
        if serv_id in reviewed:
            body = {k: v for k, v in reviewed[serv_id].items() if k not in ("serv_id", "name")}
            meta = {"drafted_by": "claude", "reviewed_by": "claude+human(1차)", "reviewed_at": "2026-11-02"}
        else:
            body = from_gold(gold[serv_id])
            meta = {"drafted_by": "converted", "reviewed_by": "claude", "reviewed_at": "2026-10-31"}
        policies.append({"serv_id": serv_id, "name": name, "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                         "status": "reviewed", **meta, **body})
    OUT.write_text(json.dumps({"version": 2, "policies": policies}, ensure_ascii=False, indent=1), encoding="utf-8")
    paths = sum(len(p["paths"]) for p in policies)
    print(f"{len(policies)}개 정책 (원문 재정리 {len(reviewed)}개), 경로 {paths}개 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
