from __future__ import annotations

import unittest
import warnings
from collections.abc import Iterator
from time import sleep
from typing import Any, cast
from unittest.mock import patch

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.outputs import (
    ChatGeneration,
    ChatGenerationChunk,
    ChatResult,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

from stockagent.agents.errors import AgentOutputError
from stockagent.agents.orchestrator import AnalysisGraphSetup
from stockagent.agents.state import (
    FundamentalsAgentOutput,
    FundamentalsOutput,
    IndustryOutput,
    MarketInputs,
    RiskOutput,
    SynthesisOutput,
    ValuationAgentOutput,
    ValuationOutput,
)
from stockagent.financials import AnnualFinancialSnapshot


class FakeAgent:
    def __init__(
        self,
        result: object,
        updates: list[object] | None = None,
        messages: list[object] | None = None,
        values: list[object] | None = None,
    ) -> None:
        self.result = result
        self.updates = updates or []
        self.messages = messages or []
        self.values = values
        self.payload: object | None = None
        self.stream_mode: object | None = None
        self.stream_completed = False
        self.stream_delay = 0.0
        self.stream_error: BaseException | None = None

    def stream(self, payload: object, *, stream_mode: object) -> object:
        self.payload = payload
        self.stream_mode = stream_mode
        if self.stream_delay:
            sleep(self.stream_delay)
        if self.stream_error is not None:
            raise self.stream_error
        for update in self.updates:
            yield ("updates", update)
        for message in self.messages:
            yield ("messages", message)
        for value in self.values or [self.result]:
            yield ("values", value)
        self.stream_completed = True


class FakeModel:
    def __init__(self, result: object) -> None:
        self.result = result
        self.payload: object | None = None
        self.output_type: type | None = None
        self.structured_output_method: str | None = None

    def with_structured_output(
        self,
        output_type: type,
        *,
        method: str = "json_schema",
    ) -> FakeModel:
        self.output_type = output_type
        self.structured_output_method = method
        return self

    def invoke(self, payload: object) -> object:
        self.payload = payload
        return self.result


class WarningSynthesisModel(FakeModel):
    def invoke(self, payload: object) -> object:
        warnings.warn(
            "Pydantic serializer warnings:\n"
            "  PydanticSerializationUnexpectedValue("
            "Expected `none` - serialized value may not be as expected "
            "[field_name='parsed', input_value=SynthesisOutput(...), "
            "input_type=SynthesisOutput])",
            UserWarning,
        )
        warnings.warn("unrelated warning", UserWarning)
        return super().invoke(payload)


class FakeStreamingSynthesisModel(BaseChatModel):
    fragments: list[str]
    output_type: type | None = None

    @property
    def _llm_type(self) -> str:
        return "fake-streaming-synthesis"

    def with_structured_output(
        self,
        output_type: type,
        **_kwargs: object,
    ) -> object:
        self.output_type = output_type
        return self | PydanticOutputParser(pydantic_object=output_type)

    def _generate(
        self,
        _messages: list[object],
        **_kwargs: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content="".join(self.fragments)),
                )
            ]
        )

    def _stream(
        self,
        _messages: list[object],
        **_kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        for fragment in self.fragments:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=fragment),
            )


class FakeProgressReporter:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def agent_started(self, agent: str) -> None:
        self.events.append(("agent_started", agent))

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        self.events.append(("agent_finished", agent, elapsed_seconds))

    def tool_started(self, agent: str, tool: str) -> None:
        self.events.append(("tool_started", agent, tool))

    def tool_finished(self, agent: str, tool: str) -> None:
        self.events.append(("tool_finished", agent, tool))

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        self.events.append(("tool_failed", agent, tool, detail))

    def model_output(self, agent: str, produced_characters: int) -> None:
        self.events.append(("model_output", agent, produced_characters))


def _valid_agent_result(name: str) -> dict[str, object]:
    if name == "industry":
        output = IndustryOutput(narrative="industry", evidence=[])
    elif name == "fundamentals":
        output = FundamentalsAgentOutput(
            narrative="fundamentals",
            concerns=[],
        )
    elif name == "valuation":
        output = ValuationAgentOutput(
            narrative="valuation",
            market_inputs=MarketInputs(),
        )
    elif name == "risk":
        output = RiskOutput(
            narrative="risk",
            overall_rating="低",
            key_risks=[],
            evidence=[],
        )
    else:
        raise AssertionError(f"unknown analysis agent: {name}")

    return {"messages": [], "structured_response": output}


class _WorkflowHarness:
    _NEXT_NODE = {
        "valuation": "risk",
        "risk": "synthesize",
        "synthesize": None,
    }
    _PREDECESSOR = {
        "valuation": "fundamentals",
        "risk": "valuation",
        "synthesize": "risk",
    }
    _OUTPUT_KEYS = {
        "industry": "industry",
        "fundamentals": "fundamentals",
        "valuation": "valuation",
        "risk": "risk",
        "synthesize": "synthesis",
    }

    def __init__(
        self,
        workflow: StateGraph,
        agents: dict[str, FakeAgent],
    ) -> None:
        self._workflow = workflow
        self._agents = agents

    def industry(self, state: dict[str, object]) -> dict[str, object]:
        return self._invoke_initial_node("industry", state)

    def fundamentals(self, state: dict[str, object]) -> dict[str, object]:
        return self._invoke_initial_node("fundamentals", state)

    def valuation(self, state: dict[str, object]) -> dict[str, object]:
        return self._invoke_node("valuation", state)

    def risk(self, state: dict[str, object]) -> dict[str, object]:
        return self._invoke_node("risk", state)

    def synthesize(self, state: dict[str, object]) -> dict[str, object]:
        return self._invoke_node("synthesize", state)

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        self._prepare_non_target_agents("synthesize")
        return self._workflow.compile().invoke(state)

    def _invoke_initial_node(
        self,
        target: str,
        state: dict[str, object],
    ) -> dict[str, object]:
        self._prepare_non_target_agents(target)
        graph = self._workflow.compile(interrupt_before=["valuation"])
        result = graph.invoke(state)
        output_key = self._OUTPUT_KEYS[target]
        return {output_key: result[output_key]}

    def _invoke_node(
        self,
        target: str,
        state: dict[str, object],
    ) -> dict[str, object]:
        self._prepare_non_target_agents(target)
        next_node = self._NEXT_NODE[target]
        interrupt_before = [target]
        if next_node is not None:
            interrupt_before.append(next_node)
        graph = self._workflow.compile(
            checkpointer=InMemorySaver(),
            interrupt_before=interrupt_before,
        )
        config = {"configurable": {"thread_id": target}}
        graph.invoke(
            {
                "ticker": state["ticker"],
                "years": state["years"],
            },
            config,
        )
        snapshot = graph.get_state(config)
        if target not in snapshot.next:
            raise AssertionError(f"workflow did not pause before {target}")
        resume_config = graph.update_state(
            snapshot.config,
            state,
            as_node=self._PREDECESSOR[target],
        )
        result = graph.invoke(None, resume_config)
        output_key = self._OUTPUT_KEYS[target]
        return {output_key: result[output_key]}

    def _prepare_non_target_agents(self, target: str) -> None:
        for name, agent in self._agents.items():
            if name != target and agent.result == {} and agent.values is None:
                agent.result = _valid_agent_result(name)


class AnalysisNodesTest(unittest.TestCase):
    def setUp(self) -> None:
        fundamentals_facts = patch(
            "stockagent.agents.orchestrator.build_fundamentals_facts",
            return_value={
                "annual_financials": [],
                "financial_filings": [],
            },
        )
        valuation_facts = patch(
            "stockagent.agents.orchestrator.build_valuation_facts",
            return_value={
                "pe_ratio": None,
                "pb_ratio": None,
                "ps_ratio": None,
            },
        )
        fundamentals_facts.start()
        valuation_facts.start()
        self.addCleanup(fundamentals_facts.stop)
        self.addCleanup(valuation_facts.stop)

    def _build_nodes(
        self,
        *,
        industry_result: object,
        fundamentals_result: object,
        valuation_result: object,
        risk_result: object,
        synthesize_result: object = {
            "summary": "摘要",
            "investment_recommendation": "投资建议",
        },
    ) -> tuple[_WorkflowHarness, dict[str, FakeAgent], FakeModel]:
        agents = {
            "industry": FakeAgent(industry_result),
            "fundamentals": FakeAgent(fundamentals_result),
            "valuation": FakeAgent(valuation_result),
            "risk": FakeAgent(risk_result),
        }
        model = FakeModel(synthesize_result)
        self.progress_reporter = FakeProgressReporter()

        with (
            patch(
                "stockagent.agents.orchestrator.build_industry_agent",
                return_value=agents["industry"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_agent",
                return_value=agents["fundamentals"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_valuation_agent",
                return_value=agents["valuation"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_risk_agent",
                return_value=agents["risk"],
            ),
        ):
            workflow = AnalysisGraphSetup(model, self.progress_reporter).build()
            nodes = _WorkflowHarness(workflow, agents)

        return nodes, agents, model

    def test_setup_builds_all_nodes_and_returns_uncompiled_workflow(self) -> None:
        model = FakeModel(
            {
                "summary": "摘要",
                "investment_recommendation": "投资建议",
            }
        )
        progress_reporter = FakeProgressReporter()
        agents = {
            "industry": FakeAgent({}),
            "fundamentals": FakeAgent({}),
            "valuation": FakeAgent({}),
            "risk": FakeAgent({}),
        }

        with (
            patch(
                "stockagent.agents.orchestrator.build_industry_agent",
                return_value=agents["industry"],
            ) as build_industry,
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_agent",
                return_value=agents["fundamentals"],
            ) as build_fundamentals,
            patch(
                "stockagent.agents.orchestrator.build_valuation_agent",
                return_value=agents["valuation"],
            ) as build_valuation,
            patch(
                "stockagent.agents.orchestrator.build_risk_agent",
                return_value=agents["risk"],
            ) as build_risk,
        ):
            workflow = AnalysisGraphSetup(model, progress_reporter).build()

        self.assertIsInstance(workflow, StateGraph)
        self.assertFalse(hasattr(workflow, "invoke"))
        graph_view = workflow.compile().get_graph()
        self.assertEqual(
            set(graph_view.nodes),
            {
                "__start__",
                "industry",
                "fundamentals",
                "valuation",
                "risk",
                "synthesize",
                "__end__",
            },
        )
        for builder in [
            build_industry,
            build_fundamentals,
            build_valuation,
            build_risk,
        ]:
            builder.assert_called_once_with(model)
        self.assertEqual(model.output_type, SynthesisOutput)
        self.assertEqual(model.structured_output_method, "function_calling")

    def test_industry_node_returns_local_typed_update(self) -> None:
        output = IndustryOutput(narrative="Industry", evidence=[])
        nodes, agents, _model = self._build_nodes(
            industry_result={"messages": [], "structured_response": output},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )

        result = nodes.industry({"ticker": "aapl", "years": 3})

        self.assertEqual(result, {"industry": output})
        self.assertEqual(
            agents["industry"].payload,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请分析 AAPL 最近 3 个财年的行业趋势、竞争格局、市场地位和主要挑战。",
                    }
                ]
            },
        )
        self.assertEqual(
            agents["industry"].stream_mode,
            ["updates", "values", "messages"],
        )

    def test_agent_stream_reports_model_output_amount_without_content(self) -> None:
        output = IndustryOutput(narrative="Industry", evidence=[])
        first_fragment = '{"narrative":"公司毛'
        second_fragment = '利率改善"}'
        nodes, agents, _model = self._build_nodes(
            industry_result={"messages": [], "structured_response": output},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )
        agents["industry"].updates = [
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "IndustryOutput",
                                    "args": {
                                        "narrative": "公司毛利率改善",
                                        "evidence": [],
                                    },
                                    "id": "structured-output",
                                    "type": "tool_call",
                                }
                            ],
                        ),
                        ToolMessage(
                            content='{"narrative":"公司毛利率改善"}',
                            name="IndustryOutput",
                            status="error",
                            tool_call_id="structured-output",
                        ),
                    ]
                }
            }
        ]
        agents["industry"].messages = [
            (
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "IndustryOutput",
                            "args": first_fragment,
                            "id": "structured-output",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                ),
                {"langgraph_node": "model"},
            ),
            (
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": None,
                            "args": second_fragment,
                            "id": None,
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                ),
                {"langgraph_node": "model"},
            ),
        ]

        result = nodes.industry({"ticker": "aapl", "years": 3})

        self.assertEqual(result, {"industry": output})
        output_events = [
            event
            for event in self.progress_reporter.events
            if event[0] == "model_output"
        ]
        self.assertEqual(
            output_events,
            [
                ("model_output", "industry_analyst", len(first_fragment)),
                (
                    "model_output",
                    "industry_analyst",
                    len(first_fragment) + len(second_fragment),
                ),
            ],
        )
        self.assertNotIn(first_fragment, repr(output_events))
        self.assertNotIn(second_fragment, repr(output_events))
        self.assertNotIn("公司毛利率改善", repr(self.progress_reporter.events))
        self.assertFalse(
            any(
                event[:3] == ("tool_started", "industry_analyst", "IndustryOutput")
                for event in self.progress_reporter.events
            )
        )

    def test_agent_stream_falls_back_to_elapsed_heartbeat(self) -> None:
        output = IndustryOutput(narrative="Industry", evidence=[])
        nodes, agents, _model = self._build_nodes(
            industry_result={"messages": [], "structured_response": output},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )
        agents["industry"].stream_delay = 0.04

        with patch(
            "stockagent.agents.progress._HEARTBEAT_INTERVAL_SECONDS",
            0.005,
        ):
            result = nodes.industry({"ticker": "aapl", "years": 3})

        self.assertEqual(result, {"industry": output})
        heartbeat_events = [
            event
            for event in self.progress_reporter.events
            if event == ("model_output", "industry_analyst", 0)
        ]
        self.assertGreaterEqual(len(heartbeat_events), 1)
        event_count = len(self.progress_reporter.events)
        sleep(0.02)
        self.assertEqual(len(self.progress_reporter.events), event_count)

    def test_agent_stream_stops_elapsed_heartbeat_after_exception(self) -> None:
        nodes, agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )
        agents["industry"].stream_delay = 0.04
        agents["industry"].stream_error = RuntimeError("stream failed")

        with (
            patch(
                "stockagent.agents.progress._HEARTBEAT_INTERVAL_SECONDS",
                0.005,
            ),
            self.assertRaisesRegex(RuntimeError, "stream failed"),
        ):
            nodes.industry({"ticker": "aapl", "years": 3})

        heartbeat_events = [
            event
            for event in self.progress_reporter.events
            if event == ("model_output", "industry_analyst", 0)
        ]
        self.assertGreaterEqual(len(heartbeat_events), 1)
        event_count = len(self.progress_reporter.events)
        sleep(0.02)
        self.assertEqual(len(self.progress_reporter.events), event_count)

    def test_agent_stream_reports_tool_events_without_args_and_with_name_fallback(
        self,
    ) -> None:
        output = IndustryOutput(narrative="Industry", evidence=[])
        query = "AAPL " + "very long market search query " * 4
        nodes, agents, _model = self._build_nodes(
            industry_result={"messages": [], "structured_response": output},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )
        agents["industry"].updates = [
            {
                "any_model_node": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "web_search",
                                    "args": {"query": query},
                                    "id": "tool-1",
                                    "type": "tool_call",
                                },
                                {
                                    "name": "custom_lookup",
                                    "args": {"ticker": "AAPL"},
                                    "id": "tool-2",
                                    "type": "tool_call",
                                },
                            ],
                        )
                    ]
                }
            },
            {
                "renamed_tool_node": {
                    "messages": [
                        ToolMessage(
                            content="ok",
                            name="web_search",
                            status="success",
                            tool_call_id="tool-1",
                        ),
                        ToolMessage(
                            content="lookup failed",
                            name="custom_lookup",
                            status="error",
                            tool_call_id="tool-2",
                        ),
                    ]
                }
            },
        ]

        result = nodes.industry({"ticker": "aapl", "years": 3})

        self.assertEqual(result, {"industry": output})
        tool_events = [
            event
            for event in self.progress_reporter.events
            if len(event) > 1
            and event[1] == "industry_analyst"
            and event[0] in {"tool_started", "tool_finished", "tool_failed"}
        ]
        self.assertEqual(
            tool_events[0],
            (
                "tool_started",
                "industry_analyst",
                "搜索市场与行业信息",
            ),
        )
        self.assertEqual(
            tool_events[1],
            (
                "tool_started",
                "industry_analyst",
                "custom_lookup",
            ),
        )
        self.assertNotIn(query, repr(tool_events))
        self.assertNotIn('{"ticker":"AAPL"}', repr(tool_events))
        self.assertEqual(
            tool_events[2],
            (
                "tool_finished",
                "industry_analyst",
                "搜索市场与行业信息",
            ),
        )
        self.assertEqual(
            tool_events[3],
            (
                "tool_failed",
                "industry_analyst",
                "custom_lookup",
                "lookup failed",
            ),
        )

    def test_agent_uses_last_complete_state_snapshot(self) -> None:
        stale = IndustryOutput(narrative="stale", evidence=[])
        final = IndustryOutput(narrative="final", evidence=[])
        nodes, agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )
        agents["industry"].values = [
            {"messages": [], "structured_response": stale},
            {"messages": [], "structured_response": final},
        ]

        result = nodes.industry({"ticker": "aapl", "years": 3})

        self.assertEqual(result, {"industry": final})

    def test_agent_tool_failure_is_reported_without_interrupting_stream(self) -> None:
        nodes, agents, _model = self._build_nodes(
            industry_result={
                "messages": [
                    ToolMessage(
                        content="search failed",
                        name="web_search",
                        status="error",
                        tool_call_id="tool-1",
                    )
                ],
            },
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )
        agents["industry"].updates = [
            {
                "tool_executor": {
                    "messages": [
                        ToolMessage(
                            content="search failed",
                            name="web_search",
                            status="error",
                            tool_call_id="tool-1",
                        )
                    ]
                }
            },
            {
                "tool_executor": {
                    "messages": [
                        ToolMessage(
                            content="later tool completed",
                            name="custom_lookup",
                            status="success",
                            tool_call_id="tool-2",
                        )
                    ]
                }
            },
        ]

        with self.assertRaises(AgentOutputError) as raised:
            nodes.industry({"ticker": "AAPL", "years": 3})

        self.assertEqual(
            str(raised.exception),
            "industry_analyst tool web_search failed: search failed",
        )
        industry_tool_events = [
            event
            for event in self.progress_reporter.events
            if len(event) > 1
            and event[1] == "industry_analyst"
            and event[0] in {"tool_started", "tool_finished", "tool_failed"}
        ]
        self.assertEqual(
            industry_tool_events[0],
            (
                "tool_failed",
                "industry_analyst",
                "搜索市场与行业信息",
                "search failed",
            ),
        )
        self.assertEqual(
            industry_tool_events[1],
            (
                "tool_finished",
                "industry_analyst",
                "custom_lookup",
            ),
        )
        self.assertTrue(agents["industry"].stream_completed)

    def test_agent_requires_a_valid_structured_response(self) -> None:
        nodes, _agents, _model = self._build_nodes(
            industry_result={"messages": []},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )

        with self.assertRaisesRegex(AgentOutputError, "missing structured_response"):
            nodes.industry({"ticker": "AAPL", "years": 3})

    def test_fundamentals_node_fetches_facts_with_analysis_state_context(self) -> None:
        output = FundamentalsAgentOutput(narrative="llm", concerns=[])
        snapshot = AnnualFinancialSnapshot(fiscal_year=2024, revenue=1_000.0)
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={
                "messages": [
                    ToolMessage(
                        content="tool result is intentionally ignored",
                        name="get_fundamentals_analysis",
                        status="success",
                        tool_call_id="tool-1",
                    ),
                ],
                "structured_response": output,
            },
            valuation_result={},
            risk_result={},
        )

        with patch(
            "stockagent.agents.orchestrator.build_fundamentals_facts",
            return_value={
                "annual_financials": [snapshot],
                "financial_filings": [],
            },
        ) as apply_facts:
            result = nodes.fundamentals({"ticker": "aapl", "years": 2})

        self.assertEqual(
            result,
            {
                "fundamentals": FundamentalsOutput(
                    narrative="llm",
                    concerns=[],
                    annual_financials=[snapshot],
                    financial_filings=[],
                )
            },
        )
        apply_facts.assert_called_once_with("aapl", 2)

    def test_valuation_node_builds_facts_from_declared_market_inputs(self) -> None:
        output = ValuationAgentOutput(
            narrative="llm",
            market_inputs=MarketInputs(
                price=40.0,
                market_cap=200.0,
                currency="USD",
            ),
        )
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={
                "messages": [],
                "structured_response": output,
            },
            risk_result={},
        )

        with patch(
            "stockagent.agents.orchestrator.build_valuation_facts",
            return_value={
                "pe_ratio": 20.0,
                "pb_ratio": 4.0,
                "ps_ratio": 2.0,
            },
        ) as build_facts:
            result = nodes.valuation(
                {
                    "ticker": "AAPL",
                    "years": 3,
                    "industry": IndustryOutput(narrative="industry", evidence=[]),
                    "fundamentals": FundamentalsOutput(
                        narrative="fundamentals", concerns=[]
                    ),
                }
            )

        self.assertEqual(
            result,
            {
                "valuation": ValuationOutput(
                    narrative="llm",
                    market_inputs=MarketInputs(
                        price=40.0,
                        market_cap=200.0,
                        currency="USD",
                    ),
                    pe_ratio=20.0,
                    pb_ratio=4.0,
                    ps_ratio=2.0,
                )
            },
        )
        build_facts.assert_called_once_with(
            "AAPL",
            3,
            price=40.0,
            market_cap=200.0,
        )

    def test_valuation_node_wraps_unknown_market_evidence_id(self) -> None:
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={
                "messages": [],
                "structured_response": {
                    "narrative": "llm",
                    "evidence": [],
                    "market_inputs": {"evidence_id": "valuation-1"},
                },
            },
            risk_result={},
        )

        with self.assertRaisesRegex(
            AgentOutputError,
            "valuation_analyst.*invalid structured_response",
        ):
            nodes.valuation(
                {
                    "ticker": "AAPL",
                    "years": 3,
                    "industry": IndustryOutput(narrative="industry", evidence=[]),
                    "fundamentals": FundamentalsOutput(
                        narrative="fundamentals",
                        concerns=[],
                    ),
                }
            )

    def test_synthesize_node_returns_narrative_fragments(self) -> None:
        nodes, _agents, model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
            synthesize_result={
                "summary": "摘要正文",
                "investment_recommendation": "投资建议正文",
            },
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="industry", evidence=[]),
            "fundamentals": FundamentalsOutput(narrative="fundamentals", concerns=[]),
            "valuation": ValuationOutput(
                narrative="valuation",
                pe_ratio=30.0,
                pb_ratio=45.0,
                ps_ratio=8.0,
                evidence=[],
                market_inputs=MarketInputs(),
            ),
            "risk": RiskOutput(
                narrative="risk",
                overall_rating="中",
                key_risks=["competition"],
                evidence=[],
            ),
        }

        result = nodes.synthesize(state)

        self.assertEqual(
            result,
            {
                "synthesis": SynthesisOutput(
                    summary="摘要正文",
                    investment_recommendation="投资建议正文",
                )
            },
        )
        self.assertIsNotNone(model.output_type)
        self.assertEqual(model.structured_output_method, "function_calling")

    def test_synthesize_node_only_suppresses_known_pydantic_serializer_warning(
        self,
    ) -> None:
        model = WarningSynthesisModel(
            {
                "summary": "摘要正文",
                "investment_recommendation": "投资建议正文",
            }
        )
        progress_reporter = FakeProgressReporter()
        agents = {
            "industry": FakeAgent({}),
            "fundamentals": FakeAgent({}),
            "valuation": FakeAgent({}),
            "risk": FakeAgent({}),
        }

        with (
            patch(
                "stockagent.agents.orchestrator.build_industry_agent",
                return_value=agents["industry"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_agent",
                return_value=agents["fundamentals"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_valuation_agent",
                return_value=agents["valuation"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_risk_agent",
                return_value=agents["risk"],
            ),
        ):
            nodes = _WorkflowHarness(
                AnalysisGraphSetup(model, progress_reporter).build(),
                agents,
            )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            nodes.synthesize(
                {
                    "ticker": "AAPL",
                    "years": 3,
                    "industry": IndustryOutput(narrative="industry", evidence=[]),
                    "fundamentals": FundamentalsOutput(
                        narrative="fundamentals",
                        concerns=[],
                    ),
                    "valuation": ValuationOutput(narrative="valuation"),
                    "risk": RiskOutput(
                        narrative="risk",
                        overall_rating="低",
                        key_risks=[],
                        evidence=[],
                    ),
                }
            )

        self.assertEqual([str(item.message) for item in caught], ["unrelated warning"])

    def test_synthesize_node_reports_model_output_amount_without_content(
        self,
    ) -> None:
        first_fragment = '{"summary":"摘要",'
        second_fragment = '"investment_recommendation":"建议"}'
        model = FakeStreamingSynthesisModel(
            fragments=[first_fragment, second_fragment],
        )
        progress_reporter = FakeProgressReporter()
        agents = {
            "industry": FakeAgent({}),
            "fundamentals": FakeAgent({}),
            "valuation": FakeAgent({}),
            "risk": FakeAgent({}),
        }

        with (
            patch(
                "stockagent.agents.orchestrator.build_industry_agent",
                return_value=agents["industry"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_agent",
                return_value=agents["fundamentals"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_valuation_agent",
                return_value=agents["valuation"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_risk_agent",
                return_value=agents["risk"],
            ),
        ):
            nodes = _WorkflowHarness(
                AnalysisGraphSetup(model, progress_reporter).build(),
                agents,
            )

        result = nodes.synthesize(
            {
                "ticker": "AAPL",
                "years": 3,
                "industry": IndustryOutput(narrative="industry", evidence=[]),
                "fundamentals": FundamentalsOutput(
                    narrative="fundamentals",
                    concerns=[],
                ),
                "valuation": ValuationOutput(narrative="valuation"),
                "risk": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                ),
            }
        )

        self.assertEqual(
            result,
            {
                "synthesis": SynthesisOutput(
                    summary="摘要",
                    investment_recommendation="建议",
                )
            },
        )
        output_events = [
            event for event in progress_reporter.events if event[0] == "model_output"
        ]
        self.assertEqual(
            output_events,
            [
                ("model_output", "synthesize", len(first_fragment)),
                (
                    "model_output",
                    "synthesize",
                    len(first_fragment) + len(second_fragment),
                ),
            ],
        )
        self.assertNotIn(first_fragment, repr(output_events))
        self.assertNotIn(second_fragment, repr(output_events))

    def test_synthesize_node_prompt_contains_all_four_upstream_outputs(self) -> None:
        nodes, _agents, model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
            synthesize_result={
                "summary": "摘要正文",
                "investment_recommendation": "投资建议正文",
            },
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="行业上游输出", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="基本面上游输出",
                concerns=["收入增长放缓"],
            ),
            "valuation": ValuationOutput(narrative="估值上游输出"),
            "risk": RiskOutput(
                narrative="风险上游输出",
                overall_rating="低",
                key_risks=["需求波动"],
                evidence=[],
            ),
        }

        nodes.synthesize(state)

        self.assertIsInstance(model.payload, list)
        prompt = cast(list[dict[str, str]], model.payload)[0]["content"]
        for output in [
            state["industry"],
            state["fundamentals"],
            state["valuation"],
            state["risk"],
        ]:
            self.assertIn(output.model_dump_json(indent=2), prompt)

    def test_all_nodes_report_agent_lifecycle_with_elapsed_time(self) -> None:
        nodes, _agents, _model = self._build_nodes(
            industry_result={
                "messages": [],
                "structured_response": IndustryOutput(
                    narrative="industry",
                    evidence=[],
                ),
            },
            fundamentals_result={
                "messages": [],
                "structured_response": FundamentalsAgentOutput(
                    narrative="fundamentals",
                    concerns=[],
                ),
            },
            valuation_result={
                "messages": [],
                "structured_response": ValuationAgentOutput(
                    narrative="valuation",
                    market_inputs=MarketInputs(
                        price=40.0,
                        market_cap=200.0,
                        currency="USD",
                    ),
                ),
            },
            risk_result={
                "messages": [],
                "structured_response": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                ),
            },
        )
        with (
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_facts",
                return_value={
                    "annual_financials": [],
                    "financial_filings": [],
                },
            ),
            patch(
                "stockagent.agents.orchestrator.build_valuation_facts",
                return_value={
                    "pe_ratio": 20.0,
                    "pb_ratio": 4.0,
                    "ps_ratio": 2.0,
                },
            ),
        ):
            state = nodes.invoke({"ticker": "AAPL", "years": 3})

        expected_agents = [
            "industry_analyst",
            "fundamentals_analyst",
            "valuation_analyst",
            "risk_analyst",
            "synthesize",
        ]
        self.assertEqual(len(self.progress_reporter.events), 10)
        for agent in expected_agents:
            lifecycle_events = [
                event
                for event in self.progress_reporter.events
                if len(event) > 1
                and event[1] == agent
                and event[0] in {"agent_started", "agent_finished"}
            ]
            self.assertEqual(len(lifecycle_events), 2)
            started, finished = lifecycle_events
            self.assertEqual(started, ("agent_started", agent))
            self.assertEqual(finished[:2], ("agent_finished", agent))
            self.assertIsInstance(finished[2], float)
            self.assertGreaterEqual(finished[2], 0.0)
        self.assertEqual(
            set(state),
            {
                "ticker",
                "years",
                "industry",
                "fundamentals",
                "valuation",
                "risk",
                "synthesis",
            },
        )
        self.assertNotIn(self.progress_reporter, state.values())


if __name__ == "__main__":
    unittest.main()
