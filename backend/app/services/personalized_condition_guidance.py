"""로그인 전용 설명. 반환 문장은 공개 진단/스냅샷에 넣거나 로그·DB에 저장하지 않는다."""
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.models.eligibility_path import COMMON_PATH, PolicyEligibility
from app.models.welfare_service import WelfareService
from app.services import eligibility_path_service as paths
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


def snapshot_guides(db: Session, snapshot: dict, policy_id: str) -> list[dict]:
    """저장 진단과 현 구조가 정확히 연결되는 gap만 설명하고 저장 결과를 바꾸지 않는다."""
    analyses = snapshot.get("analysis", {}).get("matched", {}).get("analysis_results", [])
    analysis = next((a for a in analyses if a.get("policy_id") == policy_id), None)
    if not analysis:
        return []
    stored_path = next((p for p in analysis.get("eligibility_paths", [])
                        if p["path_id"] == analysis.get("matched_path_id")), None)
    record = db.get(PolicyEligibility, policy_id)
    service = db.get(WelfareService, policy_id)
    if (not stored_path or not record or not service or record.status != "reviewed"
            or record.drafted_by == "converted" or record.source_sha256 != base.source_hash(service)):
        return []
    selected = next((p for p in record.paths if p.path_key == stored_path["path_id"]), None)
    common = next((p for p in record.paths if p.path_key == COMMON_PATH), None)
    profile = snapshot.get("profile")
    if selected is None or not isinstance(profile, dict):
        return []
    try:
        values = base.user_values(SimpleNamespace(**profile), profile.get("eligibility_conditions"))
        same_year = datetime.fromisoformat(snapshot["checkedAt"].replace("Z", "+00:00")).year == date.today().year
    except (TypeError, ValueError, KeyError, AttributeError):
        return []
    conditions = (common.conditions if common and common is not selected else []) + selected.conditions
    result = []
    for index, gap in enumerate(analysis.get("gap_conditions", [])):
        if gap.get("source_field") != "eligibility_path" or gap.get("status") != "failed":
            continue
        def matches_row(r):
            return (r.get("condition_type") == gap.get("condition_type") and r.get("status") == "failed"
                    and r.get("required_value") == gap.get("required_value")
                    and (r.get("evidence") or r.get("required_value")) == gap.get("source_text"))
        stored = [r for r in stored_path["conditions"] if matches_row(r)]
        candidates = [c for c in conditions if c.field == gap.get("condition_type")
                      and base.describe(paths._condition(c)) == gap.get("required_value")
                      and (c.evidence or base.describe(paths._condition(c))) == gap.get("source_text")]
        if len(stored) != 1 or len(candidates) != 1:
            continue
        c = paths._condition(candidates[0])
        if not same_year and ("소득" in c["field"] and c["unit"] == "%"):
            continue
        current = values.get(c["field"])
        if stored[0].get("current_value") != base.show(c["field"], current):
            continue
        text = personalized_guide(c, current, profile)
        if text:
            result.append({"gap_index": index, "condition_guide": text, "guide_kind": "state_change"})
    result += _path_guides(analysis, record, common, values, profile, same_year)
    return result


def _path_guides(analysis: dict, record, common, values: dict, profile: dict, same_year: bool) -> list[dict]:
    """모든 경로의 미충족 조건에 맞춤 안내를 붙인다. 저장 행과 현재 경로 조건이 순서·항목·기준까지 같을 때만."""
    out = []
    for stored in analysis.get("eligibility_paths", []):
        if stored.get("path_id") == COMMON_PATH:
            conditions = common.conditions if common else []
        else:
            selected = next((p for p in record.paths if p.path_key == stored.get("path_id")), None)
            if selected is None:
                continue
            conditions = (common.conditions if common else []) + selected.conditions
        rows = stored.get("conditions", [])
        if len(rows) != len(conditions):
            continue
        for index, (row, raw) in enumerate(zip(rows, conditions)):
            if row.get("status") != "failed":
                continue
            c = paths._condition(raw)
            if c["field"] != row.get("condition_type") or base.describe(c) != row.get("required_value"):
                continue
            if not same_year and ("소득" in c["field"] and c["unit"] == "%"):
                continue
            current = values.get(c["field"])
            if row.get("current_value") != base.show(c["field"], current):
                continue
            text = personalized_guide(c, current, profile)
            if text:
                out.append({"gap_index": None, "path_id": stored["path_id"], "condition_index": index,
                            "condition_guide": text, "guide_kind": "state_change"})
    return out
