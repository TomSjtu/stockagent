from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Protocol, TypeVar

from stockagent.config import DEFAULT_EDGAR_IDENTITY
from stockagent.data.errors import MissingFiscalYearsError, NoDataError
from stockagent.financials import (
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
    ValuationMetrics,
)
from stockagent.fundamentals import (
    build_cash_flow_inputs,
    build_financial_health_inputs,
    build_growth_inputs,
    build_profitability_inputs,
    build_valuation_input,
    compute_cash_flow_series,
    compute_financial_health_series,
    compute_growth_series,
    compute_profitability_series,
)
from stockagent.fundamentals import (
    compute_valuation as compute_valuation_from_input,
)

MetricT = TypeVar("MetricT", bound="HasFiscalYear")


class HasFiscalYear(Protocol):
    fiscal_year: int


@dataclass(slots=True)
class AnalysisResult:
    ticker: str
    records: list[FinancialRecord]
    profitability: dict[int, ProfitabilityMetrics]
    cash_flow: dict[int, CashFlowMetrics]
    financial_health: dict[int, FinancialHealthMetrics]
    growth: dict[int, GrowthMetrics]


def fetch_financials(ticker: str, years: int = 3) -> tuple[FinancialRecord, ...]:
    """Fetch a complete, ascending annual financial-record window from EDGAR."""
    _validate_years(years)
    normalized_ticker = ticker.upper()
    records = _fetch_financials_cached(normalized_ticker, years)
    return _complete_fiscal_year_window(normalized_ticker, records, years)


@lru_cache(maxsize=32)
def _fetch_financials_cached(
    normalized_ticker: str,
    years: int = 3,
) -> tuple[FinancialRecord, ...]:
    from edgar import set_identity

    from stockagent.data.providers import EdgarFinancialsProvider

    set_identity(DEFAULT_EDGAR_IDENTITY)

    provider = EdgarFinancialsProvider()
    records = provider.fetch_annual_records(normalized_ticker, years=years)
    if not records:
        raise NoDataError(
            ticker=normalized_ticker,
            provider="edgar",
            detail="provider returned no annual records",
        )
    return tuple(records)


def _validate_years(years: object) -> None:
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ValueError("years must be a positive integer")


def _complete_fiscal_year_window(
    ticker: str,
    records: tuple[FinancialRecord, ...],
    years: int,
) -> tuple[FinancialRecord, ...]:
    records_by_year = {record.fiscal_year: record for record in records}
    latest_year = max(records_by_year)
    target_years = range(latest_year - years + 1, latest_year + 1)
    missing_fiscal_years = tuple(
        fiscal_year
        for fiscal_year in target_years
        if fiscal_year not in records_by_year
    )
    if missing_fiscal_years:
        raise MissingFiscalYearsError(ticker, missing_fiscal_years)

    return tuple(
        replace(records_by_year[fiscal_year], ticker=ticker)
        for fiscal_year in target_years
    )


def compute_profitability(
    records: tuple[FinancialRecord, ...],
) -> dict[int, ProfitabilityMetrics]:
    """Compute profitability metrics indexed by fiscal year."""
    return _index_by_year(
        compute_profitability_series(build_profitability_inputs(list(records)))
    )


def compute_growth(records: tuple[FinancialRecord, ...]) -> dict[int, GrowthMetrics]:
    """Compute growth metrics indexed by fiscal year."""
    return _index_by_year(compute_growth_series(build_growth_inputs(list(records))))


def compute_cash_flow(
    records: tuple[FinancialRecord, ...],
) -> dict[int, CashFlowMetrics]:
    """Compute cash-flow metrics indexed by fiscal year."""
    return _index_by_year(
        compute_cash_flow_series(build_cash_flow_inputs(list(records)))
    )


def compute_financial_health(
    records: tuple[FinancialRecord, ...],
) -> dict[int, FinancialHealthMetrics]:
    """Compute financial-health metrics indexed by fiscal year."""
    return _index_by_year(
        compute_financial_health_series(build_financial_health_inputs(list(records)))
    )


def compute_valuation(
    records: tuple[FinancialRecord, ...],
    price: float | None = None,
    market_cap: float | None = None,
) -> ValuationMetrics:
    """Compute trailing valuation metrics from the latest fiscal year."""
    latest = max(records, key=lambda record: record.fiscal_year)
    valuation_input = build_valuation_input(latest, price, market_cap)
    return compute_valuation_from_input(valuation_input)


def analyze(ticker: str, years: int = 3) -> AnalysisResult:
    """Fetch records and compute the complete deterministic analysis."""
    records = fetch_financials(ticker, years)
    return AnalysisResult(
        ticker=ticker.upper(),
        records=list(records),
        profitability=compute_profitability(records),
        cash_flow=compute_cash_flow(records),
        financial_health=compute_financial_health(records),
        growth=compute_growth(records),
    )


def _index_by_year(metrics: list[MetricT]) -> dict[int, MetricT]:
    return {item.fiscal_year: item for item in metrics}
