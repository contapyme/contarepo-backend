import uuid
from sqlalchemy import String, Boolean, Text, SmallInteger, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, GUID


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "code"),
        Index("idx_accounts_company_code", "company_id", "code"),
        Index("idx_accounts_element", "company_id", "element"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    normal_balance: Mapped[str] = mapped_column(String(1), nullable=False)
    element: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("accounts.id"), index=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    allows_entries: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pcge_standard: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped["Company"] = relationship("Company", back_populates="accounts")
    parent: Mapped["Account | None"] = relationship("Account", remote_side="Account.id", back_populates="children")
    children: Mapped[list["Account"]] = relationship("Account", back_populates="parent")
    journal_lines: Mapped[list["JournalEntryLine"]] = relationship("JournalEntryLine", back_populates="account")
