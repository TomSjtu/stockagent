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
    Evidence,
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    ValuationOutput,
)
from stockagent.agents.subagent_progress import AgentProgressCallbackHandler
from stockagent.agents.valuation_agent import build_valuation_agent
from stockagent.config import LLMConfig
from stockagent.errors import StockAgentError
from stockagent.financials import SecFilingReference
from stockagent.llm import build_model
from stockagent.observability import get_logger
from stockagent.report.citations import render_citations
from stockagent.report.composer import AnnualFinancialSnapshot
from stockagent.report.evidence import EvidenceBundle


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
    # 汇总上游输出并返回 final_report 与 cited_evidence_ids 的节点
    synthesize: StateNode


@dataclass(frozen=True)
class GeneratedReport:
    """Rendered Markdown and the auditable evidence bundle from one analysis run."""

    # 已将内部证据标记渲染为脚注的最终报告正文
    markdown: str
    # 与 markdown 来自同一 final state 的证据、市场输入和 filing 元数据
    evidence_bundle: EvidenceBundle


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
    """Build a node that invokes the fundamentals agent and writes its output to state."""
    def fundamentals(state: AnalysisState) -> dict[str, FundamentalsOutput]:
        output, messages = _invoke_structured_agent(
            agent,
            agent_name="fundamentals_analyst",
            payload=_agent_payload(
                "请分析 "
                f"{state['ticker'].upper()} 最近 {state['years']} 个财年的盈利能力、"
                "现金流、财务健康和成长性。"
            ),
            output_type=FundamentalsOutput,
        )
        # 从本节点工具消息提取年度快照和 filing，并写回 fundamentals 输出
        return {
            "fundamentals": _apply_deterministic_fundamentals_snapshot(
                output,
                messages,
                ticker=state["ticker"],
                years=state["years"],
            )
        }

    return fundamentals


def _build_valuation_node(agent: Any) -> StateNode:
    """Build a node that invokes the valuation agent and writes its output to state."""
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
        # 将工具返回的 PE、PB、PS、price 和 market_cap 写入 valuation 输出
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
    """Build a node that invokes the risk agent and writes its output to state."""
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
    """Build a node that synthesizes Markdown and replaces evidence markers with footnotes."""
    def synthesize(state: AnalysisState) -> dict[str, object]:
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
                        "引用与数据口径规则：必须保留上游正文已有的内部证据标记，例如 "
                        "[industry-1]、[valuation-1]、[risk-1] 和 [sec-2024]，不得自行"
                        "发明或改写 URL、标题或证据 ID。涉及年度财务数据的段落或表格行使用对应"
                        "财年的 [sec-<财年>] 标记。报告的“数据口径”必须明确写出："
                        "财务数据仅覆盖最近可得年度 10-K，未纳入最新 10-Q 与 TTM。\n\n"
                        f"行业分析：\n{state['industry'].model_dump_json(indent=2)}\n\n"
                        f"基本面分析：\n{state['fundamentals'].model_dump_json(indent=2)}\n\n"
                        f"估值分析：\n{state['valuation'].model_dump_json(indent=2)}\n\n"
                        f"风险评估：\n{state['risk'].model_dump_json(indent=2)}"
                    ),
                }
            ]
        )
        report = _extract_markdown(response)
        # 用 state 中聚合的 evidence 将报告里的 [evidence-id] 标记替换为 Markdown 脚注
        citation_result = render_citations(
            report,
            _build_evidence_bundle(state, cited_evidence_ids=[]).evidence,
        )
        logger.info("主 agent 完成汇总最终报告")
        return {
            "final_report": citation_result.markdown,
            "cited_evidence_ids": citation_result.cited_evidence_ids,
        }

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
    """Invoke one agent and return its validated local output and local messages."""
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

    return output, messages


def _apply_deterministic_valuation_metrics(
    output: ValuationOutput,
    messages: list[Any],
    *,
    ticker: str,
    years: int,
) -> ValuationOutput:
    """Replace LLM valuation facts with the matching deterministic tool payload."""
    # 在本节点消息中找到最近一次成功的 compute_valuation_metrics 工具调用
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

    # 解析工具 JSON，并校验其中的 ticker、years、估值字段和市场输入字段
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

    tool_market_inputs = payload.get("market_inputs")
    if not isinstance(tool_market_inputs, Mapping):
        raise AgentOutputError("compute_valuation_metrics returned invalid market inputs")
    market_input_names = ("price", "market_cap")
    if any(input_name not in tool_market_inputs for input_name in market_input_names):
        raise AgentOutputError("compute_valuation_metrics omitted a market input")

    evidence_id = output.market_inputs.evidence_id
    if evidence_id is not None and evidence_id not in {
        evidence.id for evidence in output.evidence
    }:
        raise AgentOutputError("valuation_analyst returned an unknown market evidence ID")

    try:
        return ValuationOutput.model_validate(
            {
                **output.model_dump(),
                **{metric_name: valuation[metric_name] for metric_name in metric_names},
                "market_inputs": {
                    **output.market_inputs.model_dump(),
                    **{
                        input_name: tool_market_inputs[input_name]
                        for input_name in market_input_names
                    },
                },
            }
        )
    except ValidationError as exc:
        raise AgentOutputError("compute_valuation_metrics returned invalid metrics") from exc


def _apply_deterministic_fundamentals_snapshot(
    output: FundamentalsOutput,
    messages: list[Any],
    *,
    ticker: str,
    years: int,
) -> FundamentalsOutput:
    """Extract annual report facts and filing references from one tool result."""
    tool_message = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, ToolMessage)
            and message.name == "get_fundamentals_analysis"
            and message.status == "success"
        ),
        None,
    )
    if tool_message is None:
        raise AgentOutputError("fundamentals_analyst did not call get_fundamentals_analysis")
    if not isinstance(tool_message.content, str):
        raise AgentOutputError("get_fundamentals_analysis returned non-text JSON")

    try:
        payload = json.loads(tool_message.content)
    except json.JSONDecodeError as exc:
        raise AgentOutputError("get_fundamentals_analysis returned invalid JSON") from exc

    if not isinstance(payload, Mapping):
        raise AgentOutputError("get_fundamentals_analysis returned a non-object payload")
    if payload.get("ticker") != ticker.upper():
        raise AgentOutputError("get_fundamentals_analysis returned a mismatched ticker")

    records = payload.get("records")
    if not isinstance(records, list):
        raise AgentOutputError("get_fundamentals_analysis returned invalid records")
    if len(records) != years:
        raise AgentOutputError("get_fundamentals_analysis returned mismatched years")

    financial_filings: list[SecFilingReference] = []
    annual_financials: list[AnnualFinancialSnapshot] = []
    fiscal_years: list[int] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise AgentOutputError("get_fundamentals_analysis returned invalid record")

        fiscal_year = _fiscal_year(record, source="record")
        profitability = _metrics_for_fiscal_year(payload, "profitability", fiscal_year)
        cash_flow = _metrics_for_fiscal_year(payload, "cash_flow", fiscal_year)
        growth = _metrics_for_fiscal_year(payload, "growth", fiscal_year)
        annual_financials.append(
            AnnualFinancialSnapshot(
                fiscal_year=fiscal_year,
                revenue=_optional_number(record, "revenue", source="record"),
                net_income=_optional_number(record, "net_income", source="record"),
                operating_cash_flow=_optional_number(
                    record,
                    "operating_cash_flow",
                    source="record",
                ),
                capex=_optional_number(record, "capex", source="record"),
                free_cash_flow=_optional_number(
                    cash_flow,
                    "free_cash_flow",
                    source="cash_flow metrics",
                ),
                gross_margin=_optional_number(
                    profitability,
                    "gross_margin",
                    source="profitability metrics",
                ),
                net_margin=_optional_number(
                    profitability,
                    "net_margin",
                    source="profitability metrics",
                ),
                revenue_growth=_optional_number(
                    growth,
                    "revenue_growth",
                    source="growth metrics",
                ),
            )
        )
        fiscal_years.append(fiscal_year)

        filing_payload = record.get("filing")
        if filing_payload is None:
            continue
        if not isinstance(filing_payload, Mapping):
            raise AgentOutputError("get_fundamentals_analysis returned invalid filing")

        try:
            filing = SecFilingReference.model_validate(filing_payload)
        except ValidationError as exc:
            raise AgentOutputError("get_fundamentals_analysis returned invalid filing") from exc

        if fiscal_year != filing.fiscal_year:
            raise AgentOutputError("get_fundamentals_analysis returned mismatched filing")
        financial_filings.append(filing)

    if len(set(fiscal_years)) != years:
        raise AgentOutputError("get_fundamentals_analysis returned invalid fiscal years")
    if sorted(fiscal_years) != list(range(min(fiscal_years), max(fiscal_years) + 1)):
        raise AgentOutputError("get_fundamentals_analysis returned non-contiguous fiscal years")
    annual_financials.sort(key=lambda snapshot: snapshot.fiscal_year)
    financial_filings.sort(key=lambda filing: filing.fiscal_year)

    return FundamentalsOutput.model_validate(
        {
            **output.model_dump(),
            "financial_filings": financial_filings,
            "annual_financials": annual_financials,
        }
    )


def _metrics_for_fiscal_year(
    payload: Mapping[str, object],
    metric_name: str,
    fiscal_year: int,
) -> Mapping[str, object]:
    """Return one annual metrics record after checking its matching fiscal year."""
    metrics_by_year = payload.get(metric_name)
    if not isinstance(metrics_by_year, Mapping):
        raise AgentOutputError(
            f"get_fundamentals_analysis returned invalid {metric_name} metrics"
        )
    metrics = metrics_by_year.get(str(fiscal_year))
    if not isinstance(metrics, Mapping):
        raise AgentOutputError(
            f"get_fundamentals_analysis omitted {metric_name} metrics for {fiscal_year}"
        )
    if _fiscal_year(metrics, source=f"{metric_name} metrics") != fiscal_year:
        raise AgentOutputError(
            f"get_fundamentals_analysis returned mismatched {metric_name} metrics"
        )
    return metrics


def _fiscal_year(payload: Mapping[str, object], *, source: str) -> int:
    """Return a valid fiscal-year label from one deterministic payload object."""
    fiscal_year = payload.get("fiscal_year")
    if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
        raise AgentOutputError(f"get_fundamentals_analysis returned invalid {source}")
    return fiscal_year


def _optional_number(
    payload: Mapping[str, object],
    field_name: str,
    *,
    source: str,
) -> float | None:
    """Return a nullable numeric tool field without inventing a missing value."""
    if field_name not in payload:
        raise AgentOutputError(
            f"get_fundamentals_analysis omitted {field_name} from {source}"
        )
    value = payload[field_name]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentOutputError(
            f"get_fundamentals_analysis returned invalid {field_name} in {source}"
        )
    return float(value)


def _extract_markdown(response: object) -> str:
    """Extract nonempty Markdown from supported model response shapes or fail."""
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
    report = result.get("final_report")
    if not isinstance(report, str) or not report.strip():
        raise AgentOutputError("analysis graph result is missing final_report")
    return GeneratedReport(
        markdown=report,
        evidence_bundle=_build_evidence_bundle(
            result,
            cited_evidence_ids=_extract_cited_evidence_ids(result),
        ),
    )


def _build_evidence_bundle(
    state: Mapping[str, object],
    *,
    cited_evidence_ids: list[str],
) -> EvidenceBundle:
    """Collect all selected evidence and deterministic inputs from the final graph state."""
    industry = _state_output(state, "industry", IndustryOutput)
    fundamentals = _state_output(state, "fundamentals", FundamentalsOutput)
    valuation = _state_output(state, "valuation", ValuationOutput)
    risk = _state_output(state, "risk", RiskOutput)
    # 合并三个 Agent 的网页 evidence 与基本面工具返回的年度 filing evidence
    evidence = [
        *industry.evidence,
        *valuation.evidence,
        *risk.evidence,
        *[_filing_evidence(filing) for filing in fundamentals.financial_filings],
    ]
    return EvidenceBundle(
        evidence=evidence,
        cited_evidence_ids=cited_evidence_ids,
        market_inputs=valuation.market_inputs,
        financial_filings=fundamentals.financial_filings,
    )


def _state_output(
    state: Mapping[str, object],
    name: str,
    output_type: type[StructuredOutputT],
) -> StructuredOutputT:
    """Return a typed required state output or fail at the graph boundary."""
    output = state.get(name)
    if not isinstance(output, output_type):
        raise AgentOutputError(f"analysis graph result is missing {name}")
    return output


def _extract_cited_evidence_ids(state: Mapping[str, object]) -> list[str]:
    """Return the final citation IDs only when the synthesize node produced them."""
    evidence_ids = state.get("cited_evidence_ids")
    if not isinstance(evidence_ids, list) or not all(
        isinstance(evidence_id, str) for evidence_id in evidence_ids
    ):
        raise AgentOutputError("analysis graph result is missing cited_evidence_ids")
    return evidence_ids


def _filing_evidence(filing: SecFilingReference) -> Evidence:
    """Represent one deterministic annual filing as report evidence."""
    return Evidence(
        id=f"sec-{filing.fiscal_year}",
        kind="sec_filing",
        title=(
            f"SEC {filing.form}｜截至 {filing.period_end.isoformat()}｜"
            f"Filed {filing.filed_at.isoformat()}"
        ),
        url=filing.url,
        publisher="SEC",
        published_date=filing.filed_at,
        source_agent="fundamentals_analyst",
    )
