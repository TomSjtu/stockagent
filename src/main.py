from edgar import set_identity
from edgar import Company

# Use your name and email
set_identity("Tom stockagent@gmail.com")

from data.collector import collect_fundamentals

results = collect_fundamentals("AAPL", years=3)

for fi in results:
    print(f"\n=== FY {fi.fiscal_year} ===")
    print(f"  Revenue:        {fi.revenue:>15,.0f}" if fi.revenue else "  Revenue:        None")
    print(f"  Net Income:     {fi.net_income:>15,.0f}" if fi.net_income else "  Net Income:     None")
    print(f"  Gross Profit:   {fi.gross_profit:>15,.0f}" if fi.gross_profit else "  Gross Profit:   None")
    print(f"  Total Assets:   {fi.total_assets:>15,.0f}" if fi.total_assets else "  Total Assets:   None")
    print(f"  Total Liab:     {fi.total_liabilities:>15,.0f}" if fi.total_liabilities else "  Total Liab:     None")
    print(f"  Equity:         {fi.shareholders_equity:>15,.0f}" if fi.shareholders_equity else "  Equity:         None")
    print(f"  Op Cash Flow:   {fi.operating_cash_flow:>15,.0f}" if fi.operating_cash_flow else "  Op Cash Flow:   None")
    print(f"  FCF:            {fi.free_cash_flow:>15,.0f}" if fi.free_cash_flow else "  FCF:            None")
    print(f"  EPS Basic:      {fi.eps_basic}" if fi.eps_basic else "  EPS Basic:      None")
