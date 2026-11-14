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
GOLD_FILES = ["structure_gold_train.json", "structure_gold_val.json", "structure_gold_rest.json", "structure_gold_new57.json"]
REVIEWED = DATA / "eligibility_paths_reviewed.json"
OUT = DATA / "eligibility_paths.json"
SNAPSHOT = DATA / "welfare-policies.json"
BATCH_DATES = {1: "2026-11-02", 2: "2026-11-04", 3: "2026-11-11", 4: "2026-11-11"}  # 3·4차는 장지훈 재검수일
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


def source_hash(target: str | None, selection: str | None) -> str:
    """판정기(structured_condition_service.source_hash)와 같은 방식으로 원문 해시를 만든다."""
    return hashlib.sha256("\n".join(t for t in (target, selection) if t and t.strip()).encode()).hexdigest()


def load_services() -> dict:
    # 정책 원문은 dev와 같은 스냅샷(data/welfare-policies.json)에서 읽는다(로컬 DB가 비어 있어도 된다).
    return {s["serv_id"]: (s["serv_name"], s["target_details"], s["selection_criteria"])
            for s in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["data"]["welfare_services"]}


def build(services: dict, reviewed: dict, gold: dict) -> tuple[list[dict], list[str]]:
    """시드 정책 목록과 '원문이 바뀌어 재검수가 필요한' 검수본 정책 목록을 돌려준다.

    검수본은 검수할 때 본 원문의 해시(source_sha256)를 갖고 있다. 지금 원문과 다르면
    검수 내용이 새 원문과 맞는지 알 수 없으므로 시드에서 빼고(진단은 기존 분석) 재검수 목록에 올린다.
    """
    policies, stale = [], []
    for serv_id in sorted(set(services) & (set(gold) | set(reviewed))):
        name, target, selection = services[serv_id]
        current = source_hash(target, selection)
        if serv_id in reviewed:
            item = reviewed[serv_id]
            if item.get("source_sha256") != current:
                stale.append(serv_id)
                continue
            body = {k: v for k, v in item.items() if k not in ("serv_id", "name", "batch", "source_sha256", "reviewed_at")}
            # 차수(batch)가 없는 정책은 1차 검수본이다. 차수별 검수일은 BATCH_DATES에 추가한다.
            batch = item.get("batch", 1)
            meta = {"drafted_by": "claude",
                    "reviewed_by": "claude+human(1차)" if batch == 1 else f"human({batch}차)",
                    "reviewed_at": item.get("reviewed_at") or BATCH_DATES.get(batch, "")}
        else:
            # 정답지 변환본은 검수 당시 원문 해시가 없어 지금 원문 기준으로 기록한다(재검수로 모두 대체할 대상).
            body = from_gold(gold[serv_id])
            meta = {"drafted_by": "converted", "reviewed_by": "claude", "reviewed_at": "2026-10-31"}
        policies.append({"serv_id": serv_id, "name": name, "source_sha256": current, "status": "reviewed", **meta, **body})
    return policies, stale


def main() -> int:
    gold = {}
    for name in GOLD_FILES:
        gold.update({k: v for k, v in json.loads((DATA / name).read_text(encoding="utf-8")).items()
                     if not k.startswith("_")})
    reviewed = {p["serv_id"]: p for p in json.loads(REVIEWED.read_text(encoding="utf-8"))["policies"]}
    services = load_services()
    policies, stale = build(services, reviewed, gold)
    # 아직 정리하지 않은 정책은 시드에서 빼고(진단은 기존 분석으로 대체) 개수만 알려준다.
    missing = len(set(services) - set(gold) - set(reviewed))
    if missing:
        print(f"경로를 아직 정리하지 않은 정책 {missing}개는 기존 분석을 씁니다.")
    if stale:
        print(f"[재검수 필요] 검수 후 원문이 바뀐 정책 {len(stale)}개를 시드에서 뺐습니다:")
        for serv_id in stale:
            print(f"  - {serv_id} {services[serv_id][0]}")
    OUT.write_text(json.dumps({"version": 2, "policies": policies}, ensure_ascii=False, indent=1), encoding="utf-8")
    paths = sum(len(p["paths"]) for p in policies)
    print(f"{len(policies)}개 정책 (사람 검수 {len(reviewed) - len(stale)}개), 경로 {paths}개 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
