"""로그인 전용 설명. 반환 문장은 공개 진단/스냅샷에 넣거나 로그·DB에 저장하지 않는다."""
from sqlalchemy.orm import Session

from app.models.eligibility_path import PolicyEligibility
from app.models.welfare_service import WelfareService
from app.services import structured_condition_service as base


def _current_description(c: dict, current, profile: dict) -> str | None:
    field, op = c["field"], c["operator"]
    if op in {"gte", "lte", "between"}:
        if base._CHANGE_UNITS.get(field) != c["unit"] or isinstance(current, bool) or not isinstance(current, (int, float)):
            return None
        number = base._exact_number(current)
        if field == "만 나이":
            return f"입력하신 나이는 만 {number}세입니다."
        if field == "본인 연소득":
            return f"입력한 본인 월소득을 12개월로 환산한 본인 연소득은 {number}원입니다."
        if field in {"가구 소득인정액", "가구 월소득 중위소득 대비"}:
            metric = "가구 소득인정액" if field == "가구 소득인정액" else "가구 월소득"
            return f"입력값으로 계산한 {metric}은 기준 중위소득의 {number}%입니다."
        return f"입력하신 {field} 값은 {number}{c['unit']}입니다."
    if op == "one_of":
        if not isinstance(current, str) or current == "UNKNOWN":
            return None
        if field == "거주지":
            if not base._CHANGE_REGION.fullmatch(current):
                return None
            return f"입력하신 거주지는 {current}입니다."
        if current not in base._CHANGE_CHOICES.get(field, set()):
            return None
        return f"입력하신 {field} 항목은 '{current}'입니다."
    if op == "is_true" and isinstance(current, bool) and field in base._CHANGE_BOOLEANS:
        if field == "본인 명의 주택 보유":
            return "본인 명의 주택을 보유한 것으로 입력되어 있습니다." if current else "본인 명의 주택을 보유하지 않은 것으로 입력되어 있습니다."
        if field == "세대원 전원 무주택":
            own = (profile.get("eligibility_conditions") or {}).get("owns_home")
            if own in (True, "YES"):
                return "본인 명의 주택 보유 입력으로 인해 세대원 전원 무주택 요건이 미충족입니다."
            return "세대원 전원 무주택 항목은 '해당'으로 입력되어 있습니다." if current else "세대원 전원 무주택 항목은 '해당 없음'으로 입력되어 있습니다."
        if field == "재학 여부":
            return "현재 입력은 재학 중입니다." if current else "현재 입력은 재학하지 않는 상태입니다."
        return f"입력하신 '{field}' 항목은 {'해당' if current else '해당 없음'}입니다."
    return None


def personalized_guide(c: dict, current, profile: dict | None = None) -> str | None:
    """구조화된 단일 조건과 실제 비교값만 사용한다. required_value를 해석하지 않는다."""
    try:
        public = base.condition_guide(c, current, base.matches(c, current))
        if public.get("guide_kind") != "state_change":
            return None
        intro = _current_description(c, current, profile or {})
        if intro is None:
            return None
        movement = base._numeric_change(c, current)
        detail = public["condition_guide"]
        if movement:
            direction, _, delta = movement
            unit = "%p" if c["unit"] == "%" else c["unit"]
            amount = f"{base._exact_number(delta)}{unit}"
            target = base._guide_bounds(c)
            if c["field"] in base.TIME_FIELDS:
                years = f"{base._exact_number(delta)}년"
                detail = (f"{years} 뒤 {base._josa(target, '이/가')} 되면 이 조건을 충족합니다." if direction == "increase" else
                          f"{target} 기준보다 {amount} 많고, 시간이 지나도 줄지 않아 이 조건은 충족할 수 없습니다.")
            else:
                count = c["unit"] == "명"
                move = ("늘어나면" if count else "높아지면") if direction == "increase" else ("줄어들면" if count else "낮아지면")
                detail = (f"{amount} {move} "
                          f"{target} 기준에 들어 이 조건을 충족합니다.")
        if c["field"] == "본인 명의 주택 보유" and c["kind"] == "exclusion":
            detail = "본인 명의 주택을 보유하지 않는 상태여야 이 제외 조건에 해당하지 않습니다."
        elif c["field"] == "세대원 전원 무주택" and c["kind"] == "requirement":
            detail = "세대원 전원이 주택을 보유하지 않는 상태여야 이 조건을 충족합니다. 본인 주택 미보유나 월세·전세만으로 세대원 전원 무주택이 확인되지는 않습니다."
        return f"{intro} {detail}"
    except (TypeError, ValueError, ArithmeticError, KeyError):
        return None



def snapshot_details(db: Session, snapshot: dict, policy_id: str) -> dict:
    """검증된 진단에서만 안내/점수를 일시 생성한다. 저장이나 재판정은 하지 않는다."""
    from app.services.eligibility_snapshot_context import validate_snapshot
    empty = {"items": [], "difficulties": [], "unavailable_reason": None}
    analyses = snapshot.get("analysis", {}).get("matched", {}).get("analysis_results", [])
    found = [a for a in analyses if a.get("policy_id") == policy_id]
    record = db.get(PolicyEligibility, policy_id)
    service = db.get(WelfareService, policy_id)
    if (len(found) != 1 or not record or not service or record.status != "reviewed"
            or record.drafted_by == "converted"):
        return {**empty, "unavailable_reason": "policy_unavailable"}
    analysis = found[0]
    validated, reason = validate_snapshot(snapshot, analysis, service, record)
    if validated is None:
        return {**empty, "unavailable_reason": reason}
    verified, values = validated
    items, difficulties = [], []
    for path_id, index, c, row in verified:
        if row.get("status") != "failed":
            continue
        current = values.get(c["field"])
        hard = base.difficulty(c, current)
        difficulties.append({"path_id": path_id, "condition_index": index, "difficulty": hard,
                             "difficulty_group": base.difficulty_group(c) if hard is not None else None})
        text = personalized_guide(c, current, snapshot["profile"])
        if not text:
            continue
        items.append({"gap_index": None, "path_id": path_id, "condition_index": index,
                      "condition_guide": text, "guide_kind": "state_change"})
        if path_id != analysis.get("matched_path_id"):
            continue
        for gap_index, gap in enumerate(analysis.get("gap_conditions", [])):
            if (gap.get("source_field") == "eligibility_path" and gap.get("status") == "failed"
                    and gap.get("condition_type") == row["condition_type"]
                    and gap.get("required_value") == row["required_value"]
                    and gap.get("source_text") == (row["evidence"] or row["required_value"])):
                matches = [r for pid, _, _, r in verified if pid == path_id and r.get("status") == "failed"
                           and r["condition_type"] == gap["condition_type"]
                           and r["required_value"] == gap["required_value"]
                           and (r["evidence"] or r["required_value"]) == gap["source_text"]]
                if len(matches) == 1:
                    items.append({"gap_index": gap_index, "condition_guide": text, "guide_kind": "state_change"})
    # 기존 클라이언트의 대표 gap 안내 순서는 유지한다.
    items.sort(key=lambda item: (item.get("gap_index") is None, item.get("gap_index") or 0))
    return {"items": items, "difficulties": difficulties, "unavailable_reason": None}


def snapshot_guides(db: Session, snapshot: dict, policy_id: str) -> list[dict]:
    return snapshot_details(db, snapshot, policy_id)["items"]
