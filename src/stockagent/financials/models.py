from __future__ import annotations

from dataclasses import dataclass


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
