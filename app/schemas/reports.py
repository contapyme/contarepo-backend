from decimal import Decimal
from pydantic import BaseModel


class AccountBalance(BaseModel):
    code: str
    name: str
    normal_balance: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class ReportLine(BaseModel):
    label: str
    amount: Decimal
    indent: int = 0
    is_total: bool = False
    is_subtotal: bool = False


class BalanceSheetReport(BaseModel):
    company_name: str
    ruc: str
    period: str
    currency: str
    assets: list[ReportLine]
    liabilities: list[ReportLine]
    equity: list[ReportLine]
    total_assets: Decimal
    total_liabilities_equity: Decimal
    balanced: bool


class IncomeStatementReport(BaseModel):
    company_name: str
    ruc: str
    period: str
    currency: str
    lines: list[ReportLine]
    net_income: Decimal


class Form710Field(BaseModel):
    field_code: str
    field_name: str
    amount: Decimal
    section: str


class Form710Report(BaseModel):
    company_name: str
    ruc: str
    year: int
    currency: str
    income_statement: list[Form710Field]
    balance_sheet: list[Form710Field]


class TrialBalanceLine(BaseModel):
    code: str
    name: str
    total_debit: Decimal
    total_credit: Decimal
    balance_debit: Decimal
    balance_credit: Decimal


class TrialBalanceReport(BaseModel):
    lines: list[TrialBalanceLine]
    total_debit: Decimal
    total_credit: Decimal
