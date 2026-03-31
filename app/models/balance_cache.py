import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean, DateTime, Numeric, Integer, UniqueConstraint,
    Index, ForeignKey, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, GUID


class PeriodBalance(Base):
    """Caché de saldos precalculados por cuenta y período."""
    __tablename__ = "period_balances"
    __table_args__ = (
        UniqueConstraint("company_id", "account_id", "year", "month", name="uq_period_balance"),
        Index("idx_pb_company_period", "company_id", "year", "month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    total_debit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), nullable=False)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BalanceCacheStatus(Base):
    """Estado del caché de balances por empresa. Una fila por empresa."""
    __tablename__ = "balance_cache_status"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    is_dirty: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
