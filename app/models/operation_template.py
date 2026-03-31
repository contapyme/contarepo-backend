import uuid
from sqlalchemy import String, Boolean, Text, SmallInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, GUID


class OperationTemplate(Base, TimestampMixin):
    __tablename__ = "operation_templates"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped["Company"] = relationship("Company", back_populates="templates")
    lines: Mapped[list["TemplateLine"]] = relationship(
        "TemplateLine", back_populates="template",
        cascade="all, delete-orphan", order_by="TemplateLine.line_number"
    )


class TemplateLine(Base):
    __tablename__ = "template_lines"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("operation_templates.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("accounts.id"), nullable=False)
    description_template: Mapped[str | None] = mapped_column(Text)
    side: Mapped[str] = mapped_column(String(1), nullable=False)
    amount_formula: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    template: Mapped["OperationTemplate"] = relationship("OperationTemplate", back_populates="lines")
    account: Mapped["Account"] = relationship("Account")
