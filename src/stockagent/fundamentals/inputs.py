from __future__ import annotations

from dataclasses import dataclass

from stockagent.financials import FinancialRecord


@dataclass(slots=True, frozen=True)
class ProfitabilityInput:
    """Minimum fields needed to compute profitability metrics."""

    # 与输出指标关联的年度标签
    fiscal_year: int
    # 年度收入，是利润率与费用率的共同分母
    revenue: float | None
    # 年度毛利
    gross_profit: float | None
    # 年度营业利润
    operating_income: float | None
    # 年度净利润
    net_income: float | None
    # 年度研发费用
    rd_expense: float | None
    # 年度销售、一般及管理费用
    sga_expense: float | None
    # 财年末总资产
    total_assets: float | None
    # 财年末流动负债，用于资本占用额
    current_liabilities: float | None
    # 财年末股东权益
    shareholders_equity: float | None

    @classmethod
    def from_record(cls, record: FinancialRecord) -> "ProfitabilityInput":
        """Project only the fields required by profitability formulas."""
        return cls(
            fiscal_year=record.fiscal_year,
            revenue=record.revenue,
            gross_profit=record.gross_profit,
            operating_income=record.operating_income,
            net_income=record.net_income,
            rd_expense=record.rd_expense,
            sga_expense=record.sga_expense,
            total_assets=record.total_assets,
            current_liabilities=record.current_liabilities,
            shareholders_equity=record.shareholders_equity,
        )


@dataclass(slots=True, frozen=True)
class FinancialHealthInput:
    """Minimum fields needed to compute financial health metrics."""

    # 与输出指标关联的年度标签
    fiscal_year: int
    # 财年末总资产
    total_assets: float | None
    # 财年末流动资产
    current_assets: float | None
    # 财年末现金及现金等价物
    cash_and_equivalents: float | None
    # 财年末负债总额
    total_liabilities: float | None
    # 财年末流动负债
    current_liabilities: float | None
    # 财年末股东权益
    shareholders_equity: float | None
    # 年度经营现金流
    operating_cash_flow: float | None

    @classmethod
    def from_record(cls, record: FinancialRecord) -> "FinancialHealthInput":
        """Project only the fields required by financial-health formulas."""
        return cls(
            fiscal_year=record.fiscal_year,
            total_assets=record.total_assets,
            current_assets=record.current_assets,
            cash_and_equivalents=record.cash_and_equivalents,
            total_liabilities=record.total_liabilities,
            current_liabilities=record.current_liabilities,
            shareholders_equity=record.shareholders_equity,
            operating_cash_flow=record.operating_cash_flow,
        )


@dataclass(slots=True, frozen=True)
class GrowthInput:
    """Minimum fields needed to compute growth metrics."""

    # 与输出指标关联的年度标签，决定同比与 CAGR 期间长度
    fiscal_year: int
    # 年度收入
    revenue: float | None
    # 年度净利润
    net_income: float | None
    # 年度经营现金流
    operating_cash_flow: float | None
    # 年度资本开支，用于派生自由现金流
    capex: float | None

    @classmethod
    def from_record(cls, record: FinancialRecord) -> "GrowthInput":
        """Project only the fields required by growth formulas."""
        return cls(
            fiscal_year=record.fiscal_year,
            revenue=record.revenue,
            net_income=record.net_income,
            operating_cash_flow=record.operating_cash_flow,
            capex=record.capex,
        )


@dataclass(slots=True, frozen=True)
class ValuationInput:
    """Minimum fields needed to compute valuation metrics."""

    # 作为 trailing 分母的最新财年标签
    fiscal_year: int
    # 实际用于 PE 的市场价格；None 由公式传播为不可用
    price: float | None
    # 实际用于 PB、PS 和备选 PE 的市场总市值
    market_cap: float | None
    # 年度收入
    revenue: float | None
    # 年度净利润
    net_income: float | None
    # 年度稀释后每股收益
    eps_diluted: float | None
    # 财年末股东权益
    shareholders_equity: float | None

    @classmethod
    def from_record(
        cls,
        record: FinancialRecord,
        price: float | None,
        market_cap: float | None,
    ) -> "ValuationInput":
        """Project the latest annual record together with sourced market inputs."""
        return cls(
            fiscal_year=record.fiscal_year,
            price=price,
            market_cap=market_cap,
            revenue=record.revenue,
            net_income=record.net_income,
            eps_diluted=record.eps_diluted,
            shareholders_equity=record.shareholders_equity,
        )


def build_profitability_inputs(
    records: list[FinancialRecord],
) -> list[ProfitabilityInput]:
    """Project an annual record series for profitability formulas."""
    return [ProfitabilityInput.from_record(record) for record in records]


def build_financial_health_inputs(
    records: list[FinancialRecord],
) -> list[FinancialHealthInput]:
    """Project an annual record series for financial-health formulas."""
    return [FinancialHealthInput.from_record(record) for record in records]


def build_growth_inputs(
    records: list[FinancialRecord],
) -> list[GrowthInput]:
    """Project an annual record series for growth formulas."""
    return [GrowthInput.from_record(record) for record in records]


def build_valuation_input(
    record: FinancialRecord,
    price: float | None,
    market_cap: float | None,
) -> ValuationInput:
    """Project the latest annual record and sourced market inputs for valuation."""
    return ValuationInput.from_record(record, price, market_cap)
