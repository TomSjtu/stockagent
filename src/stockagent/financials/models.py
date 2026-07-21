from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel


class SecFilingReference(BaseModel):
    """Metadata needed to link annual financial data to its SEC filing."""

    # 实际采用的 SEC 年度申报表类型
    form: Literal["10-K", "10-K/A"]
    # 该 filing 对应的公司财年标签
    fiscal_year: int
    # 该 filing 覆盖的财年截止日
    period_end: date
    # 向 SEC 提交该 filing 的日期
    filed_at: date
    # SEC 为申报主体分配的唯一 CIK
    cik: str
    # SEC 为本次具体申报分配的 accession number
    accession_number: str
    # filing 目录中主 HTML 文档的文件名
    primary_document: str
    # SEC Archive 中主 HTML 文档的完整链接
    url: str


@dataclass(slots=True)
class FinancialRecord:
    """One fiscal year of standardized core financial data."""

    ticker: str
    company_name: str
    fiscal_year: int

    # Income Statement
    revenue: float | None = None
    cost_of_sales: float | None = None
    gross_profit: float | None = None
    rd_expense: float | None = None
    sga_expense: float | None = None
    operating_expenses: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None

    # Balance Sheet
    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    long_term_debt: float | None = None
    shareholders_equity: float | None = None

    # Cash Flow
    operating_cash_flow: float | None = None
    capex: float | None = None
    dividends_paid: float | None = None

    filing: SecFilingReference | None = None


@dataclass(slots=True)
class ProfitabilityMetrics:
    """Computed profitability ratios for one fiscal year."""

    fiscal_year: int
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roa: float | None = None
    roe: float | None = None
    roce: float | None = None
    rd_ratio: float | None = None
    sga_ratio: float | None = None


@dataclass(slots=True)
class CashFlowMetrics:
    """Computed cash flow metrics for one fiscal year."""

    fiscal_year: int
    free_cash_flow: float | None = None


@dataclass(slots=True)
class FinancialHealthMetrics:
    """Computed financial health ratios for one fiscal year."""

    fiscal_year: int
    equity_ratio: float | None = None
    liabilities_to_assets: float | None = None
    current_ratio: float | None = None
    cash_ratio: float | None = None
    operating_cash_flow_to_total_liabilities: float | None = None


@dataclass(slots=True)
class GrowthMetrics:
    """Computed growth metrics for one fiscal year."""

    fiscal_year: int
    revenue_growth: float | None = None
    net_income_growth: float | None = None
    free_cash_flow_growth: float | None = None
    revenue_cagr: float | None = None
    net_income_cagr: float | None = None
    free_cash_flow_cagr: float | None = None


@dataclass(slots=True)
class ValuationMetrics:
    """Computed valuation ratios for one fiscal year."""

    fiscal_year: int
    stock_price: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
