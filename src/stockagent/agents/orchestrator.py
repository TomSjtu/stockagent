from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import StateNode
from pydantic import BaseModel, ValidationError

from stockagent.agents.errors import AgentOutputError, classify_llm_error
from stockagent.agents.facts import (
    build_fundamentals_facts,
    build_valuation_facts,
)
from stockagent.agents.fundamentals_agent import build_fundamentals_agent
from stockagent.agents.industry_agent import build_industry_agent
from stockagent.agents.llm import build_model
from stockagent.agents.risk_agent import build_risk_agent
from stockagent.agents.state import (
    AnalysisState,
    FundamentalsAgentOutput,
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    SynthesisOutput,
    ValuationAgentOutput,
    ValuationOutput,
)
from stockagent.agents.subagent_progress import AgentProgressCallbackHandler
from stockagent.agents.valuation_agent import build_valuation_agent
from stockagent.config import LLMConfig
from stockagent.errors import StockAgentError
from stockagent.observability import get_logger
from stockagent.report.delivery import GeneratedReport, deliver_report


@dataclass(frozen=True)
class AnalysisNodes:
    """Concrete LangGraph node callables for one stock-analysis workflow."""

    # 调用行业 Agent 并返回 {"industry": IndustryOutput} 的节点
    industry: StateNode
    # 调用基本面 Agent 并返回 {"fundamentals": FundamentalsOutput} 的节点
    fundamentals: StateNode
    # 调用估值 Agent 并返回 {"valuation": ValuationOutput} 的节点
    valuation: StateNode
    # 调用风险 Agent 并返回 {"risk": RiskOutput} 的节点
    risk: StateNode
    # 汇总上游输出并返回摘要与投资建议叙事片段的节点
    synthesize: StateNode


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


def build_analysis_graph(nodes: AnalysisNodes):
    """Build the fixed dependency graph for one report analysis."""
    graph = StateGraph(AnalysisState)
    graph.add_node("industry", nodes.industry)
    graph.add_node("fundamentals", nodes.fundamentals)
    graph.add_node("valuation", nodes.valuation)
    graph.add_node("risk", nodes.risk)
    graph.add_node("synthesize", nodes.synthesize)

    # 从 START 并行运行行业和基本面节点，再依次写入估值、风险和最终报告
    graph.add_edge(START, "industry")
    graph.add_edge(START, "fundamentals")
    graph.add_edge(["industry", "fundamentals"], "valuation")
    graph.add_edge("valuation", "risk")
    graph.add_edge("risk", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


def build_analysis_nodes(model: BaseChatModel) -> AnalysisNodes:
    """Create the typed node implementations bound to one language model."""
    return AnalysisNodes(
        industry=_build_industry_node(build_industry_agent(model)),
        fundamentals=_build_fundamentals_node(build_fundamentals_agent(model)),
        valuation=_build_valuation_node(build_valuation_agent(model)),
        risk=_build_risk_node(build_risk_agent(model)),
        synthesize=_build_synthesize_node(model),
    )


def _build_industry_node(agent: Any) -> StateNode:
    """Build a node that invokes the industry agent and writes its output to state."""
    def industry(state: AnalysisState) -> dict[str, IndustryOutput]:
        output = _invoke_structured_agent(
            agent,
            agent_name="industry_analyst",
            payload=_agent_payload(
                "请分析 "
                f"{state['ticker'].upper()} 最近 {state['years']} 个财年的行业趋势、"
                "竞争格局、市场地位和主要挑战。"
            ),
            output_type=IndustryOutput,
        )
        return {"industry": output}

    return industry


def _build_fundamentals_node(agent: Any) -> StateNode:
    """Build a node that invokes the fundamentals agent and writes its output to state."""
    def fundamentals(state: AnalysisState) -> dict[str, FundamentalsOutput]:
        output = _invoke_structured_agent(
            agent,
            agent_name="fundamentals_analyst",
            payload=_agent_payload(
                "请分析 "
                f"{state['ticker'].upper()} 最近 {state['years']} 个财年的盈利能力、"
                "现金流、财务健康和成长性。"
            ),
            output_type=FundamentalsAgentOutput,
        )
        facts = build_fundamentals_facts(state["ticker"], state["years"])
        return {
            "fundamentals": FundamentalsOutput(
                narrative=output.narrative,
                concerns=output.concerns,
                **facts,
            )
        }

    return fundamentals


def _build_valuation_node(agent: Any) -> StateNode:
    """Build a node that invokes the valuation agent and writes its output to state."""
    def valuation(state: AnalysisState) -> dict[str, ValuationOutput]:
        output = _invoke_structured_agent(
            agent,
            agent_name="valuation_analyst",
            payload=_agent_payload(
                "请基于以下结构化上游分析评估 "
                f"{state['ticker'].upper()} 最近 {state['years']} 个财年的估值。\n\n"
                f"行业分析：\n{state['industry'].model_dump_json(indent=2)}\n\n"
                f"基本面分析：\n{state['fundamentals'].model_dump_json(indent=2)}"
            ),
            output_type=ValuationAgentOutput,
        )
        facts = build_valuation_facts(
            state["ticker"],
            state["years"],
            price=output.market_inputs.price,
            market_cap=output.market_inputs.market_cap,
        )
        return {
            "valuation": ValuationOutput(
                narrative=output.narrative,
                evidence=output.evidence,
                market_inputs=output.market_inputs,
                **facts,
            )
        }

    return valuation


def _build_risk_node(agent: Any) -> StateNode:
    """Build a node that invokes the risk agent and writes its output to state."""
    def risk(state: AnalysisState) -> dict[str, RiskOutput]:
        output = _invoke_structured_agent(
            agent,
            agent_name="risk_analyst",
            payload=_agent_payload(
                "请基于以下结构化上游分析评估 "
                f"{state['ticker'].upper()} 的财务、运营、行业和估值风险。\n\n"
                f"行业分析：\n{state['industry'].model_dump_json(indent=2)}\n\n"
                f"基本面分析：\n{state['fundamentals'].model_dump_json(indent=2)}\n\n"
                f"估值分析：\n{state['valuation'].model_dump_json(indent=2)}"
            ),
            output_type=RiskOutput,
        )
        return {"risk": output}

    return risk


def _build_synthesize_node(model: BaseChatModel) -> StateNode:
    """Build a node that generates summary and recommendation fragments."""
    def synthesize(state: AnalysisState) -> dict[str, SynthesisOutput]:
        logger = get_logger(__name__)
        logger.info("主 agent 开始汇总最终报告")
        response = model.with_structured_output(SynthesisOutput).invoke(
            [
                {
                    "role": "user",
                    "content": (
                        "请只生成摘要和投资建议两个中文 Markdown 正文片段。不要生成整篇"
                        "报告、一级或二级标题、财务表、数据口径、免责声明或参考来源；这些内容"
                        "将由报告编排器固定生成。\n\n"
                        "引用规则：可以复用上游正文已有的内部证据标记，例如 [industry-1]、"
                        "[valuation-1]、[risk-1] 和 [sec-2024]；不得自行发明或改写 URL、"
                        "标题或证据 ID。\n\n"
                        f"行业分析：\n{state['industry'].model_dump_json(indent=2)}\n\n"
                        f"基本面分析：\n{state['fundamentals'].model_dump_json(indent=2)}\n\n"
                        f"估值分析：\n{state['valuation'].model_dump_json(indent=2)}\n\n"
                        f"风险评估：\n{state['risk'].model_dump_json(indent=2)}"
                    ),
                }
            ]
        )
        synthesis = _extract_synthesis_output(response)
        logger.info("主 agent 完成汇总最终报告")
        return {"synthesis": synthesis}

    return synthesize


def _agent_payload(content: str) -> dict[str, list[dict[str, str]]]:
    return {"messages": [{"role": "user", "content": content}]}


def _invoke_structured_agent(
    agent: Any,
    *,
    agent_name: str,
    payload: dict[str, list[dict[str, str]]],
    output_type: type[StructuredOutputT],
) -> StructuredOutputT:
    """Invoke one agent and return its validated local output."""
    logger = get_logger(__name__)
    logger.info("启动 agent: %s", agent_name)
    result = agent.invoke(
        payload,
        config={"callbacks": [AgentProgressCallbackHandler(agent_name)]},
    )
    output = _extract_structured_response(
        result,
        agent_name=agent_name,
        output_type=output_type,
    )
    logger.info("agent %s 完成", agent_name)
    return output


def _extract_structured_response(
    result: object,
    *,
    agent_name: str,
    output_type: type[StructuredOutputT],
) -> StructuredOutputT:
    """Validate an agent's local result and fail before invalid data reaches another node."""
    if not isinstance(result, Mapping):
        raise AgentOutputError(f"{agent_name} returned an invalid result")

    messages = result.get("messages")
    if not isinstance(messages, list):
        raise AgentOutputError(f"{agent_name} result is missing local messages")

    # 扫描本节点消息；任一 ToolMessage 标记为 error 时立即抛出 AgentOutputError
    for message in messages:
        if isinstance(message, ToolMessage) and message.status == "error":
            tool_name = message.name or "unknown tool"
            raise AgentOutputError(f"{agent_name} tool {tool_name} failed: {message.content}")

    response = result.get("structured_response")
    if response is None:
        raise AgentOutputError(f"{agent_name} result is missing structured_response")

    try:
        output = output_type.model_validate(response)
    except ValidationError as exc:
        raise AgentOutputError(
            f"{agent_name} returned an invalid structured_response"
        ) from exc

    return output


def _extract_synthesis_output(response: object) -> SynthesisOutput:
    """Validate the summary model response before it reaches the report composer."""
    try:
        output = SynthesisOutput.model_validate(response)
    except ValidationError as exc:
        raise AgentOutputError("synthesize returned an invalid structured response") from exc

    if not output.summary.strip() or not output.investment_recommendation.strip():
        raise AgentOutputError("synthesize returned an empty structured response")
    return output


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
) -> GeneratedReport:
    """Run the graph and return a nonempty report with its matched evidence bundle."""
    model = build_model(llm_config)
    graph = build_analysis_graph(build_analysis_nodes(model))
    try:
        result = graph.invoke({"ticker": ticker, "years": years})
    except StockAgentError:
        raise
    except Exception as exc:
        raise classify_llm_error(exc, llm_config.model) from exc

    if not isinstance(result, Mapping):
        raise AgentOutputError("analysis graph returned an invalid final state")
    return deliver_report(result)
