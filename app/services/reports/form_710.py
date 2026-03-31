import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.reports import Form710Report, Form710Field
from app.services.reports.ledger_service import get_account_balances


def _sum(bmap: dict, *prefixes: str) -> Decimal:
    total = Decimal("0")
    for code, bal in bmap.items():
        for p in prefixes:
            if code.startswith(p):
                total += bal
                break
    return total


async def generate_form_710(
    db: AsyncSession,
    company_id: uuid.UUID,
    company_name: str,
    ruc: str,
    year: int,
    currency: str = "PEN",
) -> Form710Report:
    # No exclude_closing: cierre asiento must be included so 592 reflects the accumulated loss.
    # exclude_closing is used only for the year_only income statement query (balances_yr).
    balances = await get_account_balances(db, company_id, year, 12)
    bmap = {b.code: b.balance for b in balances}
    # bmap_nc: net credit (credit - debit) — sign-correct for liabilities and equity
    bmap_nc = {b.code: b.credit - b.debit for b in balances}

    def s(*p) -> Decimal:
        return _sum(bmap, *p)

    def s_nc(*p) -> Decimal:
        return _sum(bmap_nc, *p)

    # Estado de Resultados usa balances solo del año (excluye cierre)
    balances_yr = await get_account_balances(db, company_id, year, 12, year_only=True, exclude_closing=True)
    bmap_yr = {b.code: b.balance for b in balances_yr}

    def sy(*p) -> Decimal:
        return _sum(bmap_yr, *p)

    # ── Estado de Resultados (casillas 100–199) ────────────────────────────
    c100 = sy("70", "71", "72")
    c101 = sy("709")
    c102 = c100 - c101
    c103 = sy("69")
    c104 = c102 - c103
    c105 = sy("94") if sy("94") > 0 else sy("637", "631")
    c106 = sy("95") if sy("95") > 0 else (sy("62", "63", "64", "65", "68") - c105)
    c107 = sy("756")
    c108 = sy("75") - sy("756")
    c109 = sy("65")
    c110 = c104 - c105 - c106 + c107 + c108 - c109
    c111 = sy("67")
    c112 = sy("77") - sy("776")
    c116 = sy("776")
    c117 = sy("676")
    c120 = c110 - c111 + c112 + c116 - c117
    c121 = sy("87")
    c122 = sy("88")
    c124 = c120 - c121 - c122

    # ── Balance General (casillas 400–499) ────────────────────────────────
    c401 = s("10")
    c402 = s("11")
    c403 = s("12") - s("19")
    c404 = s("13")
    c405 = s("14", "16", "17")
    c407 = s("20", "21", "22", "23", "24", "25", "26") - s("29")
    c408 = s("18")
    c410 = c401 + c402 + c403 + c404 + c405 + c407 + c408
    c413 = s("30", "31")
    c415 = s("33") - s("39")
    c416 = s("34")
    c417 = s("37")
    c420 = c413 + c415 + c416 + c417
    c421 = c410 + c420

    c431 = s_nc("45")
    c432 = s_nc("42")
    c433 = s_nc("40", "41", "43", "44", "46")
    c440 = c431 + c432 + c433
    c441 = s_nc("47")
    c443 = s_nc("48")
    c449 = c440 + c441 + c443

    c451 = s_nc("50")
    c452 = s_nc("51", "52")
    c453 = s_nc("57")
    c454 = s_nc("58")
    c456 = s_nc("591", "592")  # net_credit: utilidades suman, pérdidas restan
    # Si ya existe cierre anual, el resultado está en 59x; c457 = 0 para no duplicar
    from app.services.cierre_anual_service import _cierre_ya_existe
    cierre_ejecutado = await _cierre_ya_existe(db, company_id, year)
    c457 = Decimal("0") if cierre_ejecutado else c124
    c460 = c451 + c452 + c453 + c454 + c456 + c457
    c461 = c449 + c460

    income_statement = [
        Form710Field(field_code="100", field_name="Ventas netas o ingresos por servicios", amount=c100, section="A"),
        Form710Field(field_code="101", field_name="Descuentos, rebajas y bonificaciones concedidas", amount=c101, section="A"),
        Form710Field(field_code="102", field_name="Ventas netas", amount=c102, section="A"),
        Form710Field(field_code="103", field_name="Costo de ventas", amount=c103, section="A"),
        Form710Field(field_code="104", field_name="Resultado bruto (utilidad o pérdida)", amount=c104, section="A"),
        Form710Field(field_code="105", field_name="Gastos de ventas", amount=c105, section="A"),
        Form710Field(field_code="106", field_name="Gastos de administración", amount=c106, section="A"),
        Form710Field(field_code="107", field_name="Ganancia (pérdida) por venta de activos", amount=c107, section="A"),
        Form710Field(field_code="108", field_name="Otros ingresos operacionales", amount=c108, section="A"),
        Form710Field(field_code="109", field_name="Otros gastos operacionales", amount=c109, section="A"),
        Form710Field(field_code="110", field_name="Resultado de operación", amount=c110, section="A"),
        Form710Field(field_code="111", field_name="Gastos financieros", amount=c111, section="A"),
        Form710Field(field_code="112", field_name="Ingresos financieros gravados", amount=c112, section="A"),
        Form710Field(field_code="116", field_name="Diferencia de cambio (ganancia)", amount=c116, section="A"),
        Form710Field(field_code="117", field_name="Diferencia de cambio (pérdida)", amount=c117, section="A"),
        Form710Field(field_code="120", field_name="Resultado antes de part. e impuesto", amount=c120, section="A"),
        Form710Field(field_code="121", field_name="Distribución legal de la renta neta", amount=c121, section="A"),
        Form710Field(field_code="122", field_name="Impuesto a la renta", amount=c122, section="A"),
        Form710Field(field_code="124", field_name="Resultado del ejercicio", amount=c124, section="A"),
    ]

    balance_sheet = [
        Form710Field(field_code="401", field_name="Caja y bancos", amount=c401, section="B"),
        Form710Field(field_code="402", field_name="Valores negociables", amount=c402, section="B"),
        Form710Field(field_code="403", field_name="Cuentas por cobrar comerciales (neto)", amount=c403, section="B"),
        Form710Field(field_code="404", field_name="Cuentas por cobrar a vinculadas", amount=c404, section="B"),
        Form710Field(field_code="405", field_name="Otras cuentas por cobrar", amount=c405, section="B"),
        Form710Field(field_code="407", field_name="Existencias (neto)", amount=c407, section="B"),
        Form710Field(field_code="408", field_name="Gastos pagados por anticipado", amount=c408, section="B"),
        Form710Field(field_code="410", field_name="Total activo corriente", amount=c410, section="B"),
        Form710Field(field_code="413", field_name="Inversiones", amount=c413, section="B"),
        Form710Field(field_code="415", field_name="Inmuebles, maquinaria y equipo (neto)", amount=c415, section="B"),
        Form710Field(field_code="416", field_name="Intangibles (neto)", amount=c416, section="B"),
        Form710Field(field_code="417", field_name="Activo diferido", amount=c417, section="B"),
        Form710Field(field_code="420", field_name="Total activo no corriente", amount=c420, section="B"),
        Form710Field(field_code="421", field_name="TOTAL ACTIVO", amount=c421, section="B"),
        Form710Field(field_code="431", field_name="Obligaciones financieras CP", amount=c431, section="B"),
        Form710Field(field_code="432", field_name="Cuentas por pagar comerciales", amount=c432, section="B"),
        Form710Field(field_code="433", field_name="Otras cuentas por pagar", amount=c433, section="B"),
        Form710Field(field_code="440", field_name="Total pasivo corriente", amount=c440, section="B"),
        Form710Field(field_code="441", field_name="Deudas a largo plazo", amount=c441, section="B"),
        Form710Field(field_code="443", field_name="Provisiones", amount=c443, section="B"),
        Form710Field(field_code="449", field_name="TOTAL PASIVO", amount=c449, section="B"),
        Form710Field(field_code="451", field_name="Capital social", amount=c451, section="B"),
        Form710Field(field_code="452", field_name="Capital adicional", amount=c452, section="B"),
        Form710Field(field_code="453", field_name="Excedente de revaluación", amount=c453, section="B"),
        Form710Field(field_code="454", field_name="Reservas legales", amount=c454, section="B"),
        Form710Field(field_code="456", field_name="Resultados acumulados", amount=c456, section="B"),
        Form710Field(field_code="457", field_name="Resultado del ejercicio", amount=c457, section="B"),
        Form710Field(field_code="460", field_name="TOTAL PATRIMONIO", amount=c460, section="B"),
        Form710Field(field_code="461", field_name="TOTAL PASIVO Y PATRIMONIO", amount=c461, section="B"),
    ]

    return Form710Report(
        company_name=company_name,
        ruc=ruc,
        year=year,
        currency=currency,
        income_statement=income_statement,
        balance_sheet=balance_sheet,
    )


def generate_form_710_txt(report: Form710Report) -> str:
    """Generate SUNAT-compatible TXT format."""
    lines = []
    for field in report.income_statement + report.balance_sheet:
        # Convert to cents, right-aligned 15 chars
        cents = int(abs(field.amount) * 100)
        sign = "-" if field.amount < 0 else " "
        lines.append(f"{field.section}{field.field_code}{sign}{cents:015d}")
    return "\n".join(lines)
