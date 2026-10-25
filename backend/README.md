# Backend

## 기술 스택

- Python 3.10 이상
- FastAPI, Uvicorn
- SQLAlchemy 2, SQLite
- Pydantic 2, pydantic-settings
- httpx, pytest

의존성 버전은 [`requirements.txt`](requirements.txt)에 있습니다.

## 폴더와 주요 파일

```text
backend/
├── app/
│   ├── api/routes/       # API 라우트
│   ├── clients/          # 외부 API 클라이언트
│   ├── core/config.py    # 애플리케이션 설정
│   ├── database/         # 데이터베이스 연결과 세션
│   ├── models/           # SQLAlchemy 모델
│   ├── repositories/     # 데이터 조회와 저장
│   ├── schemas/          # 요청·응답 스키마
│   ├── services/         # 서비스 로직
│   └── main.py           # FastAPI 앱 진입점
├── tests/                # 백엔드 테스트
├── .env.example          # 환경 변수 예시
└── requirements.txt      # Python 의존성
```

주요 진입 파일은 `app/main.py`이며, 사용자와 복지 API 라우트는 `app/api/routes/users.py`, `app/api/routes/welfare.py`에 있습니다.

## 개발 환경 설정

Windows PowerShell에서 저장소 루트 기준으로 실행합니다.

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`.env.example`을 참고해 로컬 설정 파일을 준비합니다.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

외부 복지 API를 사용할 때는 `.env`에 필요한 값을 설정합니다. 비밀 키가 포함된 `.env`는 공유하거나 커밋하지 마세요.

## 백엔드 서버 실행

`backend/` 디렉터리에서 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

기본 주소는 `http://127.0.0.1:8000`이며, Swagger UI는 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

## 계정과 진단 기록 (2026-10-24)

- 기존 `users`/`user_eligibility_conditions`는 진단 프로필로 유지함.
- `accounts`는 아이디, 닉네임, PBKDF2-SHA256 비밀번호 해시, 소유 프로필 ID를 저장함.
- `account_sessions`에는 로그인 토큰의 SHA-256 해시와 7일 만료 시각을 저장함. 원본 토큰은 HttpOnly·SameSite=Lax 쿠키로만 전달함.
- `account_workspaces`에 진단 당시/이전 진단/최신 현황/직전 현황과 관심 정책을 보관함. 전체 무제한 이력 저장은 아님.
- `auth_attempts`로 클라이언트 IP 기준 15분 동안 40회의 로그인·가입·프로필 재인증 시도 제한을 적용함. 로컬·단일 서버용 구현임.
- 기존 테이블을 삭제하거나 ALTER하지 않음. 서버 시작 시 위 테이블만 추가 생성됨. 과거 익명 프로필을 계정에 자동 귀속시키지 않음.
- 프로필·진단 API는 로그인 필요. 다른 사용자의 user_id로 조회하면 404를 반환함. 공공 정책 동기화 API도 로그인 필요.
- 비밀번호 재설정·이메일 인증·회원 탈퇴 기능은 이번 범위에 포함하지 않음.

### 추가 환경 설정

`FRONTEND_ORIGINS`에는 사용하는 프론트 주소를 쉼표로 나열함. 로컬에서는 `http://localhost:5173,http://127.0.0.1:5173` 사용.
`COOKIE_SECURE=false`는 로컬 HTTP 개발용임. HTTPS 배포 시 `COOKIE_SECURE=true`로 설정하고 프론트와 API를 같은 사이트에서 서비스해야 함.
백엔드 다중 인스턴스 배포 시 시도 제한·계정 상태 동시 갱신 처리를 별도 설계해야 함.

### API 변경

- 공개 정책 안내: `GET /api/v1/policies` (q, category, page, page_size) 및 `GET /api/v1/policies/{policy_id}`. 개인정보나 계정 진단 결과를 반환하지 않음. 기존 수집 데이터를 읽으며 요청마다 외부 공공 API를 호출하지 않음.
- 분야 분류는 `services/policy_catalog_service.py`의 복지로 관심분야 매핑을 사용함. 복수 분야 정책은 여러 카테고리에 포함하고 원문이 없거나 지원하지 않는 분류는 기타·미분류로 포함함. DB 구조와 판정 로직 변경 없음.

- `POST /api/v1/auth/signup`: `{username, password, display_name}` → 계정 정보 + 세션 쿠키
- `POST /api/v1/auth/login`: `{username, password}` → 계정 정보 + 세션 쿠키
- `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
- `POST /api/v1/users/profile`: 로그인한 계정의 프로필 갱신
- `GET /api/v1/users/profile`: 403 반환 (재인증 없는 원문 조회 금지)
- `POST /api/v1/users/profile/view`: `{username, password, snapshot: "current" | "diagnosis"}`로 매번 재인증 후 해당 진단 프로필 반환
- `GET /api/v1/users/state`: 계정의 진단/현황/관심 정책. 프로필 원문은 null이며 조건별 current_value도 마스킹됨
- `POST /api/v1/welfare/diagnose`: 프로필 저장 + 분석 + 결과 저장
- `POST /api/v1/welfare/refresh`: 저장된 프로필로 현황만 재분석
- `POST /api/v1/users/saved/toggle`: `{profileKey, policyId}` → 내 저장 결과에서 관심 정책 추가/해제. 클라이언트의 프로필/정책 원문을 신뢰하지 않음
- `PATCH /api/v1/users/saved`: `{profileKey, policyId, trackingStatus, note}` → 관심 정책의 관리 상태와 메모 저장. 상태는 interested/preparing/applied/archived, 메모는 최대 500자. 실제 접수 상태와 연동되지 않음.
- 이전 `PUT /api/v1/users/saved`는 410 반환

기존 익명 API 호출 예제는 로그인 쿠키를 함께 보내도록 변경해야 함. 기존 HTTP 테스트는 실제 가입 후 받은 쿠키로 검증하도록 갱신했음. 판정·파싱 서비스 로직은 유지함.

### 프로필 보호 경계

- 일반 state/diagnose/refresh/matched 응답은 입력값을 숨김. 관심 정책 식별자도 프로필 원문 대신 서버 HMAC 식별자를 반환함.
- 프로필 조회마다 현재 로그인한 계정의 아이디·비밀번호를 모두 확인함. 조회 권한 토큰이나 해제 쿠키를 별도로 발급하지 않음.
- 프론트는 조회창을 닫거나 창을 전환하거나 2분 경과 시 조회한 입력값을 지움. 수정 화면으로 옮긴 값은 메모리에만 두고 해당 화면을 떠나면 지움.
- 조회 결과의 충족/미충족 판정 자체로 일부 조건을 추론할 가능성까지 없애는 기능은 아님. 진단 결과 열람에는 로그인 인증을 적용함.
- 서버 DB의 개인정보 암호화, 다중요소 인증, 외부 보안감사는 이번 기능에 포함하지 않음.

### 검증

`python -m pytest -q`로 기존 회귀 테스트와 `tests/test_account_flow.py`의 가입·로그인·진단·결과 복원·관심 정책·재인증·계정 격리·세션 만료·CSRF·실패 시 롤백을 확인함.
테스트 정책은 메모리 DB에만 생성하며 실제 정책 DB에 넣지 않음.

## 재개 가능한 복지서비스 동기화 운영

목록 API와 상세 API의 호출 한도는 별도로 기록합니다. 날짜가 바뀌었다는 이유만으로 한도가 초기화된 것으로 간주하지 않습니다. 실제 잔여 호출 가능량을 확인한 뒤 각 API 작업용 창을 등록해야 합니다. API 키는 기존 `.env` 설정을 사용하며 명령행 인자나 출력에 넣지 않습니다.

아래 명령은 `backend/` 디렉터리에서 실행합니다. `WINDOW_ID`는 운영자가 확인한 호출 한도 구간 식별자이며, 잔여 횟수는 외부 제공자 기준으로 확인한 값이어야 합니다.

```powershell
python -m scripts.welfare_sync confirm-window --window-id WINDOW_ID --operation list --verified-available-calls 2 --operator-name YOUR_NAME --confirm-provider-quota
python -m scripts.welfare_sync confirm-window --window-id WINDOW_ID --operation detail --verified-available-calls 100 --operator-name YOUR_NAME --confirm-provider-quota
python -m scripts.welfare_sync run --start-new-batch --list-window-id WINDOW_ID --detail-window-id WINDOW_ID
```

한 번의 실행은 상세 요청을 최대 100건까지만 시도합니다. 이어서 실행할 때는 출력된 `batch_id`를 지정하고, 새로 확인한 상세 API 잔여 한도를 별도 창으로 등록한 뒤 `--detail-window-id`에 전달합니다. 실패 항목 재시도는 해당 부분 실패 배치에 `--retry-failed`를 명시해야 합니다. 성공 항목은 재조회하지 않습니다. 목록 수집, 상세 응답 저장, 자격조건 저장 및 실패 상태는 각각 별도로 결과에 표시됩니다.

기존 HTTP 경로 `POST /api/v1/welfare/sync`도 유지되지만, 계정 로그인 외에 `WELFARE_SYNC_OPERATOR_TOKEN` 설정과 `X-Welfare-Sync-Token` 헤더가 필요합니다. 운영자 토큰이 설정되지 않은 환경에서는 HTTP 동기화가 비활성화됩니다. HTTP 요청은 호출 한도 창을 만들거나 초기화하지 않습니다.

## SQLite 백업 및 복원 확인

백업·복원 명령은 명시한 원본을 읽고 새 대상 파일을 생성합니다. 대상 경로가 이미 있으면 덮어쓰지 않고 실패합니다. 백업은 동기화와 별도로 실행하며 자동으로 생성되지 않습니다.

```powershell
python -m scripts.backup_database backup --source .\youth_welfare.db --destination .\backups\youth_welfare-YYYYMMDD.db
python -m scripts.backup_database restore --source .\backups\youth_welfare-YYYYMMDD.db --destination .\backups\restore-check.db
```

명령은 SQLite `integrity_check`와 사용자 테이블별 행 수를 검사해 출력합니다. 복원 검증은 별도의 새 파일로 수행하고, 실제 운영 DB를 대상으로 복원하지 마세요. 실행 전에 대상 경로와 원본 경로가 의도한 로컬 파일인지 직접 확인하고, 백업 파일을 안전한 위치에 보관하세요.
