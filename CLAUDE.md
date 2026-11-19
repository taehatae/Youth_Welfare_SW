# 자격있청 (Youth Welfare SW)

청년이 정보를 입력하면 복지 정책마다 신청 가능 / 확인 필요 / 신청 불가를 판정하고, 안 되는 정책은 무엇이 어떻게 바뀌면 되는지(역설계) 안내하는 서비스.

- `backend/`: FastAPI + SQLAlchemy(SQLite). 판정 엔진, 정책 데이터, 검수 도구
- `frontend/`: React + Vite + TypeScript
- `docs/eligibility-paths/`: 자격 경로 데이터 설계·검수 문서

## 실행과 검증 (Windows)

```bash
# 백엔드 (backend 폴더에서). 자격 경로 판정을 켜려면 환경변수 3개 필요
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
#   USE_ELIGIBILITY_PATHS=true  USE_STRUCTURED_CONDITIONS=true  USE_LLM_JUDGE=false

# 프론트 (frontend 폴더에서). /api 는 127.0.0.1:8000 으로 프록시
node node_modules/vite/bin/vite.js

# 테스트
cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest -q
cd frontend && node --import ./tests/register-ts.mjs --test tests/*.test.mjs
cd frontend && node node_modules/typescript/bin/tsc --noEmit -p .
```

- 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`을 붙인다.
- 로컬 DB 구성은 `docs/eligibility-paths/LOCAL_SETUP.md`.

## 자격 경로 데이터

정책 하나 = 신청 경로 여러 개(또는). 경로 = 비교 조건(그리고) + 확인 사항(판정에 안 씀). 모든 경로에 공통인 조건은 `common`.

데이터 흐름:
```
welfare-policies.json (정책 원문)
  → 초안 data/eligibility_paths_batchN_draft.json (AI 작성, 조건마다 원문 근거 구절)
  → 사람 채점 (scripts/review_server.py, 결과 *_review.json)
  → scripts/merge_reviewed.py  → data/eligibility_paths_reviewed.json (검수본, 원문 해시·검수일 기록)
  → scripts/build_eligibility_paths.py → data/eligibility_paths.json (시드)
  → scripts/load_eligibility_paths.py → DB
```

- 검수본·시드를 손으로 고치지 않는다. 고친 초안을 `merge_reviewed.py`로 합치고 빌드·적재한다.
- 초안을 만든 뒤 `scripts/lint_draft.py <초안>`으로 자동 점검한다.
- 원문이 바뀌면(해시 불일치) 그 정책은 시드에서 빠지고 재검수 대상이 된다.
- 작성·검수 규칙 전체: `docs/eligibility-paths/LLM_GUIDE.md`(검수 규칙집 R1~R9), `REVIEW_GUIDE.md`.

### 검수 원칙 (가장 중요)
1. **잘못된 "불가"를 만들지 않는다.** 신청할 수 있는 사람이 불가로 나오면 안 된다. "가능"이 조금 넓게 나오는 것은 괜찮다(확인 사항으로 안내).
2. **입력으로 비교할 수 있는 기준은 비교 조건으로 넣는다.** 확인 사항에만 두지 않는다. 기준 대상(본인/세대)이 입력과 다르면 넣지 않는다.
3. **원문에 없는 말을 만들지 않는다.** 모든 조건의 `evidence`는 원문에 글자 그대로 있어야 한다(떨어진 구절은 `...`).
4. 가구 형태별로 기준이 다르면 가장 넓은 값을 조건으로, 형태별 표는 확인 사항으로.

## 판정·역설계 규칙 (backend/app/services)

- `eligibility_path_service.py`: 경로 판정. 미충족 하나라도 → 불가, 미충족 없고 충족 하나라도 → 가능, 그 밖 → 확인 필요. 정책은 가능한 경로가 하나라도 있으면 가능.
- `structured_condition_service.py`: 조건 비교, 기준 문구(`describe`), 역설계 문장(`condition_guide`), 개선 난이도(`difficulty`, `difficulty_group`).
  - 저장값은 원문 표현으로 되돌려 보여준다(2,699,999원 이하 → 270만원 미만, 50.1% 이상 → 50% 초과).
  - 시간이 지나도 다시 충족할 수 없는 조건(나이·혼인 기간·막내 자녀 나이 상한 초과)은 `impossible`, 그런 경로는 화면에서 숨긴다.
  - 성별·장애·한부모·수급 같은 대상자 조건은 "바꾸면 충족"이라고 하지 않고 "이 경로는 ○○가 대상"이라는 정보로 안내한다.
- `personalized_condition_guidance.py`: 로그인한 본인에게만 금액 차이가 들어간 맞춤 안내. 공개 응답·저장 스냅샷에는 입력값을 넣지 않는다.
- 추천 경로: 미충족 조건마다 개선 난이도 점수를 매겨 합이 가장 낮은 경로. 사용자가 화면 "추천 기준 보기·바꾸기"에서 종류별 배율을 바꿀 수 있고(`frontend/src/services/difficultyPrefs.ts`, 브라우저 저장), 판정은 바뀌지 않는다.

## 프론트

- 결과 카드: `frontend/src/components/policy/AnalysisPolicyCard.tsx`. 경로가 있는 정책은 미충족·추가 확인·충족 탭을 경로 카드로 보여주고, 추천 경로만 크게, 나머지는 "다른 경로 확인하기"에 접는다.
- 경로 카드 계산: `frontend/src/services/conditionGuidance.ts`(`pathCards`).

## 작업 규칙

- **커밋·푸시는 그 요청에서 명시적으로 부탁받았을 때만 한다.** 수정 요청은 수정·검증까지만 하고 커밋 여부를 묻는다.
- 응답은 한국어로, 짧고 쉬운 문장으로.