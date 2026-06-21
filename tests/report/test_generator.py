from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stockagent.app import AnalysisResult
from stockagent.config import RuntimeOptions
from stockagent.financials.models import FinancialRecord
from stockagent.report.generator import generate_report


class ReportGeneratorTest(unittest.TestCase):
    def test_generate_report_builds_and_writes_report_from_runtime_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "reports"
            result = AnalysisResult(
                ticker="FAKE",
                records=[
                    FinancialRecord(
                        ticker="FAKE",
                        company_name="Fake Inc.",
                        fiscal_year=2024,
                        revenue=120.0,
                    )
                ],
                profitability={},
                cash_flow={},
                financial_health={},
                growth={},
            )
            options = RuntimeOptions(
                ticker="fake",
                years=3,
                report_format="md",
                output_dir=output_dir,
            )

            output_path = generate_report(result, options)

            self.assertEqual(output_path.parent, output_dir)
            self.assertEqual(output_path.suffix, ".md")
            self.assertIn("# FAKE Stock Analysis", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
