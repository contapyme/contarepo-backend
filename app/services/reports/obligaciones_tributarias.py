import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.account import Account

MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


async def get_obligaciones_tributarias(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
) -> dict:
    """
    Detalle mensual de obligaciones tributarias SUNAT (cuentas 40xx).

    Para cada cuenta 40xx devuelve movimientos mensuales:
    - haber (crédito): obligación generada / tributo devengado
    - debe (débito): pago realizado a SUNAT
    - neto: haber - debe (positivo = pendiente de pago)
    """
    q = (
        select(
            extract("month", JournalEntry.entry_date).label("month"),
            Account.code,
            Account.name,
            func.sum(JournalEntryLine.debit).label("total_debit"),
            func.sum(JournalEntryLine.credit).label("total_credit"),
        )
        .select_from(JournalEntryLine)
        .join(Account, Account.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.company_id == company_id,
            Account.company_id == company_id,
            Account.code.like("40%"),
            extract("year", JournalEntry.entry_date) == year,
        )
        .group_by(
            extract("month", JournalEntry.entry_date),
            Account.code,
            Account.name,
        )
        .order_by(Account.code, extract("month", JournalEntry.entry_date))
    )
    rows = (await db.execute(q)).all()

    # Build: {code: {nombre, meses: {1..12: {debe, haber}}}}
    accounts: dict[str, dict] = {}
    for row in rows:
        code = row.code
        month = int(row.month)
        if code not in accounts:
            accounts[code] = {
                "nombre": row.name,
                "meses": {m: {"debe": Decimal("0"), "haber": Decimal("0")} for m in range(1, 13)},
            }
        accounts[code]["meses"][month]["debe"] += Decimal(str(row.total_debit))
        accounts[code]["meses"][month]["haber"] += Decimal(str(row.total_credit))

    obligaciones = []
    grand_total_haber = Decimal("0")
    grand_total_debe = Decimal("0")

    for code, acc in sorted(accounts.items()):
        monthly_data = []
        total_debe = Decimal("0")
        total_haber = Decimal("0")
        has_activity = False

        for m in range(1, 13):
            debe = acc["meses"][m]["debe"]
            haber = acc["meses"][m]["haber"]
            neto = haber - debe
            total_debe += debe
            total_haber += haber
            if debe != 0 or haber != 0:
                has_activity = True
            monthly_data.append({
                "mes": m,
                "nombre_mes": MONTH_NAMES[m],
                "debe": float(debe),
                "haber": float(haber),
                "neto": float(neto),
            })

        if not has_activity:
            continue

        grand_total_haber += total_haber
        grand_total_debe += total_debe
        total_neto = total_haber - total_debe

        obligaciones.append({
            "codigo": code,
            "nombre": acc["nombre"],
            "meses": monthly_data,
            "total_debe": float(total_debe),
            "total_haber": float(total_haber),
            "total_neto": float(total_neto),
        })

    return {
        "year": year,
        "obligaciones": obligaciones,
        "resumen": {
            "total_devengado": float(grand_total_haber),
            "total_pagado": float(grand_total_debe),
            "saldo_pendiente": float(grand_total_haber - grand_total_debe),
        },
    }
