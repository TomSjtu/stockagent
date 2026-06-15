from __future__ import annotations

from stockagent.app import AnalysisResult
from stockagent.config import ReportFormat


def build_report(result: AnalysisResult, report_format: ReportFormat) -> str:
    if report_format == "text":
        return build_text_report(result)
    if report_format == "md":
        raise NotImplementedError("Markdown report is not implemented yet.")
    if report_format == "html":
        raise NotImplementedError("HTML report is not implemented yet.")
    if report_format == "pdf":
        raise NotImplementedError("PDF report is not implemented yet.")
    raise ValueError(f"Unsupported report format: {report_format}")


def build_text_report(result: AnalysisResult) -> str:
    lines: list[str] = [f"Ticker: {result.ticker}"]

    for record in result.records:
        lines.append(f"\n=== FY {record.fiscal_year} ===")
        lines.append(f"  Revenue:        {_format_number(record.revenue)}")
        lines.append(f"  Net Income:     {_format_number(record.net_income)}")
        lines.append(f"  Gross Profit:   {_format_number(record.gross_profit)}")
        lines.append(f"  Total Assets:   {_format_number(record.total_assets)}")
        lines.append(f"  Total Liab:     {_format_number(record.total_liabilities)}")
        lines.append(f"  Equity:         {_format_number(record.shareholders_equity)}")
        lines.append(f"  Op Cash Flow:   {_format_number(record.operating_cash_flow)}")
        lines.append(f"  EPS Basic:      {record.eps_basic if record.eps_basic is not None else 'None'}")

        cash_flow = result.cash_flow.get(record.fiscal_year)
        lines.append("  Cash Flow:")
        lines.append(
            "    FCF:          "
            f"{_format_number(cash_flow.free_cash_flow) if cash_flow else 'None'}"
        )

        profitability = result.profitability.get(record.fiscal_year)
        lines.append("  Profitability:")
        lines.append(
            "    Gross Margin: "
            f"{_format_ratio(profitability.gross_margin) if profitability else 'None'}"
        )
        lines.append(
            "    Operating Margin: "
            f"{_format_ratio(profitability.operating_margin) if profitability else 'None'}"
        )
        lines.append(
            "    Net Margin:   "
            f"{_format_ratio(profitability.net_margin) if profitability else 'None'}"
        )
        lines.append(
            "    ROA:          "
            f"{_format_ratio(profitability.roa) if profitability else 'None'}"
        )
        lines.append(
            "    ROE:          "
            f"{_format_ratio(profitability.roe) if profitability else 'None'}"
        )
        lines.append(
            "    ROCE:         "
            f"{_format_ratio(profitability.roce) if profitability else 'None'}"
        )

        financial_health = result.financial_health.get(record.fiscal_year)
        lines.append("  Financial Health:")
        lines.append(
            "    Equity Ratio: "
            f"{_format_ratio(financial_health.equity_ratio) if financial_health else 'None'}"
        )
        lines.append(
            "    Liab/Assets:  "
            f"{_format_ratio(financial_health.liabilities_to_assets) if financial_health else 'None'}"
        )
        lines.append(
            "    Current Ratio:"
            f"{_format_multiple(financial_health.current_ratio) if financial_health else 'None'}"
        )
        lines.append(
            "    Cash Ratio:   "
            f"{_format_multiple(financial_health.cash_ratio) if financial_health else 'None'}"
        )
        lines.append(
            "    CFO/Liab:     "
            f"{_format_ratio(financial_health.operating_cash_flow_to_total_liabilities) if financial_health else 'None'}"
        )

        growth = result.growth.get(record.fiscal_year)
        lines.append("  Growth:")
        lines.append(
            "    Revenue YoY:  "
            f"{_format_ratio(growth.revenue_growth) if growth else 'None'}"
        )
        lines.append(
            "    Net Inc YoY:  "
            f"{_format_ratio(growth.net_income_growth) if growth else 'None'}"
        )
        lines.append(
            "    FCF YoY:      "
            f"{_format_ratio(growth.free_cash_flow_growth) if growth else 'None'}"
        )
        lines.append(
            "    Revenue CAGR: "
            f"{_format_ratio(growth.revenue_cagr) if growth else 'None'}"
        )
        lines.append(
            "    Net Inc CAGR: "
            f"{_format_ratio(growth.net_income_cagr) if growth else 'None'}"
        )
        lines.append(
            "    FCF CAGR:     "
            f"{_format_ratio(growth.free_cash_flow_cagr) if growth else 'None'}"
        )

    return "\n".join(lines)


def build_markdown_report(result: AnalysisResult) -> str:
    return ""


def build_html_report(result: AnalysisResult) -> str:
    return ""


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
