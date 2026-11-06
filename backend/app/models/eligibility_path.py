"""정책 원문(welfare_services)과 별도로, 검수한 자격 경로를 저장한다.

정책 하나는 경로 여러 개를 갖고, 그중 하나만 맞으면 신청할 수 있다. 경로 안의 비교 조건은 모두 맞아야 한다.
모든 경로에 공통인 조건은 path_key='_common' 경로에 저장한다. 원문 해시가 바뀌면 검수를 다시 해야 한다.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

COMMON_PATH = "_common"


class PolicyEligibility(Base):
    __tablename__ = "policy_eligibility"

    serv_id: Mapped[str] = mapped_column(String(50), ForeignKey("welfare_services.serv_id"), primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # draft: 초안, reviewed: 진단에 사용, stale: 원문이 바뀌어 재검수 필요
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    drafted_by: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    reviewed_by: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    reviewed_at: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    preferences: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    paths: Mapped[list["EligibilityPath"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="EligibilityPath.sort_order")


class EligibilityPath(Base):
    __tablename__ = "eligibility_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serv_id: Mapped[str] = mapped_column(String(50), ForeignKey("policy_eligibility.serv_id"), index=True)
    path_key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    # 기본 | 유형 | 순위 | 예외 | 공통
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="기본")
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 입력값으로 비교할 수 없는 확인 사항(안내만 하고 판정에는 쓰지 않음)
    checks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    policy: Mapped[PolicyEligibility] = relationship(back_populates="paths")
    conditions: Mapped[list["EligibilityPathCondition"]] = relationship(
        back_populates="path", cascade="all, delete-orphan", order_by="EligibilityPathCondition.id")


class EligibilityPathCondition(Base):
    __tablename__ = "eligibility_path_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path_id: Mapped[int] = mapped_column(Integer, ForeignKey("eligibility_paths.id"), index=True)
    field: Mapped[str] = mapped_column(String(50), nullable=False)
    # gte | lte | between | one_of | is_true
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    values: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # requirement | exclusion
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="requirement")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")

    path: Mapped[EligibilityPath] = relationship(back_populates="conditions")
