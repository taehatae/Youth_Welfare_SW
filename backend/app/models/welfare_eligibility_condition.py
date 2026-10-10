
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class WelfareEligibilityCondition(Base):
    """복지서비스 자격 요건을 구조화해 저장한다."""

    __tablename__ = "welfare_eligibility_conditions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    serv_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("welfare_services.serv_id"),
        nullable=False,
        index=True,
    )

    # age, income_amount, income_ratio, region,
    # employment, target_group, other
    condition_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # gte, gt, lte, lt, between, contains, unknown
    operator: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
    )

    value_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    value_number: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    upper_value_number: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="",
    )

    # 조건이 추출된 상세정보 원문 필드
    source_field: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # 원문을 그대로 보존한다.
    source_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 자동 추출 결과를 바로 비교에 사용해도 되는지 표시한다.
    comparison_ready: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # parsed 또는 manual_review
    parse_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual_review",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
