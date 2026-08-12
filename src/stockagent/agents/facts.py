from __future__ import annotations

from typing import TypedDict as _TypedDict

from stockagent.financials import (
    AnnualFinancialSnapshot as _AnnualFinancialSnapshot,
)
from stockagent.financials import (
    SecFilingReference as _SecFilingReference,
)
from stockagent.fundamentals import analysis as _analysis

__all__ = ["build_fundamentals_facts", "build_valuation_facts"]


class _FundamentalsFacts(_TypedDict):
    annual_financials: list[_AnnualFinancialSnapshot]
    financial_filings: list[_SecFilingReference]


class _ValuationFacts(_TypedDict):
    pe_ratio: float | None
    pb_ratio: float | None
    ps_ratio: float | None


def build_fundamentals_facts(
    ticker: str,
    years: int,
) -> _FundamentalsFacts:
    """Build report-facing fundamentals facts from the typed financial analysis."""
    analysis = _analysis.analyze_fundamentals(ticker, years)
    snapshots: list[_AnnualFinancialSnapshot] = []
    filings: list[_SecFilingReference] = []
    for annual_fundamentals in analysis.annual_fundamentals:
        record = annual_fundamentals.record

        snapshots.append(
            _AnnualFinancialSnapshot(
                fiscal_year=annual_fundamentals.fiscal_year,
                revenue=record.revenue,
                net_income=record.net_income,
                operating_cash_flow=record.operating_cash_flow,
                capex=record.capex,
                free_cash_flow=annual_fundamentals.cash_flow.free_cash_flow,
                gross_margin=annual_fundamentals.profitability.gross_margin,
                net_margin=annual_fundamentals.profitability.net_margin,
                revenue_growth=annual_fundamentals.growth.revenue_growth,
            )
        )
        if record.filing is not None:
            filings.append(record.filing)

    return {
        "annual_financials": snapshots,
        "financial_filings": filings,
    }


def build_valuation_facts(
    ticker: str,
    years: int,
    price: float | None,
    market_cap: float | None,
) -> _ValuationFacts:
    """Build report-facing valuation facts from declared market inputs."""
    analysis = _analysis.analyze_fundamentals(ticker, years)
    valuation = _analysis.analyze_valuation(
        analysis.annual_fundamentals,
        price=price,
        market_cap=market_cap,
    )
    return {
        "pe_ratio": valuation.pe_ratio,
        "pb_ratio": valuation.pb_ratio,
        "ps_ratio": valuation.ps_ratio,
    }
