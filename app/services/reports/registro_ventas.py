import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.fiscal_period import FiscalPeriod


async def get_registro_ventas(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int,
) -> list[dict]:
    """
    Registro de Ventas e Ingresos.
    Retorna asientos del período que afectan cuentas 70x/40x (ventas + IGV ventas).
    """
    period_filter = select(FiscalPeriod.id).where(
        FiscalPeriod.company_id == company_id,
        FiscalPeriod.year == year,
        FiscalPeriod.month == month,
    )

    # Obtener IDs de asientos que tocan cuentas 70x, 71x, 72x, 73x (ingresos)
    ventas_entries = select(JournalEntryLine.journal_entry_id).join(
        JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
    ).join(
        FiscalPeriod, FiscalPeriod.id == JournalEntry.fiscal_period_id
    ).where(
        JournalEntry.company_id == company_id,
        JournalEntry.status == "POSTED",
        JournalEntry.fiscal_period_id.in_(period_filter),
    ).distinct()

    from app.models.account import Account
    # Filtramos a los que tienen alguna línea en cuentas 7x
    ventas_entries = (
        select(JournalEntryLine.journal_entry_id)
        .join(Account, Account.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == "POSTED",
            JournalEntry.fiscal_period_id.in_(period_filter),
            Account.code.like("7%"),
        )
        .distinct()
    )

    q = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
        .where(JournalEntry.id.in_(ventas_entries))
        .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    )

    entries = (await db.execute(q)).scalars().all()

    rows = []
    for e in entries:
        base_imponible = 0.0
        igv = 0.0
        op_exonerada = 0.0
        op_inafecta = 0.0
        total = 0.0

        for l in e.lines:
            code = l.account.code if l.account else ""
            if code.startswith("4011"):
                igv += float(l.credit) - float(l.debit)
            elif code.startswith("4012"):
                pass
            elif code.startswith("70") or code.startswith("71") or code.startswith("72") or code.startswith("73"):
                base_imponible += float(l.credit) - float(l.debit)
            elif code.startswith("40"):
                pass

        total = base_imponible + igv

        # Buscar datos del cliente en aux_name/aux_type de las líneas
        cliente_doc = ""
        cliente_nombre = ""
        for l in e.lines:
            if l.aux_name:
                cliente_nombre = l.aux_name
            if l.aux_type:
                cliente_doc = l.aux_type

        rows.append({
            "entry_number": e.entry_number,
            "entry_date": e.entry_date,
            "document_type": e.document_type or "",
            "document_number": e.document_number or "",
            "cliente_doc": cliente_doc,
            "cliente_nombre": cliente_nombre,
            "base_imponible": round(base_imponible, 2),
            "igv": round(igv, 2),
            "op_exonerada": round(op_exonerada, 2),
            "op_inafecta": round(op_inafecta, 2),
            "total": round(total, 2),
        })

    return rows
