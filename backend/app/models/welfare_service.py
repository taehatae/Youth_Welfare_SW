
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class WelfareService(Base):
    """중앙부처 복지서비스의 기본 정보와 자격 조건을 저장한다."""

    __tablename__ = "welfare_services"

    # API에서 제공하는 서비스 고유 ID
    serv_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    # 복지서비스 기본 정보
    serv_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )

    department: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )

    organization: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    detail_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    support_cycle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    support_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    online_application: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="",
    )

    # 자격 조건 원문
    target_details: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    selection_criteria: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # 지원 내용과 부가 정보
    support_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    reference_year: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="",
    )

    life_stages: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    target_groups: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    interest_categories: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # 여러 건이 들어올 수 있는 정보는 JSON으로 저장
    application_methods: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    contact_numbers: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    related_websites: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    application_forms: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    related_laws: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # 데이터 생성 및 마지막 동기화 시각
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    synced_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
