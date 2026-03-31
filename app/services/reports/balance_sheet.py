import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.reports import BalanceSheetReport, ReportLine
from app.services.reports.ledger_service import get_account_balances


def _sum_codes(balances_map: dict, prefixes: list[str]) -> Decimal:
    total = Decimal("0")
    for code, bal in balances_map.items():
        for prefix in prefixes:
            if code.startswith(prefix):
                total += bal
                break
    return total


async def generate_balance_sheet(
    db: AsyncSession,
    company_id: uuid.UUID,
    company_name: str,
    ruc: str,
    year: int,
    month: int,
    currency: str = "PEN",
) -> BalanceSheetReport:
    # No exclude_closing here: the cierre asiento must be included so 592 reflects
    # the accumulated loss. exclude_closing is used only for the P&L (year_only) query below.
    balances = await get_account_balances(db, company_id, year, month)

    # bmap: balance in normal side (D accounts: debit-credit, C accounts: credit-debit)
    # Used for ASSETS (D-normal: positive balance = asset value)
    bmap: dict[str, Decimal] = {b.code: b.balance for b in balances}

    # bmap_nc: net credit position (credit - debit), sign-correct for LIABILITIES & EQUITY
    # 591 Utilidades (C-normal): credit-debit > 0 → adds to equity ✓
    # 592 Pérdidas (D-normal):   credit-debit < 0 → reduces equity ✓
    bmap_nc: dict[str, Decimal] = {b.code: b.credit - b.debit for b in balances}

    def s(*prefixes) -> Decimal:
        return _sum_codes(bmap, list(prefixes))

    def s_nc(*prefixes) -> Decimal:
        """Net credit — use for liability and equity sections."""
        return _sum_codes(bmap_nc, list(prefixes))

    period_name = f"{month:02d}/{year}"

    # ── ACTIVOS ──────────────────────────────────────────────────────────────
    caja_bancos = s("10")
    inversiones_cp = s("11")
    cxc_comerciales = s("12") - s("19")
    cxc_relacionadas = s("13")
    otras_cxc = s("14", "16", "17")
    existencias = s("20", "21", "22", "23", "24", "25", "26") - s("29")
    gastos_anticipados = s("18")
    activo_corriente = caja_bancos + inversiones_cp + cxc_comerciales + cxc_relacionadas + otras_cxc + existencias + gastos_anticipados

    inversiones_lp = s("30", "31")
    ppe_bruto = s("33")
    depreciacion = s("39")
    ppe_neto = ppe_bruto - depreciacion
    intangibles_bruto = s("34")
    amortizacion = Decimal("0")  # covered in 39
    intangibles_neto = intangibles_bruto
    activo_diferido = s("37")
    otros_activos = s("38")
    activo_no_corriente = inversiones_lp + ppe_neto + intangibles_neto + activo_diferido + otros_activos

    total_activo = activo_corriente + activo_no_corriente

    # ── PASIVOS ───────────────────────────────────────────────────────────────
    tributos_pagar = s_nc("40")
    remuneraciones_pagar = s_nc("41")
    cxp_comerciales = s_nc("42")
    cxp_relacionadas = s_nc("43")
    cxp_accionistas = s_nc("44")
    obligaciones_financieras_cp = s_nc("45")
    cxp_diversas = s_nc("46", "47")
    pasivo_corriente = tributos_pagar + remuneraciones_pagar + cxp_comerciales + cxp_relacionadas + cxp_accionistas + obligaciones_financieras_cp + cxp_diversas

    provisiones = s_nc("48")
    pasivo_diferido = s_nc("49")
    pasivo_no_corriente = provisiones + pasivo_diferido

    total_pasivo = pasivo_corriente + pasivo_no_corriente

    # ── PATRIMONIO ────────────────────────────────────────────────────────────
    # s_nc() gives credit - debit: correct sign for both 591 (utilidades, C-normal)
    # and 592 (pérdidas, D-normal) — losses reduce equity naturally
    capital = s_nc("50")
    acciones_inversion = s_nc("51")
    capital_adicional = s_nc("52")
    excedente_revaluacion = s_nc("57")
    reservas = s_nc("58")
    resultados_acumulados = s_nc("59")

    # Resultado del ejercicio: solo si el cierre anual NO se ha ejecutado.
    # Si ya se ejecutó, el resultado está absorbido en 59x (resultados_acumulados).
    from app.services.cierre_anual_service import _cierre_ya_existe
    cierre_ejecutado = await _cierre_ya_existe(db, company_id, year)
    if cierre_ejecutado:
        resultado_ejercicio = Decimal("0")
    else:
        balances_yr = await get_account_balances(db, company_id, year, month, year_only=True, exclude_closing=True)
        bmap_yr = {b.code: b.balance for b in balances_yr}
        ingresos = sum((v for c, v in bmap_yr.items() if c[:2] in {"70","71","72","73","74","75","76","77","78","79"}), Decimal("0"))
        gastos = sum((v for c, v in bmap_yr.items() if c[:2] in {"60","61","62","63","64","65","66","67","68","69"}), Decimal("0"))
        resultado_ejercicio = ingresos - gastos

    total_patrimonio = capital + acciones_inversion + capital_adicional + excedente_revaluacion + reservas + resultados_acumulados + resultado_ejercicio

    total_pasivo_patrimonio = total_pasivo + total_patrimonio

    # Build report lines
    assets: list[ReportLine] = [
        ReportLine(label="ACTIVO CORRIENTE", amount=Decimal("0"), indent=0, is_subtotal=True),
        ReportLine(label="Efectivo y Equivalentes de Efectivo", amount=caja_bancos, indent=1),
        ReportLine(label="Inversiones Financieras", amount=inversiones_cp, indent=1),
        ReportLine(label="Cuentas por Cobrar Comerciales (neto)", amount=cxc_comerciales, indent=1),
        ReportLine(label="Cuentas por Cobrar Relacionadas", amount=cxc_relacionadas, indent=1),
        ReportLine(label="Otras Cuentas por Cobrar", amount=otras_cxc, indent=1),
        ReportLine(label="Existencias (neto)", amount=existencias, indent=1),
        ReportLine(label="Gastos Pagados por Anticipado", amount=gastos_anticipados, indent=1),
        ReportLine(label="TOTAL ACTIVO CORRIENTE", amount=activo_corriente, indent=0, is_total=True),
        ReportLine(label="ACTIVO NO CORRIENTE", amount=Decimal("0"), indent=0, is_subtotal=True),
        ReportLine(label="Inversiones Mobiliarias e Inmobiliarias", amount=inversiones_lp, indent=1),
        ReportLine(label="Inmuebles, Maquinaria y Equipo (neto)", amount=ppe_neto, indent=1),
        ReportLine(label="Intangibles (neto)", amount=intangibles_neto, indent=1),
        ReportLine(label="Activo Diferido", amount=activo_diferido, indent=1),
        ReportLine(label="Otros Activos", amount=otros_activos, indent=1),
        ReportLine(label="TOTAL ACTIVO NO CORRIENTE", amount=activo_no_corriente, indent=0, is_total=True),
        ReportLine(label="TOTAL ACTIVO", amount=total_activo, indent=0, is_total=True),
    ]

    liabilities: list[ReportLine] = [
        ReportLine(label="PASIVO CORRIENTE", amount=Decimal("0"), indent=0, is_subtotal=True),
        ReportLine(label="Tributos por Pagar", amount=tributos_pagar, indent=1),
        ReportLine(label="Remuneraciones por Pagar", amount=remuneraciones_pagar, indent=1),
        ReportLine(label="Cuentas por Pagar Comerciales", amount=cxp_comerciales, indent=1),
        ReportLine(label="Cuentas por Pagar Relacionadas", amount=cxp_relacionadas, indent=1),
        ReportLine(label="Cuentas por Pagar Accionistas", amount=cxp_accionistas, indent=1),
        ReportLine(label="Obligaciones Financieras", amount=obligaciones_financieras_cp, indent=1),
        ReportLine(label="Otras Cuentas por Pagar", amount=cxp_diversas, indent=1),
        ReportLine(label="TOTAL PASIVO CORRIENTE", amount=pasivo_corriente, indent=0, is_total=True),
        ReportLine(label="PASIVO NO CORRIENTE", amount=Decimal("0"), indent=0, is_subtotal=True),
        ReportLine(label="Provisiones", amount=provisiones, indent=1),
        ReportLine(label="Pasivo Diferido", amount=pasivo_diferido, indent=1),
        ReportLine(label="TOTAL PASIVO NO CORRIENTE", amount=pasivo_no_corriente, indent=0, is_total=True),
        ReportLine(label="TOTAL PASIVO", amount=total_pasivo, indent=0, is_total=True),
    ]

    equity: list[ReportLine] = [
        ReportLine(label="Capital Social", amount=capital, indent=1),
        ReportLine(label="Acciones de Inversión", amount=acciones_inversion, indent=1),
        ReportLine(label="Capital Adicional", amount=capital_adicional, indent=1),
        ReportLine(label="Excedente de Revaluación", amount=excedente_revaluacion, indent=1),
        ReportLine(label="Reservas", amount=reservas, indent=1),
        ReportLine(label="Resultados Acumulados", amount=resultados_acumulados, indent=1),
        ReportLine(label="Resultado del Ejercicio", amount=resultado_ejercicio, indent=1),
        ReportLine(label="TOTAL PATRIMONIO", amount=total_patrimonio, indent=0, is_total=True),
        ReportLine(label="TOTAL PASIVO Y PATRIMONIO", amount=total_pasivo_patrimonio, indent=0, is_total=True),
    ]

    return BalanceSheetReport(
        company_name=company_name,
        ruc=ruc,
        period=period_name,
        currency=currency,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=total_activo,
        total_liabilities_equity=total_pasivo_patrimonio,
        balanced=abs(total_activo - total_pasivo_patrimonio) < Decimal("0.01"),
    )
