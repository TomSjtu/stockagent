from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping

import pandas as pd
from edgar import Company

from stockagent.data.errors import (
    NoDataError,
    ProviderError,
    ProviderResponseError,
)
from stockagent.data.providers.edgar_filings import (
    AnnualFilingCompany,
    resolve_annual_filings,
)
from stockagent.financials import FinancialRecord, SecFilingReference
from stockagent.observability import get_logger

FieldConceptMap = dict[str, tuple[str, ...]]
AnnualFilingResolver = Callable[
    [AnnualFilingCompany, Collection[int]], Mapping[int, SecFilingReference]
]

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

    def __init__(
        self,
        company_factory: Callable[[str], Company] = Company,
        filing_resolver: AnnualFilingResolver = resolve_annual_filings,
    ) -> None:
        """Create a provider with injectable EDGAR access and filing resolution."""
        self._company_factory = company_factory
        self._filing_resolver = filing_resolver

    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        """Fetch sorted annual records or translate provider failures to domain errors."""
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
        # 按 FinancialRecord.fiscal_year 原地排序后返回 records
        records.sort(key=lambda record: record.fiscal_year)
        return records

    def _fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        """Normalize EDGAR statement tables into the domain annual-record shape."""
        company = self._company_factory(ticker)
        company_name = company.get_ticker()

        income = company.income_statement(period="annual", periods=years, as_dataframe=True)
        balance = company.balance_sheet(period="annual", periods=years, as_dataframe=True)
        cashflow = company.cashflow_statement(period="annual", periods=years, as_dataframe=True)

        # 为 income 表中的每个 FY 列创建一条 FinancialRecord，并收集到 records
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

            # 依次从收入、资产负债和现金流表的同一 FY 列填充 record 字段
            _fill_from_df(record, income, col, INCOME_FIELD_CONCEPTS)
            _fill_from_df(record, balance, col, BALANCE_FIELD_CONCEPTS)
            _fill_from_df(record, cashflow, col, CASHFLOW_FIELD_CONCEPTS)

            records.append(record)

        filings = self._resolve_filings(company, records, ticker)
        for record in records:
            record.filing = filings.get(record.fiscal_year)

        return records

    def _resolve_filings(
        self,
        company: AnnualFilingCompany,
        records: list[FinancialRecord],
        ticker: str,
    ) -> Mapping[int, SecFilingReference]:
        """Resolve filing metadata without discarding usable financial statements."""
        try:
            return self._filing_resolver(
                company,
                {record.fiscal_year for record in records},
            )
        except Exception:
            # filing 解析异常时记录 warning，并返回空映射，使各 record.filing 保持 None
            get_logger(__name__).warning(
                "无法获取 %s 的年度 SEC filing 元数据，报告将保留缺失来源",
                ticker,
                exc_info=True,
            )
            return {}


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
    """Fill a record from ordered EDGAR concept aliases without overwriting data."""
    for field_name, concepts in field_concepts.items():
        # 已有值跳过；否则按 field_concepts 中的概念顺序为该字段查找值
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
    """Return the first parseable value from the configured EDGAR concept order."""
    if period_col not in df.columns:
        return None

    for concept in concepts:
        if concept not in df.index:
            continue

        value = df.loc[concept, period_col]
        # 同一概念有多行时，逐个单元格转换并返回第一个可解析的 float
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
    """Normalize a provider cell while preserving absence as None."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
