from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

from stockagent.config import AppConfig, RuntimeOptions
from stockagent.data.errors import NoDataError
from stockagent.data.providers.base import FinancialsProvider
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

IdentitySetter = Callable[[str], None]


class HasFiscalYear(Protocol):
    fiscal_year: int


MetricT = TypeVar("MetricT", bound=HasFiscalYear)


@dataclass(slots=True)
class AnalysisResult:
    ticker: str
    records: list[FinancialRecord]
    profitability: dict[int, ProfitabilityMetrics]
    cash_flow: dict[int, CashFlowMetrics]
    financial_health: dict[int, FinancialHealthMetrics]
    growth: dict[int, GrowthMetrics]


def run_stock_analysis(
    options: RuntimeOptions,
    config: AppConfig,
    provider: FinancialsProvider | None = None,
    identity_setter: IdentitySetter | None = None,
) -> AnalysisResult:
    if identity_setter is None:
        from edgar import set_identity

        identity_setter = set_identity

    if provider is None:
        from stockagent.data.providers.edgar import EdgarFinancialsProvider

        provider = EdgarFinancialsProvider()

    identity_setter(config.edgar_identity)

    records = provider.fetch_annual_records(
        options.ticker.upper(),
        years=options.years,
    )
    if not records:
        provider_name = provider.__class__.__name__
        raise NoDataError(
            ticker=options.ticker.upper(),
            provider=provider_name,
            detail="provider returned no annual records",
        )

    return AnalysisResult(
        ticker=options.ticker.upper(),
        records=records,
        cash_flow=_index_by_year(
            compute_cash_flow_series(build_cash_flow_inputs(records))
        ),
        profitability=_index_by_year(
            compute_profitability_series(build_profitability_inputs(records))
        ),
        financial_health=_index_by_year(
            compute_financial_health_series(build_financial_health_inputs(records))
        ),
        growth=_index_by_year(
            compute_growth_series(build_growth_inputs(records))
        ),
    )


def _index_by_year(metrics: list[MetricT]) -> dict[int, MetricT]:
    return {item.fiscal_year: item for item in metrics}
