# 자격있청 기술 인수인계서

## 1. 인수인계 기준과 Git 상태

2026-11-20 한국시간 기준입니다. 저장소는 [taehatae/Youth_Welfare_SW](https://github.com/taehatae/Youth_Welfare_SW)이며, 두 사람이 작업 브랜치에서 개발하고 `dev`에 통합합니다. 아래 내용은 해당 시점의 코드, 원격 참조, Git 이력, 정책 파일과 공유 SQLite를 대조한 결과입니다. 후속 세션에서는 먼저 현재 상태를 다시 확인하세요.

| 참조 | 커밋 | 관계 |
| --- | --- | --- |
| 로컬 `Hwang` (현재 HEAD) | `4c0abe3da9c64e1ebd7f1dede962404f615ec1f8` | 로컬 `dev`, 로컬 `origin/dev`, 실제 원격 `dev`와 동일 |
| 실제 원격 `Hwang` / 로컬 `origin/Hwang` | `973a32e146085bbc8abab91a8ed8c048cf56bd98` | 로컬 `Hwang`보다 병합 커밋 1개 뒤. 안전성 변경 커밋 자체는 이미 원격과 `dev`에 있음 |
| 실제 원격 `Jang` / 로컬 `origin/Jang` | `86b003df58a8f6f1f8f763126eec8a0c62b3782e` | 현재 `dev`의 조상. `dev` 대비 8개 뒤이며 별도 로컬 `Jang` 없음 |

- 원격 SHA는 `git ls-remote`로 확인했습니다. 현재 `Hwang`과 `dev`에는 브랜치별 코드 차이가 없습니다. 원격 `Hwang`과 `Jang`에도 현재 `dev`에 없는 별도 커밋은 확인되지 않았습니다.
- 작성 전 `git status`에서 추적 파일 변경·스테이징은 없었습니다. 기존 미추적 `docs/superpowers/plans/2026-11-19-reverse-guidance-privacy.md`는 당시 계획·검증 이력으로 로컬에 남아 있습니다.
- 루트 [CLAUDE.md](../CLAUDE.md)는 실행·검수·판정과 작업 규칙을 전달하는 추적 문서입니다. 앱 설정을 읽거나 적용하는 파일은 아닙니다. 이전 `Hwang`의 `2968a52` 문서 변경은 #23 병합에 포함됐습니다.

| 병합된 PR | 후속 작업에서 알아둘 내용 |
| --- | --- |
| [#15](https://github.com/taehatae/Youth_Welfare_SW/pull/15) | 경로 엔진·검수 도구 도입. 당시 20개 사람 검수, 132개 변환본 |
| [#19](https://github.com/taehatae/Youth_Welfare_SW/pull/19) | 로그인 세션을 이용한 진단 당시 입력값 기반 맞춤 안내 |
| [#20](https://github.com/taehatae/Youth_Welfare_SW/pull/20) | 경로별 카드, 개선 난이도와 사용자 가중치, 일부 정책 재검수. `CLAUDE.md` 도입 |
| [#21](https://github.com/taehatae/Youth_Welfare_SW/pull/21) | 7차 검수 반영. 152개 전부 사람 검수, 신청 경로 420개 |
| [#22](https://github.com/taehatae/Youth_Welfare_SW/pull/22) | 계정 데이터가 비어 있는 정책 DB 적재본을 Git LFS로 공유 |
| [#23](https://github.com/taehatae/Youth_Welfare_SW/pull/23) | 정확한 난이도 점수 보호, 스냅샷 동일성 검증, 전용 응답의 메모리 관리, 경로 문구 보완. 현재 HEAD의 병합 |

## 2. 프로젝트 목표와 구현 범위

청년이 정책을 찾고, 입력한 상태를 정책 기준과 비교해 충족·미충족·추가 확인 항목을 이해하도록 돕습니다. 현재 진단 입력 연령은 만 19~34세입니다. 정책 탐색·상세 조회는 별도로 이용할 수 있습니다. 자격 진단은 현재 입력과 수집된 정책 기준에 따른 사전 안내이며, 담당 기관의 최종 결정과 구분합니다. [UserProfileCreate](../backend/app/schemas/user.py) · [DiagnosisPage](../frontend/src/features/diagnosis/DiagnosisPage.tsx)

| 상태 | 범위 |
| --- | --- |
| 구현됨 | 정책 검색·상세, 계정·세션, 프로필 제출, 진단·최신 현황·이전 결과, 관심 정책 저장·상태·메모, 검수 경로 판정, 경로별 역설계, 로그인 맞춤 안내, 사용자별 난이도 가중치 |
| 제한적으로 구현됨 | 입력값과 구조화된 조건으로 비교 가능한 항목만 자동 판정. 일부 필드와 값만 구체적 개인화 지원. 검증할 수 없는 과거 진단은 일반 안내와 저장 판정 유지 |
| 실험·레거시 | `USE_LLM_JUDGE`는 선택 실험 경로. `GET /api/v1/welfare/reverse-engineering`은 프로필 소유권 확인 뒤 빈 `recommendations`를 반환하는 자리표시자. 실제 역설계 화면은 경로 결과와 전용 안내 API를 사용 |
| 미해결 | 환경별 줄바꿈에 따른 계산 지문 차이, 일부 검수 근거 경고. §11 참조 |

## 3. 핵심 기술과 데이터 흐름

프론트는 React 19, TypeScript, Vite 및 CSS/Tailwind입니다. `main.tsx`에서 앱을 띄우고 `App.tsx`가 해시 라우팅, 로그인 복구·전환 및 계정 진단 상태를 관리합니다. 백엔드는 FastAPI, Pydantic 설정·스키마, SQLAlchemy 2, SQLite를 사용합니다. `app/main.py`가 `/api/v1`의 인증·정책·사용자·복지 라우트를 등록하고, `database/connection.py`의 `get_db()`로 요청마다 세션을 엽니다. [프론트 진입점](../frontend/src/main.tsx) · [App](../frontend/src/app/App.tsx) · [FastAPI 진입점](../backend/app/main.py) · [DB 연결](../backend/app/database/connection.py)

1. **탐색** — `PolicyExplorerPage`와 `PolicyDetailPage`가 `welfareApi.ts`로 `GET /api/v1/policies`, `GET /api/v1/policies/{id}`를 호출합니다. `PolicyCatalogService.search()/detail()`이 저장된 정책 원문·분야·신청 정보를 제공하며 로그인이나 개인 프로필 조회를 요구하지 않습니다. 정책 상세의 지원 주기와 실제 접수 일정은 다른 정보입니다. [목록](../frontend/src/features/policies/PolicyExplorerPage.tsx) · [상세](../frontend/src/features/policies/PolicyDetailPage.tsx) · [카탈로그 서비스](../backend/app/services/policy_catalog_service.py)
2. **입력과 평가** — 로그인한 사용자가 `DiagnosisPage`에서 필수 기본값과 선택 정보를 입력합니다. `App.completeDiagnosis()` → `diagnoseAccount()` → `POST /api/v1/welfare/diagnose` → `AccountService.analyze()` → `EligibilityMatchingService.analyze_user()`로 이어집니다. [프론트 API](../frontend/src/services/welfareApi.ts) · [진단 라우트](../backend/app/api/routes/welfare.py) · [계정 서비스](../backend/app/services/account_service.py)
3. **저장과 조회** — 새 진단은 본인 프로필과 `account_workspaces.state`의 스냅샷을 같은 트랜잭션에 저장합니다. 새 결과는 `diagnosis`와 `current`에 기록하고 이전 진단은 `previousDiagnosis`로 관리합니다. `POST /welfare/refresh`는 저장 프로필로 최신 현황 `current`를 갱신하고 `previous`에 이전 현황을 남깁니다. `diagnosis`는 새 입력 진단에서 갱신됩니다. `GET /users/state`는 계정의 저장 결과를 읽어 공개 범위에 맞춰 돌려줍니다. [계정 저장소](../backend/app/repositories/account_repository.py) · [응답 스키마](../backend/app/schemas/account.py)
4. **화면과 개인화** — `policyResults()`가 분석 응답을 화면 행으로 바꾸고 `ResultPage`와 `DashboardPage`가 각각 진단 기록과 최신 현황을 보여줍니다. 미충족 탭에서 `PersonalizedGuideAccess`가 로그인 전용 안내를 요청해 기존 판정과 함께 표시합니다. [결과 매핑](../frontend/src/services/policyResults.ts) · [진단 결과](../frontend/src/features/diagnosis/ResultPage.tsx) · [나의 현황](../frontend/src/features/dashboard/DashboardPage.tsx)

## 4. 정책 데이터와 검수 체계

데이터는 `serv_id`로 연결합니다. [welfare-policies.json](../backend/data/welfare-policies.json)은 수집한 정책 원문과 기존 파싱 조건의 이전용 스냅샷, [eligibility_paths_reviewed.json](../backend/data/eligibility_paths_reviewed.json)은 사람 검수본, [eligibility_paths.json](../backend/data/eligibility_paths.json)은 실제 적재 시드입니다. `structured_conditions.json`과 `structure_gold_*.json`은 각각 경로 적용 실패 시 사용할 구조화 분석 데이터와 과거 정답지 입력입니다. 자동 변환 기능은 시드 빌더에 남아 있으나 현재 적재 대상에는 변환본이 없습니다.

| 항목 | 확인한 현재 값 |
| --- | ---: |
| 원문 정책 / 기존 파싱 조건 | 152개 / 1,749개 |
| 사람 검수본 / 시드 정책 / 시드 변환본 | 152개 / 152개 (시드 버전 2) / 0개 |
| 시드의 신청 경로 (단독 기본 경로 포함) | 420개 |
| 공유 DB 경로 행 | 572행 (신청 경로 420 + 정책별 `_common` 152) |
| 경로 비교 조건 (공통 조건을 경로마다 중복 집계하지 않음) | 533개 (공통 153 + 경로별 380) |
| 자체 비교 조건이 없는 신청 경로 / 공통을 합쳐도 비교 조건이 없는 신청 경로 | 168개 / 66개 |
| 정책 ID·원문 정합성 | 원문·검수본·시드 ID 집합 일치. 시드·검수본·DB 원문 해시 불일치 각각 0건 |

- **표현** — 정책은 여러 신청 경로 중 하나를 보는 OR 구조입니다. 모든 경로에 공통인 `common`과 해당 경로의 `conditions`는 함께 비교합니다. `checks`와 `common_checks`는 서류·공고·기관 확인용이며 자동 비교에 쓰지 않습니다. `preferences`는 우대·선호 메타데이터로 전달되며 현재 판정과 순위 계산 항목에는 들어가지 않습니다. `evidence`는 원문 근거 구절입니다.
- **구분** — 엔진이 읽는 정책 레코드는 `status=reviewed`입니다. 과거에 정답지로부터 자동 변환된 것도 이 상태일 수 있어 사람 검수 여부에는 `drafted_by == "converted"`와 응답의 `path_review`를 함께 확인합니다.
- **검수** — 정책 원문을 근거로 초안 작성 → `lint_draft.py`와 `make_review_sheet.py` 점검 → `review_server.py` 사람 채점 → 채점 반영본을 `merge_reviewed.py`로 검수본에 병합 → `build_eligibility_paths.py`로 시드 생성 → 의도한 DB에 `load_eligibility_paths.py`로 반영합니다. 검수본과 생성된 시드를 함께 검토합니다. 기존 상태 확인에는 이 쓰기 도구들이 필요 없습니다. [작성 규칙](eligibility-paths/LLM_GUIDE.md) · [검수 절차](eligibility-paths/REVIEW_GUIDE.md)
- **원문 변경** — `source_hash()`는 비어 있지 않은 대상 상세와 선정 기준을 줄바꿈으로 연결한 문자열의 SHA-256입니다. 시드를 생성할 때 검수 당시와 다른 원문은 재검수 대상으로 제외하고, 런타임에서도 DB 원문 해시가 맞지 않으면 해당 정책은 경로 판정 대신 이전 분석을 사용합니다. [빌더](../backend/scripts/build_eligibility_paths.py) · [경로 엔진](../backend/app/services/eligibility_path_service.py)

## 5. 자격 판정과 경로별 역설계

**엔진 선택.** `analyze_user()`는 `USE_LLM_JUDGE`가 켜지면 실험 판정으로 조기 반환합니다. 그 외에는 레거시 분석을 만든 뒤 `USE_STRUCTURED_CONDITIONS`의 구조화 분석으로, 이어 `USE_ELIGIBILITY_PATHS`의 검수 경로 분석으로 가능한 정책만 덮어씁니다. 레거시는 원문이 있으면 현재 파서로 재해석하고, 원문이 없으면 저장된 기존 조건을 사용합니다. 경로 분석이 없거나 해시 확인에 실패하면 그 정책의 이전 분석이 남습니다. `analysis_results`는 전체 결과이며 `policies`는 `eligible` 요약입니다. [엔진 선택](../backend/app/services/eligibility_matching_service.py) · [원문 파서](../backend/app/services/eligibility_condition_service.py)

**비교.** `user_values()`가 기본·추가 프로필을 조건 필드별 값으로 정리합니다. 연령, 지역, 고용·학업, 가구, 소득인정액 비율 등을 단위와 대상에 맞춰 구분합니다. 예를 들어 본인 월소득, 가구 월소득, 가구 소득인정액을 서로 대체하지 않습니다. `matches()`는 `gte/lte/between/one_of/is_true`로 평가하며, 제외 조건은 확인된 비교 결과를 반전합니다. 미입력·알 수 없음 또는 입력 구간이 기준 일부만 겹치면 확인 필요입니다. `None`과 유효한 `False`·0은 다른 값입니다. [비교와 값 변환](../backend/app/services/structured_condition_service.py)

**경로와 판정.** `_evaluate_path()`에서 미충족이 하나라도 있으면 `ineligible`, 미충족 없이 충족이 하나라도 있으면 `eligible`, 충족·미충족이 모두 없으면 `needs_review`입니다. `eligible`은 현재 입력값을 바탕으로 자격 판정 엔진이 계산한 상태입니다. 일부 미확인 비교 조건이나 `checks`가 남을 수 있습니다. 실제 신청 자격은 행정적으로 최종 확정된 상태가 아니며, 공식 공고와 담당 기관을 통한 추가 확인이 필요할 수 있습니다. 정책은 가능한 경로가 있으면 가능, 그다음 확인 필요, 모든 경로가 불가면 불가입니다. `_rank_paths()`는 판정 우선순위 → `impossible` 여부 → 기본 난이도의 합 → 미충족 수 → 미확인 수 → 원문 순서로 정렬합니다. `matched_path_id`는 진단 당시 대표 경로이고 `match_score`는 그 경로에서 충족 / (충족 + 미충족) × 100을 소수 첫째 자리로 반올림한 값입니다. 비교한 조건이 없으면 0입니다. `gap_conditions`는 대표 경로의 실패 요약이며, 불가에서 공통 조건이 막으면 공통 실패 조건으로 요약합니다. 전체 경로는 `eligibility_paths`에 남습니다. [경로 비교·순위·요약](../backend/app/services/eligibility_path_service.py)

**역설계.** 일반 `condition_guide()`는 현재 값·정확한 차이를 노출하지 않으면서 필요한 상태·방향을 안내합니다. 로그인 전용 `personalized_guide()`는 진단 당시 실제 비교값을 바탕으로 지원하는 단일 조건에서 수치 차이(원·세·%p 등)나 범주 차이를 설명합니다. 기준 표시 문자열을 역으로 파싱하지 않습니다. 나이 상한 초과처럼 시간이 지나면 회복할 수 없는 조건을 그렇게 설명하고, 성별·장애 등은 대상 조건으로 설명합니다. 고용·거주·소득의 기준 차이를 보여주는 것과 퇴사·이사·소득 감소를 행동으로 권하는 것은 구별합니다. [일반 안내와 수치 차이](../backend/app/services/structured_condition_service.py) · [맞춤 안내](../backend/app/services/personalized_condition_guidance.py)

**난이도와 프론트 순위.** 조건별 `difficulty()`는 지원하는 수치 조건에 기준 대비 차이를 반영하며, 시간 조건은 필요한 햇수, 상태 조건은 그룹별 기본점을 씁니다. `impossible_failure()`는 나이·혼인 기간·막내 자녀 나이와 같은 시간 값에서 감소가 필요한 실패를 표시합니다. `pathCards()`는 가능한 경로가 있으면 `impossible` 경로를 접힌 목록에서도 숨기고, 모두 불가능하면 이유를 볼 수 있게 남깁니다. 모든 미충족 점수를 전용 응답에서 확인했을 때만 종류별 가중치(0.25·0.5·1·2·4배)로 화면 순위를 다시 계산합니다. 점수가 없거나 불완전하면 저장 순위를 사용합니다. 이 추천 순위는 진단 당시 판정·`match_score`·`matched_path_id`와 분리됩니다. 개선 비용과 실현 가능성의 객관적 평가가 아닌 비교용 지표입니다. [점수 공식](../backend/app/services/structured_condition_service.py) · [화면 정렬](../frontend/src/services/conditionGuidance.ts) · [가중치](../frontend/src/services/difficultyPrefs.ts)

## 6. 개인정보 보호와 전용 API

| 보호 계층 | 실제 동작 |
| --- | --- |
| 인증·소유권 | `auth_service.current_account()`가 HttpOnly 세션 쿠키의 해시로 SQLite 세션과 만료를 확인합니다. `X-Account-ID`가 있으면 계정 전환도 감지합니다. `/users/condition-guides/view`는 현재 계정 워크스페이스에서 `snapshot`(`current` 또는 `diagnosis`), `profile_key`, `checked_at`, `policy_id`를 대조합니다. `profileKey`는 서버 HMAC 식별자입니다. |
| 스냅샷 유효성 | 세션 확인 후 저장된 정책·조건·계산 기준과 현재 정책의 동일성을 검증합니다. 실패하면 맞춤 안내와 점수 목록을 비워 반환합니다. §7 참조 |
| 일반 응답·신규 저장 | `public_state()/hide_input_values()`는 일반 응답에서 프로필을 제거하고 표시용 현재 값을 마스킹하며 `difficulty`·`evaluation_context`를 `null`로 반환합니다. `/welfare/matched`도 적용됩니다. `without_difficulty()`는 **신규 스냅샷**에 정확한 난이도 점수를 저장하지 않도록 합니다. 서버 내부에는 재현용 당시 프로필·평가 행·지문이 남습니다. 이미 저장된 레거시 점수는 응답에서만 숨기며 원본을 일괄 수정하지 않습니다. |
| 전용 응답·브라우저 수명 | `POST /api/v1/users/condition-guides/view`는 `items`, `difficulties`, `unavailable_reason`을 제공합니다. 경로·조건 순번 또는 대표 gap 순번으로 연결하고, `/api/v1/` 백엔드 응답에 `Cache-Control: no-store`, 전용 프론트 요청에도 `cache: "no-store"`가 적용됩니다. |

비밀번호는 서버에서 salt가 있는 PBKDF2 해시로 관리하고, 세션 토큰은 DB에 해시로 저장합니다. 계정 로그인은 쿠키 기반입니다. **개인화 API는 로그인 세션을 사용하고, 저장된 전체 프로필 열람 `POST /users/profile/view`는 별도 본인 확인**을 요구합니다. 전용 안내의 보호를 프로필 열람 권한으로 확대하지 마세요. [인증 로직](../backend/app/services/auth_service.py) · [사용자 API](../backend/app/api/routes/users.py) · [마스킹](../backend/app/services/profile_privacy.py) · [캐시·출처 검사](../backend/app/main.py)

`createPrivateGuideSession()/createPrivateGuideLoader()`는 전용 데이터를 진단·정책별 메모리 맵에 보관합니다. 타깃 키와 요청 세대가 달라진 응답은 버리고, 탭 닫기·화면 이탈·진단 변경·계정 전환·로그아웃 시 이전 맵 참조까지 비웁니다. 숨김·페이지 이탈 이벤트와 탭 간 인증 변경 알림을 사용하며, 보이는 화면에서 복귀·주기적 재조회로 세션을 확인합니다. 프론트의 지속 저장 대상은 사용자 가중치 설정(`youth-welfare:difficulty-prefs`)이며, 정확한 점수·맞춤 안내는 별도 저장하지 않습니다. 서버 저장 관심 정책과 진단 JSON은 공유 DB나 로그로 내보내지 마세요. [세션 맵](../frontend/src/services/conditionGuidance.ts) · [컴포넌트 수명](../frontend/src/components/policy/PersonalizedGuideAccess.tsx) · [인증 알림](../frontend/src/services/welfareApi.ts)

## 7. evaluation_context와 스냅샷 검증

`eligibility_path_service.analyze()`가 정책별 진단 결과에 `evaluation_context` v1을 채웁니다. `AccountService.analyze()`가 다른 경로 분석 결과와 함께 스냅샷의 `analysis.matched.analysis_results[]`에 저장합니다. 지문 입력에는 사용자 값이나 난이도 점수가 없습니다. [지문 구현](../backend/app/services/eligibility_snapshot_context.py)

| 필드 | 검증 대상 |
| --- | --- |
| `source_sha256` | 정책 대상 상세·선정 기준 및 검수 시드의 원문 지문 일치 |
| `policy_sha256` | 서비스 ID, 경로 ID·순서·라벨·종류·우선순위·checks, 비교 필드·연산자·값·단위·제외 역할·근거 등 |
| `calculation_sha256` | 네 계산 소스 파일의 해시(줄바꿈을 LF로 통일한 뒤 계산). % 단위 조건이 있으면 기준 연도와 중위소득·도시근로자 참조표도 포함 |

`snapshot_details()`는 사람 검수 정책만 대상으로 `validate_snapshot()`을 통과한 뒤 저장 당시 프로필에서 비교값을 복원합니다. 원문·지문 외에도 저장된 경로 순서와 개수, 각 조건 행의 표시 기준·근거·공통 여부·당시 비교값, 대표 경로의 존재를 확인합니다. 같은 검증을 대표 gap 안내와 전체 경로 안내에 적용합니다. 지문 없는 이전 진단, 원문·구조 변경, 계산 변경, 입력 맥락 불일치 등은 이유 코드와 빈 `items/difficulties`로 처리합니다. 현재 데이터를 과거 진단에 소급하거나 저장된 판정과 대표 경로를 다시 쓰지 않습니다. [검증과 응답 조립](../backend/app/services/personalized_condition_guidance.py)

**줄바꿈 호환성.** `structured_condition_service.py`, `eligibility_path_service.py`, `median_income_reference.py`, `urban_worker_income_reference.py`는 해시 전에 CRLF/CR을 LF로 통일합니다(`code_hash`). 그래서 Windows(CRLF)와 LF 체크아웃에서 같은 커밋은 같은 계산 지문을 냅니다. 이 수정 전에 CRLF 작업 트리에서 만든 진단 기록은 지문이 한 번 달라져 `calculation_changed`가 되며, 이때도 **개인화 안내와 전용 점수만 생략**되고 저장 판정과 민감값 마스킹은 유지됩니다. LF 환경에서 만든 기존 기록은 지문이 그대로입니다.

## 8. 프론트 화면에서 확인할 동작

- [ResultPage](../frontend/src/features/diagnosis/ResultPage.tsx)는 `diagnosis`를 표시하고 검색·분류·사람 검수 경로 필터를 제공합니다. [DashboardPage](../frontend/src/features/dashboard/DashboardPage.tsx)는 `current/previous`와 저장 정책을 다룹니다. 관심 저장·메모·진행 상태는 사용자 API와 연결됩니다.
- [AnalysisPolicyCard](../frontend/src/components/policy/AnalysisPolicyCard.tsx)는 충족·미충족·추가 확인 탭, 대표 경로, 접어서 표시하는 다른 경로와 공식 안내 링크를 제공합니다. 현재 탭의 조건이 동일한 다른 경로는 이름을 묶습니다. 미확인 비교 조건이 남으면 필요한 추가 확인을 표시하며, `checks`가 있으면 공식 안내 확인을 별도로 표시합니다.
- 미충족 탭에서는 전용 안내 → 일반 변화 안내 → 정책 기준 순서로 표시합니다. 전용 점수 수신 전·실패·과거 스냅샷에는 보통 **대표 경로**를 표시합니다. 점수를 정상 수신해 정렬할 수 있는 미충족 경로에는 **현재 설정 기준 추천 경로**를 사용합니다. `DifficultySettings`로 가중치를 바꿔도 백엔드 판정과 대표 경로 값은 그대로입니다. [정렬 상태와 문구](../frontend/src/services/conditionGuidance.ts) · [가중치 UI](../frontend/src/components/policy/DifficultySettings.tsx)

## 9. SQLite·Git LFS·개발 환경

`Settings.database_url`의 기본값은 `sqlite:///./youth_welfare.db`입니다. `backend/`에서 실행하면 그 폴더의 DB를 사용합니다. 설정은 실행 디렉터리의 `.env`를 읽고 프로세스 환경변수가 우선합니다. `app.main` import 시 `create_all()`이 없는 테이블을 생성합니다. 기존 스키마 변경을 수행하는 마이그레이션은 아닙니다. SQLite 연결에는 외래 키 검사를 켭니다. [설정](../backend/app/core/config.py) · [환경 예시](../backend/.env.example) · [DB 연결](../backend/app/database/connection.py)

| 영역 | 테이블과 관계 |
| --- | --- |
| 정책 | `welfare_services` → `welfare_eligibility_conditions`(기존 분석용), `policy_eligibility` → `eligibility_paths` → `eligibility_path_conditions` |
| 사용자와 기록 | `accounts` ↔ `users`와 `user_eligibility_conditions`, `account_sessions`와 `auth_attempts`, `account_workspaces.state`(진단·현황·관심 정책 JSON) |
| 동기화 | `welfare_sync_batches/items`와 `welfare_api_quota_windows`. 운영자 CLI에서 확인한 쿼터와 배치 진행 상황을 기록하며 앱 진단과 별개 |

[공유 DB](../backend/youth_welfare.db)는 읽기 전용으로 검사했습니다. 계정·세션·워크스페이스·사용자·추가 프로필·인증 시도 행은 모두 0, 무결성 검사 `ok`, 외래 키 오류 0건입니다. SHA-256과 크기는 Git 인덱스의 LFS 포인터와 일치합니다. LFS의 현재 추적 파일은 이 DB와 `frontend/src/assets/brand/youth-wordmark.png`입니다.

- 루트 [.gitignore](../.gitignore)는 일반 DB·비밀 설정·`.tmp-*`·로그·빌드 결과·의존성을 제외합니다. `.env.example`과 프론트 데모용 `.env.demo`는 예외입니다. [backend/.gitignore](../backend/.gitignore)의 `!youth_welfare.db`는 공유 DB의 예외입니다. **이 공유 파일에 가상 또는 실제 계정을 만든 뒤 그대로 스테이징하면 사용자 데이터까지 들어갈 수 있습니다.** 진단 검증에는 별도 DB 및 테스트 계정을 사용하세요.
- [.gitattributes](../.gitattributes)는 DB·이미지 등 바이너리를 LFS 포인터로 추적합니다. Git 상태/추가/푸시에서 LFS 임시 경로 접근이 거부되면 객체 해시·크기를 먼저 확인하세요. 필터를 끈 상태의 DB 변경 표시는 실제 내용 차이의 근거로 삼지 말고, LFS 설정·스테이징·복원으로 우회하지 않습니다. 이번 문서 작성 시 일반 `git status`가 정상 동작했습니다.
- 내려받은 공유본이 온전하면 현재 시드가 이미 적재되어 있습니다. 빈 격리 DB를 별도로 구성할 때만, 의도한 경로를 지정한 뒤 테이블 생성 → `scripts.policy_data import` 미리보기와 백업을 포함한 `--apply` → `scripts.load_eligibility_paths` 순서로 진행합니다. 정책 import는 대상 서비스의 저장 조건을 교체하고, 경로 적재는 경로·조건을 통째로 교체하며 시드에 없는 기존 경로 레코드를 삭제합니다. 두 작업은 사용자·진단 테이블을 갱신하지 않지만, 기존 스냅샷이 새 정책과 불일치해 개인화가 보류될 수 있습니다. `load()`도 **경로 테이블 전체가 비어 있으면** 요청 중 시드를 적재·커밋할 수 있습니다. 일부만 있다고 자동 갱신하지 않습니다. [정책 이전](../backend/app/services/policy_data_transfer.py) · [경로 적재](../backend/scripts/load_eligibility_paths.py) · [백업 도구](../backend/scripts/backup_database.py)
- 외부 정책 갱신은 [welfare_sync.py](../backend/scripts/welfare_sync.py) 및 동기화 서비스 영역입니다. 정상적인 로컬 진단과 시드 적재에는 외부 공공 API 키나 Ollama가 필요 없습니다. `POST /welfare/sync`는 로그인과 별도의 운영자 토큰을 요구하며, 토큰이 설정되지 않으면 비활성화됩니다.

### 검증용 서버 실행 예시 (Windows PowerShell)

아래의 `.tmp-handoff-validation/integration.db`는 **이미 생성되고 정책 데이터가 적재된 격리 DB**가 있을 때 사용하는 예시 경로입니다. 해당 파일이 없으면 `Resolve-Path`가 실패할 수 있습니다. 격리 DB가 없다면 공유 `backend/youth_welfare.db`를 테스트용으로 대신 사용하지 마세요. 격리 DB 생성과 정책 시드 적재는 별도의 명시적인 요청이 있고 대상 경로와 기존 데이터에 미칠 영향을 확인한 뒤 진행합니다. 최초 점검 과정에서는 실행하지 마세요. `backend/`에서 `.venv`와 [requirements.txt](../backend/requirements.txt), `frontend/`에서 [package.json](../frontend/package.json)과 lockfile 기준으로 의존성을 준비합니다.

```powershell
# 저장소 루트에서 시작하는 백엔드 터미널
cd backend
$testDb = (Resolve-Path -LiteralPath '.tmp-handoff-validation/integration.db').Path
$env:DATABASE_URL = 'sqlite:///' + $testDb.Replace('\', '/')
$env:USE_ELIGIBILITY_PATHS = 'true'
$env:USE_STRUCTURED_CONDITIONS = 'true'
$env:USE_LLM_JUDGE = 'false'
$env:FRONTEND_ORIGINS = 'http://127.0.0.1:5191'
$env:COOKIE_SECURE = 'false' # 로컬 HTTP 검증에서만
.\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8019
```

```powershell
# 별도 터미널에서 저장소 루트 기준
cd frontend
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8019/api/v1'
npm.cmd run dev -- --host 127.0.0.1 --port 5191 --strictPort
```

기본 개발 포트는 백엔드 8000, Vite 5173입니다. Vite 개발 프록시는 기본 `/api`를 8000으로 전달하므로 격리 포트에서는 API 주소를 명시합니다. `FRONTEND_ORIGINS`와 브라우저 주소의 호스트·포트를 맞추세요. [Vite 설정](../frontend/vite.config.ts) · [API URL](../frontend/src/services/welfareApi.ts)

## 10. 테스트와 검증 방법

| 검사 | 실행 위치와 명령 |
| --- | --- |
| 백엔드 전체 | `backend/`에서 `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider` |
| 프론트 전체 | `frontend/`에서 `npm.cmd test` |
| TypeScript | `frontend/`에서 `node node_modules/typescript/bin/tsc --noEmit -p .` |
| 빌드 | `frontend/`에서 `npm.cmd run build` |

[백엔드 conftest](../backend/tests/conftest.py)가 기본 DB를 메모리 SQLite로 설정하고 세 기능 플래그를 끕니다. 관련 테스트는 필요에 따라 플래그를 켜고 합성 계정 또는 임시 DB를 사용합니다. 프론트 테스트는 Node 테스트 러너와 TS 로더를 사용하며 실제 브라우저 통합 검증과 구분합니다. [프론트 스크립트](../frontend/package.json)

- **판정·검수 데이터** — [test_eligibility_path_service.py](../backend/tests/test_eligibility_path_service.py), [test_build_eligibility_paths.py](../backend/tests/test_build_eligibility_paths.py), [test_review_sheet.py](../backend/tests/test_review_sheet.py), [condition-paths.test.mjs](../frontend/tests/condition-paths.test.mjs). 같은 프로필·정책·기준 연도로 상태, `match_score`, `matched_path_id`, 경로별 비교와 난이도를 함께 대조합니다.
- **인증·개인화·호환성** — [test_account_flow.py](../backend/tests/test_account_flow.py), [test_personalized_condition_guides.py](../backend/tests/test_personalized_condition_guides.py), [test_reverse_privacy_context.py](../backend/tests/test_reverse_privacy_context.py), [private-condition-guides.test.mjs](../frontend/tests/private-condition-guides.test.mjs), [private-difficulty.test.mjs](../frontend/tests/private-difficulty.test.mjs), [condition-card-layout.test.mjs](../frontend/tests/condition-card-layout.test.mjs). 다른 계정·만료 세션·진단 변경·지문 불일치·레거시 읽기·공개 응답 마스킹·점수 미수신 문구를 점검합니다.
- **DB 운영** — [test_policy_data_transfer.py](../backend/tests/test_policy_data_transfer.py), [test_welfare_sync_resumable.py](../backend/tests/test_welfare_sync_resumable.py). 정책 적재의 영향 범위나 재개형 동기화를 바꿀 때 우선 확인합니다.

**PR #23의 검증 이력.** 백엔드 948개 통과(폐기 예정 API 등 경고 1,017개), 프론트 59개 통과, TypeScript 및 Vite 빌드 통과. 합성 3프로필 × 152정책의 경로 엔진 결과 456건에서 판정·`match_score`·대표 경로·난이도 계산이 같았습니다. 격리 DB와 가상 계정으로 실제 Chrome에서 새 진단·맞춤 안내·가중치·점수 지연과 실패·과거 스냅샷·계정 변경을 확인했고, 행복주택과 두루누리에서 문구 수정도 확인했습니다. 이 문서 작성 중에는 테스트와 브라우저 검증을 재실행하지 않았습니다. [PR #23 검증 기록](https://github.com/taehatae/Youth_Welfare_SW/pull/23)

브라우저 재현 시 새 가상 계정으로 진단한 뒤 **두루누리**에서 소득 차이와 점수 도착 전후, **행복주택**에서 미확인 비교 조건·공식 확인 사항·경로 순서를 확인하세요. 개발자 도구에서는 일반 진단과 전용 응답을 따로 확인하고, 요청을 지연하거나 실패시켜 대표 경로 문구를 검증합니다. 로그아웃·계정 전환·재진단 시 이전 안내가 사라지는지도 확인합니다. 과거 결과 호환 검사에는 격리 픽스처나 해당 회귀 테스트를 사용하세요.

## 11. 알려진 제한과 문서 불일치

| 구분 | 내용 |
| --- | --- |
| 해결된 문제 | **CRLF/LF** 차이로 계산 지문이 달라지던 문제는 줄바꿈 통일 해시로 고쳤습니다. 수정 전 CRLF 환경에서 만든 진단 기록만 개인화가 한 번 생략됩니다. |
| 의도된 제한 | 지문 없는 기록, 현재 정책/기준과 맞지 않는 저장 기록, 변환본, 지원하지 않는 복합 조건 등은 안내 또는 점수를 제공하지 않을 수 있습니다. 과거 기록을 읽기만 해서는 새 지문과 판정이 생기지 않습니다. |
| 의도된 제한 | `eligible`은 일부 미확인 항목과 공존합니다. 비교 조건이 없는 경로 66개는 공통까지 포함해도 비어 있으며 해당 경로 자체는 `needs_review`입니다. 다른 OR 경로가 어떻게 판정됐는지도 함께 봐야 합니다. |
| 설계상 주의사항 | `impossible`은 구현된 시간 값의 상한 초과를 반영하는 화면·추천 기준입니다. 향후 법령이나 정책 자격이 변할 가능성 전체를 평가하지 않습니다. 난이도 순위도 행동 권고나 승인 가능성으로 해석하지 않습니다. |
| 확인된 검수 경고 | 현재 시드의 비교 조건을 `make_review_sheet.problems()`로 읽기 전용 점검한 결과 근거 조각 불일치 3건(국가유공자·보훈대상자, 재학 여부, 세대원 전원 무주택 각 1건)이 나왔습니다. `lint_draft.lint_policy()`의 추가 휴리스틱은 R1 192, R3 2, R4 5, R5 14건이었습니다. 원문 해시 일치와 별개이며, 자동 경고 자체로 정책 판정 오류를 확정할 수 없습니다. |
| 확인된 운영 위험 | LFS 예외인 공유 DB에서 회원가입·진단·시드 재적재를 실행하면 DB 파일 자체가 변경될 수 있습니다. 기존 개인 데이터가 섞인 공유 DB를 올리거나 복사·초기화하지 마세요. |
| 미확인 | 다른 팀원 PC·배포 환경의 DB, 운영 데이터의 현재 스냅샷 수, 모든 정책의 행정적 정확성과 최신 공고는 이번에 확인하지 않았습니다. |

**읽을 때 주의할 문서.** [LOCAL_SETUP.md](eligibility-paths/LOCAL_SETUP.md)와 [백엔드 README](../backend/README.md)의 검수 **60/92** 및 DB 미공유 설명은 이전 시점 기준입니다. [REVIEW_GUIDE.md](eligibility-paths/REVIEW_GUIDE.md)의 **20/132**도 초기 검수 기록입니다. 2026-11-20 확인 기준으로는 152/0이며 공유 적재본이 LFS에 있습니다. 위 문서의 설명이 최신 통합 상태와 충돌하면 현재 소스코드와 실제 DB 상태를 우선 확인하세요. 이 인수인계서도 2026-11-20 시점의 기록이므로 이후 코드나 데이터가 바뀌면 다시 확인해야 합니다. `LOCAL_SETUP.md`에 개인화 코드가 미추적으로 남아 있다는 설명 역시 #23 병합 후에는 해당하지 않습니다. `CLAUDE.md`의 저장 스냅샷 관련 요약은 **맞춤 안내 문장과 정확한 점수가 저장되지 않는 것**으로 이해해야 합니다. 내부 재현용 당시 프로필과 표시 전 비교 행은 서버 스냅샷에 남고, 외부 응답에서 보호합니다.

## 12. Claude Code 최초 점검 순서

1. `git status --short --branch`, `git log --oneline --decorate -12`, `git branch -vv`로 브랜치·HEAD·작업 트리를 확인합니다. 필요하면 `git ls-remote --heads origin refs/heads/dev refs/heads/Hwang refs/heads/Jang`으로 원격을 읽습니다. 기존 변경을 보존하고 브랜치 전환이나 통합은 별도로 판단합니다.
2. [CLAUDE.md](../CLAUDE.md), 이 인수인계서와 [자격 경로 개요](eligibility-paths/README.md)를 읽습니다. 현재 코드·시드와 충돌하는 이전 문서는 날짜가 있는 참고 기록으로 사용합니다.
3. `frontend/src/app/App.tsx`, `frontend/src/services/welfareApi.ts`, `backend/app/api/routes/welfare.py`, `backend/app/services/account_service.py` 순으로 입력·저장·조회 경로를 확인합니다.
4. 정책 JSON과 `eligibility_path_service.py`, `structured_condition_service.py`를 대조합니다. DB 확인이 필요하면 설정된 절대 경로를 확인한 뒤 읽기 전용으로 행 수·원문 해시만 조회합니다. 코드 파악을 위해 `app.main`을 import하거나 시드를 적재할 필요는 없습니다.
5. `users.py` 전용 API, `profile_privacy.py`, `eligibility_snapshot_context.py`, `personalized_condition_guidance.py`를 살펴봅니다. 정상 경로와 실패 경로 모두에서 인증·소유권·검증·공개 마스킹을 지킵니다.
6. `AnalysisPolicyCard.tsx`, `PersonalizedGuideAccess.tsx`, `conditionGuidance.ts`에서 진단 당시 상태와 화면 추천을 구분합니다. 테스트 명령과 기존 회귀 검증 범위는 §10을 확인합니다.
7. 작업 범위를 합의한 뒤 변경합니다. 정책을 수정할 때는 근거와 사람 검수를 유지하고, 입력되지 않은 값을 추정하지 않습니다. 난이도·문구만 바꿀 때는 입력 대비 판정·점수·대표 경로가 그대로인지 비교합니다. DB·정책 시드·환경설정 쓰기와 Git 외부 반영은 명시적으로 요청된 경우에만 진행합니다. 팀원의 기존 구현을 보존하고, 큰 변경은 영향 범위와 선택지를 먼저 설명합니다.
