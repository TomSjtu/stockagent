from __future__ import annotations

from stockagent.app import AnalysisResult
from stockagent.config import ReportFormat


def build_report(result: AnalysisResult, report_format: ReportFormat) -> str:
    if report_format == "md":
        return build_markdown_report(result)
    if report_format == "html":
        raise NotImplementedError("HTML report is not implemented yet.")
    if report_format == "pdf":
        raise NotImplementedError("PDF report is not implemented yet.")
    raise ValueError(f"Unsupported report format: {report_format}")


def build_markdown_report(result: AnalysisResult) -> str:
    lines: list[str] = [f"# {result.ticker} Stock Analysis", ""]

    for record in result.records:
        lines.extend(
            [
                f"## FY {record.fiscal_year}",
                "",
                "### Financials",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Revenue | {_format_markdown_number(record.revenue)} |",
                f"| Gross Profit | {_format_markdown_number(record.gross_profit)} |",
                f"| Net Income | {_format_markdown_number(record.net_income)} |",
                f"| Total Assets | {_format_markdown_number(record.total_assets)} |",
                f"| Total Liabilities | {_format_markdown_number(record.total_liabilities)} |",
                f"| Shareholders' Equity | {_format_markdown_number(record.shareholders_equity)} |",
                f"| Operating Cash Flow | {_format_markdown_number(record.operating_cash_flow)} |",
                f"| EPS Basic | {_format_markdown_number(record.eps_basic)} |",
                "",
            ]
        )

        cash_flow = result.cash_flow.get(record.fiscal_year)
        lines.extend(
            [
                "### Cash Flow",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Free Cash Flow | {_format_markdown_number(cash_flow.free_cash_flow if cash_flow else None)} |",
                "",
            ]
        )

        profitability = result.profitability.get(record.fiscal_year)
        lines.extend(
            [
                "### Profitability",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Gross Margin | {_format_markdown_ratio(profitability.gross_margin if profitability else None)} |",
                f"| Operating Margin | {_format_markdown_ratio(profitability.operating_margin if profitability else None)} |",
                f"| Net Margin | {_format_markdown_ratio(profitability.net_margin if profitability else None)} |",
                f"| ROA | {_format_markdown_ratio(profitability.roa if profitability else None)} |",
                f"| ROE | {_format_markdown_ratio(profitability.roe if profitability else None)} |",
                f"| ROCE | {_format_markdown_ratio(profitability.roce if profitability else None)} |",
                "",
            ]
        )

        financial_health = result.financial_health.get(record.fiscal_year)
        lines.extend(
            [
                "### Financial Health",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Equity Ratio | {_format_markdown_ratio(financial_health.equity_ratio if financial_health else None)} |",
                f"| Liabilities / Assets | {_format_markdown_ratio(financial_health.liabilities_to_assets if financial_health else None)} |",
                f"| Current Ratio | {_format_markdown_multiple(financial_health.current_ratio if financial_health else None)} |",
                f"| Cash Ratio | {_format_markdown_multiple(financial_health.cash_ratio if financial_health else None)} |",
                f"| CFO / Liabilities | {_format_markdown_ratio(financial_health.operating_cash_flow_to_total_liabilities if financial_health else None)} |",
                "",
            ]
        )

        growth = result.growth.get(record.fiscal_year)
        lines.extend(
            [
                "### Growth",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Revenue YoY | {_format_markdown_ratio(growth.revenue_growth if growth else None)} |",
                f"| Net Income YoY | {_format_markdown_ratio(growth.net_income_growth if growth else None)} |",
                f"| FCF YoY | {_format_markdown_ratio(growth.free_cash_flow_growth if growth else None)} |",
                f"| Revenue CAGR | {_format_markdown_ratio(growth.revenue_cagr if growth else None)} |",
                f"| Net Income CAGR | {_format_markdown_ratio(growth.net_income_cagr if growth else None)} |",
                f"| FCF CAGR | {_format_markdown_ratio(growth.free_cash_flow_cagr if growth else None)} |",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def build_html_report(result: AnalysisResult) -> str:
    return ""


def _format_markdown_number(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.0f}"


def _format_markdown_ratio(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _format_markdown_multiple(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"
