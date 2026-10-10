from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    age: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    region: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    income_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    employment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class UserEligibilityConditions(Base):
    __tablename__ = "user_eligibility_conditions"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id"),
        primary_key=True,
    )

    conditions: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
