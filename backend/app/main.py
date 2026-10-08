from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.users import router as users_router
from app.api.routes.welfare import router as welfare_router
from app.core.config import settings
from app.database.connection import Base, engine

# 모델을 import해야 SQLAlchemy가 테이블을 인식한다.
from app.models.user import User  # noqa: F401


# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Router 등록
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