from __future__ import annotations

from collections.abc import Collection, Iterable
from datetime import date, datetime
from typing import Protocol

from stockagent.financials import SecFilingReference

SEC_ARCHIVE_BASE_URL = "https://www.sec.gov/Archives/edgar/data"


class AnnualFilingCompany(Protocol):
    """The subset of an EDGAR company used to resolve annual filing metadata."""

    def get_filings(self, **kwargs: object) -> Iterable[object]:
        """Return provider filing objects matching the requested filters."""
        ...


def resolve_annual_filings(
    company: AnnualFilingCompany,
    fiscal_years: Collection[int],
) -> dict[int, SecFilingReference]:
    """Resolve the latest 10-K or 10-K/A for each requested fiscal year."""
    requested_years = set(fiscal_years)
    references: dict[int, SecFilingReference] = {}

    # 遍历 10-K 和 10-K/A；同一财年只保留排序键最大的 filing 引用
    for filing in company.get_filings(form="10-K", amendments=True):
        reference = _to_reference(filing)
        if reference is None or reference.fiscal_year not in requested_years:
            continue

        current = references.get(reference.fiscal_year)
        if current is None or _filing_sort_key(reference) > _filing_sort_key(current):
            references[reference.fiscal_year] = reference

    return references


def _to_reference(filing: object) -> SecFilingReference | None:
    """Convert a provider filing only when it can form a complete audit link."""
    form = getattr(filing, "form", None)
    period_end = _to_date(getattr(filing, "report_date", None))
    filed_at = _to_date(getattr(filing, "filing_date", None))
    cik = _normalize_cik(getattr(filing, "cik", None))
    accession_number = getattr(filing, "accession_number", None)
    primary_document = getattr(filing, "primary_document", None)

    # 缺少表单、日期、CIK、accession 或主文档时返回 None；齐全时构造 Archive URL
    if (
        form not in {"10-K", "10-K/A"}
        or period_end is None
        or filed_at is None
        or cik is None
        or not isinstance(accession_number, str)
        or not accession_number
        or not isinstance(primary_document, str)
        or not primary_document
    ):
        return None

    accession_path = accession_number.replace("-", "")
    return SecFilingReference(
        form=form,
        fiscal_year=period_end.year,
        period_end=period_end,
        filed_at=filed_at,
        cik=cik,
        accession_number=accession_number,
        primary_document=primary_document,
        url=(f"{SEC_ARCHIVE_BASE_URL}/{cik}/{accession_path}/{primary_document}"),
    )


def _to_date(value: object) -> date | None:
    """Normalize provider date values or return None for unsupported values."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _normalize_cik(value: object) -> str | None:
    """Normalize a positive CIK to its archive-path representation."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if isinstance(value, str) and value.isdigit():
        normalized = value.lstrip("0")
        return normalized or None
    return None


def _filing_sort_key(reference: SecFilingReference) -> tuple[date, bool, str]:
    """Order duplicate annual filings by recency, amendment status, and accession."""
    return (
        reference.filed_at,
        reference.form == "10-K/A",
        reference.accession_number,
    )
