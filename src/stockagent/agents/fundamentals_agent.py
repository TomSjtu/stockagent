from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel

from stockagent.agents.state import FundamentalsAgentOutput
from stockagent.tools import get_fundamentals_analysis

FUNDAMENTALS_PROMPT = (
    "你是一名专业财务分析师。调用 get_fundamentals_analysis 获取目标公司的财务记录"
    "及全部确定性指标，然后形成中文基本面分析。\n\n"
    "分析必须覆盖：\n"
    "1. 盈利能力趋势，包括毛利率、净利率、ROE、ROA 和 ROCE\n"
    "2. 现金流质量，包括自由现金流和经营现金流与净利润的匹配度\n"
    "3. 财务健康，包括负债水平、流动性和偿债能力\n"
    "4. 成长性，包括收入、净利润、自由现金流增速和 CAGR\n\n"
    "年度财务数字仅来自工具提供的 SEC 10-K filing；涉及年度财务数据的段落或表格行"
    "使用对应财年的内部标记，例如 [sec-2024]，不得伪造 URL、标题或 filing。\n\n"
    "不要只罗列数据，要解释趋势和含义。以 FundamentalsAgentOutput 返回分析正文和"
    "主要关注点。"
)


def build_fundamentals_agent(model: BaseChatModel):
    """Build the fundamentals agent backed by deterministic financial tools."""
    return create_agent(
        model=model,
        tools=[get_fundamentals_analysis],
        system_prompt=FUNDAMENTALS_PROMPT,
        response_format=ToolStrategy(FundamentalsAgentOutput, handle_errors=False),
    )
