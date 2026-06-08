from __future__ import annotations

import re

import pandas as pd
from edgar import Company

from src.data.schemas import FundamentalInput

# XBRL concept → FundamentalInput field
# Using concept names (DataFrame index) for stable matching across companies.
INCOME_CONCEPTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "Revenues": "revenue",
    "CostOfGoodsAndServicesSold": "cost_of_sales",
    "CostOfRevenue": "cost_of_sales",
    "GrossProfit": "gross_profit",
    "ResearchAndDevelopmentExpense": "rd_expense",
    "SellingGeneralAndAdministrativeExpense": "sga_expense",
    "OperatingExpenses": "operating_expenses",
    "OperatingIncomeLoss": "operating_income",
    "NetIncomeLoss": "net_income",
    "EarningsPerShareBasic": "eps_basic",
    "EarningsPerShareDiluted": "eps_diluted",
}

BALANCE_CONCEPTS = {
    "Assets": "total_assets",
    "AssetsCurrent": "current_assets",
    "CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "Liabilities": "total_liabilities",
    "LiabilitiesCurrent": "current_liabilities",
    "LongTermDebtNoncurrent": "long_term_debt",
    "LongTermDebt": "long_term_debt",
    "StockholdersEquity": "shareholders_equity",
}

CASHFLOW_CONCEPTS = {
    "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capex",
    "PaymentsOfDividends": "dividends_paid",
    "PaymentsOfDividendsCommonStock": "dividends_paid",
}


def collect_fundamentals(ticker: str, years: int = 5) -> list[FundamentalInput]:
    """Collect annual financial data from SEC EDGAR and return sorted by fiscal year."""
    company = Company(ticker)
    company_name = company.get_ticker()

    income = company.income_statement(period="annual", periods=years, as_dataframe=True)
    balance = company.balance_sheet(period="annual", periods=years, as_dataframe=True)
    cashflow = company.cashflow_statement(period="annual", periods=years, as_dataframe=True)

    period_cols = _get_period_columns(income)

    results = []
    for col in period_cols:
        fy = _parse_fiscal_year(col)
        if fy is None:
            continue

        fi = FundamentalInput(ticker=ticker, company_name=company_name, fiscal_year=fy)

        _fill_from_df(fi, income, col, INCOME_CONCEPTS)
        _fill_from_df(fi, balance, col, BALANCE_CONCEPTS)
        _fill_from_df(fi, cashflow, col, CASHFLOW_CONCEPTS)

        if fi.operating_cash_flow is not None and fi.capex is not None:
            fi.free_cash_flow = fi.operating_cash_flow - fi.capex

        results.append(fi)

    results.sort(key=lambda f: f.fiscal_year)
    return results


def _get_period_columns(df: pd.DataFrame) -> list[str]:
    """Extract period column names like 'FY 2025', 'FY 2024'."""
    return [c for c in df.columns if re.match(r"FY \d{4}", c)]


def _parse_fiscal_year(col: str) -> int | None:
    """'FY 2025' → 2025"""
    m = re.search(r"\d{4}", col)
    return int(m.group()) if m else None


def _fill_from_df(
    fi: FundamentalInput,
    df: pd.DataFrame,
    period_col: str,
    concept_map: dict[str, str],
) -> None:
    """Fill FundamentalInput fields from a DataFrame using concept index mapping."""
    for concept, field_name in concept_map.items():
        if concept not in df.index:
            continue
        if getattr(fi, field_name) is not None:
            continue
        val = df.at[concept, period_col]
        if pd.notna(val):
            setattr(fi, field_name, float(val))
