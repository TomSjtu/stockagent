from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ReportFormat = Literal["text", "md", "html", "pdf"]

@dataclass(frozen=True)
class AppConfig:
    edgar_identity: str


@dataclass(frozen=True)
class RuntimeOptions:
    ticker: str
    years: int
    report_format: ReportFormat = "text"


def load_app_config() -> AppConfig:
    return AppConfig(
        edgar_identity=os.getenv("STOCKAGENT_EDGAR_IDENTITY", "stock stockagent@gmail.com"),
    )
