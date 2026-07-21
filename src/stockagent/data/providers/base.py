from __future__ import annotations

from typing import Protocol

from stockagent.financials import FinancialRecord


class FinancialsProvider(Protocol):
    """Common interface for providers that supply standardized financial records."""

    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        """Return standardized annual records for the requested recent-year window."""
        ...
