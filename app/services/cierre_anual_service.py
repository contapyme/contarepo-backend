"""
Proceso de cierre anual contable.

Genera el asiento de cierre que transfiere todos los saldos de cuentas de gestión
(elementos 6 y 7) a la cuenta 591 Utilidades no distribuidas (o 592 Pérdidas acumuladas).

Asiento de cierre:
  - Por cada cuenta 7x con saldo: DEBE la cuenta 7x → HABER 591
  - Por cada cuenta 6x con saldo: DEBE 591 → HABER la cuenta 6x
  - Si hay pérdida neta: DEBE 592 → ajuste

Luego del cierre:
  - Cuentas 6x y 7x quedan con saldo cero
  - El resultado queda acumulado en 59x
"""
import uuid
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.fiscal_period import FiscalPeriod
from app.schemas.journal_entry import JournalEntryCreate, JournalLineCreate
from app.services.reports.ledger_service import get_account_balances
from app.services import journal_entry_service


async def _find_account(db: AsyncSession, company_id: uuid.UUID, code: str) -> Account | None:
    r = await db.execute(
        select(Account).where(
            Account.company_id == company_id,
            Account.code == code,
            Account.is_active == True,
        )
    )
    return r.scalar_one_or_none()


async def preview_cierre_anual(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
) -> dict:
    """Previsualiza el asiento de cierre sin ejecutarlo."""
    balances = await get_account_balances(db, company_id, year, 12)
    bmap = {b.code: b for b in balances}

    ingresos_lines = []
    gastos_lines = []
    total_ingresos = Decimal("0")
    total_gastos = Decimal("0")

    for code, b in sorted(bmap.items()):
        if b.balance == 0:
            continue
        if code.startswith("7"):
            ingresos_lines.append({"code": code, "name": b.name, "amount": float(b.balance)})
            total_ingresos += b.balance
        elif code.startswith("6"):
            gastos_lines.append({"code": code, "name": b.name, "amount": float(b.balance)})
            total_gastos += b.balance

    resultado = total_ingresos - total_gastos
    ya_cerrado = await _cierre_ya_existe(db, company_id, year)

    return {
        "year": year,
        "ingresos": ingresos_lines,
        "gastos": gastos_lines,
        "total_ingresos": float(total_ingresos),
        "total_gastos": float(total_gastos),
        "resultado_neto": float(resultado),
        "es_utilidad": resultado >= 0,
        "ya_cerrado": ya_cerrado,
        "lineas_asiento": len(ingresos_lines) + len(gastos_lines) + 1,
    }


async def _cierre_ya_existe(db: AsyncSession, company_id: uuid.UUID, year: int) -> bool:
    """Verifica si ya existe un asiento de cierre para el año."""
    r = await db.execute(
        select(JournalEntry).where(
            JournalEntry.company_id == company_id,
            JournalEntry.source == "CIERRE_ANUAL",
        ).join(
            FiscalPeriod,
            (FiscalPeriod.id == JournalEntry.fiscal_period_id) &
            (FiscalPeriod.year == year) &
            (FiscalPeriod.month == 12),
        )
    )
    return r.scalar_one_or_none() is not None


async def ejecutar_cierre_anual(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    year: int,
) -> dict:
    """Ejecuta el asiento de cierre anual."""

    if await _cierre_ya_existe(db, company_id, year):
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un asiento de cierre para el año {year}"
        )

    balances = await get_account_balances(db, company_id, year, 12)
    bmap = {b.code: b for b in balances}

    # Buscar cuenta destino del resultado
    cuenta_utilidades = await _find_account(db, company_id, "591")
    cuenta_perdidas = await _find_account(db, company_id, "592")

    if not cuenta_utilidades and not cuenta_perdidas:
        raise HTTPException(
            status_code=400,
            detail="No se encontraron las cuentas 591 (Utilidades) ni 592 (Pérdidas). Verifique el plan contable."
        )

    lines: list[JournalLineCreate] = []
    total_ingresos = Decimal("0")
    total_gastos = Decimal("0")

    # Cerrar cuentas de ingresos (7x): DEBE la 7x → HABER 591
    for code, b in sorted(bmap.items()):
        if not code.startswith("7") or b.balance == 0:
            continue
        # Buscar la cuenta por código
        acc = await _find_account(db, company_id, code)
        if not acc or not acc.allows_entries:
            continue
        total_ingresos += b.balance
        lines.append(JournalLineCreate(
            account_id=acc.id,
            description=f"Cierre de ingresos {year} — {acc.name}",
            debit=float(b.balance),
            credit=0,
        ))

    # Cerrar cuentas de gastos (6x): DEBE 591 → HABER la 6x
    for code, b in sorted(bmap.items()):
        if not code.startswith("6") or b.balance == 0:
            continue
        acc = await _find_account(db, company_id, code)
        if not acc or not acc.allows_entries:
            continue
        total_gastos += b.balance
        lines.append(JournalLineCreate(
            account_id=acc.id,
            description=f"Cierre de gastos {year} — {acc.name}",
            debit=0,
            credit=float(b.balance),
        ))

    if not lines:
        raise HTTPException(
            status_code=400,
            detail="No hay saldos en cuentas de gestión (6x/7x) para cerrar."
        )

    resultado = total_ingresos - total_gastos

    # Línea de contrapartida en 591 o 592
    if resultado >= 0:
        cuenta_resultado = cuenta_utilidades or cuenta_perdidas
        lines.append(JournalLineCreate(
            account_id=cuenta_resultado.id,
            description=f"Resultado del ejercicio {year} — Utilidad neta",
            debit=0,
            credit=float(resultado),
        ))
    else:
        cuenta_resultado = cuenta_perdidas or cuenta_utilidades
        lines.append(JournalLineCreate(
            account_id=cuenta_resultado.id,
            description=f"Resultado del ejercicio {year} — Pérdida neta",
            debit=float(abs(resultado)),
            credit=0,
        ))

    entry_data = JournalEntryCreate(
        entry_date=date(year, 12, 31),
        description=f"Asiento de cierre del ejercicio {year}",
        document_type=None,
        document_number=None,
        lines=lines,
    )

    # Patch source after creation
    entry = await journal_entry_service.create_entry(db, company_id, user_id, entry_data, skip_allows_entries_check=True)
    entry.source = "CIERRE_ANUAL"
    await db.flush()

    # Auto-post the closing entry
    entry.status = "POSTED"
    await db.flush()

    return {
        "entry_id": str(entry.id),
        "entry_number": entry.entry_number,
        "year": year,
        "total_ingresos": float(total_ingresos),
        "total_gastos": float(total_gastos),
        "resultado_neto": float(resultado),
        "lineas": len(lines),
    }
