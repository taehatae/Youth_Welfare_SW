# Youth Welfare SW

청년 복지 정책 조회와 자격 진단을 위한 프로젝트입니다.

## 폴더 구성

- `frontend/`: React, TypeScript, Vite 기반 웹 프런트엔드와 API 연동 문서
- `backend/`: 백엔드 작업 위치. 백엔드 담당자가 별도로 구성할 예정
- `LICENSE`: 저장소 라이선스

## 프런트엔드 실행

```sh
cd frontend
pnpm install
pnpm dev
```

백엔드 주소는 `frontend/.env.example`을 `frontend/.env.local`로 복사한 뒤 `VITE_API_BASE_URL`에 설정합니다. API 요청·응답 규격은 `frontend/docs/FRONTEND_API.md`를 참고하세요.
