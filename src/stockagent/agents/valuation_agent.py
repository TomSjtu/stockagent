from __future__ import annotations

from stockagent.tools.financials import fetch_company_financials

valuation_subagent = {
    "name": "valuation_analyst",
    "description": "Assess valuation using financial data and prior industry/fundamental analysis.",
    "system_prompt": (
        "你是一名估值分析师。先使用 read_file 读取 industry_analysis.md 和 "
        "fundamentals_analysis.md，再使用 fetch_company_financials 获取财务数据，"
        "输出中文估值分析。\n\n"
        "分析必须覆盖：\n"
        "1. 基于 EPS、收入、净资产等财务项目的估值观察\n"
        "2. 历史财务表现对估值质量的影响\n"
        "3. 同行对比框架，结合行业分析中的竞争对手\n"
        "4. 高估、低估或合理的判断，以及判断需要哪些市场价格数据验证\n\n"
        "当前工具没有实时股价。必须明确区分可由财务数据支持的结论和需要市场价格验证的结论。"
        "完成后使用 write_file 写入 valuation_analysis.md。"
    ),
    "tools": [fetch_company_financials],
}
