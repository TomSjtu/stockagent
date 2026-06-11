from __future__ import annotations

import argparse

from edgar import set_identity

from stockagent.data.providers.edgar import EdgarFinancialsProvider
from stockagent.fundamentals.cash_flow import compute_cash_flow_series
from stockagent.fundamentals.financial_health import compute_financial_health_series
from stockagent.fundamentals.inputs import (
    build_cash_flow_inputs,
    build_financial_health_inputs,
    build_profitability_inputs,
)
from stockagent.fundamentals.profitability import compute_profitability_series


def _format_number(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:>15,.0f}"


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:>15.2%}"


def _format_multiple(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:>15.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    args = parser.parse_args()

    set_identity("Tom stockagent@gmail.com")

    records = EdgarFinancialsProvider().fetch_annual_records(
        args.ticker.upper(),
        years=3,
    )

    cash_flow_series = compute_cash_flow_series(build_cash_flow_inputs(records))
    cash_flow_metrics = {}
    for metrics in cash_flow_series:
        cash_flow_metrics[metrics.fiscal_year] = metrics

    profitability_series = compute_profitability_series(
        build_profitability_inputs(records)
    )
    profitability_metrics = {}
    for metrics in profitability_series:
        profitability_metrics[metrics.fiscal_year] = metrics

    financial_health_series = compute_financial_health_series(
        build_financial_health_inputs(records)
    )
    financial_health_metrics = {}
    for metrics in financial_health_series:
        financial_health_metrics[metrics.fiscal_year] = metrics

    for record in records:
        cash_flow = cash_flow_metrics.get(record.fiscal_year)
        profitability = profitability_metrics.get(record.fiscal_year)
        financial_health = financial_health_metrics.get(record.fiscal_year)
        free_cash_flow = cash_flow.free_cash_flow if cash_flow else None

        print(f"\n=== FY {record.fiscal_year} ===")
        print(f"  Revenue:        {_format_number(record.revenue)}")
        print(f"  Net Income:     {_format_number(record.net_income)}")
        print(f"  Gross Profit:   {_format_number(record.gross_profit)}")
        print(f"  Total Assets:   {_format_number(record.total_assets)}")
        print(f"  Total Liab:     {_format_number(record.total_liabilities)}")
        print(f"  Equity:         {_format_number(record.shareholders_equity)}")
        print(f"  Op Cash Flow:   {_format_number(record.operating_cash_flow)}")
        print(f"  FCF:            {_format_number(free_cash_flow)}")
        print(
            f"  EPS Basic:      "
            f"{record.eps_basic if record.eps_basic is not None else 'None'}"
        )

        print("  Profitability:")
        print(
            "    Gross Margin: "
            f"{_format_ratio(profitability.gross_margin) if profitability else 'None'}"
        )
        print(
            "    Operating Margin: "
            f"{_format_ratio(profitability.operating_margin) if profitability else 'None'}"
        )
        print(
            "    Net Margin:   "
            f"{_format_ratio(profitability.net_margin) if profitability else 'None'}"
        )
        print(
            "    ROA:          "
            f"{_format_ratio(profitability.roa) if profitability else 'None'}"
        )
        print(
            "    ROE:          "
            f"{_format_ratio(profitability.roe) if profitability else 'None'}"
        )
        print(
            "    ROCE:         "
            f"{_format_ratio(profitability.roce) if profitability else 'None'}"
        )

        print("  Financial Health:")
        print(
            "    Equity Ratio: "
            f"{_format_ratio(financial_health.equity_ratio) if financial_health else 'None'}"
        )
        print(
            "    Liab/Assets:  "
            f"{_format_ratio(financial_health.liabilities_to_assets) if financial_health else 'None'}"
        )
        print(
            "    Current Ratio:"
            f"{_format_multiple(financial_health.current_ratio) if financial_health else 'None'}"
        )
        print(
            "    Cash Ratio:   "
            f"{_format_multiple(financial_health.cash_ratio) if financial_health else 'None'}"
        )
        print(
            "    CFO/Liab:     "
            f"{_format_ratio(financial_health.operating_cash_flow_to_total_liabilities) if financial_health else 'None'}"
        )
