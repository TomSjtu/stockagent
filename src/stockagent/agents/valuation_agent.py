from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel

from stockagent.agents.state import ValuationAgentOutput
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
    "证据与内部标记规则：仅将实际采用的 web_search 结果放入 evidence，"
    "不得把全部搜索结果当作引用。每项证据需保留原始标题、URL、发布者、发布日期、"
    "裁剪摘要，kind='web'，并以 source_agent='valuation_analyst' 返回；搜索结果未提供"
    "发布者或发布日期时返回 null；ID 使用 valuation-1、"
    "valuation-2 等本次运行内唯一值。在相关外部事实所在段落或表格行使用 "
    "[valuation-1] 这样的内部标记；没有可靠来源时可给出分析，但不得伪造标记或来源。"
    "对实际传入 compute_valuation_metrics 的价格和市值，返回 market_inputs："
    "evidence_id 指向支撑它们的 evidence，currency 和 as_of 仅在来源可见时填写，否则"
    "为 null。\n\n"
    "来源优先级：财务披露和管理层指引优先 SEC 或公司 IR；监管和政策优先政府或监管"
    "机构原文；产品和公司公告优先公司官网；行业与市场观点可使用可信财经媒体。\n\n"
    "以 ValuationAgentOutput 返回中文分析、evidence 和 market_inputs；不得自行"
    "重新计算 PE、PB、PS。"
)


def build_valuation_agent(model: BaseChatModel):
    """Build the valuation agent with sourced market data and deterministic metrics."""
    return create_agent(
        model=model,
        tools=[web_search, compute_valuation_metrics],
        system_prompt=VALUATION_PROMPT,
        response_format=ToolStrategy(ValuationAgentOutput, handle_errors=False),
    )
