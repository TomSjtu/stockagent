from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from stockagent.financials import SecFilingReference


@dataclass(frozen=True, slots=True)
class AnnualFinancialSnapshot:
    """The annual facts rendered for one fiscal year in a research report."""

    # 财务数据所属的完整财年
    fiscal_year: int
    # 年度收入，沿用来源金额单位
    revenue: float | None = None
    # 归属于公司股东的年度净利润，沿用来源金额单位
    net_income: float | None = None
    # 年度经营活动产生的现金流，沿用来源金额单位
    operating_cash_flow: float | None = None
    # 正数表示的年度资本开支额，沿用来源金额单位
    capex: float | None = None
    # 年度经营现金流减资本开支额，沿用来源金额单位
    free_cash_flow: float | None = None
    # 毛利除以收入，以小数形式存储
    gross_margin: float | None = None
    # 净利润除以收入，以小数形式存储
    net_margin: float | None = None
    # 相对上一财年的收入增速，以小数形式存储
    revenue_growth: float | None = None


@dataclass(frozen=True, slots=True)
class ReportContent:
    """The complete, validated input required to compose one research report."""

    # 报告覆盖的股票代码，输出标题时统一转换为大写
    ticker: str
    # 报告的生成日期
    report_date: date
    # 汇总模型生成的摘要 Markdown 正文
    summary: str
    # 行业分析 Agent 生成的 Markdown 正文
    industry_analysis: str
    # 基本面分析 Agent 生成的 Markdown 正文
    fundamentals_analysis: str
    # 估值分析 Agent 生成的 Markdown 正文
    valuation_analysis: str
    # 风险分析 Agent 生成的 Markdown 正文
    risk_assessment: str
    # 汇总模型生成的投资建议 Markdown 正文
    investment_recommendation: str
    # 请求范围内按财年提供的确定性财务事实
    annual_financials: Sequence[AnnualFinancialSnapshot]
    # 用于生成年度 SEC 证据标记的 filing 元数据
    financial_filings: Sequence[SecFilingReference]


class ReportComposer:
    """Compose the fixed Markdown structure for a research report."""

    def compose(self, content: ReportContent) -> str:
        """Render report content while preserving internal evidence markers."""
        financial_snapshot = self._render_financial_snapshot(
            content.annual_financials,
            content.financial_filings,
        )
        # 固定报告章节
        sections = [
            f"# {content.ticker.upper()} 研究报告\n\n报告日期：{content.report_date.isoformat()}",
            self._section("摘要", content.summary),
            self._section("行业分析", content.industry_analysis),
            self._section("财务数据快照", financial_snapshot),
            self._section("基本面分析", content.fundamentals_analysis),
            self._section("估值分析", content.valuation_analysis),
            self._section("风险评估", content.risk_assessment),
            self._section("投资建议", content.investment_recommendation),
            self._section(
                "数据口径",
                "财务数据覆盖请求的完整财年 10-K/10-K/A，未纳入最新 10-Q 与 TTM；"
                "金额单位为百万美元。",
            ),
            self._section("免责声明", "本报告仅用于研究和学习，不构成投资建议。"),
        ]
        return "\n\n".join(sections) + "\n"

    def _render_financial_snapshot(
        self,
        annual_financials: Sequence[AnnualFinancialSnapshot],
        financial_filings: Sequence[SecFilingReference],
    ) -> str:
        # 输入顺序不构成交付契约，始终按财年升序展示
        snapshots = sorted(annual_financials, key=lambda snapshot: snapshot.fiscal_year)
        # filing 仅用于生成 SEC 内部证据标记；实际脚注由后续引用渲染负责
        filings_by_year = {
            filing.fiscal_year: filing for filing in financial_filings
        }
        if not snapshots:
            return "暂无可用年度财务数据。"

        table = [
            self._table_row(
                ["指标", *[self._column_header(snapshot, filings_by_year) for snapshot in snapshots]]
            ),
            self._table_row(["---", *["---" for _snapshot in snapshots]]),
        ]
        # 在一处声明指标名称、快照字段和单位格式，确保每列使用一致口径
        rows: tuple[tuple[str, str, Callable[[float | None], str]], ...] = (
            ("收入", "revenue", self._format_amount),
            ("净利润", "net_income", self._format_amount),
            ("经营现金流", "operating_cash_flow", self._format_amount),
            ("资本开支（支出）", "capex", self._format_amount),
            ("自由现金流", "free_cash_flow", self._format_amount),
            ("毛利率", "gross_margin", self._format_percent),
            ("净利率", "net_margin", self._format_percent),
            ("收入同比增速", "revenue_growth", self._format_percent),
        )
        for label, attribute, formatter in rows:
            table.append(
                self._table_row(
                    [
                        label,
                        *[
                            formatter(getattr(snapshot, attribute))
                            for snapshot in snapshots
                        ],
                    ]
                )
            )

        # 缺少单年 filing 不应丢弃可用财务数据，改为显式暴露数据质量问题
        unavailable_years = [
            snapshot.fiscal_year
            for snapshot in snapshots
            if snapshot.fiscal_year not in filings_by_year
        ]
        if unavailable_years:
            years = "、".join(str(year) for year in unavailable_years)
            table.append(
                f"> 数据质量提示：{years} 财年的 10-K 链接暂不可用。"
            )
        return "\n".join(table)

    @staticmethod
    def _section(title: str, body: str) -> str:
        return f"## {title}\n\n{body.strip()}"

    @staticmethod
    def _column_header(
        snapshot: AnnualFinancialSnapshot,
        filings_by_year: dict[int, SecFilingReference],
    ) -> str:
        if snapshot.fiscal_year in filings_by_year:
            # 此标记会在引用渲染阶段替换为对应 10-K 或 10-K/A 的脚注
            return f"{snapshot.fiscal_year} [sec-{snapshot.fiscal_year}]"
        return f"{snapshot.fiscal_year}（10-K 链接暂不可用）"

    @staticmethod
    def _table_row(cells: Sequence[str]) -> str:
        return f"| {' | '.join(cells)} |"

    @staticmethod
    def _format_amount(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value / 1_000_000:,.1f}"

    @staticmethod
    def _format_percent(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value * 100:,.1f}%"
