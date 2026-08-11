from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from stockagent.data.errors import MissingFiscalYearsError, NoDataError
from stockagent.financials import (
    AnnualFundamentals,
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
    ValuationMetrics,
)
from stockagent.fundamentals.annual import (
    compute_cash_flow,
    compute_financial_health,
    compute_profitability,
)
from stockagent.fundamentals.growth import compute_growth_series
from stockagent.fundamentals.valuation import compute_valuation


@dataclass(slots=True)
class FundamentalsAnalysis:
    """Deterministic annual fundamentals analysis for one ticker."""

    # 规范化为大写的请求股票代码
    ticker: str
    # 连续财年窗口内、按财年升序排列的标准化原始记录
    records: list[FinancialRecord]
    # 以财年为键的确定性指标，便于工具边界序列化和查询
    profitability: dict[int, ProfitabilityMetrics]
    # 以财年为键的自由现金流指标
    cash_flow: dict[int, CashFlowMetrics]
    # 以财年为键的杠杆、流动性和现金偿债指标
    financial_health: dict[int, FinancialHealthMetrics]
    # 以财年为键的同比增速和相对窗口首年的 CAGR
    growth: dict[int, GrowthMetrics]
    # 同一财年事实与指标已对齐、按财年升序排列的不可变窗口
    annual_fundamentals: tuple[AnnualFundamentals, ...] = ()


def fetch_financials(ticker: str, years: int = 3) -> tuple[FinancialRecord, ...]:
    """Fetch a complete, ascending annual financial-record window from EDGAR."""
    _validate_years(years)
    # 将请求 ticker 转为大写，并以它作为缓存键和 EDGAR 查询参数
    normalized_ticker = ticker.upper()
    records = _fetch_financials_cached(normalized_ticker, years)
    return _complete_fiscal_year_window(normalized_ticker, records, years)


@lru_cache(maxsize=32)
def _fetch_financials_cached(
    normalized_ticker: str,
    years: int = 3,
) -> tuple[FinancialRecord, ...]:
    """Fetch one normalized ticker window through the process-local provider cache."""
    from stockagent.data.providers import EdgarFinancialsProvider

    provider = EdgarFinancialsProvider()
    records = provider.fetch_annual_records(normalized_ticker, years=years)
    if not records:
        raise NoDataError(
            ticker=normalized_ticker,
            provider="edgar",
            detail="provider returned no annual records",
        )
    return tuple(records)


def _validate_years(years: object) -> None:
    """Reject values that cannot express a positive count of fiscal years."""
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ValueError("years must be a positive integer")


def _complete_fiscal_year_window(
    ticker: str,
    records: tuple[FinancialRecord, ...],
    years: int,
) -> tuple[FinancialRecord, ...]:
    """Return an unbroken ascending annual window or raise its missing years."""
    # 从最新财年向前生成 years 个目标年份，并检查每个年份都有一条记录
    records_by_year = {record.fiscal_year: record for record in records}
    latest_year = max(records_by_year)
    target_years = range(latest_year - years + 1, latest_year + 1)
    missing_fiscal_years = tuple(
        fiscal_year
        for fiscal_year in target_years
        if fiscal_year not in records_by_year
    )
    if missing_fiscal_years:
        raise MissingFiscalYearsError(ticker, missing_fiscal_years)

    return tuple(
        replace(records_by_year[fiscal_year], ticker=ticker)
        for fiscal_year in target_years
    )


def analyze_profitability(
    records: tuple[FinancialRecord, ...],
) -> dict[int, ProfitabilityMetrics]:
    """Compute profitability metrics indexed by fiscal year."""
    return {record.fiscal_year: compute_profitability(record) for record in records}


def analyze_growth(records: tuple[FinancialRecord, ...]) -> dict[int, GrowthMetrics]:
    """Compute growth metrics indexed by fiscal year."""
    # 成长性跨年计算，须整窗传入；其余三类逐年独立
    return {
        metrics.fiscal_year: metrics
        for metrics in compute_growth_series(list(records))
    }


def analyze_cash_flow(
    records: tuple[FinancialRecord, ...],
) -> dict[int, CashFlowMetrics]:
    """Compute cash-flow metrics indexed by fiscal year."""
    return {record.fiscal_year: compute_cash_flow(record) for record in records}


def analyze_financial_health(
    records: tuple[FinancialRecord, ...],
) -> dict[int, FinancialHealthMetrics]:
    """Compute financial-health metrics indexed by fiscal year."""
    return {record.fiscal_year: compute_financial_health(record) for record in records}


def analyze_valuation(
    records: tuple[FinancialRecord, ...],
    price: float | None = None,
    market_cap: float | None = None,
) -> ValuationMetrics:
    """Compute trailing valuation metrics from the latest fiscal year."""
    # 选择 records 中 fiscal_year 最大的记录，连同市场输入直接喂给估值公式
    latest = max(records, key=lambda record: record.fiscal_year)
    return compute_valuation(latest, price, market_cap)


def analyze_fundamentals(ticker: str, years: int = 3) -> FundamentalsAnalysis:
    """Fetch records and compute the complete deterministic fundamentals analysis."""
    records = fetch_financials(ticker, years)
    profitability = analyze_profitability(records)
    cash_flow = analyze_cash_flow(records)
    financial_health = analyze_financial_health(records)
    growth = analyze_growth(records)
    annual_fundamentals = tuple(
        AnnualFundamentals(
            record=record,
            profitability=profitability[record.fiscal_year],
            cash_flow=cash_flow[record.fiscal_year],
            financial_health=financial_health[record.fiscal_year],
            growth=growth[record.fiscal_year],
        )
        for record in records
    )
    return FundamentalsAnalysis(
        ticker=ticker.upper(),
        records=list(records),
        profitability=profitability,
        cash_flow=cash_flow,
        financial_health=financial_health,
        growth=growth,
        annual_fundamentals=annual_fundamentals,
    )
