import uuid
from datetime import datetime
from sqlalchemy import String, SmallInteger, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID


class FiscalPeriod(Base):
    __tablename__ = "fiscal_periods"
    __table_args__ = (UniqueConstraint("company_id", "year", "month"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship("Company", back_populates="fiscal_periods")
    journal_entries: Mapped[list["JournalEntry"]] = relationship("JournalEntry", back_populates="fiscal_period")
