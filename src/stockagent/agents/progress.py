from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from contextlib import AbstractContextManager
from threading import Event, Lock, Thread
from types import TracebackType
from typing import Any, Protocol

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ToolMessage,
)


class ProgressReporter(Protocol):
    """Receive progress events without depending on a presentation library."""

    def agent_started(self, agent: str) -> None:
        """Report that one agent has started."""
        ...

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        """Report that one agent has finished and include its elapsed time."""
        ...

    def tool_started(self, agent: str, tool: str) -> None:
        """Report that an agent has started one tool call."""
        ...

    def tool_finished(self, agent: str, tool: str) -> None:
        """Report that an agent has finished one tool call."""
        ...

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        """Report that an agent tool call has failed."""
        ...

    def model_output(self, agent: str, produced_characters: int) -> None:
        """Report how many model-output characters one agent has produced."""
        ...


_HEARTBEAT_INTERVAL_SECONDS = 1.0


class ModelGenerationProgress(
    AbstractContextManager["ModelGenerationProgress"]
):
    """Keep model generation visibly alive while preferring real output counts."""

    def __init__(
        self,
        progress_reporter: ProgressReporter,
        agent_name: str,
    ) -> None:
        self._progress_reporter = progress_reporter
        self._agent_name = agent_name
        self._interval = _HEARTBEAT_INTERVAL_SECONDS
        self._stop = Event()
        self._lock = Lock()
        self._active_tools = 0
        self._produced_characters = 0
        self._streaming_available = False
        self._thread: Thread | None = None

    def __enter__(self) -> ModelGenerationProgress:
        self._thread = Thread(
            target=self._run,
            name=f"stockagent-heartbeat-{self._agent_name}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    def agent_started(self, agent: str) -> None:
        self._progress_reporter.agent_started(agent)

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        self._progress_reporter.agent_finished(agent, elapsed_seconds)

    def tool_started(self, agent: str, tool: str) -> None:
        with self._lock:
            self._active_tools += 1
            self._progress_reporter.tool_started(agent, tool)

    def tool_finished(self, agent: str, tool: str) -> None:
        with self._lock:
            self._progress_reporter.tool_finished(agent, tool)
            self._active_tools = max(0, self._active_tools - 1)
            if self._active_tools == 0:
                self._streaming_available = False

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        with self._lock:
            self._progress_reporter.tool_failed(agent, tool, detail)
            self._active_tools = max(0, self._active_tools - 1)
            if self._active_tools == 0:
                self._streaming_available = False

    def model_output(self, agent: str, produced_characters: int) -> None:
        with self._lock:
            self._produced_characters = produced_characters
            self._streaming_available = True
            self._progress_reporter.model_output(agent, produced_characters)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            with self._lock:
                if self._active_tools == 0 and not self._streaming_available:
                    self._progress_reporter.model_output(
                        self._agent_name,
                        self._produced_characters,
                    )


_STAGE_DISPLAY_NAMES = {
    ("industry_analyst", "web_search"): "搜索市场与行业信息",
    ("fundamentals_analyst", "get_fundamentals_analysis"): "获取并分析公司基本面",
    ("valuation_analyst", "web_search"): "搜索股价、市值与同行估值信息",
    ("valuation_analyst", "compute_valuation_metrics"): "计算估值指标",
    ("risk_analyst", "web_search"): "搜索近期公司风险信息",
}

def report_agent_update(
    update: object,
    *,
    agent_name: str,
    progress_reporter: ProgressReporter,
    structured_output_tool: str | None = None,
) -> None:
    """Translate one agent update into presentation-independent progress events."""
    for message in _messages_in(update):
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                tool_name = tool_call.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                if tool_name == structured_output_tool:
                    continue
                progress_reporter.tool_started(
                    agent_name,
                    _stage_name(agent_name, tool_name),
                )
        elif isinstance(message, ToolMessage):
            tool_name = message.name or "unknown tool"
            if tool_name == structured_output_tool:
                continue
            stage_name = _stage_name(agent_name, tool_name)
            if message.status == "error":
                progress_reporter.tool_failed(
                    agent_name,
                    stage_name,
                    _message_detail(message.content),
                )
            else:
                progress_reporter.tool_finished(agent_name, stage_name)


def report_model_message(
    message_event: object,
    *,
    agent_name: str,
    produced_characters: int,
    progress_reporter: ProgressReporter,
) -> int:
    """Count one model message delta without exposing its structured content."""
    if not isinstance(message_event, tuple) or len(message_event) != 2:
        return produced_characters
    message, _metadata = message_event
    if not isinstance(message, AIMessageChunk):
        return produced_characters

    delta_characters = len(message.text) + sum(
        len(args)
        for tool_call in message.tool_call_chunks
        if isinstance((args := tool_call.get("args")), str)
    )
    if delta_characters == 0:
        return produced_characters

    produced_characters += delta_characters
    progress_reporter.model_output(agent_name, produced_characters)
    return produced_characters


def _messages_in(value: object) -> Iterable[BaseMessage]:
    if isinstance(value, BaseMessage):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _messages_in(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _messages_in(nested)


def _message_detail(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _stage_name(agent_name: str, tool_name: str) -> str:
    return _STAGE_DISPLAY_NAMES.get((agent_name, tool_name), tool_name)
