"""진단 당시 정책 구조의 버전 있는 지문. 사용자 값·점수는 해시 입력에 넣지 않는다.

객체 키만 정렬하고 배열(경로/조건/선택값) 순서는 보존한다. 숫자는 Decimal로
정규화해 26과 26.0을 같게 취급한다. 문자열은 줄바꿈만 LF로 통일한다.
SQL 내부 ID, 검수자, 갱신 시각은 의미 구조가 아니므로 포함하지 않는다.
"""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.models.eligibility_path import COMMON_PATH
from app.services import structured_condition_service as base
from app.services.median_income_reference import MONTHLY_MEDIAN_INCOME_WON
from app.services.urban_worker_income_reference import MONTHLY_URBAN_WORKER_INCOME_WON

VERSION = 1


def _canonical(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Non-finite policy value")
        return {"number": format(number.normalize(), "f")}
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    raise ValueError("Unsupported policy value")


def _hash(value):
    return hashlib.sha256(json.dumps(_canonical(value), sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def condition(c):
    from app.services.eligibility_path_service import _condition
    return {**_condition(c), "evidence": c.evidence}


def evaluation_paths(record):
    common = next((p for p in record.paths if p.path_key == COMMON_PATH), None)
    paths = [p for p in record.paths if p.path_key != COMMON_PATH]
    if not paths:
        return [(common, common.conditions)] if common else []
    return [(p, (common.conditions if common else []) + p.conditions) for p in paths]


def create_context(service, record):
    graph = [{"id": p.path_key, "label": p.label, "kind": p.kind, "priority": p.priority,
              "checks": p.checks or [], "conditions": [condition(c) for c in p.conditions]}
             for p in record.paths]
    uses_reference = any(condition(c)["unit"] == "%" for p in record.paths for c in p.conditions)
    # 코드/참조 데이터가 달라지면 과거 입력을 새 계산으로 해석하지 않는다.
    calculations = {"version": VERSION, "code": {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("structured_condition_service.py", "eligibility_path_service.py",
                     "median_income_reference.py", "urban_worker_income_reference.py")}}
    if uses_reference:
        calculations.update(year=date.today().year, median=MONTHLY_MEDIAN_INCOME_WON,
                            urban=MONTHLY_URBAN_WORKER_INCOME_WON)
    return {"version": VERSION, "source_sha256": base.source_hash(service),
            "policy_sha256": _hash({"serv_id": service.serv_id, "paths": graph}),
            "calculation_sha256": _hash(calculations)}


def validate_snapshot(snapshot, analysis, service, record):
    """저장 결과를 수정/재판정하지 않고 연결만 검증한다. 실패 시 둘 다 같은 경로로 보류."""
    context = analysis.get("evaluation_context")
    if not isinstance(context, dict) or context.get("version") != VERSION:
        return None, "legacy_context_missing"
    try:
        current = create_context(service, record)
        if context.get("source_sha256") != current["source_sha256"] or record.source_sha256 != current["source_sha256"]:
            return None, "source_changed"
        if context.get("policy_sha256") != current["policy_sha256"]:
            return None, "condition_changed"
        if context.get("calculation_sha256") != current["calculation_sha256"]:
            return None, "calculation_changed"
        profile = snapshot["profile"]
        values = base.user_values(SimpleNamespace(**profile), profile.get("eligibility_conditions"))
        checked_year = datetime.fromisoformat(snapshot["checkedAt"].replace("Z", "+00:00")).year
        expected = evaluation_paths(record)
        if any(condition(c)["unit"] == "%" for _, cs in expected for c in cs) and checked_year != date.today().year:
            return None, "calculation_changed"
        stored = analysis.get("eligibility_paths", [])
        if [p["path_id"] for p in stored] != [p.path_key for p, _ in expected]:
            return None, "path_structure_changed"
        common = next((p for p in record.paths if p.path_key == COMMON_PATH), None)
        verified = []
        for old, (path, conditions) in zip(stored, expected):
            rows = old.get("conditions", [])
            if len(rows) != len(conditions) or old.get("label") != path.label or old.get("kind") != path.kind:
                return None, "path_structure_changed"
            for index, (row, raw) in enumerate(zip(rows, conditions)):
                c = condition(raw)
                is_common = common is not None and common is not path and raw in common.conditions
                if (row.get("condition_type") != c["field"] or row.get("required_value") != base.describe(c)
                        or row.get("evidence", "") != raw.evidence or row.get("common", False) != is_common):
                    return None, "condition_changed"
                if row.get("current_value") != base.show(c["field"], values.get(c["field"])):
                    return None, "input_context_changed"
                verified.append((path.path_key, index, c, row))
        if analysis.get("matched_path_id") not in [p.path_key for p, _ in expected]:
            return None, "path_structure_changed"
        return (verified, values), None
    except (KeyError, TypeError, ValueError, AttributeError, ArithmeticError):
        return None, "invalid_snapshot_context"
