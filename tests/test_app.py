from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from stockagent.agents.orchestrator import GeneratedReport
from stockagent.app import run_stock_analysis
from stockagent.config import AppConfig, CLIOptions, LLMConfig
from stockagent.errors import ConfigurationError
from stockagent.report.evidence import EvidenceBundle
from stockagent.report.writer import ReportArtifacts


class RunStockAnalysisTest(unittest.TestCase):
    def test_run_stock_analysis_requires_tavily_api_key(self) -> None:
        options = CLIOptions(ticker="fake", years=2)

        with (
            patch(
                "stockagent.app.load_app_config",
                side_effect=ConfigurationError("TAVILY_API_KEY is required"),
            ),
            self.assertRaisesRegex(ConfigurationError, "TAVILY_API_KEY"),
        ):
            run_stock_analysis(options)

    def test_run_stock_analysis_writes_agent_delivery_artifacts(self) -> None:
        options = CLIOptions(ticker="fake", years=2)
        config = AppConfig(
            llm=LLMConfig(
                api_key="llm-key",
                base_url="https://llm.example.test/v1",
                model="openai:test-model",
            ),
            tavily_api_key="tavily-key",
            edgar_identity="Stock Agent contact@example.test",
        )
        report = GeneratedReport(
            markdown="# Agent Report\n",
            evidence_bundle=EvidenceBundle(),
        )
        artifacts = ReportArtifacts(
            markdown_path=Path("output/FAKE.md"),
            sources_path=Path("output/FAKE.sources.json"),
        )

        with (
            patch("stockagent.app.load_app_config", return_value=config),
            patch("edgar.set_identity") as set_identity,
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

        set_identity.assert_called_once_with(config.edgar_identity)
        run_agent.assert_called_once_with("fake", 2, config.llm)
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
        config = AppConfig(
            llm=LLMConfig(
                api_key="llm-key",
                base_url="https://llm.example.test/v1",
                model="openai:test-model",
            ),
            tavily_api_key="tavily-key",
            edgar_identity="Stock Agent contact@example.test",
        )

        with (
            patch("stockagent.app.load_app_config", return_value=config),
            patch("edgar.set_identity"),
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
