# Youth Welfare SW

청년 복지 정책 조회와 자격 진단을 위한 프로젝트입니다.

## 폴더 구성

- `frontend/`: React, TypeScript, Vite 기반 웹 프런트엔드와 API 연동 문서
- `backend/`: FastAPI 백엔드, 자격 판정·역설계, 정책 데이터
- `LICENSE`: 저장소 라이선스

## 프런트엔드 실행

```sh
cd frontend
pnpm install
pnpm dev
```

[백엔드 실행 가이드](backend/README.md)에 따라 별도 로컬 DB를 준비하고 백엔드를 실행합니다. Vite는 기본적으로 `/api` 요청을 `127.0.0.1:8000`으로 전달합니다. 다른 백엔드 주소를 쓸 때는 [환경변수 예시](frontend/.env.example)를 참고해 `VITE_API_BASE_URL`을 설정하세요. [프런트엔드 API 문서](frontend/docs/FRONTEND_API.md) · [자격 경로 설계·검수 문서](docs/eligibility-paths/README.md)
