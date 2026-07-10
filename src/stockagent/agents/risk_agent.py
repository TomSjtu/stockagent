from __future__ import annotations

from stockagent.tools import (
    compute_financial_health_metrics,
    fetch_company_financials,
)

risk_subagent = {
    "name": "risk_analyst",
    "description": "Assess financial, operating, industry, and valuation risks.",
    "system_prompt": (
        "你是一名风险评估分析师。先使用 read_file 读取 industry_analysis.md、"
        "fundamentals_analysis.md 和 valuation_analysis.md，再使用财务工具补充风险数据，"
        "输出中文风险评估。\n\n"
        "分析必须覆盖：\n"
        "1. 财务风险，包括负债、流动性、现金流可持续性\n"
        "2. 运营风险，包括盈利波动、业务模式和集中度风险\n"
        "3. 行业风险，包括周期、监管、技术变化和竞争风险\n"
        "4. 估值风险，包括估值下行空间和需要进一步验证的假设\n"
        "5. 综合风险评级：低、中或高，并按重要性排序关键风险\n\n"
        "完成后使用 write_file 写入 risk_analysis.md。"
    ),
    "tools": [fetch_company_financials, compute_financial_health_metrics],
}
