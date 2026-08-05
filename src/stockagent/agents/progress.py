from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from langchain_core.callbacks import BaseCallbackHandler

from stockagent.observability import get_logger


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


class AgentProgressCallbackHandler(BaseCallbackHandler):
    """Log known tool stages for one agent without changing agent control flow."""

    def __init__(self, agent_name: str) -> None:
        """Create a callback that correlates tool events for the named agent."""
        # run_id 是 LangChain 生命周期关联键，只用于将开始/结束日志配对
        self.agent_name = agent_name
        self._logger = get_logger("stockagent.agents.orchestrator")
        self._tool_names_by_run_id: dict[str, str] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        """Log the start of a recognized tool invocation."""
        tool_name = _tool_name(serialized)
        stage_name = _stage_name(self.agent_name, tool_name)
        if stage_name is None:
            return

        self._tool_names_by_run_id[str(run_id)] = tool_name
        self._logger.info("agent %s 开始: %s", self.agent_name, stage_name)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        """Log completion of a previously recognized tool invocation."""
        tool_name = self._tool_names_by_run_id.pop(str(run_id), None)
        if tool_name is None:
            return

        stage_name = _stage_name(self.agent_name, tool_name)
        if stage_name is not None:
            self._logger.info("agent %s 完成: %s", self.agent_name, stage_name)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        """Log failure of a previously recognized tool invocation."""
        tool_name = self._tool_names_by_run_id.pop(str(run_id), None)
        if tool_name is None:
            return

        stage_name = _stage_name(self.agent_name, tool_name)
        if stage_name is not None:
            self._logger.error("agent %s 失败: %s", self.agent_name, stage_name)


def _tool_name(serialized: Mapping[str, Any]) -> str:
    name = serialized.get("name")
    if isinstance(name, str):
        return name

    tool_id = serialized.get("id")
    if isinstance(tool_id, list) and tool_id:
        last_item = tool_id[-1]
        if isinstance(last_item, str):
            return last_item

    return ""


def _stage_name(agent_name: str, tool_name: str) -> str | None:
    return _STAGE_DISPLAY_NAMES.get((agent_name, tool_name))
