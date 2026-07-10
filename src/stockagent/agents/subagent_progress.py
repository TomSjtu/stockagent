from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from stockagent.observability import get_logger

_TASK_TOOL_NAME = "task"
_STAGE_DISPLAY_NAMES = {
    ("industry_analyst", "web_search"): "搜索市场与行业信息",
    ("fundamentals_analyst", "fetch_company_financials"): "获取公司财务数据",
    ("fundamentals_analyst", "compute_profitability_metrics"): "分析盈利能力",
    ("fundamentals_analyst", "compute_growth_metrics"): "分析成长性",
    ("fundamentals_analyst", "compute_cash_flow_metrics"): "分析现金流",
    ("fundamentals_analyst", "compute_financial_health_metrics"): "分析财务健康性",
    ("valuation_analyst", "web_search"): "搜索股价、市值与同行估值信息",
    ("valuation_analyst", "fetch_company_financials"): "获取估值所需财务数据",
    ("valuation_analyst", "compute_valuation_metrics"): "计算估值指标",
}


class SubagentProgressCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        self._logger = get_logger("stockagent.agents.orchestrator")
        self._subagents_by_run_id: dict[str, str] = {}
        self._tool_context_by_run_id: dict[str, tuple[str, str]] = {}
        self._task_run_ids: set[str] = set()

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self._inherit_subagent_context(str(run_id), _run_key(parent_run_id))

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        if run_key not in self._task_run_ids:
            self._subagents_by_run_id.pop(run_key, None)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        if run_key not in self._task_run_ids:
            self._subagents_by_run_id.pop(run_key, None)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = _tool_name(serialized)
        run_key = str(run_id)
        parent_key = _run_key(parent_run_id)

        if tool_name == _TASK_TOOL_NAME:
            subagent_name = _subagent_name(inputs)
            if subagent_name is None:
                return
            self._subagents_by_run_id[run_key] = subagent_name
            self._task_run_ids.add(run_key)
            self._logger.info("启动 subagent: %s", subagent_name)
            return

        subagent_name = self._inherit_subagent_context(run_key, parent_key)
        if subagent_name is None:
            return

        stage_name = _stage_name(subagent_name, tool_name)
        if stage_name is None:
            return

        self._tool_context_by_run_id[run_key] = (subagent_name, tool_name)
        self._logger.info("subagent %s 开始: %s", subagent_name, stage_name)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        if run_key in self._task_run_ids:
            self._task_run_ids.remove(run_key)
            subagent_name = self._subagents_by_run_id.pop(run_key, None)
            if subagent_name is None:
                return
            self._logger.info("subagent %s 完成", subagent_name)
            return

        tool_context = self._tool_context_by_run_id.pop(run_key, None)
        self._subagents_by_run_id.pop(run_key, None)
        if tool_context is None:
            return

        subagent_name, tool_name = tool_context
        stage_name = _stage_name(subagent_name, tool_name)
        if stage_name is None:
            return

        self._logger.info("subagent %s 完成: %s", subagent_name, stage_name)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        if run_key in self._task_run_ids:
            self._task_run_ids.remove(run_key)
            subagent_name = self._subagents_by_run_id.pop(run_key, None)
            if subagent_name is None:
                return
            self._logger.error("subagent %s 失败: %s", subagent_name, error)
            return

        tool_context = self._tool_context_by_run_id.pop(run_key, None)
        self._subagents_by_run_id.pop(run_key, None)
        if tool_context is None:
            return

        subagent_name, tool_name = tool_context
        stage_name = _stage_name(subagent_name, tool_name)
        if stage_name is None:
            return

        self._logger.error("subagent %s 失败: %s", subagent_name, stage_name)

    def _inherit_subagent_context(
        self,
        run_key: str,
        parent_key: str | None,
    ) -> str | None:
        subagent_name = self._subagents_by_run_id.get(run_key)
        if subagent_name is not None:
            return subagent_name

        if parent_key is None:
            return None

        subagent_name = self._subagents_by_run_id.get(parent_key)
        if subagent_name is None:
            return None

        self._subagents_by_run_id[run_key] = subagent_name
        return subagent_name


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


def _subagent_name(inputs: Mapping[str, Any] | None) -> str | None:
    if inputs is None:
        return None
    value = inputs.get("subagent_type")
    if isinstance(value, str) and value:
        return value
    return None


def _stage_name(subagent_name: str, tool_name: str) -> str | None:
    return _STAGE_DISPLAY_NAMES.get((subagent_name, tool_name))


def _run_key(run_id: Any | None) -> str | None:
    if run_id is None:
        return None
    return str(run_id)
