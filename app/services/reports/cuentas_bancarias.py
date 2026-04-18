import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.bank_account import BankAccount
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.account import Account


async def get_cuentas_bancarias(
    db: AsyncSession,
    company_id: uuid.UUID,
    from_date: date | None,
    to_date: date | None,
) -> list[dict]:
    """
    Reporte de cuentas bancarias: lista de bancos con saldo inicial,
    movimientos del período y saldo final.
    """
    # 1. Obtener todas las cuentas bancarias de la empresa
    banks_q = (
        select(BankAccount)
        .where(BankAccount.company_id == company_id, BankAccount.is_active == True)
        .order_by(BankAccount.bank_name)
    )
    banks = (await db.execute(banks_q)).scalars().all()

    result = []

    for bank in banks:
        # 2. Obtener la cuenta contable asociada
        account_q = select(Account).where(Account.id == bank.account_id)
        account = (await db.execute(account_q)).scalar_one_or_none()
        if not account:
            continue

        # 3. Saldo anterior al período (todo lo previo a from_date)
        saldo_anterior = 0.0
        if from_date:
            prev_q = (
                select(JournalEntryLine)
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
                .where(
                    JournalEntry.company_id == company_id,
                    JournalEntry.status == "POSTED",
                    JournalEntryLine.account_id == bank.account_id,
                    JournalEntry.entry_date < from_date,
                )
            )
            prev_lines = (await db.execute(prev_q)).scalars().all()
            for l in prev_lines:
                saldo_anterior += float(l.debit) - float(l.credit)

        # 4. Movimientos del período
        mov_q = (
            select(JournalEntry, JournalEntryLine)
            .join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "POSTED",
                JournalEntryLine.account_id == bank.account_id,
            )
        )
        if from_date:
            mov_q = mov_q.where(JournalEntry.entry_date >= from_date)
        if to_date:
            mov_q = mov_q.where(JournalEntry.entry_date <= to_date)
        mov_q = mov_q.order_by(JournalEntry.entry_date, JournalEntry.entry_number)

        rows = (await db.execute(mov_q)).all()

        movimientos = []
        total_debitos = 0.0
        total_creditos = 0.0
        saldo_acum = saldo_anterior

        for entry, line in rows:
            debit = float(line.debit)
            credit = float(line.credit)
            saldo_acum += debit - credit
            total_debitos += debit
            total_creditos += credit
            movimientos.append({
                "fecha": entry.entry_date,
                "numero": entry.entry_number,
                "documento": entry.document_number or "",
                "tipo": entry.document_type or "",
                "descripcion": entry.description,
                "debito": round(debit, 2),
                "credito": round(credit, 2),
                "saldo": round(saldo_acum, 2),
            })

        result.append({
            "banco": bank.bank_name,
            "numero_cuenta": bank.account_number,
            "moneda": bank.currency,
            "cuenta_contable": account.code,
            "cuenta_nombre": account.name,
            "saldo_anterior": round(saldo_anterior, 2),
            "total_debitos": round(total_debitos, 2),
            "total_creditos": round(total_creditos, 2),
            "saldo_final": round(saldo_anterior + total_debitos - total_creditos, 2),
            "movimientos": movimientos,
        })

    return result
