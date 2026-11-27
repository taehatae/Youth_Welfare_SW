# 사용자 프로필 기반 복지서비스 추천 분류 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 기존 자격 분석을 변경하지 않고 백엔드의 별도 추천 분류와 상세 확인 조건을 제공해 결과 화면에 안전하게 표시한다.

**Architecture:** `EligibilityMatchingService.analyze_service()`가 기존 평가 결과에서 추천 분류, 사유, 불확실성, 통과 조건을 파생한다. Pydantic 응답 모델에 additive 필드를 선언하고 프런트엔드는 그 필드를 표시하며 추천 판정 규칙을 재구현하지 않는다.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, React, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-10-25-profile-based-welfare-recommendations-design.md`

## Global Constraints

- 기존 `status`, `gap_conditions`, `review_conditions`, `match_score`는 수정하지 않는다.
- 전체 `analysis_results`에서 분류하고 eligible-only `policies`로 분류하지 않는다.
- 필수 여부 또는 논리 관계가 불명확하면 `additional_review`로 분류한다.
- 서로 다른 원문 그룹에서 온 조건이 함께 분석되고 gap이 있으면 관계를 추정하지 않고 `additional_review`로 분류한다.
- DB, 파서, 자동 비교 및 점수 규칙은 변경하지 않는다.
- `match_score`를 확률로 표시하지 않는다.
- API 필드 추가는 호환성을 유지하고, 오래된 세션 데이터는 추가 확인으로 안전하게 표시한다.

## Review Focus

- **Gap + review 동시 존재:** 각 원래 목록과 `needs_review`를 그대로 보존하고 추천은 추가 확인이어야 한다. Task 1 테스트.
- **출처가 불분명한 gap:** 명시적 selection criteria가 아닌 실패를 확정 불일치로 과장하지 않는다. Task 1 테스트.
- **정보가 없는 서비스:** 자동 평가 0건을 우선 추천이나 조건 불일치로 보지 않는다. Task 1 테스트.
- **구형 스냅샷:** 신규 추천 필드가 없어도 파싱되고 안전하게 추가 확인으로 표시되어야 한다. Task 3 타입 검사와 fallback 점검.
- **통과 조건의 표시:** 점수만으로 통과 조건을 재구성하지 말고 백엔드가 전달한 상세 조건을 표시한다. Task 2 frontend build.

---

### Task 1: 백엔드 추천 분류 및 응답 모델

**Files:**
- Modify: `backend/app/services/eligibility_matching_service.py`
- Modify: `backend/app/schemas/welfare.py`
- Test: `backend/tests/test_eligibility_matching_service.py`

**Interfaces:**
- Consumes: `analyze_service()`의 기존 `evaluated`, `gaps`, `review` 결과와 조건의 `source_field`, `source_text`.
- Produces: 기존 analysis dictionary에 `recommendation_status`, `recommendation_reason`, `recommendation_uncertainty`, `confirmed_conditions` 추가. 기존 판정 필드는 그대로 둔다.

- [x] **Step 1: 실패 테스트 작성** 네 분류, gap+review, 정보 없음, ambiguous source/OR/exception, confirmed condition, 기존 상태와 점수 보존을 검증한다.
- [x] **Step 2: RED 실행** `backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/test_eligibility_matching_service.py -k recommendation`을 실행하고 새 기대값에서 실패하는지 확인한다.
- [x] **Step 3: 최소 구현** 서비스 분석 결과의 기존 상태를 변경하지 않고 추천 필드를 생성한다. Pydantic `EligibilityAnalysis`에 새 필드를 추가한다. `condition_mismatch`는 gap만 있고 모든 실패가 `selection_criteria` 출처이며 OR/예외 불확실성이 없을 때에만 허용한다.
- [x] **Step 4: GREEN 실행** 같은 명령을 실행한다. 기대: recommendation 관련 테스트 통과.
- [x] **Step 5: 전체 백엔드 테스트** `backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`를 실행한다.

### Task 2: 결과 카드에 추천 분류 표시

**Files:**
- Modify: `frontend/src/types/welfareApi.ts`
- Modify: `frontend/src/services/analysisSession.ts`
- Modify: `frontend/src/services/policyResults.ts`
- Modify: `frontend/src/components/policy/AnalysisPolicyCard.tsx`

**Interfaces:**
- Consumes: Task 1에서 제공한 추천 필드와 `confirmed_conditions`.
- Produces: `PolicyRow`에 별도 추천 상태·사유·불확실성·확인 조건을 전달하고 카드에서 한국어 분류와 상세 항목을 표시한다.

- [x] **Step 1: 응답 타입 확장** 신규 필드를 현재 API 타입에 정의하되 기존 저장 세션의 호환을 위해 클라이언트 복원 타입에서 누락을 허용한다.
- [x] **Step 2: 매핑 변경** `policyResults()`가 `analysis_results` 기준 신규 필드를 보존하고 구형 데이터의 추천 상태를 `additional_review`로 처리한다. 백엔드 정책 분류를 복제하지 않는다.
- [x] **Step 3: 카드 UI 변경** 주 라벨을 추천 분류로 표시하고 분석 상태, 추천 사유, 통과 조건, gap/review 및 불확실성을 구분한다. 기존 결과 페이지의 예비 진단 문구가 유지되는 것을 확인한다.
- [x] **Step 4: 프런트엔드 검증** `frontend`에서 `npm exec tsc -- --noEmit`과 `npm run build`를 실행한다.

### Task 3: 통합 응답·최종 검증

**Files:**
- Test: `backend/tests/test_eligibility_matching_service.py`
- Verify: `backend/app/schemas/welfare.py`, `frontend/src/services/analysisSession.ts`

**Interfaces:**
- Consumes: Task 1 response schema and Task 2 client mapping.
- Produces: API payload round-trip and compatibility evidence.

- [x] **Step 1: 전체 백엔드 테스트** `backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`.
- [x] **Step 2: 프런트엔드 타입 검사 및 빌드** `npm exec tsc -- --noEmit`, `npm run build`.
- [x] **Step 3: diff 검증** `git diff --check`; inspect response/schema changes and ensure no DB/model change.
- [x] **Step 4: 브라우저 가능성 확인** 브라우저 자동화 도구가 없으면 실행 검증 불가로 기록한다.

## Execution order

Task 1 must precede Task 2 because the frontend types and card consume the backend field names. Task 3 follows both. Do not push to `dev` or auto-merge. Any Hwang push or PR action will use only the feature branch and happen after validation.
