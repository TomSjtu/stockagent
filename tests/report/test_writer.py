from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from stockagent.report.evidence import EvidenceBundle
from stockagent.report.writer import write_report_artifacts


class ReportWriterTest(unittest.TestCase):
    def test_write_report_artifacts_writes_markdown_and_sources_with_same_stem(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"

            with self.assertLogs("stockagent.report.writer", level="INFO") as logs:
                artifacts = write_report_artifacts(
                    "aapl",
                    "# Report\n",
                    evidence_bundle=EvidenceBundle(),
                    output_dir=output_dir,
                    report_date=date(2026, 6, 21),
                )

            self.assertTrue(output_dir.exists())
            self.assertEqual(artifacts.markdown_path.name, "AAPL-2026-06-21.md")
            self.assertEqual(
                artifacts.sources_path.name,
                "AAPL-2026-06-21.sources.json",
            )
            self.assertEqual(artifacts.markdown_path.read_text(encoding="utf-8"), "# Report\n")
            payload = json.loads(artifacts.sources_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["ticker"], "AAPL")
            self.assertEqual(payload["report_date"], "2026-06-21")
            self.assertEqual(payload["evidence"], [])
            self.assertIn(
                "INFO:stockagent.report.writer:开始写入报告产物",
                logs.output,
            )
            self.assertIn(
                "INFO:stockagent.report.writer:报告产物写入完成: "
                f"{artifacts.markdown_path}, {artifacts.sources_path}",
                logs.output,
            )


if __name__ == "__main__":
    unittest.main()
