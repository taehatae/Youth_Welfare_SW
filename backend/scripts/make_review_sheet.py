"""자격 경로 초안으로 사람 검수표(CSV)와 원문 대조 문서(Markdown)를 만든다.

- 검수는 경로 단위로 한다: 경로마다 한 줄, 정책마다 '빠진 경로' 확인 한 줄.
- 초안의 입력 항목·연산자가 진단에서 쓸 수 있는 것인지, 근거 구절이 원문에 그대로 있는지도 함께 확인한다.
- CSV는 엑셀에서 한글이 깨지지 않도록 BOM이 붙은 UTF-8로 저장한다.

    python scripts/make_review_sheet.py data/eligibility_paths_batch2_draft.json ../docs/eligibility-paths/batch-2
"""
import csv
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import structured_condition_service as base  # noqa: E402
from app.services.eligibility_path_service import UNITS  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "welfare-policies.json"
OPS = {"gte", "lte", "between", "one_of", "is_true"}
KINDS = {"기본", "유형", "순위", "예외"}
EMPTY_USER = SimpleNamespace(age=None, region=None, income_level=None, employment_status=None)
FIELDS = set(base.user_values(EMPTY_USER, {}))
COLUMNS = ["번호", "serv_id", "정책명", "구분", "경로 ID", "경로 이름", "종류", "비교 조건(모두 충족)", "근거 구절",
           "확인 사항(판정에 안 씀)", "자동 점검", "①원문에 있는 경로인가(O/X)", "②조건이 맞는가(O/X)",
           "③빠진 경로·조건(정책 행에 기입)", "수정 의견", "검수자"]


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def describe(c: dict) -> str:
    cond = {"field": c["field"], "operator": c["op"], "value": c.get("value"), "upper_value": c.get("upper"),
            "values": c.get("values", []), "kind": c.get("kind", "requirement"), "unit": UNITS.get(c["field"], "")}
    return base.describe(cond)


def problems(c: dict, source: str) -> list[str]:
    found = []
    if c["field"] not in FIELDS:
        found.append(f"입력 항목 없음: {c['field']}")
    if c["op"] not in OPS:
        found.append(f"연산자 오류: {c['op']}")
    # 근거 구절은 '...'로 생략할 수 있다. 조각마다 원문에 그대로 있어야 한다.
    pieces = [squash(p) for p in c.get("evidence", "").split("...") if squash(p)]
    if not pieces:
        found.append(f"근거 구절 없음: {c['field']}")
    elif any(p not in squash(source) for p in pieces):
        found.append(f"근거 구절이 원문에 없음: {c['field']}")
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    draft = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    services = {s["serv_id"]: s for s in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["data"]["welfare_services"]}

    rows, doc, issues = [], [f"# 자격 경로 {draft.get('batch', '')}차 검수 원문 대조\n",
                             "검수표(`review_sheet.csv`)와 함께 본다. 정책마다 원문 → 초안 순서로 적었다.\n"], 0
    for number, policy in enumerate(draft["policies"], 1):
        service = services[policy["serv_id"]]
        source = "\n".join(t for t in (service["target_details"], service["selection_criteria"]) if t and t.strip())
        common, common_checks = policy.get("common", []), policy.get("common_checks", [])
        base_row = {"번호": number, "serv_id": policy["serv_id"], "정책명": policy["name"]}

        for c in common:
            for problem in problems(c, source):
                print(f"[{policy['name']}] 공통 조건 {problem}")
                issues += 1
        rows.append({**base_row, "구분": "공통", "경로 ID": "_common", "경로 이름": "모든 경로 공통",
                     "비교 조건(모두 충족)": "\n".join(describe(c) for c in common) or "(없음)",
                     "근거 구절": "\n".join(c.get("evidence", "") for c in common),
                     "확인 사항(판정에 안 씀)": "\n".join(common_checks),
                     "자동 점검": "\n".join(p for c in common for p in problems(c, source)) or "OK"})
        for path in policy["paths"]:
            found = [p for c in path.get("conditions", []) for p in problems(c, source)]
            if path.get("kind", "기본") not in KINDS:
                found.append(f"경로 종류 오류: {path.get('kind')}")
            if not common and not path.get("conditions", []):
                found.append("비교 조건 없음 → 이 정책은 '불가'가 되지 않음")
            for problem in found:
                print(f"[{policy['name']} / {path['label']}] {problem}")
            issues += len(found)
            rows.append({**base_row, "구분": "경로", "경로 ID": path["id"], "경로 이름": path["label"],
                         "종류": path.get("kind", "기본"),
                         "비교 조건(모두 충족)": "\n".join(describe(c) for c in path.get("conditions", [])) or "(공통 조건만)",
                         "근거 구절": "\n".join(c.get("evidence", "") for c in path.get("conditions", [])),
                         "확인 사항(판정에 안 씀)": "\n".join(path.get("checks", [])),
                         "자동 점검": "\n".join(found) or "OK"})
        rows.append({**base_row, "구분": "정책", "경로 이름": "빠진 경로가 있는가",
                     "확인 사항(판정에 안 씀)": "우대(판정에 안 씀): " + " / ".join(policy.get("preferences", []))
                     if policy.get("preferences") else ""})

        doc.append(f"\n## {number}. {policy['name']} (`{policy['serv_id']}`)\n")
        doc.append("### 원문\n")
        doc.append("```text\n" + source.strip() + "\n```\n")
        doc.append("### 초안\n")
        if common or common_checks:
            doc.append("**모든 경로 공통**\n")
            doc.extend(f"- {describe(c)} — “{c.get('evidence', '')}”" for c in common)
            doc.extend(f"- (확인) {text}" for text in common_checks)
            doc.append("")
        for path in policy["paths"]:
            doc.append(f"**경로 `{path['id']}` {path['label']}** ({path.get('kind', '기본')})\n")
            doc.extend(f"- {describe(c)} — “{c.get('evidence', '')}”" for c in path.get("conditions", []))
            doc.extend(f"- (확인) {text}" for text in path.get("checks", []))
            if not path.get("conditions", []) and not path.get("checks"):
                doc.append("- 공통 조건만")
            doc.append("")
        if policy.get("preferences"):
            doc.append("**우대(판정에 안 씀)**\n")
            doc.extend(f"- {text}" for text in policy["preferences"])
            doc.append("")

    with (out / "review_sheet.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    (out / "originals.md").write_text("\n".join(doc), encoding="utf-8")
    paths = sum(len(p["paths"]) for p in draft["policies"])
    print(f"정책 {len(draft['policies'])}개, 경로 {paths}개, 자동 점검 문제 {issues}건 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
