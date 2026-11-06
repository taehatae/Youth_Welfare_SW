"""자격 경로로 진단 입력값과 정책 자격을 비교한다.

판정 규칙
- 조건: 충족 / 미충족 / 미입력. 확인 사항(checks)은 입력으로 비교할 수 없어 안내만 하고 판정에는 쓰지 않는다.
- 경로: 미충족이 하나라도 있으면 불가, 비교 조건이 모두 충족이면 가능, 그 밖(미입력, 비교 조건 없음)은 확인 필요.
- 정책: 가능한 경로가 하나라도 있으면 가능, 모든 경로가 불가면 불가, 그 밖은 확인 필요.
  비교 조건이 없는 경로가 있으면 그 정책은 불가가 되지 않는다(신청할 수 있는 사람을 놓치지 않기 위해).
- 역설계: 불가면 모든 경로가 막히는 공통 조건, 없으면 미충족이 가장 적은 경로를 보여준다.

검수된(reviewed) 정책 중 원문 해시가 그대로인 것만 쓰고, 나머지는 None을 돌려 기존 분석을 그대로 쓰게 한다.
"""
import json
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session, selectinload

from app.models.eligibility_path import COMMON_PATH, EligibilityPath, EligibilityPathCondition, PolicyEligibility
from app.services import structured_condition_service as base

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "eligibility_paths.json"
UNITS = {"만 나이": "세", "가구 소득인정액": "%", "도시근로자 월평균소득 대비 가구소득": "%", "가구 총재산": "원", "본인 총재산": "원",
         "본인 월소득": "원", "본인 연소득": "원", "가구원 수": "명", "자녀 수": "명"}
RANK = {"eligible": 0, "needs_review": 1, "ineligible": 2}


def seed_from_file(db: Session, path: Path = SEED_PATH) -> int:
    """JSON 시드를 DB에 넣는다. 같은 정책은 경로를 통째로 바꾸고, 시드에서 빠진 정책(재검수 대상 등)은 지운다."""
    data = json.loads(path.read_text(encoding="utf-8"))
    keep = {item["serv_id"] for item in data["policies"]}
    for record in db.query(PolicyEligibility).filter(PolicyEligibility.serv_id.notin_(keep)):
        db.delete(record)
    for item in data["policies"]:
        record = db.get(PolicyEligibility, item["serv_id"])
        if record is None:
            record = PolicyEligibility(serv_id=item["serv_id"])
            db.add(record)
        record.source_sha256 = item["source_sha256"]
        record.status = item.get("status", "reviewed")
        record.drafted_by = item.get("drafted_by", "")
        record.reviewed_by = item.get("reviewed_by", "")
        record.reviewed_at = item.get("reviewed_at", "")
        record.version = data.get("version", 1)
        record.preferences = item.get("preferences", [])
        record.paths.clear()
        paths = [{"id": COMMON_PATH, "label": "공통 조건", "kind": "공통", "conditions": item.get("common", []),
                  "checks": item.get("common_checks", [])}] + item["paths"]
        for order, p in enumerate(paths):
            record.paths.append(EligibilityPath(
                path_key=p["id"], label=p["label"], kind=p.get("kind", "기본"), priority=p.get("priority"),
                sort_order=order, checks=p.get("checks", []),
                conditions=[EligibilityPathCondition(
                    field=c["field"], operator=c["op"], value=c.get("value"), upper_value=c.get("upper"),
                    values=c.get("values", []), kind=c.get("kind", "requirement"), evidence=c.get("evidence", ""))
                    for c in p.get("conditions", [])]))
    db.commit()
    return len(data["policies"])


def load(db: Session) -> dict[str, PolicyEligibility]:
    query = db.query(PolicyEligibility).options(
        selectinload(PolicyEligibility.paths).selectinload(EligibilityPath.conditions))
    if not db.query(PolicyEligibility.serv_id).first() and SEED_PATH.exists():
        seed_from_file(db)
    return {record.serv_id: record for record in query.filter(PolicyEligibility.status == "reviewed")}


def _condition(c: EligibilityPathCondition) -> dict:
    return {"field": c.field, "operator": c.operator, "value": c.value, "upper_value": c.upper_value,
            "values": c.values or [], "kind": c.kind, "unit": UNITS.get(c.field, ""), "or_group": ""}


def _status(result: bool | None) -> str:
    return "passed" if result is True else "failed" if result is False else "needs_review"


def _evaluate_path(path: EligibilityPath, common: EligibilityPath | None, values: dict) -> dict:
    rows = []
    for c in (common.conditions if common else []) + path.conditions:
        cond = _condition(c)
        rows.append({"condition_type": c.field, "status": _status(base.matches(cond, values.get(c.field))),
                     "current_value": base.show(c.field, values.get(c.field)), "required_value": base.describe(cond),
                     "evidence": c.evidence, "common": common is not None and c in common.conditions})
    statuses = {r["status"] for r in rows}
    status = "ineligible" if "failed" in statuses else "eligible" if rows and statuses == {"passed"} else "needs_review"
    return {"path_id": path.path_key, "label": path.label, "kind": path.kind, "priority": path.priority,
            "status": status, "conditions": rows, "checks": (common.checks if common else []) + (path.checks or [])}


def _row(r: dict, message: str, guide: str) -> dict:
    return {"condition_type": r["condition_type"], "status": r["status"], "current_value": r["current_value"],
            "required_value": r["required_value"], "message": message, "action_guide": guide,
            "source_field": "eligibility_path", "source_text": r["evidence"] or r["required_value"]}


def _check_row(text: str) -> dict:
    return {"condition_type": "확인 사항", "status": "needs_review", "current_value": "미확인", "required_value": text,
            "message": "입력값으로 비교할 수 없는 조건입니다.", "action_guide": "공식 안내에서 확인하세요.",
            "source_field": "eligibility_path_check", "source_text": text}


def analyze(service, user, profile: dict | None, record: PolicyEligibility | None,
            legacy: dict | None = None) -> dict | None:
    if record is None or record.source_sha256 != base.source_hash(service):
        return None
    values = base.user_values(user, profile)
    common = next((p for p in record.paths if p.path_key == COMMON_PATH), None)
    paths = [_evaluate_path(p, common, values) for p in record.paths if p.path_key != COMMON_PATH]
    if not paths:
        paths = [_evaluate_path(common, None, values)] if common else []
    count = lambda p, s: sum(r["status"] == s for r in p["conditions"])
    best = min(paths, key=lambda p: (RANK[p["status"]], count(p, "failed"), count(p, "needs_review"), -count(p, "passed")))
    status = best["status"]
    # 모든 경로가 같은 공통 조건에서 막히면 그 조건을 보여준다.
    blocked = [r for r in best["conditions"] if r["common"] and r["status"] == "failed"] if status == "ineligible" else []
    shown = blocked or [r for r in best["conditions"] if r["status"] == "failed"]

    confirmed = [_row(r, "입력한 정보로 조건을 충족합니다.", "별도 조치가 필요하지 않습니다.")
                 for r in best["conditions"] if r["status"] == "passed"]
    gaps = [_row(r, "입력한 정보로는 조건을 충족하지 않습니다.", "입력 정보가 맞는지 확인하고, 다른 경로나 정책을 살펴보세요.")
            for r in shown]
    review = [_row(r, "입력하지 않은 정보라 비교하지 못했습니다.", "관련 정보를 입력하고 다시 진단하세요.")
              for r in best["conditions"] if r["status"] == "needs_review"]
    review += [_check_row(text) for text in best["checks"]]
    # 확인 사항을 따로 적지 않은 정책은 기존 분석의 추가 확인 항목을 함께 보여준다.
    if not any(p["checks"] for p in paths):
        review += [{**item, "status": "needs_review"} for item in (legacy or {}).get("review_conditions", [])
                   if item.get("condition_type") in base.LEGACY_REVIEW_TYPES]

    fields = lambda rows: ", ".join(dict.fromkeys(r["condition_type"] for r in rows))
    multiple = len(paths) > 1
    where = f"'{best['label']}' 경로" if multiple else "정책"
    if status == "eligible":
        reason = f"{where}의 비교 조건 {len(confirmed)}개를 모두 충족합니다."
    elif status == "needs_review":
        missing = [r for r in best["conditions"] if r["status"] == "needs_review"]
        reason = (f"{fields(missing)} 정보를 입력하면 {where}의 자격을 비교할 수 있어요." if missing
                  else "입력값으로 비교할 수 있는 조건이 없어 공식 안내에서 자격을 확인해야 합니다.")
    elif blocked:
        reason = f"모든 경로에 공통으로 필요한 {fields(blocked)} 조건을 충족하지 않습니다."
    else:
        reason = f"가장 가까운 경로 '{best['label']}'에서 {fields(shown)} 조건이 부족합니다." if multiple \
            else f"{fields(shown)} 조건을 충족하지 않습니다."
    evaluated = count(best, "passed") + count(best, "failed")
    return {
        **(legacy or {}),
        "policy_id": service.serv_id,
        "title": service.serv_name,
        "status": status,
        "match_score": round(count(best, "passed") / evaluated * 100, 1) if evaluated else 0.0,
        "evaluated_conditions": evaluated,
        "passed_conditions": count(best, "passed"),
        "gap_conditions": gaps,
        "review_conditions": review,
        "confirmed_conditions": confirmed,
        "recommendation_status": {"eligible": "priority_recommendation", "needs_review": "additional_review",
                                  "ineligible": "condition_mismatch"}[status],
        "recommendation_reason": reason,
        "recommendation_uncertainty": None,
        "detail_url": service.detail_url,
        "eligibility_paths": paths,
        "matched_path_id": best["path_id"],
        "blocked_by_common": list(dict.fromkeys(r["condition_type"] for r in blocked)),
        "preferences": record.preferences or [],
        # 원문을 다시 읽고 경로로 정리한 정책(reviewed)과 기존 정답지에서 옮긴 정책(converted)을 구분한다.
        "path_review": "converted" if record.drafted_by == "converted" else "reviewed",
    }
