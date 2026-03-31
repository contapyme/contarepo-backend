"""
Versión read-only del servicio de cierre anual para contarepo-backend.
Solo expone _cierre_ya_existe — no genera ni ejecuta asientos.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.journal_entry import JournalEntry
from app.models.fiscal_period import FiscalPeriod


async def _cierre_ya_existe(db: AsyncSession, company_id: uuid.UUID, year: int) -> bool:
    """Verifica si ya existe un asiento de cierre anual para el año dado."""
    result = await db.execute(
        select(JournalEntry.id).join(
            FiscalPeriod, FiscalPeriod.id == JournalEntry.fiscal_period_id
        ).where(
            JournalEntry.company_id == company_id,
            JournalEntry.source == "CIERRE_ANUAL",
            FiscalPeriod.year == year,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
