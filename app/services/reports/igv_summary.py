import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.reports.ledger_service import get_account_balances


async def generate_igv_summary(
    db: AsyncSession,
    company_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    """
    Resumen IGV del período para declaración mensual (PDT 621).

    - IGV débito fiscal (ventas): cuentas 4011
    - IGV crédito fiscal (compras): cuentas 4012
    - Base imponible ventas: cuentas 70x
    - Base imponible compras: cuentas 60x, 63x, 64x, 65x, 67x
    """
    balances = await get_account_balances(db, company_id, year, month)

    # Solo el mes, no acumulado — necesitamos balances solo del mes
    # Usamos get_account_balances con year/month y restamos year/month-1
    balances_prev = []
    if month > 1:
        balances_prev = await get_account_balances(db, company_id, year, month - 1)
    else:
        balances_prev = await get_account_balances(db, company_id, year - 1, 12)

    bmap_curr = {b.code: b for b in balances}
    bmap_prev = {b.code: b for b in balances_prev}

    def month_balance(code_prefix: str) -> Decimal:
        """Saldo del mes = acumulado actual - acumulado anterior."""
        total_curr = Decimal("0")
        total_prev = Decimal("0")
        for code, b in bmap_curr.items():
            if code.startswith(code_prefix):
                total_curr += b.balance
        for code, b in bmap_prev.items():
            if code.startswith(code_prefix):
                total_prev += b.balance
        return total_curr - total_prev

    def month_debit(code_prefix: str) -> Decimal:
        total_curr = Decimal("0")
        total_prev = Decimal("0")
        for code, b in bmap_curr.items():
            if code.startswith(code_prefix):
                total_curr += b.debit
        for code, b in bmap_prev.items():
            if code.startswith(code_prefix):
                total_prev += b.debit
        return total_curr - total_prev

    def month_credit(code_prefix: str) -> Decimal:
        total_curr = Decimal("0")
        total_prev = Decimal("0")
        for code, b in bmap_curr.items():
            if code.startswith(code_prefix):
                total_curr += b.credit
        for code, b in bmap_prev.items():
            if code.startswith(code_prefix):
                total_prev += b.credit
        return total_curr - total_prev

    # IGV débito fiscal = lo que el negocio cobró de IGV a sus clientes (ventas)
    # Cuenta 4011 tiene saldo acreedor (normal_balance=C), el movimiento al Haber son las ventas
    igv_debito = month_credit("4011") - month_debit("4011")
    if igv_debito < 0:
        igv_debito = Decimal("0")

    # IGV crédito fiscal = IGV pagado en compras, deducible
    # Cuenta 4012 tiene saldo deudor, movimiento al Debe son compras
    igv_credito = month_debit("4012") - month_credit("4012")
    if igv_credito < 0:
        igv_credito = Decimal("0")

    # Base imponible ventas (operaciones gravadas)
    base_ventas = month_balance("70") + month_balance("71") + month_balance("72") + month_balance("73")

    # Base imponible compras (operaciones gravadas con crédito fiscal)
    base_compras = (
        month_balance("60") + month_balance("61") +
        month_balance("63") + month_balance("64") +
        month_balance("65") + month_balance("67")
    )

    # IGV resultante
    igv_por_pagar = igv_debito - igv_credito
    saldo_a_favor = max(Decimal("0"), -igv_por_pagar)
    igv_por_pagar = max(Decimal("0"), igv_por_pagar)

    # Detalle de cuentas IGV con movimientos
    igv_accounts = []
    all_codes = set(list(bmap_curr.keys()) + list(bmap_prev.keys()))
    for code in sorted(all_codes):
        if code.startswith("40"):
            curr = bmap_curr.get(code)
            prev = bmap_prev.get(code)
            d = (curr.debit if curr else Decimal("0")) - (prev.debit if prev else Decimal("0"))
            c = (curr.credit if curr else Decimal("0")) - (prev.credit if prev else Decimal("0"))
            if d != 0 or c != 0:
                name = curr.name if curr else (prev.name if prev else "")
                igv_accounts.append({"code": code, "name": name, "debit": float(d), "credit": float(c)})

    month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    return {
        "period": f"{month_names[month]} {year}",
        "year": year,
        "month": month,
        "base_imponible_ventas": float(base_ventas),
        "igv_debito_fiscal": float(igv_debito),
        "base_imponible_compras": float(base_compras),
        "igv_credito_fiscal": float(igv_credito),
        "igv_por_pagar": float(igv_por_pagar),
        "saldo_a_favor": float(saldo_a_favor),
        "igv_accounts": igv_accounts,
    }
