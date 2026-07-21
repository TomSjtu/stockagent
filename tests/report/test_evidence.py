from __future__ import annotations

import json
import unittest
from datetime import date

from pydantic import ValidationError

from stockagent.agents.state import Evidence, MarketInputs
from stockagent.financials import SecFilingReference
from stockagent.report.evidence import EvidenceBundle, serialize_sources


class EvidenceSerializationTest(unittest.TestCase):
    def test_evidence_bundle_rejects_duplicate_cited_ids(self) -> None:
        evidence = Evidence(
            id="industry-1",
            kind="web",
            title="Industry source",
            url="https://example.test/industry",
            source_agent="industry_analyst",
        )

        with self.assertRaises(ValidationError):
            EvidenceBundle(
                evidence=[evidence],
                cited_evidence_ids=["industry-1", "industry-1"],
            )

    def test_evidence_bundle_rejects_duplicate_evidence_ids(self) -> None:
        evidence = Evidence(
            id="industry-1",
            kind="web",
            title="Industry source",
            url="https://example.test/industry",
            source_agent="industry_analyst",
        )

        with self.assertRaises(ValidationError):
            EvidenceBundle(evidence=[evidence, evidence])

    def test_evidence_bundle_rejects_cited_ids_not_in_selected_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle(cited_evidence_ids=["unknown-1"])

    def test_serialize_sources_preserves_selected_evidence_and_missing_values(self) -> None:
        bundle = EvidenceBundle(
            evidence=[
                Evidence(
                    id="industry-1",
                    kind="web",
                    title="Industry source",
                    url="https://example.test/industry",
                    publisher=None,
                    published_date=None,
                    excerpt="Selected excerpt",
                    source_agent="industry_analyst",
                )
            ],
            cited_evidence_ids=["industry-1"],
            market_inputs=MarketInputs(
                price=125.5,
                market_cap=2_500_000_000.0,
                currency=None,
                as_of=None,
                evidence_id="industry-1",
            ),
            financial_filings=[
                SecFilingReference(
                    form="10-K",
                    fiscal_year=2025,
                    period_end=date(2025, 1, 26),
                    filed_at=date(2025, 2, 26),
                    cik="1045810",
                    accession_number="0001045810-25-000021",
                    primary_document="nvda-20250126.htm",
                    url=(
                        "https://www.sec.gov/Archives/edgar/data/1045810/"
                        "000104581025000021/nvda-20250126.htm"
                    ),
                )
            ],
        )

        payload = json.loads(
            serialize_sources(
                ticker="nvda",
                report_date=date(2026, 7, 20),
                evidence_bundle=bundle,
            )
        )

        self.assertEqual(payload["ticker"], "NVDA")
        self.assertEqual(payload["report_date"], "2026-07-20")
        self.assertEqual(payload["cited_evidence_ids"], ["industry-1"])
        self.assertIsNone(payload["evidence"][0]["publisher"])
        self.assertIsNone(payload["evidence"][0]["published_date"])
        self.assertIsNone(payload["market_inputs"]["currency"])
        self.assertIsNone(payload["market_inputs"]["as_of"])
        self.assertEqual(payload["financial_filings"][0]["fiscal_year"], 2025)
        self.assertEqual(payload["financial_filings"][0]["filed_at"], "2025-02-26")


if __name__ == "__main__":
    unittest.main()
