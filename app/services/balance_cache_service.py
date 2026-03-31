import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.models.balance_cache import PeriodBalance, BalanceCacheStatus
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.fiscal_period import FiscalPeriod
from app.models.account import Account


async def get_status(db: AsyncSession, company_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(BalanceCacheStatus).where(BalanceCacheStatus.company_id == company_id)
    )
    status = result.scalar_one_or_none()
    if not status:
        return {"is_dirty": True, "last_modified_at": None, "last_calculated_at": None}
    return {
        "is_dirty": status.is_dirty,
        "last_modified_at": status.last_modified_at,
        "last_calculated_at": status.last_calculated_at,
    }


async def mark_dirty(db: AsyncSession, company_id: uuid.UUID) -> None:
    """Llamar al postear, reversar o eliminar cualquier asiento."""
    result = await db.execute(
        select(BalanceCacheStatus).where(BalanceCacheStatus.company_id == company_id)
    )
    status = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if status:
        status.is_dirty = True
        status.last_modified_at = now
    else:
        db.add(BalanceCacheStatus(
            company_id=company_id,
            is_dirty=True,
            last_modified_at=now,
            last_calculated_at=None,
        ))
    await db.flush()


async def recalculate(db: AsyncSession, company_id: uuid.UUID) -> dict:
    """
    Recalcula todos los saldos del período para la empresa.
    Borra los registros anteriores y los vuelve a insertar desde cero.
    """
    # Borrar caché anterior
    await db.execute(
        delete(PeriodBalance).where(PeriodBalance.company_id == company_id)
    )

    # Agregar debit/credit por cuenta y período (solo asientos POSTED)
    rows = await db.execute(
        select(
            FiscalPeriod.year,
            FiscalPeriod.month,
            JournalEntryLine.account_id,
            func.sum(JournalEntryLine.debit).label("total_debit"),
            func.sum(JournalEntryLine.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .join(FiscalPeriod, FiscalPeriod.id == JournalEntry.fiscal_period_id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == "POSTED",
        )
        .group_by(FiscalPeriod.year, FiscalPeriod.month, JournalEntryLine.account_id)
    )

    count = 0
    for row in rows.fetchall():
        db.add(PeriodBalance(
            company_id=company_id,
            account_id=row.account_id,
            year=row.year,
            month=row.month,
            total_debit=row.total_debit or Decimal("0"),
            total_credit=row.total_credit or Decimal("0"),
        ))
        count += 1

    # Marcar como limpio
    result = await db.execute(
        select(BalanceCacheStatus).where(BalanceCacheStatus.company_id == company_id)
    )
    status = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if status:
        status.is_dirty = False
        status.last_calculated_at = now
    else:
        db.add(BalanceCacheStatus(
            company_id=company_id,
            is_dirty=False,
            last_modified_at=now,
            last_calculated_at=now,
        ))

    await db.flush()
    return {"rows_calculated": count, "calculated_at": now.isoformat()}
