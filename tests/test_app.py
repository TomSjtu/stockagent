from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from stockagent.agents.orchestrator import GeneratedReport
from stockagent.app import run_stock_analysis
from stockagent.config import CLIOptions
from stockagent.errors import ConfigurationError
from stockagent.report.evidence import EvidenceBundle
from stockagent.report.writer import ReportArtifacts


class RunStockAnalysisTest(unittest.TestCase):
    def test_run_stock_analysis_requires_tavily_api_key(self) -> None:
        options = CLIOptions(ticker="fake", years=2)

        with (
            patch("stockagent.app.load_llm_config", return_value="llm-config"),
            patch.dict("stockagent.app.os.environ", {"TAVILY_API_KEY": ""}),
            self.assertRaisesRegex(ConfigurationError, "TAVILY_API_KEY"),
        ):
            run_stock_analysis(options)

    def test_run_stock_analysis_writes_agent_delivery_artifacts(self) -> None:
        options = CLIOptions(ticker="fake", years=2)
        report = GeneratedReport(
            markdown="# Agent Report\n",
            evidence_bundle=EvidenceBundle(),
        )
        artifacts = ReportArtifacts(
            markdown_path=Path("output/FAKE.md"),
            sources_path=Path("output/FAKE.sources.json"),
        )

        with (
            patch("stockagent.app.load_llm_config", return_value="llm-config"),
            patch.dict(
                "stockagent.app.os.environ", {"TAVILY_API_KEY": "tavily-key"}
            ),
            patch(
                "stockagent.agents.orchestrator.run_stock_analysis_agent",
                return_value=report,
            ) as run_agent,
            patch(
                "stockagent.report.writer.write_report_artifacts",
                return_value=artifacts,
            ) as write_report,
        ):
            output_artifacts = run_stock_analysis(options)

        run_agent.assert_called_once_with("fake", 2, "llm-config")
        write_report.assert_called_once_with(
            "fake",
            "# Agent Report\n",
            evidence_bundle=report.evidence_bundle,
            output_dir=options.output_dir,
            report_date=ANY,
        )
        self.assertEqual(output_artifacts, artifacts)

    def test_run_stock_analysis_logs_main_stages(self) -> None:
        options = CLIOptions(ticker="fake", years=2)

        with (
            patch("stockagent.app.load_llm_config", return_value="llm-config"),
            patch.dict(
                "stockagent.app.os.environ", {"TAVILY_API_KEY": "tavily-key"}
            ),
            patch(
                "stockagent.agents.orchestrator.run_stock_analysis_agent",
                return_value=GeneratedReport(
                    markdown="# Agent Report\n",
                    evidence_bundle=EvidenceBundle(),
                ),
            ),
            patch(
                "stockagent.report.writer.write_report_artifacts",
                return_value=ReportArtifacts(
                    markdown_path=Path("output/FAKE.md"),
                    sources_path=Path("output/FAKE.sources.json"),
                ),
            ),
            self.assertLogs("stockagent.app", level="INFO") as logs,
        ):
            run_stock_analysis(options)

        self.assertIn("INFO:stockagent.app:加载 LLM 配置完成", logs.output)
        self.assertIn("INFO:stockagent.app:启动主分析 agent", logs.output)
        self.assertIn("INFO:stockagent.app:主分析 agent 完成", logs.output)
        self.assertIn("INFO:stockagent.app:开始写入报告", logs.output)


if __name__ == "__main__":
    unittest.main()
