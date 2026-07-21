from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from stockagent.errors import ConfigurationError

LogLevel = Literal["debug", "info", "warning", "error"]
DEFAULT_LLM_MODEL = "openai:gpt-5.5"
DEFAULT_EDGAR_IDENTITY = "stockagent stockagent@example.com"


def default_output_dir() -> Path:
    """Return the default directory for generated report artifacts."""
    return Path.cwd() / "output"


@dataclass(frozen=True)
class LLMConfig:
    """Connection settings for the language model used by the report workflow."""

    # 传给聊天模型客户端的 API 密钥
    api_key: str
    # 聊天模型服务的基础 URL；空字符串表示使用客户端默认地址
    base_url: str
    # 形如 "openai:model-name" 的模型标识，供 build_model 选择客户端和模型名
    model: str


@dataclass(frozen=True)
class CLIOptions:
    """Validated command-line arguments for one analysis run."""

    # CLI 位置参数传入的证券代码
    ticker: str
    # CLI --years 传入的年度记录数量
    years: int
    # CLI --output-dir 传入的报告文件写入目录
    output_dir: Path = field(default_factory=default_output_dir)
    # CLI --log-level 传入的控制台日志级别
    log_level: LogLevel = "info"


def load_llm_config() -> LLMConfig:
    """Load LLM settings from the environment or fail when credentials are absent."""
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "LLM_API_KEY is required for agent reports. "
            "Set it in .env before running the default CLI analysis."
        )
    return LLMConfig(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", ""),
        model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
    )
