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
