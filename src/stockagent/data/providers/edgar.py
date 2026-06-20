from __future__ import annotations

import re
from collections.abc import Callable

import pandas as pd
from edgar import Company

from stockagent.data.errors import (
    NoDataError,
    ProviderError,
    ProviderResponseError,
)
from stockagent.financials.models import FinancialRecord

FieldConceptMap = dict[str, tuple[str, ...]]

# FinancialRecord field -> prioritized XBRL concepts.
# Concept names are DataFrame index values and are more stable than labels.
INCOME_FIELD_CONCEPTS: FieldConceptMap = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ),
    "cost_of_sales": (
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
    ),
    "gross_profit": ("GrossProfit",),
    "rd_expense": ("ResearchAndDevelopmentExpense",),
    "sga_expense": ("SellingGeneralAndAdministrativeExpense",),
    "operating_expenses": ("OperatingExpenses",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "eps_basic": ("EarningsPerShareBasic",),
    "eps_diluted": ("EarningsPerShareDiluted",),
}

BALANCE_FIELD_CONCEPTS: FieldConceptMap = {
    "total_assets": ("Assets",),
    "current_assets": ("AssetsCurrent",),
    "cash_and_equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
    "total_liabilities": ("Liabilities",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "long_term_debt": (
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ),
    "shareholders_equity": ("StockholdersEquity",),
}

CASHFLOW_FIELD_CONCEPTS: FieldConceptMap = {
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "dividends_paid": (
        "PaymentsOfDividends",
        "PaymentsOfDividendsCommonStock",
    ),
}


class EdgarFinancialsProvider:
    """Fetch standardized annual financial records from SEC EDGAR."""

    provider_name = "edgar"

    def __init__(self, company_factory: Callable[[str], Company] = Company) -> None:
        self._company_factory = company_factory

    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        try:
            records = self._fetch_annual_records(ticker, years)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderResponseError(
                ticker=ticker,
                provider=self.provider_name,
                detail=str(exc),
            ) from exc

        if not records:
            raise NoDataError(
                ticker=ticker,
                provider=self.provider_name,
                detail="no annual fiscal periods were parsed",
            )
        records.sort(key=lambda record: record.fiscal_year)
        return records

    def _fetch_annual_records(
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

            _fill_from_df(record, income, col, INCOME_FIELD_CONCEPTS)
            _fill_from_df(record, balance, col, BALANCE_FIELD_CONCEPTS)
            _fill_from_df(record, cashflow, col, CASHFLOW_FIELD_CONCEPTS)

            records.append(record)

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
    field_concepts: FieldConceptMap,
) -> None:
    """Fill FinancialRecord fields from a DataFrame using concept index mapping."""
    for field_name, concepts in field_concepts.items():
        if getattr(record, field_name) is not None:
            continue

        value = _first_available_value(df, period_col, concepts)
        if value is not None:
            setattr(record, field_name, value)


def _first_available_value(
    df: pd.DataFrame,
    period_col: str,
    concepts: tuple[str, ...],
) -> float | None:
    if period_col not in df.columns:
        return None

    for concept in concepts:
        if concept not in df.index:
            continue

        value = df.loc[concept, period_col]
        if isinstance(value, pd.Series):
            for item in value:
                parsed = _to_float_or_none(item)
                if parsed is not None:
                    return parsed
            continue

        parsed = _to_float_or_none(value)
        if parsed is not None:
            return parsed

    return None


def _to_float_or_none(value: object) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
