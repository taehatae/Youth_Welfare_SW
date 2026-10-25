from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.users import router as users_router
from app.api.routes.welfare import router as welfare_router
from app.api.routes.auth import router as auth_router
from app.api.routes.policies import router as policies_router
from app.core.config import settings
from app.database.connection import Base, engine

# 모델을 import해야 SQLAlchemy가 테이블을 인식한다.
from app.models.user import User, UserEligibilityConditions  # noqa: F401
from app.models.welfare_service import WelfareService  # noqa: F401
from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,  # noqa: F401
)
from app.models.account import Account, AccountSession, AccountWorkspace, AuthAttempt  # noqa: F401
from app.models.welfare_sync import (  # noqa: F401
    WelfareApiQuotaWindow,
    WelfareSyncBatch,
    WelfareSyncItem,
)

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.middleware("http")
async def protect_account_requests(request: Request, call_next):
    # 쿠키 인증을 사용하는 쓰기 요청은 허용된 프론트 출처에서만 받는다.
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in settings.cors_origins:
        return JSONResponse(status_code=403, content={"detail": "허용되지 않은 요청 출처입니다."})
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse(status_code=403, content={"detail": "다른 사이트에서 보낸 요청은 허용되지 않습니다."})
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Router 등록
app.include_router(auth_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(
    users_router,
    prefix="/api/v1",
)

app.include_router(
    welfare_router,
    prefix="/api/v1",
)


@app.get("/")
def root():
    return {
        "status": "success",
        "message": "Youth Welfare Backend API is running.",
        "version": settings.app_version,
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }
