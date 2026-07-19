from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel

from stockagent.agents.state import ValuationOutput
from stockagent.tools import (
    compute_valuation_metrics,
    web_search,
)

VALUATION_PROMPT = (
    "你是一名估值分析师。用户消息会提供目标公司、财年范围、行业分析和基本面分析。"
    "使用 web_search 搜索当前股价、市值、同行估值及可靠来源，然后调用 "
    "compute_valuation_metrics 计算确定性估值指标。\n\n"
    "分析必须覆盖：\n"
    "1. 当前估值水平，包括 PE、PB、PS\n"
    "2. 同行对比，并说明同行数据来源\n"
    "3. 高估、低估或合理的判断\n"
    "4. 股价和市值的来源、日期、单位及数据限制\n"
    "5. 工具返回的不可用指标及原因\n\n"
    "以 ValuationOutput 返回中文分析和估值字段；不得自行重新计算 PE、PB、PS。"
)


def build_valuation_agent(model: BaseChatModel):
    return create_agent(
        model=model,
        tools=[web_search, compute_valuation_metrics],
        system_prompt=VALUATION_PROMPT,
        response_format=ToolStrategy(ValuationOutput, handle_errors=False),
    )
