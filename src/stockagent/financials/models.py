from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel


class SecFilingReference(BaseModel):
    """Metadata needed to link annual financial data to its SEC filing."""

    # 实际采用的 SEC 年度申报表类型
    form: Literal["10-K", "10-K/A"]
    # 该 filing 对应的公司财年标签
    fiscal_year: int
    # 该 filing 覆盖的财年截止日
    period_end: date
    # 向 SEC 提交该 filing 的日期
    filed_at: date
    # SEC 为申报主体分配的唯一 CIK
    cik: str
    # SEC 为本次具体申报分配的 accession number
    accession_number: str
    # filing 目录中主 HTML 文档的文件名
    primary_document: str
    # SEC Archive 中主 HTML 文档的完整链接
    url: str


@dataclass(frozen=True, slots=True)
class AnnualFinancialSnapshot:
    """A cross-cutting projection of raw annual fields and derived metrics."""

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


@dataclass(slots=True)
class FinancialRecord:
    """Standardized annual financial data for one company fiscal year."""

    # 该年度记录所属公司的股票代码
    ticker: str
    # EDGAR 公司对象返回的公司名称
    company_name: str
    # 该记录对应的公司财年标签，例如 2024
    fiscal_year: int

    # 以下损益表字段保存 EDGAR 对应 FY 列的金额；None 表示该字段没有可解析的来源值
    # 公司主营业务产生的年度收入
    revenue: float | None = None
    # 与销售直接相关的年度成本
    cost_of_sales: float | None = None
    # 收入减销售成本后的年度毛利
    gross_profit: float | None = None
    # 研发费用，用于研发强度比率
    rd_expense: float | None = None
    # 销售、一般及管理费用，用于期间费用强度比率
    sga_expense: float | None = None
    # 年度经营费用总额
    operating_expenses: float | None = None
    # 年度营业利润
    operating_income: float | None = None
    # 归属于公司股东的年度净利润
    net_income: float | None = None
    # 基本每股收益；不与金额字段共用单位
    eps_basic: float | None = None
    # 稀释后每股收益，是价格法 PE 的优先分母
    eps_diluted: float | None = None

    # 以下资产负债表字段保存该财年末时点金额；None 表示来源中没有可解析值
    # 财年末资产总额
    total_assets: float | None = None
    # 财年末一年内可变现或耗用的资产
    current_assets: float | None = None
    # 财年末现金及现金等价物
    cash_and_equivalents: float | None = None
    # 财年末负债总额
    total_liabilities: float | None = None
    # 财年末一年内到期或结算的负债
    current_liabilities: float | None = None
    # 财年末长期债务
    long_term_debt: float | None = None
    # 财年末股东权益
    shareholders_equity: float | None = None

    # 以下现金流字段保存该财年期间金额；资本开支与股利的符号保持 EDGAR 来源值
    # 经营活动产生的年度现金流
    operating_cash_flow: float | None = None
    # 资本性支出，计算自由现金流时按来源符号相减
    capex: float | None = None
    # 支付股利的年度现金流，保留来源符号
    dividends_paid: float | None = None

    # 该财年关联的 SEC filing 元数据；无法解析 filing 时为 None
    filing: SecFilingReference | None = None


@dataclass(slots=True)
class ProfitabilityMetrics:
    """Computed profitability ratios for one fiscal year."""

    # 与输入记录一致的财年标签
    fiscal_year: int
    # 毛利除以收入；所有比率均为小数而非百分数，None 表示缺少输入或无法安全计算
    gross_margin: float | None = None
    # 营业利润除以收入
    operating_margin: float | None = None
    # 净利润除以收入
    net_margin: float | None = None
    # 净利润除以总资产
    roa: float | None = None
    # 净利润除以股东权益
    roe: float | None = None
    # 营业利润除以资本占用额（总资产减流动负债）
    roce: float | None = None
    # 研发费用除以收入
    rd_ratio: float | None = None
    # 销售、一般及管理费用除以收入
    sga_ratio: float | None = None


@dataclass(slots=True)
class CashFlowMetrics:
    """Computed cash flow metrics for one fiscal year."""

    # 与输入记录一致的财年标签
    fiscal_year: int
    # 经营现金流减资本开支，沿用输入金额单位；任一输入缺失时为 None
    free_cash_flow: float | None = None


@dataclass(slots=True)
class FinancialHealthMetrics:
    """Computed financial health ratios for one fiscal year."""

    # 与输入记录一致的财年标签
    fiscal_year: int
    # 股东权益除以总资产；所有比率均为小数而非百分数，None 表示缺少输入或分母为零
    equity_ratio: float | None = None
    # 总负债除以总资产
    liabilities_to_assets: float | None = None
    # 流动资产除以流动负债
    current_ratio: float | None = None
    # 现金及等价物除以流动负债
    cash_ratio: float | None = None
    # 经营现金流除以总负债，衡量以经营现金偿债的能力
    operating_cash_flow_to_total_liabilities: float | None = None


@dataclass(slots=True)
class GrowthMetrics:
    """Computed growth metrics for one fiscal year."""

    # 与输入记录一致的财年标签
    fiscal_year: int
    # 相对上一财年的收入增速；增速与 CAGR 均为小数，首年、非连续期或不满足公式前提时为 None
    revenue_growth: float | None = None
    # 相对上一财年的净利润增速
    net_income_growth: float | None = None
    # 相对上一财年的自由现金流增速
    free_cash_flow_growth: float | None = None
    # 相对窗口首年的收入复合年增长率
    revenue_cagr: float | None = None
    # 相对窗口首年的净利润复合年增长率
    net_income_cagr: float | None = None
    # 相对窗口首年的自由现金流复合年增长率
    free_cash_flow_cagr: float | None = None


@dataclass(slots=True)
class ValuationMetrics:
    """Computed valuation ratios for one fiscal year."""

    # 估值使用的最新财年标签
    fiscal_year: int
    # 市场输入保留原始数值与来源口径；None 表示工具没有得到可用输入
    stock_price: float | None = None
    # 与股价同一市场时点的总市值
    market_cap: float | None = None
    # 优先使用价格/稀释 EPS，否则使用市值/净利润的市盈率
    pe_ratio: float | None = None
    # 市值除以股东权益的市净率
    pb_ratio: float | None = None
    # 市值除以收入的市销率
    ps_ratio: float | None = None
