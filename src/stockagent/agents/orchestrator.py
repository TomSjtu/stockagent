from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import StateNode
from pydantic import BaseModel, ValidationError

from stockagent.agents.errors import AgentOutputError, classify_llm_error
from stockagent.agents.fundamentals_agent import build_fundamentals_agent
from stockagent.agents.industry_agent import build_industry_agent
from stockagent.agents.risk_agent import build_risk_agent
from stockagent.agents.state import (
    AnalysisState,
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    ValuationOutput,
)
from stockagent.agents.subagent_progress import AgentProgressCallbackHandler
from stockagent.agents.valuation_agent import build_valuation_agent
from stockagent.config import LLMConfig
from stockagent.errors import StockAgentError
from stockagent.llm import build_model
from stockagent.observability import get_logger


@dataclass(frozen=True)
class AnalysisNodes:
    industry: StateNode
    fundamentals: StateNode
    valuation: StateNode
    risk: StateNode
    synthesize: StateNode


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


def build_analysis_graph(nodes: AnalysisNodes):
    graph = StateGraph(AnalysisState)
    graph.add_node("industry", nodes.industry)
    graph.add_node("fundamentals", nodes.fundamentals)
    graph.add_node("valuation", nodes.valuation)
    graph.add_node("risk", nodes.risk)
    graph.add_node("synthesize", nodes.synthesize)

    graph.add_edge(START, "industry")
    graph.add_edge(START, "fundamentals")
    graph.add_edge(["industry", "fundamentals"], "valuation")
    graph.add_edge("valuation", "risk")
    graph.add_edge("risk", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


def build_analysis_nodes(model: BaseChatModel) -> AnalysisNodes:
    return AnalysisNodes(
        industry=_build_industry_node(build_industry_agent(model)),
        fundamentals=_build_fundamentals_node(build_fundamentals_agent(model)),
        valuation=_build_valuation_node(build_valuation_agent(model)),
        risk=_build_risk_node(build_risk_agent(model)),
        synthesize=_build_synthesize_node(model),
    )


def _build_industry_node(agent: Any) -> StateNode:
    def industry(state: AnalysisState) -> dict[str, IndustryOutput]:
        output, _messages = _invoke_structured_agent(
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
    def fundamentals(state: AnalysisState) -> dict[str, FundamentalsOutput]:
        output, _messages = _invoke_structured_agent(
            agent,
            agent_name="fundamentals_analyst",
            payload=_agent_payload(
                "请分析 "
                f"{state['ticker'].upper()} 最近 {state['years']} 个财年的盈利能力、"
                "现金流、财务健康和成长性。"
            ),
            output_type=FundamentalsOutput,
        )
        return {"fundamentals": output}

    return fundamentals


def _build_valuation_node(agent: Any) -> StateNode:
    def valuation(state: AnalysisState) -> dict[str, ValuationOutput]:
        output, messages = _invoke_structured_agent(
            agent,
            agent_name="valuation_analyst",
            payload=_agent_payload(
                "请基于以下结构化上游分析评估 "
                f"{state['ticker'].upper()} 最近 {state['years']} 个财年的估值。\n\n"
                f"行业分析：\n{state['industry'].model_dump_json(indent=2)}\n\n"
                f"基本面分析：\n{state['fundamentals'].model_dump_json(indent=2)}"
            ),
            output_type=ValuationOutput,
        )
        return {
            "valuation": _apply_deterministic_valuation_metrics(
                output,
                messages,
                ticker=state["ticker"],
                years=state["years"],
            )
        }

    return valuation


def _build_risk_node(agent: Any) -> StateNode:
    def risk(state: AnalysisState) -> dict[str, RiskOutput]:
        output, _messages = _invoke_structured_agent(
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
    def synthesize(state: AnalysisState) -> dict[str, str]:
        logger = get_logger(__name__)
        logger.info("主 agent 开始汇总最终报告")
        response = model.invoke(
            [
                {
                    "role": "user",
                    "content": (
                        "请根据以下结构化分析生成完整中文 Markdown 股票研究报告。\n\n"
                        "报告必须包含：摘要、行业分析、基本面分析、估值分析、"
                        "风险评估、投资建议；必须使用给定的 PE/PB/PS，不得自行重新计算；"
                        "必须说明数据限制并包含“非投资建议”免责声明。\n\n"
                        f"行业分析：\n{state['industry'].model_dump_json(indent=2)}\n\n"
                        f"基本面分析：\n{state['fundamentals'].model_dump_json(indent=2)}\n\n"
                        f"估值分析：\n{state['valuation'].model_dump_json(indent=2)}\n\n"
                        f"风险评估：\n{state['risk'].model_dump_json(indent=2)}"
                    ),
                }
            ]
        )
        report = _extract_markdown(response)
        logger.info("主 agent 完成汇总最终报告")
        return {"final_report": report}

    return synthesize


def _agent_payload(content: str) -> dict[str, list[dict[str, str]]]:
    return {"messages": [{"role": "user", "content": content}]}


def _invoke_structured_agent(
    agent: Any,
    *,
    agent_name: str,
    payload: dict[str, list[dict[str, str]]],
    output_type: type[StructuredOutputT],
) -> tuple[StructuredOutputT, list[Any]]:
    logger = get_logger(__name__)
    logger.info("启动 agent: %s", agent_name)
    result = agent.invoke(
        payload,
        config={"callbacks": [AgentProgressCallbackHandler(agent_name)]},
    )
    output, messages = _extract_structured_response(
        result,
        agent_name=agent_name,
        output_type=output_type,
    )
    logger.info("agent %s 完成", agent_name)
    return output, messages


def _extract_structured_response(
    result: object,
    *,
    agent_name: str,
    output_type: type[StructuredOutputT],
) -> tuple[StructuredOutputT, list[Any]]:
    if not isinstance(result, Mapping):
        raise AgentOutputError(f"{agent_name} returned an invalid result")

    messages = result.get("messages")
    if not isinstance(messages, list):
        raise AgentOutputError(f"{agent_name} result is missing local messages")

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

    return output, messages


def _apply_deterministic_valuation_metrics(
    output: ValuationOutput,
    messages: list[Any],
    *,
    ticker: str,
    years: int,
) -> ValuationOutput:
    tool_message = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, ToolMessage)
            and message.name == "compute_valuation_metrics"
            and message.status == "success"
        ),
        None,
    )
    if tool_message is None:
        raise AgentOutputError("valuation_analyst did not call compute_valuation_metrics")
    if not isinstance(tool_message.content, str):
        raise AgentOutputError("compute_valuation_metrics returned non-text JSON")

    try:
        payload = json.loads(tool_message.content)
    except json.JSONDecodeError as exc:
        raise AgentOutputError(
            "compute_valuation_metrics returned invalid JSON"
        ) from exc

    if not isinstance(payload, Mapping):
        raise AgentOutputError("compute_valuation_metrics returned a non-object payload")
    if payload.get("ticker") != ticker.upper():
        raise AgentOutputError("compute_valuation_metrics returned a mismatched ticker")
    if payload.get("years") != years:
        raise AgentOutputError("compute_valuation_metrics returned mismatched years")

    valuation = payload.get("valuation")
    if not isinstance(valuation, Mapping):
        raise AgentOutputError("compute_valuation_metrics returned invalid valuation data")

    metric_names = ("pe_ratio", "pb_ratio", "ps_ratio")
    if any(metric_name not in valuation for metric_name in metric_names):
        raise AgentOutputError("compute_valuation_metrics omitted a valuation metric")

    try:
        return ValuationOutput.model_validate(
            {
                **output.model_dump(),
                **{metric_name: valuation[metric_name] for metric_name in metric_names},
            }
        )
    except ValidationError as exc:
        raise AgentOutputError("compute_valuation_metrics returned invalid metrics") from exc


def _extract_markdown(response: object) -> str:
    if isinstance(response, str) and response.strip():
        return response

    content = getattr(response, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text = "\n".join(
            item.get("text", "") if isinstance(item, Mapping) else str(item)
            for item in content
        ).strip()
        if text:
            return text

    raise AgentOutputError("synthesize returned an empty Markdown report")


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
) -> str:
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
    report = result.get("final_report")
    if not isinstance(report, str) or not report.strip():
        raise AgentOutputError("analysis graph result is missing final_report")
    return report
