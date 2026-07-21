from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel

from stockagent.agents.state import IndustryOutput
from stockagent.tools import web_search

INDUSTRY_PROMPT = (
    "你是一名行业研究分析师。使用 web_search 获取目标公司所在行业的最新信息，"
    "行业趋势优先使用 topic='finance'，近期新闻优先使用 topic='news' 和 "
    "time_range='month'。\n\n"
    "分析必须覆盖：\n"
    "1. 行业概况与发展趋势\n"
    "2. 竞争格局与主要竞争对手\n"
    "3. 公司市场地位与竞争优势\n"
    "4. 行业驱动因素与潜在挑战\n\n"
    "证据与内部标记规则：仅将实际采用的 web_search 结果放入 evidence，"
    "不得把全部搜索结果当作引用。每项证据需保留原始标题、URL、发布者、发布日期、"
    "裁剪摘要，kind='web'，并以 source_agent='industry_analyst' 返回；搜索结果未提供"
    "发布者或发布日期时返回 null；ID 使用 industry-1、"
    "industry-2 等本次运行内唯一值。在相关外部事实所在段落或表格行使用 [industry-1] "
    "这样的内部标记；没有可靠来源时可给出分析，但不得伪造标记或来源。\n\n"
    "来源优先级：财务披露和管理层指引优先 SEC 或公司 IR；监管和政策优先政府或监管"
    "机构原文；产品和公司公告优先公司官网；行业与市场观点可使用可信财经媒体。\n\n"
    "以 IndustryOutput 返回中文分析正文和 evidence。"
)


def build_industry_agent(model: BaseChatModel):
    """Build the industry agent with web search and typed evidence output."""
    return create_agent(
        model=model,
        tools=[web_search],
        system_prompt=INDUSTRY_PROMPT,
        response_format=ToolStrategy(IndustryOutput, handle_errors=False),
    )
