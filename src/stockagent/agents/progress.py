from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


class ProgressReporter(Protocol):
    """Receive progress events without depending on a presentation library."""

    def agent_started(self, agent: str) -> None:
        """Report that one agent has started."""
        ...

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        """Report that one agent has finished and include its elapsed time."""
        ...

    def tool_started(self, agent: str, tool: str, args_summary: str) -> None:
        """Report that an agent has started one tool call."""
        ...

    def tool_finished(self, agent: str, tool: str) -> None:
        """Report that an agent has finished one tool call."""
        ...

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        """Report that an agent tool call has failed."""
        ...

    def tokens(self, agent: str, produced: int) -> None:
        """Report the amount of model output produced for one agent."""
        ...


_STAGE_DISPLAY_NAMES = {
    ("industry_analyst", "web_search"): "搜索市场与行业信息",
    ("fundamentals_analyst", "get_fundamentals_analysis"): "获取并分析公司基本面",
    ("valuation_analyst", "web_search"): "搜索股价、市值与同行估值信息",
    ("valuation_analyst", "compute_valuation_metrics"): "计算估值指标",
    ("risk_analyst", "web_search"): "搜索近期公司风险信息",
}

_ARGS_SUMMARY_WIDTH = 60


def report_agent_update(
    update: object,
    *,
    agent_name: str,
    progress_reporter: ProgressReporter,
) -> None:
    """Translate one agent update into presentation-independent progress events."""
    for message in _messages_in(update):
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                tool_name = tool_call.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                progress_reporter.tool_started(
                    agent_name,
                    _stage_name(agent_name, tool_name),
                    _args_summary(tool_call.get("args")),
                )
        elif isinstance(message, ToolMessage):
            tool_name = message.name or "unknown tool"
            stage_name = _stage_name(agent_name, tool_name)
            if message.status == "error":
                progress_reporter.tool_failed(
                    agent_name,
                    stage_name,
                    _message_detail(message.content),
                )
            else:
                progress_reporter.tool_finished(agent_name, stage_name)


def _messages_in(value: object) -> Iterable[BaseMessage]:
    if isinstance(value, BaseMessage):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _messages_in(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _messages_in(nested)


def _args_summary(args: object) -> str:
    if args is None:
        return ""
    if isinstance(args, str):
        summary = args
    else:
        try:
            summary = json.dumps(
                args,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError):
            summary = str(args)
    if len(summary) <= _ARGS_SUMMARY_WIDTH:
        return summary
    return f"{summary[: _ARGS_SUMMARY_WIDTH - 1]}…"


def _message_detail(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _stage_name(agent_name: str, tool_name: str) -> str:
    return _STAGE_DISPLAY_NAMES.get((agent_name, tool_name), tool_name)
