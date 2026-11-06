"""구조화 초안을 정답지와 비교해 정책 단위 정확도를 낸다.

정책 하나가 '정답'이려면, 진단에 그대로 쓰일 조건(신청자 본인 대상, 입력 항목이 있고, 검수 표시가 없는 조건)이
정답지의 필수 조건을 모두 포함하고, 정답지에 없는 조건이 하나도 없고, '또는' 묶음까지 같아야 한다.

    python scripts/score_structure.py data/structured_train_v3.json data/structure_gold_train.json
"""
import json
import sys
from pathlib import Path

OP_CLASS = {"gte": "min", "gt": "min", "lte": "max", "lt": "max", "between": "range", "one_of": "one_of",
            "is_true": "is_true"}


def key(field, kind, op, value=None, upper=None, values=()):
    numbers = (value, upper) if op in {"min", "max", "range"} else (None, None)
    return field, kind, op, *numbers, tuple(sorted(values)) if op == "one_of" else ()


def gold_key(g: dict):
    return key(g["field"], g.get("kind", "requirement"), g["op"], g.get("value"), g.get("upper"), g.get("values", ()))


def used_conditions(policy: dict) -> list[dict]:
    return [c for c in policy["conditions"] if c["input_field"] != "없음" and c["applies_to"] == "applicant"
            and not c["review_reasons"]]


def score_policy(policy: dict, gold: dict) -> list[str]:
    problems = []
    preds = {}
    for c in used_conditions(policy):
        k = key(c["input_field"], c["kind"], OP_CLASS[c["operator"]], c["value"], c["upper_value"], c["values"])
        preds.setdefault(k, set()).add(c["or_group"])
    required = {gold_key(g) for g in gold.get("required", [])}
    or_groups = [frozenset(gold_key(g) for g in group) for group in gold.get("or", [])]
    allowed = required | {gold_key(g) for g in gold.get("optional", [])} | set().union(*or_groups)
    for k in sorted(required | set().union(*or_groups), key=str):
        if k not in preds:
            problems.append(f"누락: {k[0]} {k[2]} {k[3] if k[3] is not None else ''}{'~' + str(k[4]) if k[4] is not None else ''} {list(k[5]) or ''}".strip())
    for k in preds:
        if k not in allowed:
            problems.append(f"오답: {k[0]} {k[1]} {k[2]} {k[3] if k[3] is not None else ''}{'~' + str(k[4]) if k[4] is not None else ''} {list(k[5]) or ''}".strip())
    # '또는' 묶음 비교: 예측에서 같은 이름으로 묶인 조건 집합(2개 이상)이 정답 묶음과 같아야 한다.
    named: dict[str, set] = {}
    for k, groups in preds.items():
        for g in groups - {""}:
            named.setdefault(g, set()).add(k)
    predicted_groups = {frozenset(ks) for ks in named.values() if len(ks) > 1}
    for group in or_groups:
        if group <= set(preds) and group not in predicted_groups:
            problems.append("또는 묶음 불일치: " + ", ".join(sorted(k[0] for k in group)))
    for group in predicted_groups:
        if group not in or_groups and group <= allowed:
            problems.append("잘못된 또는 묶음: " + ", ".join(sorted(k[0] for k in group)))
    return problems


def main(argv: list[str]) -> int:
    pred_path, gold_path = argv
    preds = {p["serv_id"]: p for p in json.loads(Path(pred_path).read_text(encoding="utf-8"))}
    gold = {k: v for k, v in json.loads(Path(gold_path).read_text(encoding="utf-8")).items() if not k.startswith("_")}
    correct = 0
    for serv_id, expected in gold.items():
        if serv_id not in preds:
            print(f"✗ {expected['name']}: 결과 없음")
            continue
        # 해석이 갈리는 정책은 다른 정답(alternatives) 중 하나라도 맞으면 정답으로 본다.
        candidates = [expected] + expected.get("alternatives", [])
        problems = min((score_policy(preds[serv_id], c) for c in candidates), key=len)
        correct += not problems
        print(("✓ " if not problems else "✗ ") + expected["name"] + ("" if not problems else " — " + " / ".join(problems)))
    review = sum(bool(c["review_reasons"]) for p in preds.values() for c in p["conditions"])
    print(f"\n정확도 {correct}/{len(gold)} = {correct / len(gold):.0%} · 검수 표시 조건 {review}개")
    print(field_report(preds, gold))
    return 0


def field_report(preds: dict, gold: dict) -> str:
    """입력 항목별로 놓친 조건(신청 가능으로 잘못 뜸)과 지어낸 조건(신청 불가로 잘못 뜸)을 센다."""
    stats: dict[str, list[int]] = {}
    for serv_id, expected in gold.items():
        if serv_id not in preds:
            continue
        must = {gold_key(g) for g in expected.get("required", [])} | {gold_key(g) for grp in expected.get("or", []) for g in grp}
        allowed = must | {gold_key(g) for g in expected.get("optional", [])}
        for alt in expected.get("alternatives", []):
            allowed |= {gold_key(g) for g in alt.get("required", []) + alt.get("optional", [])}
            allowed |= {gold_key(g) for grp in alt.get("or", []) for g in grp}
        got = {key(c["input_field"], c["kind"], OP_CLASS[c["operator"]], c["value"], c["upper_value"], c["values"])
               for c in used_conditions(preds[serv_id])}
        for k in must:
            s = stats.setdefault(k[0], [0, 0, 0])
            s[0] += 1
            s[1] += k not in got and not expected.get("alternatives")
        for k in got - allowed:
            stats.setdefault(k[0], [0, 0, 0])[2] += 1
    lines = ["\n항목별: 정답 조건 수 / 놓침(잘못된 신청 가능) / 지어냄(잘못된 신청 불가)"]
    for field, (total, missed, invented) in sorted(stats.items(), key=lambda x: -x[1][0]):
        lines.append(f"  {field}: {total} / {missed} / {invented}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
