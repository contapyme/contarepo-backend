import uuid
from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, GUID


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    ruc: Mapped[str] = mapped_column(String(11), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(255))
    direccion: Mapped[str | None] = mapped_column(Text)
    ubigeo: Mapped[str | None] = mapped_column(String(6))
    telefono: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    plan_contable: Mapped[str] = mapped_column(String(50), default="PCGE_2023", nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), default="PEN", nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["UserCompany"]] = relationship("UserCompany", back_populates="company")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="company")
    fiscal_periods: Mapped[list["FiscalPeriod"]] = relationship("FiscalPeriod", back_populates="company")
    journal_entries: Mapped[list["JournalEntry"]] = relationship("JournalEntry", back_populates="company")
    templates: Mapped[list["OperationTemplate"]] = relationship("OperationTemplate", back_populates="company")
    cost_centers: Mapped[list["CostCenter"]] = relationship("CostCenter", back_populates="company")
