from datetime import datetime
from sqlalchemy import DateTime, func, Uuid
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

# Native UUID type: uses PostgreSQL's uuid column, falls back to String(32) in SQLite
GUID = Uuid(as_uuid=True, native_uuid=True)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
