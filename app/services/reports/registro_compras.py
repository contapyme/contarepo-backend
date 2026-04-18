import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.fiscal_period import FiscalPeriod
from app.models.account import Account
from app.models.contact import Contact


async def get_registro_compras(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int | None,
    month: int | None,
) -> list[dict]:
    """
    Registro de Compras (RCE).
    year=None → todo el historial. month=None → todo el año.
    Usa contact_id cuando está disponible; fallback a aux_name/aux_type.
    """
    period_q = select(FiscalPeriod.id).where(FiscalPeriod.company_id == company_id)
    if year is not None:
        period_q = period_q.where(FiscalPeriod.year == year)
        if month is not None:
            period_q = period_q.where(FiscalPeriod.month == month)

    compras_entries = (
        select(JournalEntryLine.journal_entry_id)
        .join(Account, Account.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == "POSTED",
            JournalEntry.fiscal_period_id.in_(period_q),
            Account.code.like("6%"),
        )
        .distinct()
    )

    q = (
        select(JournalEntry)
        .options(
            selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account),
            selectinload(JournalEntry.lines).selectinload(JournalEntryLine.contact),
        )
        .where(JournalEntry.id.in_(compras_entries))
        .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    )

    entries = (await db.execute(q)).scalars().all()

    rows = []
    for e in entries:
        base_imponible = 0.0
        igv = 0.0
        op_no_gravada = 0.0

        for l in e.lines:
            code = l.account.code if l.account else ""
            if code.startswith("4012"):
                igv += float(l.debit) - float(l.credit)
            elif code.startswith("6"):
                base_imponible += float(l.debit) - float(l.credit)

        total = base_imponible + igv

        # Obtener proveedor: primero contact_id, luego fallback a aux_name
        proveedor_doc = ""
        proveedor_nombre = ""
        for l in e.lines:
            if l.contact_id and l.contact:
                proveedor_doc = l.contact.doc_number
                proveedor_nombre = l.contact.razon_social
                break
        if not proveedor_nombre:
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
