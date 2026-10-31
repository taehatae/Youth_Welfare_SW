"""검수를 마친 정책별 자격 조건을 하나의 시드 파일(data/structured_conditions.json)로 묶는다.

정책 원문(DB의 target_details, selection_criteria)을 사람이 읽고 정리한 정답지 세 개를 합친다.
진단에는 '신청자 본인에게 반드시 적용되는 조건(required)'과 '그중 하나만 해당하면 되는 묶음(or)'만 쓴다.
optional(있어도 되고 없어도 되는 조건)과 해석이 갈리는 대안(alternatives)은 진단에 쓰지 않는다.
원문이 바뀌면 source_sha256이 달라지므로 다시 검수해야 한다.

    python scripts/build_structured_seed.py
"""
import hashlib
import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
GOLD_FILES = ["structure_gold_train.json", "structure_gold_val.json", "structure_gold_rest.json"]
OUT = DATA / "structured_conditions.json"
REVIEWED_AT = "2026-10-31"

# 진단 입력값 중 어느 값과 비교하는지. additional_conditions.* 는 eligibility_conditions 아래 값이다.
PROFILE_KEYS = {
    "만 나이": "age",
    "거주지": "region",
    "성별": "eligibility_conditions.gender",
    "본인 월소득": "income_level",
    "본인 연소득": "income_level",  # 월소득 × 12와 비교
    "가구 소득인정액": "eligibility_conditions.additional_conditions.recognized_household_income_won",
    "가구원 수": "eligibility_conditions.household_size",
    "자녀 수": "eligibility_conditions.children_count",
    "고용 상태": "employment_status",
    "재학 여부": "eligibility_conditions.student_status",
    "등록 장애인": "eligibility_conditions.disability_status",
    "본인 명의 주택 보유": "eligibility_conditions.owns_home",
    "국적": "eligibility_conditions.additional_conditions.nationality",
    "기초생활보장 수급자": "eligibility_conditions.additional_conditions.basic_benefit_status",
    "차상위계층": "eligibility_conditions.additional_conditions.near_poverty_status",
    "한부모가족": "eligibility_conditions.additional_conditions.single_parent_support_status",
    "국가유공자·보훈대상자": "eligibility_conditions.additional_conditions.special_targets:VETERAN",
    "북한이탈주민": "eligibility_conditions.additional_conditions.special_targets:NK_DEFECTOR",
    "결혼이민자·다문화가족": "eligibility_conditions.additional_conditions.special_targets:MULTICULTURAL",
    "농업인·어업인": "eligibility_conditions.additional_conditions.special_targets:FARMER",
}
OPERATORS = {"min": "gte", "max": "lte", "range": "between", "one_of": "one_of", "is_true": "is_true"}
UNITS = {"만 나이": "세", "본인 월소득": "원", "본인 연소득": "원", "가구 소득인정액": "%", "가구원 수": "명", "자녀 수": "명"}

# 검증용 정답지를 만든 뒤 성별을 입력 항목에 추가하면서 보완한 정책.
OVERRIDES = {
    "WLF00000922": {"required": [{"field": "성별", "op": "one_of", "values": ["여성"]}]},
    "WLF00000975": {"required": [{"field": "성별", "op": "one_of", "values": ["여성"]}]},
}


def condition(item: dict, or_group: str = "") -> dict:
    field = item["field"]
    return {
        "field": field,
        "profile_key": PROFILE_KEYS[field],
        "kind": item.get("kind", "requirement"),
        "operator": OPERATORS[item["op"]],
        "value": item.get("value"),
        "upper_value": item.get("upper"),
        "unit": UNITS.get(field, ""),
        "values": item.get("values", []),
        "or_group": or_group,
    }


def main() -> int:
    answers = {}
    for name in GOLD_FILES:
        for serv_id, entry in json.loads((DATA / name).read_text(encoding="utf-8")).items():
            if not serv_id.startswith("_"):
                answers[serv_id] = {**entry, **OVERRIDES.get(serv_id, {})}
    db = sqlite3.connect(f"file:{DATA.parent / 'youth_welfare.db'}?mode=ro", uri=True)
    services = {row[0]: row[1:] for row in db.execute(
        "select serv_id, serv_name, target_details, selection_criteria from welfare_services")}
    missing = sorted(set(services) - set(answers))
    if missing:
        raise SystemExit(f"검수되지 않은 정책이 있어요: {', '.join(missing)}")

    policies = []
    for serv_id in sorted(answers):
        name, target, selection = services[serv_id]
        entry = answers[serv_id]
        conditions = [condition(item) for item in entry.get("required", [])]
        for index, group in enumerate(entry.get("or", []), start=1):
            conditions += [condition(item, f"대상{index}") for item in group]
        source = "\n".join(text for text in (target, selection) if text and text.strip())
        policies.append({
            "serv_id": serv_id,
            "name": name,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "reviewed_by": "claude",
            "reviewed_at": REVIEWED_AT,
            "conditions": conditions,
        })
    OUT.write_text(json.dumps({"version": 1, "policies": policies}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(policies)}개 정책, 조건 {sum(len(p['conditions']) for p in policies)}개 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
