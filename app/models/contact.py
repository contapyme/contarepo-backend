"""
Modelo de solo lectura que mapea a la tabla contacts de ContaPYME.
ContaREPO no crea ni modifica contactos, solo los lee para los reportes.
"""
import uuid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, GUID


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(10))
    doc_number: Mapped[str] = mapped_column(String(20))
    razon_social: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(20))
