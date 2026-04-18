import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Text, Integer, SmallInteger, ForeignKey,
    Date, DateTime, Numeric, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, GUID


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_period_id", "entry_number"),
        Index("idx_je_company_period", "company_id", "fiscal_period_id"),
        Index("idx_je_entry_date", "company_id", "entry_date"),
        Index("idx_je_status", "company_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("fiscal_periods.id"), nullable=False)
    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    document_type: Mapped[str | None] = mapped_column(String(10))
    document_number: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="MANUAL", nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("operation_templates.id"))
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("journal_entries.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship("Company", back_populates="journal_entries")
    fiscal_period: Mapped["FiscalPeriod"] = relationship("FiscalPeriod", back_populates="journal_entries")
    lines: Mapped[list["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="journal_entry",
        cascade="all, delete-orphan", order_by="JournalEntryLine.line_number"
    )
    template: Mapped["OperationTemplate | None"] = relationship("OperationTemplate")
    reversal_of: Mapped["JournalEntry | None"] = relationship("JournalEntry", remote_side="JournalEntry.id")


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        Index("idx_jel_entry", "journal_entry_id"),
        Index("idx_jel_account", "account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("accounts.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("cost_centers.id"))
    aux_type: Mapped[str | None] = mapped_column(String(30))
    aux_name: Mapped[str | None] = mapped_column(String(255))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["Account"] = relationship("Account", back_populates="journal_lines")
    cost_center: Mapped["CostCenter | None"] = relationship("CostCenter")
    contact: Mapped["Contact | None"] = relationship("Contact", foreign_keys=[contact_id], primaryjoin="JournalEntryLine.contact_id == Contact.id")
