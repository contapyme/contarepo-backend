import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.account import Account
from app.models.fiscal_period import FiscalPeriod


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


async def _get_month_totals(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int,
    account_prefixes: list[str],
) -> Decimal:
    """Suma débitos o créditos de cuentas con ciertos prefijos en un mes específico."""
    fp_ids = select(FiscalPeriod.id).where(
        FiscalPeriod.company_id == company_id,
        FiscalPeriod.year == year,
        FiscalPeriod.month == month,
    )

    # Para cuentas de resultado: normal_balance="C" → el saldo es credit - debit
    # Para ingresos (7x): normal_balance = C → balance = credit - debit
    # Para gastos (6x): normal_balance = D → balance = debit - credit
    q = (
        select(
            Account.code,
            Account.normal_balance,
            func.coalesce(func.sum(JournalEntryLine.debit), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit), 0).label("total_credit"),
        )
        .select_from(JournalEntryLine)
        .join(JournalEntry, and_(
            JournalEntry.id == JournalEntryLine.journal_entry_id,
            JournalEntry.status == "POSTED",
            JournalEntry.source != "CIERRE_ANUAL",
            JournalEntry.fiscal_period_id.in_(fp_ids),
        ))
        .join(Account, Account.id == JournalEntryLine.account_id)
        .where(Account.company_id == company_id)
        .group_by(Account.code, Account.normal_balance)
    )

    rows = (await db.execute(q)).all()
    total = Decimal("0")

    for row in rows:
        if not any(row.code.startswith(p) for p in account_prefixes):
            continue
        debit = Decimal(str(row.total_debit))
        credit = Decimal(str(row.total_credit))
        if row.normal_balance == "C":
            total += credit - debit
        else:
            total += debit - credit

    return max(total, Decimal("0"))


async def get_tendencia_mensual(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
) -> list[dict]:
    """Retorna ingresos y gastos mes a mes para todos los meses del año indicado."""
    result = []
    ingresos_acum = Decimal("0")
    gastos_acum = Decimal("0")

    for month in range(1, 13):
        ingresos = await _get_month_totals(db, company_id, year, month, ["70", "71", "72", "75", "76", "77"])
        gastos = await _get_month_totals(db, company_id, year, month, ["60", "61", "62", "63", "64", "65", "66", "67", "68", "69"])
        ingresos_acum += ingresos
        gastos_acum += gastos

        result.append({
            "year": year,
            "month": month,
            "label": MESES[month - 1],
            "ingresos": float(ingresos),
            "gastos": float(gastos),
            "resultado": float(ingresos - gastos),
            "ingresos_acum": float(ingresos_acum),
            "gastos_acum": float(gastos_acum),
            "resultado_acum": float(ingresos_acum - gastos_acum),
        })

    return result
