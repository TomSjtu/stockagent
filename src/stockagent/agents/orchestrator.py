from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypedDict, TypeVar
from warnings import catch_warnings, filterwarnings

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
from stockagent.agents.progress import (
    ModelGenerationProgress,
    ProgressReporter,
    report_agent_update,
    report_model_message,
)
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
from stockagent.agents.valuation_agent import build_valuation_agent
from stockagent.config import LLMConfig
from stockagent.errors import StockAgentError
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


class _StructuredModelState(TypedDict, total=False):
    """Internal state used only to expose one model call's message stream."""

    payload: object
    response: object


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)
ProgressResultT = TypeVar("ProgressResultT")


def _build_analysis_workflow(nodes: AnalysisNodes) -> StateGraph:
    """Register the fixed analysis topology without compiling the workflow."""
    workflow = StateGraph(AnalysisState)
    workflow.add_node("industry", nodes.industry)
    workflow.add_node("fundamentals", nodes.fundamentals)
    workflow.add_node("valuation", nodes.valuation)
    workflow.add_node("risk", nodes.risk)
    workflow.add_node("synthesize", nodes.synthesize)

    # 从 START 并行运行行业和基本面节点，再依次写入估值、风险和汇总叙事
    workflow.add_edge(START, "industry")
    workflow.add_edge(START, "fundamentals")
    workflow.add_edge(["industry", "fundamentals"], "valuation")
    workflow.add_edge("valuation", "risk")
    workflow.add_edge("risk", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow


class AnalysisGraphSetup:
    """Assemble the analysis workflow for one model and progress-reporter pair."""

    def __init__(
        self,
        model: BaseChatModel,
        progress_reporter: ProgressReporter,
    ) -> None:
        self._model = model
        self._progress_reporter = progress_reporter

    def build(self) -> StateGraph:
        """Create all analysis nodes and return their uncompiled workflow."""
        return _build_analysis_workflow(
            AnalysisNodes(
                industry=self._build_industry_node(),
                fundamentals=self._build_fundamentals_node(),
                valuation=self._build_valuation_node(),
                risk=self._build_risk_node(),
                synthesize=self._build_synthesize_node(),
            )
        )

    def _build_industry_node(self) -> StateNode:
        """Build a node that invokes the industry agent and writes its output."""
        agent = build_industry_agent(self._model)

        def industry(state: AnalysisState) -> dict[str, IndustryOutput]:
            def run() -> dict[str, IndustryOutput]:
                output = _invoke_structured_agent(
                    agent,
                    agent_name="industry_analyst",
                    payload=_agent_payload(
                        "请分析 "
                        f"{state['ticker'].upper()} 最近 {state['years']} 个财年的行业趋势、"
                        "竞争格局、市场地位和主要挑战。"
                    ),
                    output_type=IndustryOutput,
                    progress_reporter=self._progress_reporter,
                )
                return {"industry": output}

            return _run_with_progress(
                progress_reporter=self._progress_reporter,
                agent_name="industry_analyst",
                operation=run,
            )

        return industry

    def _build_fundamentals_node(self) -> StateNode:
        """Build a node that invokes the fundamentals agent and writes its output."""
        agent = build_fundamentals_agent(self._model)

        def fundamentals(state: AnalysisState) -> dict[str, FundamentalsOutput]:
            def run() -> dict[str, FundamentalsOutput]:
                output = _invoke_structured_agent(
                    agent,
                    agent_name="fundamentals_analyst",
                    payload=_agent_payload(
                        "请分析 "
                        f"{state['ticker'].upper()} 最近 {state['years']} 个财年的盈利能力、"
                        "现金流、财务健康和成长性。"
                    ),
                    output_type=FundamentalsAgentOutput,
                    progress_reporter=self._progress_reporter,
                )
                facts = build_fundamentals_facts(state["ticker"], state["years"])
                return {
                    "fundamentals": FundamentalsOutput(
                        narrative=output.narrative,
                        concerns=output.concerns,
                        **facts,
                    )
                }

            return _run_with_progress(
                progress_reporter=self._progress_reporter,
                agent_name="fundamentals_analyst",
                operation=run,
            )

        return fundamentals

    def _build_valuation_node(self) -> StateNode:
        """Build a node that invokes the valuation agent and writes its output."""
        agent = build_valuation_agent(self._model)

        def valuation(state: AnalysisState) -> dict[str, ValuationOutput]:
            def run() -> dict[str, ValuationOutput]:
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
                    progress_reporter=self._progress_reporter,
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

            return _run_with_progress(
                progress_reporter=self._progress_reporter,
                agent_name="valuation_analyst",
                operation=run,
            )

        return valuation

    def _build_risk_node(self) -> StateNode:
        """Build a node that invokes the risk agent and writes its output."""
        agent = build_risk_agent(self._model)

        def risk(state: AnalysisState) -> dict[str, RiskOutput]:
            def run() -> dict[str, RiskOutput]:
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
                    progress_reporter=self._progress_reporter,
                )
                return {"risk": output}

            return _run_with_progress(
                progress_reporter=self._progress_reporter,
                agent_name="risk_analyst",
                operation=run,
            )

        return risk

    def _build_synthesize_node(self) -> StateNode:
        """Build a node that generates summary and recommendation fragments."""
        # OpenAI-compatible endpoints may ignore response_format=json_schema and
        # return plain text. Tool calling is already required by the analysis agents.
        structured_model = self._model.with_structured_output(
            SynthesisOutput,
            method="function_calling",
        )
        model_stream = _build_structured_model_stream(structured_model)

        def synthesize(state: AnalysisState) -> dict[str, SynthesisOutput]:
            def run() -> dict[str, SynthesisOutput]:
                response = _invoke_structured_model(
                    model_stream,
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
                    ],
                    agent_name="synthesize",
                    progress_reporter=self._progress_reporter,
                )
                synthesis = _extract_synthesis_output(response)
                return {"synthesis": synthesis}

            return _run_with_progress(
                progress_reporter=self._progress_reporter,
                agent_name="synthesize",
                operation=run,
            )

        return synthesize


def _build_structured_model_stream(structured_model: Any) -> Any:
    """Wrap one structured model call so LangGraph exposes raw message deltas."""

    def generate(state: _StructuredModelState) -> dict[str, object]:
        # Temporary compatibility workaround for OpenAI SDK structured streaming:
        # langchain-openai serializes the final parsed event through Pydantic, whose
        # generated generic field still expects None even though parsing succeeded.
        with catch_warnings():
            filterwarnings(
                "ignore",
                message=(
                    r"(?s)^Pydantic serializer warnings:"
                    r".*field_name='parsed'"
                    r".*input_type=SynthesisOutput"
                ),
                category=UserWarning,
            )
            response = structured_model.invoke(state["payload"])
        return {"response": response}

    graph = StateGraph(_StructuredModelState)
    graph.add_node("generate", generate)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _agent_payload(content: str) -> dict[str, list[dict[str, str]]]:
    return {"messages": [{"role": "user", "content": content}]}


def _invoke_structured_agent(
    agent: Any,
    *,
    agent_name: str,
    payload: dict[str, list[dict[str, str]]],
    output_type: type[StructuredOutputT],
    progress_reporter: ProgressReporter,
) -> StructuredOutputT:
    """Stream one agent and validate its final complete state snapshot."""
    result = _consume_model_stream(
        agent.stream(
            payload,
            stream_mode=["updates", "values", "messages"],
        ),
        agent_name=agent_name,
        progress_reporter=progress_reporter,
        structured_output_tool=output_type.__name__,
    )
    output = _extract_structured_response(
        result,
        agent_name=agent_name,
        output_type=output_type,
    )
    return output


def _invoke_structured_model(
    model_stream: Any,
    payload: object,
    *,
    agent_name: str,
    progress_reporter: ProgressReporter,
) -> object:
    """Stream one structured model while retaining its parsed final response."""
    state = _consume_model_stream(
        model_stream.stream(
            {"payload": payload},
            stream_mode=["messages", "values"],
        ),
        agent_name=agent_name,
        progress_reporter=progress_reporter,
    )
    if isinstance(state, Mapping):
        return state.get("response")
    return None


def _consume_model_stream(
    events: Iterable[tuple[str, object]],
    *,
    agent_name: str,
    progress_reporter: ProgressReporter,
    structured_output_tool: str | None = None,
) -> object:
    """Consume model deltas and return the final complete-state snapshot."""
    result: object = None
    produced_characters = 0
    with ModelGenerationProgress(
        progress_reporter,
        agent_name,
    ) as generation_progress:
        for mode, chunk in events:
            if mode == "messages":
                produced_characters = report_model_message(
                    chunk,
                    agent_name=agent_name,
                    produced_characters=produced_characters,
                    progress_reporter=generation_progress,
                )
            elif mode == "updates":
                report_agent_update(
                    chunk,
                    agent_name=agent_name,
                    progress_reporter=generation_progress,
                    structured_output_tool=structured_output_tool,
                )
            elif mode == "values":
                result = chunk
    return result


def _run_with_progress(
    *,
    progress_reporter: ProgressReporter,
    agent_name: str,
    operation: Callable[[], ProgressResultT],
) -> ProgressResultT:
    """Run one complete node operation between progress lifecycle events."""
    progress_reporter.agent_started(agent_name)
    started_at = perf_counter()
    result = operation()
    progress_reporter.agent_finished(
        agent_name,
        perf_counter() - started_at,
    )
    return result


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
            raise AgentOutputError(
                f"{agent_name} tool {tool_name} failed: {message.content}"
            )

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
        raise AgentOutputError(
            "synthesize returned an invalid structured response"
        ) from exc

    if not output.summary.strip() or not output.investment_recommendation.strip():
        raise AgentOutputError("synthesize returned an empty structured response")
    return output


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
    progress_reporter: ProgressReporter,
) -> GeneratedReport:
    """Run the graph and return a nonempty report with its matched evidence bundle."""
    model = build_model(llm_config)
    workflow = AnalysisGraphSetup(model, progress_reporter).build()
    graph = workflow.compile()
    try:
        result = graph.invoke({"ticker": ticker, "years": years})
    except StockAgentError:
        raise
    except Exception as exc:
        raise classify_llm_error(exc, llm_config.model) from exc

    if not isinstance(result, Mapping):
        raise AgentOutputError("analysis graph returned an invalid final state")
    return deliver_report(result)
