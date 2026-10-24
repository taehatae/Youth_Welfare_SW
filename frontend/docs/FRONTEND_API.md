# 프론트엔드 입력과 조회 규약

## 실행 및 인증

- `pnpm dev`: 실제 API 연결. 기본 주소는 `/api/v1`이며 Vite 개발 서버가 백엔드 8000 포트로 전달함. `VITE_API_BASE_URL`로 변경 가능함.
- 계정 진단과 정책 찾기는 실제 백엔드 응답을 사용함. 정책 찾기는 공개 정책 안내이며 개인별 진단 결과와 구분함.
- 회원가입: `POST /auth/signup` (`username`, `password`, `display_name`). 가입 후 바로 로그인됨.
- 로그인/로그아웃: `POST /auth/login`, `POST /auth/logout`. 인증 확인: `GET /auth/me`.
- 아이디는 영문·숫자·밑줄 3~30자, 대소문자 구분 없음. 비밀번호는 10~128자.
- 인증은 HttpOnly 세션 쿠키를 사용함. 프론트 요청에는 `credentials: include`를 지정함. 토큰과 비밀번호를 localStorage에 보관하지 않음.
- 계정별 요청에 `X-Account-ID`를 보내 다른 창에서 로그인 계정이 바뀐 경우 쓰기를 차단함.

## 계정 프로필·진단·현황

1. 로그인 직후 `GET /users/state`로 진단 당시 결과, 이전 진단, 최신 현황, 직전 현황, 관심 정책을 불러옴. 프로필 원문은 포함하지 않음.
2. 최종 입력 확인 후 `POST /welfare/diagnose`에 프로필을 전송함. 프로필 갱신과 분석 결과 저장을 같은 트랜잭션으로 처리함.
3. 같은 계정은 같은 프로필 레코드를 갱신함. 재진단마다 새로운 user_id를 만들지 않음.
4. `POST /welfare/refresh`는 서버에 저장된 프로필로 재분석함. 진단 당시 기록은 보존하고 현황만 갱신함.
5. `POST /users/profile/view`는 아이디·비밀번호 재확인 후 프로필을 조회함. `GET /users/profile`은 403을 반환함. `POST /users/profile` 단독 저장은 진단을 실행하지 않음.
6. 기존 `GET /welfare/matched?user_id=...`, `/reverse-engineering?user_id=...`는 로그인과 프로필 소유권 확인이 필요함.
7. `POST /users/saved/toggle`로 진단 결과에 있는 정책을 계정에 저장/해제함(최대 200개).
8. 현황에는 모든 정책의 진단 상태를 표시함. 자동 비교상 충족한 정책의 신청 기간은 별도 영역으로 표시함.
9. 작성 중 입력은 메모리에만 유지함. 새로고침 시 결과만 복원하며, 저장된 프로필 원문은 재인증 후 조회함. 로그아웃·인증 만료 시 화면의 계정 정보를 비움.
10. 조회 오류 시 마지막 결과를 유지함. 기존 익명 브라우저 기록을 새 계정에 자동 연결하지 않음.

공공데이터 수집은 별도 작업임. 현황 새로고침은 이미 수집한 정책을 재분석하며 외부 공공 API를 호출하지 않음.
별도 역설계 추천 로직은 아직 미구현이며 현재 추천 목록은 비어 있음. 로그인 추가로 매칭 알고리즘의 판정 범위를 바꾸지 않음.

## 정책 찾기

- `GET /policies?q=&category=all&page=1&page_size=12`: 공개 정책 목록. 서버에 수집된 데이터에서 검색·분야 필터·페이지 처리를 수행함.
- `GET /policies/{policy_id}`: 지원 내용·지원 대상·선정 기준·신청 및 처리 절차·공식 링크·수집 시각을 제공함.
- 분야는 `housing`, `employment`, `finance`, `education`, `health`, `living`, `culture`, `safety`, `other`. 복지로 관심분야 원문을 묶은 서비스 내 분류이며 한 정책이 여러 분야에 속할 수 있음.
- 카테고리별 개수는 검색어에 맞는 전체 결과 기준. 전체 개수는 중복 정책을 한 번만 계산함.
- 검색어·분야·페이지는 URL 해시에 반영하여 뒤로가기와 목록 복귀 시 유지함. 홈의 분야 링크도 같은 필터를 사용함.
- 목록에 예시 이미지·예시 충족률을 표시하지 않음. 신청기간은 구조화된 값이 없어 공식 공고 확인으로 안내함.
- 카드는 12개씩 조회하며 스크롤 등장 시 최대 120ms 간격으로 페이드와 작은 이동 효과를 적용함. 오류·로딩·검색 결과 없음을 구분함.

## 입력 형식

입력 화면에는 자유 서술 칸이 없음. 표시 문구와 저장 코드를 분리함.

| 항목 | 저장 형식 |
| --- | --- |
| 나이 | 만 19~34세 정수 |
| 거주지 | 시도 + 시군구 문자열. 세종은 시도 이름만 전송 |
| 본인 월평균 세전 소득 | 백만원 단위와 나머지 만원 단위를 선택, 합산 후 원 단위 정수 전송. 0~9,999만원 |
| 성별 | MALE / FEMALE / UNKNOWN |
| 가구원 수 | 주민등록상 1~20명 또는 null |
| 주된 소득 종류 | LABOR / BUSINESS / FREELANCE / NONE / UNKNOWN |
| 총재산 | UNDER_100M / 100M_200M / 200M_300M / 300M_500M / OVER_500M 또는 null |
| 주거 형태 | OWNED / JEONSE / MONTHLY / FREE / OTHER |
| 본인 주택 보유 | true / false / null |
| 장애·재학 여부 | YES / NO / UNKNOWN |
| 혼인 | SINGLE / MARRIED / DIVORCED / WIDOWED / UNKNOWN |
| 자녀 수 | 0~20명 또는 null |
| 자격증 | DRIVER_1 / DRIVER_2 / SOCIAL_WORKER_1 / SOCIAL_WORKER_2 / COMPUTER_1 / COMPUTER_2 / ENGINEER_INFORMATION / OTHER 배열 |

소득을 임의 구간의 중간값으로 변환하지 않음. 가구소득과 소득인정액은 추가 정보로 별도 수집함. 본인 소득으로 대체하거나 부채 공제를 임의로 계산하면 안 됨. 숫자 선택 범위 밖은 임의로 최댓값을 선택하지 않아야 함. 추가 조건은 미확인으로 둘 수 있음.

`qualification_status`는 YES / NO / UNKNOWN으로 별도 보존함. 빈 자격증 배열만으로 미보유를 판단하면 안 됨. `OTHER` 자격은 구체적인 자격 요건을 충족했다고 판정하면 안 됨.

### 고용 상태 호환

화면은 EMPLOYED / EMPLOYED_SME / PART_TIME / UNEMPLOYED / SELF_EMPLOYED / FREELANCER / OTHER를 사용함. 학생은 고용 상태에서 제외하고 재학 여부로 분리함.

현재 백엔드 enum에는 PART_TIME이 없어 전송 시 OTHER로 변환함. 원래 선택은 `eligibility_conditions.additional_conditions.employment_detail = PART_TIME`에 보존함. 백엔드에서 세부 고용 상태를 반영하거나 enum을 확장해야 함. 아르바이트를 무직으로 바꾸지 않음.

### 프로필 전송 예시

```json
{
  "age": 24,
  "region": "서울특별시 관악구",
  "income_level": 2150000,
  "employment_status": "OTHER",
  "eligibility_conditions": {
    "gender": "UNKNOWN",
    "household_size": 1,
    "income_type": "LABOR",
    "asset_range": "UNDER_100M",
    "housing_type": "MONTHLY",
    "owns_home": false,
    "disability_status": "UNKNOWN",
    "student_status": "YES",
    "marital_status": "SINGLE",
    "children_count": 0,
    "qualifications": ["COMPUTER_2"],
    "additional_conditions": {
      "qualification_status": "YES",
      "profile_schema_version": 3,
      "employment_detail": "PART_TIME"
    }
  }
}
```

`additional_conditions`에는 선택 입력한 상세 정보를 함께 저장함. 항목을 입력하지 않으면 `null`, 모름을 선택하면 `UNKNOWN`으로 보냄. 두 값은 구분됨.

| 필드 | 형식 | 값 |
|---|---|---|
| `basic_benefit_status`, `near_poverty_status`, `single_parent_support_status`, `household_basic_benefit_status` | 문자열 또는 `null` | `YES`, `NO`, `UNKNOWN` |
| `basic_benefit_types` | 문자열 배열 또는 `null` | `LIVELIHOOD`, `MEDICAL`, `HOUSING`, `EDUCATION`; 해당 없음은 `NONE` |
| `household_monthly_income_won`, `recognized_household_income_won`, `protection_duration_months` | 정수 또는 `null` | 원 또는 개월. 소득인정액을 모르면 계산하지 않음 |
| `household_income_recognition_known`, `child_welfare_protection_experience`, `protection_ended`, `job_seek_registration`, `employment_support_program`, `self_sufficiency_program_status` | 문자열 또는 `null` | `YES`, `NO`, `UNKNOWN` |
| `protection_end_month`, `registered_residence_start_month` | `YYYY-MM` 문자열 또는 `null` | 연월 |
| `registered_address_sido`, `registered_address_district` | 문자열 또는 `null` | 시도·시군구 |

가구 소득과 소득인정액은 본인 월소득과 별도로 저장함. 저장된 응답은 사용자 입력이며 공식 자격 증명이 아님.

기존 한글 주거·재산·자격증 문자열은 위 코드로 변경했음. 백엔드 조건 파서와 비교 로직도 이 코드 규약을 사용해야 함. UNKNOWN / null을 false 또는 0으로 취급하면 안 됨.

## 맞춤 정책 응답에 필요한 날짜 확장

기존 필수 필드: policy_id, title, category, support_amount, match_score.

아래 필드는 **프론트엔드에서 수용하도록 준비한 계약 초안**이며, 현재 백엔드에는 제공되지 않음. 실제 신청 종료·새 공고를 구분하려면 백엔드의 수집·저장·응답에도 반영해야 함.

```json
{
  "policy_id": "POL_001",
  "title": "정책명",
  "category": "주거",
  "support_amount": "공고의 지원 내용",
  "match_score": 100,
  "detail_url": "https://official.example/policy/1",
  "application_period_type": "DATED",
  "application_start_date": "2026-10-01",
  "application_end_date": "2026-10-31",
  "published_at": "2026-09-20"
}
```

- 날짜는 한국시간 기준 YYYY-MM-DD. 날짜만 제공하는 계약이므로 마감일 당일까지 접수 기간 내로 취급함. 시각별 조기 마감·예산 소진은 공식 공고 확인이 필요함.
- 종료일이 조회일보다 이전이면 신청 종료, 시작일이 이후면 접수 예정.
- 종료일이 없으면 기간 확인 필요. 상시 접수는 application_period_type=ALWAYS를 명시해야 함.
- 잘못된 날짜·시작일보다 빠른 종료일은 기간 확인 필요.
- 이번 조회에 추가: 직전 조회에 없던 policy_id. 새 공고 발표와는 다른 의미임.
- published_at은 향후 새 공고 분류를 위한 필드이며 현재 추가 배지는 ID 비교만 사용함.
- 이전 결과에 있던 정책이 응답에서 사라져도 종료일이 없으면 종료로 단정하지 않음.
- detail_url은 http/https만 링크로 제공함. 링크가 없으면 미제공 안내를 표시함.

시연 자료에는 2026-12-31 마감 정책과 2026-10-15 마감 정책이 있음. 결과 화면은 진단 시각 기준, 현황은 마지막 새로고침 시각 기준으로 날짜를 판별함. 새로고침을 누를 때마다 가상의 정책을 추가하지 않음.

## 계정 저장과 프로필 보호

- 가입/로그인 후 받은 HttpOnly 쿠키를 `credentials: include`로 보냄. 비밀번호나 로그인 토큰을 localStorage에 저장하지 않음.
- 진단을 완료하면 프로필과 결과가 서버의 내 계정에 저장됨. 입력 중인 초안은 메모리에만 유지하며 진단 화면을 떠나면 지움.
- 이전 익명 버전의 `youth-welfare:session:v2:*`, `youth-welfare:saved:v1:*` 두 저장 항목(live/demo)은 시작 시 정리함. 과거 익명 입력을 현재 계정에 임의로 연결하지 않음.
- 진단/현황/관심 정책 조회 응답의 profile은 null이며, 입력값이 들어 있는 current_value는 마스킹됨. profileKey는 서버에서 만든 불투명한 식별자임.
- `POST /users/profile/view`에 현재 계정의 아이디·비밀번호와 snapshot(`current` 또는 `diagnosis`)을 보내 매번 본인 확인함. 성공한 요청에서만 프로필 원문을 받음.
- 프로필 조회창은 닫기·창 전환·2분 경과 시 입력값을 지움. 수정으로 이동하려면 본인 확인을 거치며 조회 권한을 쿠키로 유지하지 않음.
- 관심 정책은 `POST /users/saved/toggle`에 `{profileKey, policyId}`를 보내 추가/해제함. 이전 PUT 일괄 저장 방식은 사용하지 않음.
- 관심 정책 관리 정보는 `PATCH /users/saved`에 `{profileKey, policyId, trackingStatus, note}`를 보내 저장함. 상태는 `interested`(관심 있음), `preparing`(준비 중), `applied`(신청 완료), `archived`(보관)이며 메모는 최대 500자임. 현재 계정이 저장한 정책만 수정할 수 있음.
- 상태·메모는 서버 계정에 보관하며 실제 신청/선정 결과와 연동되지 않음. 기존 데이터는 관심 있음·빈 메모로 표시함. 보관은 삭제가 아니며 상태를 바꿔 다시 관리할 수 있음.
- 다른 창에서 계정이 바뀐 경우 `X-Account-ID` 검증으로 이전 계정 화면의 요청을 거절함.

## 지역 목록 관리

`src/data/regions.ts`의 고정 선택 목록을 사용함. 행정구역 개편 시 갱신이 필요함.
2026년 인천 개편과 화성 4개 일반구를 반영했음.

- 인천광역시 행정체제 개편: https://www.incheon.go.kr/IC01070101
- 화성시 인구통계·구청 목록: https://www.hscity.go.kr/www/popltnSttus/BD_selectPopltnSttusList.do

실서비스에서는 백엔드와 공통 행정구역 코드 목록을 관리하는 것이 후속 과제임. 이번 변경은 기존 API와 맞추기 위해 전체 지역명을 전송함.

## 진단 기록 비교와 화면 동작

- 진단 결과는 `session.diagnosis`, 현황은 `session.current`를 표시함. 현황 새로고침으로 진단 당시 기록을 덮어쓰지 않음.
- 현황은 최근 확인 상태 → 직전 조회와의 변화 → 관심 정책 관리 → 내 정보 순서임. 전체 분석/신청 일정 목록은 현황에서 제거했고 전체 진단 근거는 진단 결과로 연결함.
- 관심 정책은 동일한 `profileKey`의 최신 결과가 있을 때만 최근 조회 결과를 표시함. 이전 프로필의 정책이나 이번 조회에 없는 정책은 저장 당시 결과임을 표시함.
- 새 진단 성공 시 직전 진단을 `previousDiagnosis`로 보관함. 기존 저장 데이터에 이 필드가 없으면 null로 복원함.
- 직전 진단과 정책 ID·판정 상태·조건 안내·조건 개수를 비교함. 입력값 원문은 재인증 조회에서만 제공함. 현황은 직전 새로고침 결과와 정책 변화를 비교함.
- 추가·제외는 응답 차이이며 새 공고·마감으로 단정하지 않음. 정책 데이터도 달라질 수 있어 입력 변경만의 효과로 설명하지 않음.
- 정책 카드에는 충족·미충족·추가 확인 개수를 표시함. 자동 판정 조건이 없으면 판정 정보 부족으로 안내하고, 충족 조건의 상세 내역은 생성하지 않음.
- 관련 입력 수정은 아이디·비밀번호 재확인 후 해당 진단의 프로필로 입력 초안을 복원함. 서버 재진단 성공 전에는 기존 결과를 유지함.
- 홈과 스크롤 구간은 한 번 등장하며, 진단 단계와 상세 열기에 짧은 전환을 적용함. 홈 목록의 일시정지 버튼으로 흐르는 목록을 제어함.
- 현재 계정 진단은 실제 백엔드 응답만 사용하며 예시 정책으로 자동 대체하지 않음.
