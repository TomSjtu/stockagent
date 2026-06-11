from __future__ import annotations

import argparse

from edgar import set_identity

from stockagent.data.providers.edgar import EdgarFinancialsProvider
from stockagent.fundamentals.cash_flow import compute_cash_flow_series
from stockagent.fundamentals.inputs import build_cash_flow_inputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    args = parser.parse_args()

    set_identity("Tom stockagent@gmail.com")

    results = EdgarFinancialsProvider().fetch_annual_records(args.ticker.upper(), years=3)
    cash_flow_metrics = {
        metrics.fiscal_year: metrics
        for metrics in compute_cash_flow_series(build_cash_flow_inputs(results))
    }

    for fi in results:
        cash_flow = cash_flow_metrics.get(fi.fiscal_year)
        free_cash_flow = cash_flow.free_cash_flow if cash_flow else None

        print(f"\n=== FY {fi.fiscal_year} ===")
        print(f"  Revenue:        {fi.revenue:>15,.0f}" if fi.revenue else "  Revenue:        None")
        print(f"  Net Income:     {fi.net_income:>15,.0f}" if fi.net_income else "  Net Income:     None")
        print(f"  Gross Profit:   {fi.gross_profit:>15,.0f}" if fi.gross_profit else "  Gross Profit:   None")
        print(f"  Total Assets:   {fi.total_assets:>15,.0f}" if fi.total_assets else "  Total Assets:   None")
        print(f"  Total Liab:     {fi.total_liabilities:>15,.0f}" if fi.total_liabilities else "  Total Liab:     None")
        print(f"  Equity:         {fi.shareholders_equity:>15,.0f}" if fi.shareholders_equity else "  Equity:         None")
        print(f"  Op Cash Flow:   {fi.operating_cash_flow:>15,.0f}" if fi.operating_cash_flow else "  Op Cash Flow:   None")
        print(f"  FCF:            {free_cash_flow:>15,.0f}" if free_cash_flow else "  FCF:            None")
        print(f"  EPS Basic:      {fi.eps_basic}" if fi.eps_basic else "  EPS Basic:      None")
