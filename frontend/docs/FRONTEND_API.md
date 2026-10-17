# 프론트엔드 입력과 조회 규약

## 실행 모드

- `pnpm dev`: 실제 API 연결. 기본 주소는 `http://localhost:8000/api/v1`이고 `VITE_API_BASE_URL`로 변경함.
- `pnpm dev:demo`: 서버 호출 없이 정해진 시연 결과를 표시함. 입력값에 따라 자격을 계산하는 모드가 아님. 상단에 항상 안내함.
- 정책 둘러보기의 목록은 현재 정적 예시임. 실제 진단 결과는 결과·현황 화면에 따로 표시함.

## 진단 결과와 현황

1. 진단 완료 시 `POST /users/profile`로 입력 정보를 저장함.
2. 반환된 `user_id`로 맞춤 정책과 역설계 추천을 조회함.
   - `GET /welfare/matched?user_id=...`
   - `GET /welfare/reverse-engineering?user_id=...`
3. 진단 결과에는 당시 프로필·결과·조회 시각을 보관함.
4. 현황 새로고침은 저장된 `user_id`로 위 GET 두 개만 다시 호출함. 프로필을 중복 생성하지 않음.
5. 새로고침은 현황 기록만 변경함. 새 진단을 완료하면 진단 결과와 현황을 모두 새 프로필로 교체함.
6. 수정 중인 입력값은 재진단을 완료하기 전까지 조회 프로필에 반영하지 않음.
7. 조회 실패·20초 시간 초과·잘못된 응답이 발생하면 기존 현황을 유지함.

공공데이터 수집은 백엔드 배치의 역할임. 현황 버튼은 데이터 수집 API를 호출하지 않으며 서버에 이미 등록된 자료를 재조회함. 마지막 조회 시각과 공공데이터 수집 시각은 구분해야 함.

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

소득을 임의 구간의 중간값으로 변환하지 않음. 가구소득·소득인정액·부채 공제는 수집하지 않으므로 본인 소득만으로 해당 조건을 충족했다고 단정하면 안 됨. 숫자 선택 범위 밖은 임의로 최댓값을 선택하지 않아야 함. 추가 조건은 미확인으로 둘 수 있음.

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
      "profile_schema_version": 2,
      "employment_detail": "PART_TIME"
    }
  }
}
```

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

## 브라우저 저장

- 입력 초안·진행 단계·진단 기록·최근 현황·직전 조회 기록·같은 프로필로 조회했던 정책 목록을 localStorage에 저장함.
- 시연/실서비스 저장 공간을 분리함. 계정 동기화 기능은 없음.
- 현황에서 브라우저 저장 정보를 삭제할 수 있음. 서버 데이터 삭제 API는 호출하지 않음.
- 읽기 실패 시 안내하고 새 입력으로 시작함. 저장 실패 시 새로고침 후 유실 가능성을 안내함.
- 공유 기기에서는 사용 후 저장 정보를 삭제할 수 있도록 사용자에게 안내함.

## 지역 목록 관리

`src/data/regions.ts`의 고정 선택 목록을 사용함. 행정구역 개편 시 갱신이 필요함.
2026년 인천 개편과 화성 4개 일반구를 반영했음.

- 인천광역시 행정체제 개편: https://www.incheon.go.kr/IC01070101
- 화성시 인구통계·구청 목록: https://www.hscity.go.kr/www/popltnSttus/BD_selectPopltnSttusList.do

실서비스에서는 백엔드와 공통 행정구역 코드 목록을 관리하는 것이 후속 과제임. 이번 변경은 기존 API와 맞추기 위해 전체 지역명을 전송함.
