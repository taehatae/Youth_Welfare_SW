# Youth Welfare Backend

청년 복지서비스 데이터를 저장하고, 사용자의 기본 프로필을 바탕으로 자격 조건을 사전 비교하는 FastAPI 백엔드입니다. 이 결과는 참고용 사전 분석이며 행정기관의 최종 수급 자격 판정을 대신하지 않습니다.

## 구현 범위

현재 구현된 기능:

- 사용자 프로필 등록 및 추가 자격 조건 JSON 저장
- 중앙부처 복지서비스 API의 목록·상세 데이터 동기화 및 저장
- 복지서비스 자격 조건 원문에서 일부 나이·소득 기준을 구조화
- 프로필과 저장된 복지서비스 조건을 비교하고 분석 결과 반환
- `/` 및 `/health` 상태 확인

자격 매칭은 파싱된 나이 조건을 중심으로 자동 비교합니다. 소득액·중위소득 비율·지역·고용 상태·대상 그룹 등은 현재 자동 판정하지 않고 추가 확인 대상으로 처리합니다. 외부 기관 심사가 필요한 조건도 별도 확인이 필요합니다. 따라서 결과는 행정기관의 최종 수급 결정이 아닙니다.

`/api/v1/welfare/reverse-engineering`의 추천 계산 로직은 아직 구현되지 않았으며, 사용자가 존재하면 현재 항상 빈 `recommendations` 목록을 반환합니다.

## 기술 스택

- Python 3.10 이상 (코드의 `X | None` 타입 표기 사용)
- FastAPI, Uvicorn
- SQLAlchemy 2, SQLite 기본 설정
- Pydantic 2 및 pydantic-settings
- httpx (외부 복지 API 요청)
- pytest

정확한 패키지 버전은 [`requirements.txt`](requirements.txt)를 기준으로 설치합니다.

## 폴더 및 주요 파일

```text
backend/
├── app/
│   ├── api/routes/       # 사용자 및 복지 API 라우트
│   ├── clients/          # 외부 복지 API 요청과 XML 파싱
│   ├── core/             # 앱 설정
│   ├── database/         # SQLAlchemy 엔진, 세션, DB 의존성
│   ├── models/           # 사용자, 복지서비스, 자격 조건 모델
│   ├── repositories/     # DB 조회·저장
│   ├── schemas/          # 요청·응답 스키마와 입력 검증
│   ├── services/         # 프로필, 동기화, 파싱, 자격 매칭 로직
│   └── main.py            # FastAPI 앱과 라우터 등록
├── tests/                 # API 및 DB 통합 테스트
├── .env.example           # 환경 변수 예시
└── requirements.txt       # Python 의존성
```

주요 진입점은 `app/main.py`, 프로필 라우트는 `app/api/routes/users.py`, 복지 라우트는 `app/api/routes/welfare.py`입니다.

## 개발 환경 설정

아래 명령은 Windows PowerShell 기준입니다. 먼저 저장소 루트에서 백엔드 폴더로 이동합니다.

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

PowerShell 실행 정책 때문에 가상환경 활성화가 차단되면 활성화하지 않고 가상환경의 Python을 직접 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 환경 변수

`backend/`에서 `.env.example`을 `.env`로 복사합니다. 기존 `.env`가 있으면 덮어쓰지 마세요.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

설정이 필요한 경우 로컬 `.env`에서 다음 변수만 조정합니다.

| 환경 변수 | 용도 및 코드 기본값 |
|---|---|
| `APP_NAME` | FastAPI 앱 이름. 기본값은 `Youth Welfare Reverse Engineering API` |
| `APP_VERSION` | 앱 버전. 기본값은 `0.1.0` |
| `DATABASE_URL` | SQLAlchemy 연결 주소. 기본값은 `sqlite:///./youth_welfare.db` |
| `FRONTEND_ORIGINS` | CORS 허용 출처 목록. 기본값은 `http://localhost:5173`; 여러 출처는 쉼표로 구분 |
| `WELFARE_API_SERVICE_KEY` | 복지서비스 API 인증 키. 동기화 기능에 필요 |
| `WELFARE_API_BASE_URL` | 복지서비스 API 기본 URL. 동기화 기능에 필요 |

변수명과 기본값은 `.env.example` 및 `app/core/config.py`에 근거합니다. 실제 API 키는 저장소나 문서에 기록하지 말고 로컬 `.env`에서만 관리하세요. `.env`는 Git에서 제외됩니다.

## 서버 실행

`backend/` 디렉터리에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

가상환경을 활성화했다면 다음 명령도 사용할 수 있습니다.

```powershell
python -m uvicorn app.main:app --reload
```

로컬 주소:

- API 기본 주소: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- 상태 확인: `http://127.0.0.1:8000/health`

## API 엔드포인트

모든 사용자·복지 API 경로의 접두사는 `/api/v1`입니다.

| 메서드 및 경로 | 목적 |
|---|---|
| `GET /` | 앱 실행 상태와 버전 반환 |
| `GET /health` | 간단한 상태 확인 |
| `POST /api/v1/users/profile` | 프로필 등록. `age`, `region`, `income_level`, `employment_status`가 필요하며 `eligibility_conditions`는 선택 사항입니다. 응답 필드는 `user_id`, `status`, `message`입니다. |
| `POST /api/v1/welfare/sync` | 외부 복지서비스 목록·상세 데이터 동기화. `max_services`는 선택 쿼리로 1~500을 받습니다. 예: `/api/v1/welfare/sync?max_services=5`. 생략하면 코드상 개수 상한 없이 조회합니다. |
| `GET /api/v1/welfare/matched?user_id={user_id}` | 해당 사용자와 저장된 서비스 조건의 매칭 및 검토 결과 반환. 존재하지 않는 사용자 ID는 404입니다. |
| `GET /api/v1/welfare/reverse-engineering?user_id={user_id}` | 역설계 추천 응답. 현재 알고리즘은 미구현이며 `recommendations`가 빈 배열입니다. 존재하지 않는 사용자 ID는 404입니다. |

프로필의 `age`는 19~34, `income_level`은 0 이상의 월 소득(원), `region`은 비어 있지 않은 문자열입니다. 고용 상태 허용 값은 `EMPLOYED`, `EMPLOYED_SME`, `UNEMPLOYED`, `STUDENT`, `SELF_EMPLOYED`, `FREELANCER`, `OTHER`입니다. 추가 조건은 JSON 객체 또는 `null`로 받을 수 있으며, 저장 시 `UNKNOWN`, `false`, 빈 배열·객체 같은 값을 임의로 불리언으로 바꾸지 않습니다.

복지 데이터 동기화는 외부 API 서비스 키와 기본 URL이 설정되어야 합니다. 동기화하지 않은 DB에는 매칭할 복지서비스가 없을 수 있습니다.

## SQLite 데이터베이스

기본 주소 `sqlite:///./youth_welfare.db`의 상대 경로는 **프로세스의 현재 작업 디렉터리** 기준입니다. 위 안내대로 `backend/`에서 실행하면 기본 DB 파일은 `backend/youth_welfare.db`에 생성됩니다. `DATABASE_URL`로 다른 SQLAlchemy 연결 주소를 지정할 수 있습니다.

앱 시작 시 `app/main.py`가 SQLAlchemy 모델을 등록하고 `Base.metadata.create_all()`을 호출해 없는 테이블을 생성합니다. 이 방식은 기존 테이블에 새 컬럼을 추가하는 스키마 마이그레이션 도구가 아닙니다. SQLite에서는 연결마다 외래 키 제약을 활성화합니다.

로컬 DB에는 사용자·서비스 데이터가 들어갈 수 있으므로 공유하거나 저장소에 커밋하지 마세요. `backend/.gitignore`는 DB 파일을 제외하고, 저장소 루트 `.gitignore`도 루트의 `youth_welfare.db`를 제외합니다. 로컬 DB를 지우거나 초기화하면 저장된 데이터가 사라질 수 있습니다.

## 테스트

`backend/` 디렉터리에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

프로필 API와 응답 계약, 추가 조건의 JSON 값 보존, SQLite 외래 키와 롤백, 기존 사용자 테이블 호환성을 테스트합니다. 테스트는 인메모리 SQLite를 사용하며 로컬 DB 파일에 연결하지 않습니다.

## 문제 해결

- `No module named ...`: `backend/`에 있는지 확인하고 가상환경 Python으로 `python -m pip install -r requirements.txt`를 실행합니다.
- `Could not import module "app.main"`: 서버를 `backend/` 작업 디렉터리에서 실행하고 명령의 모듈 경로가 `app.main:app`인지 확인합니다.
- 포트 사용 오류: 포트 8000을 사용 중인 프로세스를 확인하거나 Uvicorn의 `--port` 옵션을 지정합니다.
- 브라우저 CORS 오류: 프런트엔드 출처가 `FRONTEND_ORIGINS`에 포함되어 있는지 확인합니다. 기본값은 `http://localhost:5173`입니다.
- 복지 동기화 오류: `.env`의 `WELFARE_API_BASE_URL`과 `WELFARE_API_SERVICE_KEY`가 제공자 설정과 일치하는지 확인합니다. 키 값은 로그나 저장소에 붙여넣지 마세요.
- 기존 DB 파일을 사용하는 경우: 실행 작업 디렉터리와 `DATABASE_URL`이 의도한 파일을 가리키는지 확인합니다. DB 삭제·초기화 전에 보존이 필요한 데이터가 있는지 확인하세요.

## 로컬 정보 보호

- 실제 API 서비스 키는 `.env` 등 로컬 비밀 설정으로만 관리하고 커밋하지 않습니다.
- 개인 프로필과 복지 데이터가 포함될 수 있는 SQLite DB 파일은 공유하거나 커밋하지 않습니다.
- 로그, 이슈, 문서 예시에 실제 사용자 정보나 키를 붙여넣지 않습니다.
