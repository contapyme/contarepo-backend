import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_, and_
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.account import Account
from app.models.fiscal_period import FiscalPeriod
from app.schemas.reports import AccountBalance, TrialBalanceLine, TrialBalanceReport


async def get_account_balances(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int | None = None,
    year_only: bool = False,
    exclude_closing: bool = False,
) -> list[AccountBalance]:
    """Get debit/credit/balance for all accounts up to given year/month.

    year_only=False (default): cumulative desde el inicio de la empresa.
        Correcto para Balance General y Balance de Comprobación.

    year_only=True: solo períodos del año indicado.
        Correcto para Estado de Resultados (cuentas 6x-7x se reinician cada año).
    """
    # Build period ID subquery with proper scope
    base = select(FiscalPeriod.id).where(FiscalPeriod.company_id == company_id)

    if year_only:
        period_filter = base.where(FiscalPeriod.year == year)
        if month:
            period_filter = period_filter.where(FiscalPeriod.month <= month)
    else:
        if month:
            period_filter = base.where(
                or_(
                    FiscalPeriod.year < year,
                    and_(FiscalPeriod.year == year, FiscalPeriod.month <= month),
                )
            )
        else:
            period_filter = base.where(FiscalPeriod.year <= year)

    # Subquery: pre-aggregate only the lines that belong to the filtered periods.
    # Using LEFT JOIN on Account ensures accounts with no movements still appear.
    # The INNER JOIN inside the subquery ensures only period-scoped lines are summed.
    je_filter = (
        (JournalEntry.id == JournalEntryLine.journal_entry_id)
        & (JournalEntry.status == "POSTED")
        & (JournalEntry.fiscal_period_id.in_(period_filter))
    )
    if exclude_closing:
        je_filter = je_filter & (JournalEntry.source != "CIERRE_ANUAL")

    agg = (
        select(
            JournalEntryLine.account_id,
            func.sum(JournalEntryLine.debit).label("total_debit"),
            func.sum(JournalEntryLine.credit).label("total_credit"),
        )
        .join(JournalEntry, je_filter)
        .group_by(JournalEntryLine.account_id)
        .subquery()
    )

    q = (
        select(
            Account.code,
            Account.name,
            Account.normal_balance,
            func.coalesce(agg.c.total_debit, 0).label("total_debit"),
            func.coalesce(agg.c.total_credit, 0).label("total_credit"),
        )
        .select_from(Account)
        .outerjoin(agg, agg.c.account_id == Account.id)
        .where(Account.company_id == company_id, Account.is_active == True)
        .order_by(Account.code)
    )

    rows = (await db.execute(q)).all()
    result = []
    for row in rows:
        normal_balance = row.normal_balance or "D"  # fallback for malformed accounts
        debit = Decimal(str(row.total_debit))
        credit = Decimal(str(row.total_credit))
        balance = debit - credit if normal_balance == "D" else credit - debit
        result.append(AccountBalance(
            code=row.code,
            name=row.name,
            normal_balance=normal_balance,
            debit=debit,
            credit=credit,
            balance=balance,
        ))
    return result


async def get_trial_balance(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int,
) -> TrialBalanceReport:
    balances = await get_account_balances(db, company_id, year, month)
    lines = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for b in balances:
        if b.debit == 0 and b.credit == 0:
            continue
        # balance > 0 = saldo en el lado normal de la cuenta
        # balance < 0 = saldo en el lado contrario (ej. cuenta deudora con más créditos)
        if b.balance >= 0:
            bal_d = b.balance if b.normal_balance == "D" else Decimal("0")
            bal_c = b.balance if b.normal_balance == "C" else Decimal("0")
        else:
            # Saldo en lado contrario al normal (negativo)
            bal_d = Decimal("0") if b.normal_balance == "D" else abs(b.balance)
            bal_c = abs(b.balance) if b.normal_balance == "D" else Decimal("0")
        total_debit += b.debit
        total_credit += b.credit
        lines.append(TrialBalanceLine(
            code=b.code,
            name=b.name,
            total_debit=b.debit,
            total_credit=b.credit,
            balance_debit=bal_d,
            balance_credit=bal_c,
        ))

    return TrialBalanceReport(lines=lines, total_debit=total_debit, total_credit=total_credit)


async def get_libro_mayor(
    db: AsyncSession,
    company_id: uuid.UUID,
    account_id: uuid.UUID,
    year: int,
    month: int,
):
    """Get all posted journal entry lines for an account with running balance."""
    from sqlalchemy.orm import selectinload
    period_filter = select(FiscalPeriod.id).where(
        FiscalPeriod.company_id == company_id,
        FiscalPeriod.year == year,
        FiscalPeriod.month <= month,
    )

    r = await db.execute(select(Account).where(Account.id == account_id, Account.company_id == company_id))
    account = r.scalar_one_or_none()
    if not account:
        return None, []

    q = (
        select(JournalEntryLine, JournalEntry.entry_date, JournalEntry.entry_number, JournalEntry.description)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntryLine.account_id == account_id,
            JournalEntry.status == "POSTED",
            JournalEntry.fiscal_period_id.in_(period_filter),
        )
        .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    )

    rows = (await db.execute(q)).all()
    running = Decimal("0")
    lines = []
    for line, entry_date, entry_number, entry_desc in rows:
        if account.normal_balance == "D":
            running += line.debit - line.credit
        else:
            running += line.credit - line.debit
        lines.append({
            "entry_number": entry_number,
            "entry_date": entry_date,
            "entry_description": entry_desc,
            "line_description": line.description,
            "debit": line.debit,
            "credit": line.credit,
            "balance": running,
        })

    return account, lines
