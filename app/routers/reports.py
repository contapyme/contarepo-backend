import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.dependencies import get_active_company, CompanyContext
from app.models.company import Company
from app.schemas.reports import BalanceSheetReport, IncomeStatementReport, Form710Report, TrialBalanceReport
from app.services.reports.balance_sheet import generate_balance_sheet
from app.services.reports.income_statement import generate_income_statement
from app.services.reports.form_710 import generate_form_710, generate_form_710_txt
from app.services.reports.ledger_service import get_trial_balance, get_libro_mayor
from app.services.reports.igv_summary import generate_igv_summary
from app.services.reports.libro_diario import get_libro_diario
from app.services.reports.registro_ventas import get_registro_ventas
from app.services.reports.registro_compras import get_registro_compras

router = APIRouter(prefix="/reports", tags=["Reports"])


async def _get_company(ctx: CompanyContext, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.id == ctx.company_id))
    return result.scalar_one()


@router.get("/balance-sheet", response_model=BalanceSheetReport)
async def balance_sheet(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ctx, db)
    return await generate_balance_sheet(db, ctx.company_id, company.razon_social, company.ruc, year, month, company.moneda)


@router.get("/income-statement", response_model=IncomeStatementReport)
async def income_statement(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ctx, db)
    return await generate_income_statement(db, ctx.company_id, company.razon_social, company.ruc, year, month, company.moneda)


@router.get("/form-710", response_model=Form710Report)
async def form_710(
    year: int = Query(...),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ctx, db)
    return await generate_form_710(db, ctx.company_id, company.razon_social, company.ruc, year, company.moneda)


@router.get("/form-710/txt", response_class=PlainTextResponse)
async def form_710_txt(
    year: int = Query(...),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ctx, db)
    report = await generate_form_710(db, ctx.company_id, company.razon_social, company.ruc, year, company.moneda)
    txt = generate_form_710_txt(report)
    return PlainTextResponse(
        content=txt,
        headers={"Content-Disposition": f"attachment; filename=F710_{company.ruc}_{year}.txt"},
    )


@router.get("/trial-balance", response_model=TrialBalanceReport)
async def trial_balance(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    return await get_trial_balance(db, ctx.company_id, year, month)


@router.get("/igv-summary")
async def igv_summary(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    return await generate_igv_summary(db, ctx.company_id, year, month)


@router.get("/libro-mayor")
async def libro_mayor(
    account_id: uuid.UUID = Query(...),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    account, lines = await get_libro_mayor(db, ctx.company_id, account_id, year, month)
    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {
        "account_code": account.code,
        "account_name": account.name,
        "normal_balance": account.normal_balance,
        "movements": lines,
    }


@router.get("/libro-diario")
async def libro_diario(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    return await get_libro_diario(db, ctx.company_id, year, month)


@router.get("/registro-ventas")
async def registro_ventas(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    return await get_registro_ventas(db, ctx.company_id, year, month)


@router.get("/registro-compras")
async def registro_compras(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    return await get_registro_compras(db, ctx.company_id, year, month)


# ── Balance Cache ──────────────────────────────────────────────────────────────

@router.get("/balance-cache/status")
async def balance_cache_status(
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    from app.services.balance_cache_service import get_status
    return await get_status(db, ctx.company_id)


@router.post("/balance-cache/recalculate")
async def balance_cache_recalculate(
    ctx: CompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
):
    from app.services.balance_cache_service import recalculate
    result = await recalculate(db, ctx.company_id)
    await db.commit()
    return result
