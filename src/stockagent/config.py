from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from stockagent.errors import ConfigurationError

ReportFormat = Literal["md", "html", "pdf"]


def default_output_dir() -> Path:
    return Path.cwd() / "output"


@dataclass(frozen=True)
class AppConfig:
    edgar_identity: str


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class RuntimeOptions:
    ticker: str
    years: int
    report_format: ReportFormat = "md"
    output_dir: Path = field(default_factory=default_output_dir)


def load_app_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        edgar_identity=os.getenv("STOCKAGENT_EDGAR_IDENTITY", "stock stockagent@gmail.com"),
    )


def load_llm_config() -> LLMConfig:
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
        model=os.getenv("LLM_MODEL", "openai:gpt-5.4"),
    )


def apply_llm_environment(config: LLMConfig) -> None:
    provider, _, _model_name = config.model.partition(":")
    provider = provider.lower()

    if provider == "anthropic":
        os.environ.setdefault("ANTHROPIC_API_KEY", config.api_key)
    elif provider == "openai":
        os.environ.setdefault("OPENAI_API_KEY", config.api_key)
        if config.base_url:
            os.environ.setdefault("OPENAI_BASE_URL", config.base_url)
