"""자격 경로 초안을 사람 채점 전에 자동 점검한다(채점에서 반복된 지적을 규칙으로 만든 것).

규칙은 docs/eligibility-paths/LLM_GUIDE.md '검수 규칙집'의 번호(R1~)와 같다.
- R1 확인 사항에 입력으로 비교할 수 있는 기준이 있는데, 그 경로(공통 포함)에 해당 비교 조건이 없다.
- R3 원문 어디를 말하는지 모를 일반론("공고 기준 확인" 등)이다.
- R4 청년 서비스 범위 밖 나이 경로(만 65세 이상 등)를 만들었다.
- R5 같은 금액·비율 기준이 경로마다 다르게 빠졌다(한 경로엔 있고 다른 경로엔 없음).

    python scripts/lint_draft.py data/eligibility_paths_batch5_draft.json
"""
import json
import re
import sys
from pathlib import Path

# 확인 문장에 이 말이 있으면 → 이 입력 항목 중 하나가 비교 조건으로 있어야 한다.
COMPARABLE = [
    (r"수급자|수급권자|수급\s*가구|생계급여|의료급여|주거급여|교육급여",
     {"기초생활보장 수급자", "기초생활보장 수급 가구", "생계급여 수급자", "의료급여 수급자", "주거급여 수급자", "교육급여 수급자"}),
    (r"차상위", {"차상위계층"}),
    (r"한부모", {"한부모가족"}),
    (r"중증|장애의\s*정도가\s*심한", {"중증 장애인"}),
    (r"장애인|장애\s*정도|등록\s*장애", {"등록 장애인", "중증 장애인"}),
    (r"중위\s*소득", {"가구 월소득 중위소득 대비", "가구 소득인정액"}),
    (r"소득인정액", {"가구 소득인정액"}),
    (r"만\s*\d+\s*세|\d+\s*세\s*(이하|이상|미만|초과)", {"만 나이"}),
    (r"연봉|연\s*소득|연간\s*소득", {"본인 연소득", "부부합산 연소득"}),
    (r"월\s*소득|월평균\s*(소득|보수)", {"본인 월소득", "가구 월소득 중위소득 대비"}),
    (r"부부\s*합산", {"부부합산 연소득"}),
    (r"맞벌이", {"맞벌이", "부부합산 연소득"}),
    (r"자동차|차량", {"자동차가액"}),
    (r"순자산", {"본인 순자산", "가구 순자산"}),
    (r"총\s*자산|총\s*재산", {"본인 총재산", "가구 총재산", "본인 순자산", "가구 순자산"}),
    (r"대학원", {"학교 구분"}),
    (r"재학|휴학|입학\s*예정|복학", {"재학 여부", "학교 구분"}),
    (r"재직|근로자|취업자|직장\s*가입자|사업주|자영업|개인사업자|창업|프리랜서|미취업",
     {"고용 상태"}),
    (r"구직\s*등록|워크넷|고용24", {"구직 등록", "고용 상태"}),
    (r"무주택", {"세대원 전원 무주택", "본인 명의 주택 보유"}),
    (r"혼인|신혼|기혼", {"혼인 상태", "혼인 기간"}),
    (r"임신|임산부", {"임신 중"}),
    (r"6세\s*이하|미취학|미성년\s*자녀", {"6세 이하 자녀", "막내 자녀 나이"}),
    (r"자녀", {"자녀 수", "6세 이하 자녀", "막내 자녀 나이"}),
    (r"국가유공|보훈", {"국가유공자·보훈대상자"}),
    (r"북한이탈", {"북한이탈주민"}),
    (r"다문화|결혼이민", {"결혼이민자·다문화가족"}),
    (r"자립준비|보호\s*종료|보호종료", {"자립준비청년"}),
    (r"농업인|어업인", {"농업인·어업인"}),
    (r"신용\s*(점수|평점)", {"신용점수(KCB)", "신용점수(NICE)"}),
    (r"외국인|국적", {"국적"}),
]
GENERIC = re.compile(r"공고(문)?\s*(기준|에서)?\s*확인|기관에\s*(별도\s*)?확인|세부\s*기준\s*확인|담당\s*기관.*확인")
AGE_OUT_OF_SCOPE = 50  # 진단은 청년(만 19~39세 중심)만 입력받는다. 이보다 높은 '이상' 경로는 만들 필요가 없다.


def _fields(conditions):
    return {c["field"] for c in conditions}


def lint_policy(policy: dict) -> list[tuple[str, str, str]]:
    """(위치 키, 규칙, 설명) 목록. 위치 키는 채점 화면 키와 같다(경로id|k번호 등)."""
    found = []
    common = policy.get("common", [])
    blocks = [("_common", common, policy.get("common_checks", []))]
    blocks += [(p["id"], p.get("conditions", []), p.get("checks", [])) for p in policy["paths"]]
    common_fields = _fields(common)

    for pid, conditions, checks in blocks:
        have = _fields(conditions) | common_fields
        if pid == "_common":
            # 공통 확인 사항이 말하는 기준은 경로 쪽 조건으로 들어가 있어도 인정한다.
            have |= set().union(*(_fields(p.get("conditions", [])) for p in policy["paths"]))
        for i, text in enumerate(checks):
            key = f"{pid}|k{i}"
            if GENERIC.search(text):
                found.append((key, "R3", f"원문 위치가 불분명한 일반론: {text[:40]}"))
            for pattern, fields in COMPARABLE:
                m = re.search(pattern, text)
                if not m:
                    continue
                if not fields & have:
                    found.append((key, "R1", f"'{m.group(0)}'는 비교 조건으로 쓸 수 있음 → {' / '.join(sorted(fields))}"))
        for i, c in enumerate(conditions):
            if c["field"] == "만 나이" and c["op"] == "gte" and (c.get("value") or 0) >= AGE_OUT_OF_SCOPE:
                found.append((f"{pid}|c{i}", "R4", f"청년 진단 범위 밖 나이 경로(만 {c['value']}세 이상)"))

    # R5: 금액·비율 조건이 일부 경로에만 있다(공통이 아니면서 경로 절반 이상에 있는 항목이 빠진 경로).
    paths = policy["paths"]
    if len(paths) >= 3:
        for field in {"자동차가액", "가구 총재산", "본인 총재산", "본인 순자산", "가구 순자산"}:
            with_field = [p for p in paths if field in _fields(p.get("conditions", []))]
            if field not in common_fields and len(paths) / 2 <= len(with_field) < len(paths):
                for p in paths:
                    if p not in with_field:
                        found.append((f"{p['id']}|c", "R5", f"다른 경로엔 있는 '{field}' 기준이 이 경로엔 없음"))
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 1
    draft = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    total = 0
    for number, policy in enumerate(draft["policies"], 1):
        for key, rule, message in lint_policy(policy):
            print(f"{number:>2}. {policy['name']} [{key}] {rule} {message}")
            total += 1
    print(f"자동 점검 {total}건")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
