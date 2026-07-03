from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stockagent.agents.errors import LLMError, classify_llm_error
from stockagent.agents.fundamentals_agent import fundamentals_subagent
from stockagent.agents.industry_agent import industry_subagent
from stockagent.agents.risk_agent import risk_subagent
from stockagent.agents.valuation_agent import valuation_subagent
from stockagent.config import LLMConfig, apply_llm_environment
from stockagent.errors import ConfigurationError
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
必须明确说明这不是投资建议，且估值部分若缺少实时价格，应说明限制。

重要：最后一条回复必须直接输出完整 Markdown 报告正文。

"""


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
            "LLM_MODEL must include a provider prefix, for example: openai:gpt-5.5"
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

    return ChatOpenAI(
        model=model_name,
        api_key=llm_config.api_key,
        base_url=llm_config.base_url or None,
        use_responses_api=True,
        timeout=60,
    )


def build_anthropic_model(llm_config: LLMConfig, model_name: str):
    pass


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
) -> str:
    agent = create_stock_analysis_agent(llm_config)
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
            }
        )
    except LLMError:
        raise
    except Exception as exc:
        raise classify_llm_error(exc, llm_config.model) from exc
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
