import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.fiscal_period import FiscalPeriod
from app.models.account import Account


async def get_libro_diario(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int,
):
    period_filter = select(FiscalPeriod.id).where(
        FiscalPeriod.company_id == company_id,
        FiscalPeriod.year == year,
        FiscalPeriod.month == month,
    )

    q = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == "POSTED",
            JournalEntry.fiscal_period_id.in_(period_filter),
        )
        .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    )

    entries = (await db.execute(q)).scalars().all()

    result = []
    for e in entries:
        result.append({
            "entry_number": e.entry_number,
            "entry_date": e.entry_date,
            "description": e.description,
            "document_type": e.document_type,
            "document_number": e.document_number,
            "source": e.source,
            "lines": [
                {
                    "line_number": l.line_number,
                    "account_code": l.account.code if l.account else "",
                    "account_name": l.account.name if l.account else "",
                    "description": l.description,
                    "debit": float(l.debit),
                    "credit": float(l.credit),
                }
                for l in e.lines
            ],
        })
    return result
