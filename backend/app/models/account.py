from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(250), nullable=False)
    # 기존 users는 자격 진단용 프로필이다. 과거 익명 기록을 자동으로 계정에 연결하지 않는다.
    profile_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), unique=True)


class AccountSession(Base):
    __tablename__ = "account_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class AccountWorkspace(Base):
    __tablename__ = "account_workspaces"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
