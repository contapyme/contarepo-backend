import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.fiscal_period import FiscalPeriod
from app.models.account import Account


async def get_registro_compras(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int,
) -> list[dict]:
    """
    Registro de Compras (RCE).
    Retorna asientos del período que afectan cuentas 60x/61x + 4012 (compras + IGV compras).
    """
    period_filter = select(FiscalPeriod.id).where(
        FiscalPeriod.company_id == company_id,
        FiscalPeriod.year == year,
        FiscalPeriod.month == month,
    )

    compras_entries = (
        select(JournalEntryLine.journal_entry_id)
        .join(Account, Account.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == "POSTED",
            JournalEntry.fiscal_period_id.in_(period_filter),
            Account.code.like("6%"),
        )
        .distinct()
    )

    q = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
        .where(JournalEntry.id.in_(compras_entries))
        .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    )

    entries = (await db.execute(q)).scalars().all()

    rows = []
    for e in entries:
        base_imponible = 0.0
        igv = 0.0
        op_no_gravada = 0.0
        total = 0.0

        for l in e.lines:
            code = l.account.code if l.account else ""
            if code.startswith("4012"):
                igv += float(l.debit) - float(l.credit)
            elif code.startswith("40"):
                pass
            elif code.startswith("6"):
                base_imponible += float(l.debit) - float(l.credit)

        total = base_imponible + igv

        proveedor_doc = ""
        proveedor_nombre = ""
        for l in e.lines:
            if l.aux_name:
                proveedor_nombre = l.aux_name
            if l.aux_type:
                proveedor_doc = l.aux_type

        rows.append({
            "entry_number": e.entry_number,
            "entry_date": e.entry_date,
            "document_type": e.document_type or "",
            "document_number": e.document_number or "",
            "proveedor_doc": proveedor_doc,
            "proveedor_nombre": proveedor_nombre,
            "base_imponible": round(base_imponible, 2),
            "igv": round(igv, 2),
            "op_no_gravada": round(op_no_gravada, 2),
            "total": round(total, 2),
        })

    return rows
