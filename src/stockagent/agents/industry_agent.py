from __future__ import annotations

from stockagent.tools.search import web_search

industry_subagent = {
    "name": "industry_analyst",
    "description": "Analyze industry trends, competition, and the company's market position.",
    "system_prompt": (
        "你是一名行业研究分析师。使用 web_search 获取目标公司所在行业的最新信息，"
        "行业趋势优先使用 topic='finance'，近期新闻优先使用 topic='news' 和 time_range='month'。"
        "然后输出中文行业分析。\n\n"
        "分析必须覆盖：\n"
        "1. 行业概况与发展趋势\n"
        "2. 竞争格局与主要竞争对手\n"
        "3. 公司市场地位与竞争优势\n"
        "4. 行业驱动因素与潜在挑战\n\n"
        "完成后使用 write_file 写入 industry_analysis.md。"
    ),
    "tools": [web_search],
}
