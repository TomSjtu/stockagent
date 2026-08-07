from __future__ import annotations

from dataclasses import dataclass

from stockagent.financials import FinancialRecord


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


def build_valuation_input(
    record: FinancialRecord,
    price: float | None,
    market_cap: float | None,
) -> ValuationInput:
    """Project the latest annual record and sourced market inputs for valuation."""
    return ValuationInput.from_record(record, price, market_cap)
