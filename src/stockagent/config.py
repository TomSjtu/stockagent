from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ReportFormat = Literal["md", "html", "pdf"]


def default_output_dir() -> Path:
    return Path.cwd() / "output"


@dataclass(frozen=True)
class AppConfig:
    edgar_identity: str


@dataclass(frozen=True)
class RuntimeOptions:
    ticker: str
    years: int
    report_format: ReportFormat = "md"
    output_dir: Path = field(default_factory=default_output_dir)


def load_app_config() -> AppConfig:
    return AppConfig(
        edgar_identity=os.getenv("STOCKAGENT_EDGAR_IDENTITY", "stock stockagent@gmail.com"),
    )
