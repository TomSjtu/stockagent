from __future__ import annotations

from stockagent.tools.financials import (
    compute_cash_flow_metrics,
    compute_financial_health_metrics,
    compute_growth_metrics,
    compute_profitability_metrics,
    fetch_company_financials,
)

fundamentals_subagent = {
    "name": "fundamentals_analyst",
    "description": "Analyze profitability, cash flow, financial health, and growth.",
    "system_prompt": (
        "你是一名专业财务分析师。使用财务工具获取数据并计算指标，"
        "然后输出中文基本面分析。\n\n"
        "分析必须覆盖：\n"
        "1. 盈利能力趋势，包括毛利率、净利率、ROE、ROA 和 ROCE\n"
        "2. 现金流质量，包括自由现金流和经营现金流与净利润的匹配度\n"
        "3. 财务健康，包括负债水平、流动性和偿债能力\n"
        "4. 成长性，包括收入、净利润、自由现金流增速和 CAGR\n\n"
        "不要只罗列数据，要解释趋势和含义。"
        "完成后使用 write_file 写入 fundamentals_analysis.md。"
    ),
    "tools": [
        fetch_company_financials,
        compute_profitability_metrics,
        compute_growth_metrics,
        compute_cash_flow_metrics,
        compute_financial_health_metrics,
    ],
}
