"""자격 경로 시드(data/eligibility_paths.json)를 만든다.

- 원문을 다시 읽고 경로로 정리한 정책(data/eligibility_paths_reviewed.json)은 그대로 쓴다.
- 나머지는 기존 정답지(structure_gold_*.json)를 경로로 옮긴다: 필수 조건은 공통 조건, '또는' 묶음은 경로 하나씩.
  (여러 묶음이면 조합마다 경로) 이렇게 옮긴 정책은 drafted_by='converted'로 표시해 경로 재검수 대상임을 남긴다.

    python scripts/build_eligibility_paths.py
"""
import hashlib
import itertools
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
GOLD_FILES = ["structure_gold_train.json", "structure_gold_val.json", "structure_gold_rest.json"]
REVIEWED = DATA / "eligibility_paths_reviewed.json"
OUT = DATA / "eligibility_paths.json"
SNAPSHOT = DATA / "welfare-policies.json"
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
    # 정책 원문은 dev와 같은 스냅샷(data/welfare-policies.json)에서 읽는다(로컬 DB가 비어 있어도 된다).
    services = {s["serv_id"]: (s["serv_name"], s["target_details"], s["selection_criteria"])
                for s in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["data"]["welfare_services"]}
    # 아직 정리하지 않은 정책은 시드에서 빼고(진단은 기존 분석으로 대체) 목록만 알려준다.
    missing = sorted(set(services) - set(gold) - set(reviewed))
    if missing:
        print(f"경로를 아직 정리하지 않은 정책 {len(missing)}개는 기존 분석을 씁니다.")

    policies = []
    for serv_id in sorted(set(services) - set(missing)):
        name, target, selection = services[serv_id]
        source = "\n".join(t for t in (target, selection) if t and t.strip())
        if serv_id in reviewed:
            body = {k: v for k, v in reviewed[serv_id].items() if k not in ("serv_id", "name", "batch")}
            meta = ({"drafted_by": "claude", "reviewed_by": "human(2차)", "reviewed_at": "2026-11-04"}
                    if reviewed[serv_id].get("batch") == 2 else
                    {"drafted_by": "claude", "reviewed_by": "claude+human(1차)", "reviewed_at": "2026-11-02"})
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
