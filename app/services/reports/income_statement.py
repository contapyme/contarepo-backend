import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.reports import IncomeStatementReport, ReportLine
from app.services.reports.ledger_service import get_account_balances


def _sum_codes(bmap: dict, *prefixes: str) -> Decimal:
    total = Decimal("0")
    for code, bal in bmap.items():
        for p in prefixes:
            if code.startswith(p):
                total += bal
                break
    return total


async def generate_income_statement(
    db: AsyncSession,
    company_id: uuid.UUID,
    company_name: str,
    ruc: str,
    year: int,
    month: int,
    currency: str = "PEN",
) -> IncomeStatementReport:
    balances = await get_account_balances(db, company_id, year, month, year_only=True, exclude_closing=True)
    bmap = {b.code: b.balance for b in balances}

    def s(*prefixes) -> Decimal:
        return _sum_codes(bmap, *prefixes)

    ventas_brutas = s("70", "71", "72")
    devoluciones = s("709")
    ventas_netas = ventas_brutas - devoluciones

    costo_ventas = s("69")
    utilidad_bruta = ventas_netas - costo_ventas

    gastos_ventas = s("94") if s("94") > 0 else s("637", "631")
    gastos_admin = s("95") if s("95") > 0 else (s("62", "63", "64", "65", "68") - gastos_ventas)
    otros_ingresos = s("75", "76")
    otros_gastos = s("655", "659")
    resultado_operacion = utilidad_bruta - gastos_ventas - gastos_admin + otros_ingresos - otros_gastos

    ingresos_financieros = s("77")
    gastos_financieros = s("67")
    diferencia_cambio = s("776") - s("676")
    resultado_antes_ir = resultado_operacion + ingresos_financieros - gastos_financieros + diferencia_cambio

    participaciones = s("87")
    impuesto_renta = s("88")
    resultado_neto = resultado_antes_ir - participaciones - impuesto_renta

    lines: list[ReportLine] = [
        ReportLine(label="Ventas netas o ingresos por servicios", amount=ventas_brutas, indent=1),
        ReportLine(label="(-) Devoluciones sobre ventas", amount=-devoluciones, indent=1),
        ReportLine(label="VENTAS NETAS", amount=ventas_netas, indent=0, is_subtotal=True),
        ReportLine(label="(-) Costo de ventas", amount=-costo_ventas, indent=1),
        ReportLine(label="UTILIDAD BRUTA", amount=utilidad_bruta, indent=0, is_total=True),
        ReportLine(label="(-) Gastos de ventas", amount=-gastos_ventas, indent=1),
        ReportLine(label="(-) Gastos de administración", amount=-gastos_admin, indent=1),
        ReportLine(label="(+) Otros ingresos operacionales", amount=otros_ingresos, indent=1),
        ReportLine(label="(-) Otros gastos operacionales", amount=-otros_gastos, indent=1),
        ReportLine(label="RESULTADO DE OPERACIÓN", amount=resultado_operacion, indent=0, is_total=True),
        ReportLine(label="(+) Ingresos financieros", amount=ingresos_financieros, indent=1),
        ReportLine(label="(-) Gastos financieros", amount=-gastos_financieros, indent=1),
        ReportLine(label="Diferencia de cambio (neta)", amount=diferencia_cambio, indent=1),
        ReportLine(label="RESULTADO ANTES DE PART. E IR", amount=resultado_antes_ir, indent=0, is_total=True),
        ReportLine(label="(-) Participación de trabajadores", amount=-participaciones, indent=1),
        ReportLine(label="(-) Impuesto a la Renta", amount=-impuesto_renta, indent=1),
        ReportLine(label="RESULTADO DEL EJERCICIO", amount=resultado_neto, indent=0, is_total=True),
    ]

    return IncomeStatementReport(
        company_name=company_name,
        ruc=ruc,
        period=f"Enero - {_month_name(month)} {year}",
        currency=currency,
        lines=lines,
        net_income=resultado_neto,
    )


def _month_name(m: int) -> str:
    return ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][m]
