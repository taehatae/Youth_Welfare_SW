from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WelfareSyncBatch(Base):
    __tablename__ = "welfare_sync_batches"
    __table_args__ = (
        Index("uq_welfare_sync_active_life_array", "active_key", unique=True),
    )

    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    life_array: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    active_key: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="listing")
    listing_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    list_window_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail_window_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    worker_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WelfareSyncItem(Base):
    __tablename__ = "welfare_sync_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "serv_id", name="uq_welfare_sync_batch_service"),
        CheckConstraint("attempt_count >= 0", name="ck_welfare_sync_attempt_count_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("welfare_sync_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    serv_id: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    worker_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detail_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class WelfareApiQuotaWindow(Base):
    __tablename__ = "welfare_api_quota_windows"
    __table_args__ = (
        UniqueConstraint("window_id", "operation", name="uq_welfare_api_quota_window_operation"),
        CheckConstraint("operation IN ('list', 'detail')", name="ck_welfare_api_quota_operation"),
        CheckConstraint("used_count >= 0", name="ck_welfare_api_quota_used_nonnegative"),
        CheckConstraint("limit_count BETWEEN 1 AND 100", name="ck_welfare_api_quota_limit"),
        CheckConstraint("confirmed_available_calls BETWEEN 0 AND 100", name="ck_welfare_api_quota_confirmed_available"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    window_id: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    confirmed_available_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    operator_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
