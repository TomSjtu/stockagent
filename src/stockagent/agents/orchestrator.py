from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from langchain_core.callbacks import BaseCallbackHandler

from stockagent.agents.errors import LLMError, classify_llm_error
from stockagent.agents.fundamentals_agent import fundamentals_subagent
from stockagent.agents.industry_agent import industry_subagent
from stockagent.agents.risk_agent import risk_subagent
from stockagent.agents.valuation_agent import valuation_subagent
from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig, apply_llm_environment
from stockagent.errors import ConfigurationError
from stockagent.observability import get_logger
from stockagent.tools.financials import get_full_analysis
from stockagent.tools.search import web_search

ORCHESTRATOR_PROMPT = """你是一名资深股票研究总监，负责协调团队完成中文股票分析报告。

团队包括：
- industry_analyst：行业趋势、竞争格局、市场地位
- fundamentals_analyst：盈利能力、现金流、财务健康、成长性
- valuation_analyst：估值合理性和同行对比
- risk_analyst：财务、运营、行业和估值风险

工作流程：
1. 使用 write_todos 规划任务
2. 通过 task 工具分别委派 industry_analyst 和 fundamentals_analyst
3. 两者完成后，委派 valuation_analyst
4. 估值完成后，委派 risk_analyst
5. 使用 read_file 读取四份分析文件
6. 合成一份结构完整、逻辑连贯、面向投资研究的中文 Markdown 报告
7. 使用 write_file 将最终报告写入 final_report.md

最终报告必须包含：摘要、行业分析、基本面分析、估值分析、风险评估、投资建议。
必须明确说明这不是投资建议，且估值部分若缺少可靠股价/市值来源，应说明限制。

重要：最后一条回复必须直接输出完整 Markdown 报告正文。

"""

_TASK_TOOL_NAME = "task"
_BUSINESS_TOOL_NAMES = frozenset(
    {"get_full_analysis", "web_search", "compute_valuation_metrics"}
)


class _AgentProgressCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._subagents_by_run_id: dict[str, str] = {}
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

        if tool_name not in _BUSINESS_TOOL_NAMES:
            return

        subagent_name = self._inherit_subagent_context(run_key, parent_key)
        if subagent_name is None:
            return

        self._logger.info("subagent %s 调用工具: %s", subagent_name, tool_name)

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

        subagent_name = self._subagents_by_run_id.pop(run_key, None)
        if subagent_name is None:
            return

        self._logger.info("subagent %s 工具返回: success", subagent_name)

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

        subagent_name = self._subagents_by_run_id.pop(run_key, None)
        if subagent_name is None:
            return

        self._logger.error("subagent %s 工具返回: failed", subagent_name)

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


def _run_key(run_id: Any | None) -> str | None:
    if run_id is None:
        return None
    return str(run_id)


def create_stock_analysis_agent(llm_config: LLMConfig):
    apply_llm_environment(llm_config)

    from deepagents import create_deep_agent

    return create_deep_agent(
        model=_build_model(llm_config),
        tools=[get_full_analysis, web_search],
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=[
            industry_subagent,
            fundamentals_subagent,
            valuation_subagent,
            risk_subagent,
        ],
    )


def _build_model(llm_config: LLMConfig):
    provider, separator, model_name = llm_config.model.partition(":")
    if not separator or not provider.strip() or not model_name.strip():
        raise ConfigurationError(
            f"LLM_MODEL must include a provider prefix, for example: {DEFAULT_LLM_MODEL}"
        )

    builders = {
        "openai": build_openai_model,
        "anthropic": build_anthropic_model,
    }
    builder = builders.get(provider.lower())
    if builder is None:
        raise ConfigurationError(f"Unsupported LLM provider: {provider}")
    return builder(llm_config, model_name)


def build_openai_model(llm_config: LLMConfig, model_name: str):
    from langchain_openai import ChatOpenAI

    llm_kwargs = {
        "model": model_name,
        "api_key": llm_config.api_key,
        "base_url": llm_config.base_url or None,
        "timeout": 180,
    }
    if _is_native_openai_base_url(llm_config.base_url):
        llm_kwargs["use_responses_api"] = True

    return ChatOpenAI(
        **llm_kwargs,
    )


def build_anthropic_model(llm_config: LLMConfig, model_name: str):
    pass


def _is_native_openai_base_url(base_url: str | None) -> bool:
    """Responses API is only safe on native OpenAI endpoints."""
    if not base_url:
        return True
    normalized_base_url = base_url
    if "://" not in normalized_base_url:
        normalized_base_url = "https://" + normalized_base_url
    host = urlparse(normalized_base_url).hostname or ""
    return host == "api.openai.com" or host.endswith(".openai.com")


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
) -> str:
    agent = create_stock_analysis_agent(llm_config)
    progress_handler = _AgentProgressCallbackHandler()
    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"请对 {ticker.upper()} 进行全面股票分析，"
                            f"覆盖最近 {years} 个财年。"
                        ),
                    }
                ]
            },
            config={"callbacks": [progress_handler]},
        )
    except LLMError:
        raise
    except Exception as exc:
        raise classify_llm_error(exc, llm_config.model) from exc
    get_logger(__name__).info("主 agent 开始汇总最终报告")
    return extract_final_report(result)


def extract_final_report(result: Mapping[str, Any]) -> str:
    files = result.get("files")
    if isinstance(files, Mapping):
        report = files.get("final_report.md")
        if isinstance(report, str) and report.strip():
            return report

    messages = result.get("messages")
    if isinstance(messages, list) and messages:
        content = getattr(messages[-1], "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )

    return str(result)
