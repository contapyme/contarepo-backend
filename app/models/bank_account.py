import uuid
from sqlalchemy import String, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, GUID


class BankAccount(Base, TimestampMixin):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "account_number", "bank_code", name="uq_bank_account_company_number_bank"),
        Index("idx_bank_account_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    bank_code: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)  # NOSTRO | VOSTRO
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    description: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("accounts.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped["Company"] = relationship("Company")
    account: Mapped["Account"] = relationship("Account")
