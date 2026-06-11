from __future__ import annotations

import re
from collections.abc import Callable

import pandas as pd
from edgar import Company

from stockagent.financials.models import FinancialRecord

# XBRL concept -> FinancialRecord field.
# Concept names are DataFrame index values and are more stable than labels.
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


class EdgarFinancialsProvider:
    """Fetch standardized annual financial records from SEC EDGAR."""

    def __init__(self, company_factory: Callable[[str], Company] = Company) -> None:
        self._company_factory = company_factory

    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        company = self._company_factory(ticker)
        company_name = company.get_ticker()

        income = company.income_statement(period="annual", periods=years, as_dataframe=True)
        balance = company.balance_sheet(period="annual", periods=years, as_dataframe=True)
        cashflow = company.cashflow_statement(period="annual", periods=years, as_dataframe=True)

        records = []
        for col in _get_period_columns(income):
            fiscal_year = _parse_fiscal_year(col)
            if fiscal_year is None:
                continue

            record = FinancialRecord(
                ticker=ticker,
                company_name=company_name,
                fiscal_year=fiscal_year,
            )

            _fill_from_df(record, income, col, INCOME_CONCEPTS)
            _fill_from_df(record, balance, col, BALANCE_CONCEPTS)
            _fill_from_df(record, cashflow, col, CASHFLOW_CONCEPTS)

            records.append(record)

        records.sort(key=lambda record: record.fiscal_year)
        return records


def _get_period_columns(df: pd.DataFrame) -> list[str]:
    """Extract period column names like 'FY 2025', 'FY 2024'."""
    return [col for col in df.columns if re.match(r"FY \d{4}", col)]


def _parse_fiscal_year(col: str) -> int | None:
    """Parse a fiscal year from a period column like 'FY 2025'."""
    match = re.search(r"\d{4}", col)
    return int(match.group()) if match else None


def _fill_from_df(
    record: FinancialRecord,
    df: pd.DataFrame,
    period_col: str,
    concept_map: dict[str, str],
) -> None:
    """Fill FinancialRecord fields from a DataFrame using concept index mapping."""
    for concept, field_name in concept_map.items():
        if concept not in df.index:
            continue
        if getattr(record, field_name) is not None:
            continue
        value = df.at[concept, period_col]
        if pd.notna(value):
            setattr(record, field_name, float(value))
