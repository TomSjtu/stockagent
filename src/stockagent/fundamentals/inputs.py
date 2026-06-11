from __future__ import annotations

from dataclasses import dataclass

from stockagent.financials.models import FinancialRecord


@dataclass(slots=True, frozen=True)
class CashFlowInput:
    """Minimum fields needed to compute cash flow metrics."""

    fiscal_year: int
    operating_cash_flow: float | None
    capex: float | None

    @classmethod
    def from_record(cls, record: FinancialRecord) -> "CashFlowInput":
        return cls(
            fiscal_year=record.fiscal_year,
            operating_cash_flow=record.operating_cash_flow,
            capex=record.capex,
        )


@dataclass(slots=True, frozen=True)
class ProfitabilityInput:
    """Minimum fields needed to compute profitability metrics."""

    fiscal_year: int
    revenue: float | None
    gross_profit: float | None
    operating_income: float | None
    net_income: float | None
    rd_expense: float | None
    sga_expense: float | None
    total_assets: float | None
    current_liabilities: float | None
    shareholders_equity: float | None

    @classmethod
    def from_record(cls, record: FinancialRecord) -> "ProfitabilityInput":
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


def build_profitability_inputs(
    records: list[FinancialRecord],
) -> list[ProfitabilityInput]:
    return [ProfitabilityInput.from_record(record) for record in records]


def build_cash_flow_inputs(
    records: list[FinancialRecord],
) -> list[CashFlowInput]:
    return [CashFlowInput.from_record(record) for record in records]
