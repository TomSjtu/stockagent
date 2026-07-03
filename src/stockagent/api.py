from __future__ import annotations

from functools import lru_cache

from typing import Protocol, TypeVar

from stockagent.app import AnalysisResult
from stockagent.config import RuntimeOptions, load_app_config
from stockagent.data.errors import NoDataError
from stockagent.financials.models import (
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
)
from stockagent.fundamentals.cash_flow import compute_cash_flow_series
from stockagent.fundamentals.financial_health import compute_financial_health_series
from stockagent.fundamentals.growth import compute_growth_series
from stockagent.fundamentals.inputs import (
    build_cash_flow_inputs,
    build_financial_health_inputs,
    build_growth_inputs,
    build_profitability_inputs,
)
from stockagent.fundamentals.profitability import compute_profitability_series

MetricT = TypeVar("MetricT", bound="HasFiscalYear")


class HasFiscalYear(Protocol):
    fiscal_year: int


def fetch_financials(ticker: str, years: int = 3) -> tuple[FinancialRecord, ...]:
    """Fetch normalized annual financial records from EDGAR."""
    return _fetch_financials_cached(ticker.upper(), years)


@lru_cache(maxsize=32)
def _fetch_financials_cached(
    normalized_ticker: str,
    years: int = 3,
) -> tuple[FinancialRecord, ...]:
    from edgar import set_identity
    from stockagent.data.providers.edgar import EdgarFinancialsProvider

    config = load_app_config()
    set_identity(config.edgar_identity)

    provider = EdgarFinancialsProvider()
    records = provider.fetch_annual_records(normalized_ticker, years=years)
    if not records:
        raise NoDataError(
            ticker=normalized_ticker,
            provider=provider.__class__.__name__,
            detail="provider returned no annual records",
        )
    return tuple(records)


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


def analyze_options(options: RuntimeOptions) -> AnalysisResult:
    """Run the public API from parsed runtime options."""
    return analyze(options.ticker, options.years)


def _index_by_year(metrics: list[MetricT]) -> dict[int, MetricT]:
    return {item.fiscal_year: item for item in metrics}
