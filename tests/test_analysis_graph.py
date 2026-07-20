from __future__ import annotations

import unittest

from stockagent.agents.orchestrator import AnalysisNodes, build_analysis_graph
from stockagent.agents.state import (
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    ValuationOutput,
)


class AnalysisGraphTest(unittest.TestCase):
    def test_graph_runs_complete_analysis_data_flow(self) -> None:
        observed_inputs: dict[str, set[str]] = {}

        def industry(state: dict) -> dict:
            observed_inputs["industry"] = set(state)
            return {
                "industry": IndustryOutput(
                    narrative=f"{state['ticker']} industry",
                    evidence=[],
                )
            }

        def fundamentals(state: dict) -> dict:
            observed_inputs["fundamentals"] = set(state)
            return {
                "fundamentals": FundamentalsOutput(
                    narrative=f"{state['years']} years fundamentals",
                    key_metrics={"revenue_growth": 0.12},
                    concerns=[],
                )
            }

        def valuation(state: dict) -> dict:
            observed_inputs["valuation"] = set(state)
            return {
                "valuation": ValuationOutput(
                    narrative=(
                        f"{state['industry'].narrative}; "
                        f"{state['fundamentals'].narrative}"
                    ),
                    pe_ratio=20.0,
                    pb_ratio=3.0,
                    ps_ratio=5.0,
                )
            }

        def risk(state: dict) -> dict:
            observed_inputs["risk"] = set(state)
            return {
                "risk": RiskOutput(
                    narrative=state["valuation"].narrative,
                    overall_rating="中",
                    key_risks=["competition"],
                    evidence=[],
                )
            }

        def synthesize(state: dict) -> dict:
            observed_inputs["synthesize"] = set(state)
            return {"final_report": f"# Report\n\n{state['risk'].narrative}"}

        graph = build_analysis_graph(
            AnalysisNodes(
                industry=industry,
                fundamentals=fundamentals,
                valuation=valuation,
                risk=risk,
                synthesize=synthesize,
            )
        )

        result = graph.invoke({"ticker": "AAPL", "years": 3})

        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["years"], 3)
        self.assertEqual(result["industry"].narrative, "AAPL industry")
        self.assertEqual(result["fundamentals"].narrative, "3 years fundamentals")
        self.assertEqual(
            result["final_report"],
            "# Report\n\nAAPL industry; 3 years fundamentals",
        )
        self.assertEqual(observed_inputs["industry"], {"ticker", "years"})
        self.assertEqual(observed_inputs["fundamentals"], {"ticker", "years"})
        self.assertEqual(
            observed_inputs["valuation"],
            {"ticker", "years", "industry", "fundamentals"},
        )
        self.assertEqual(
            observed_inputs["risk"],
            {"ticker", "years", "industry", "fundamentals", "valuation"},
        )
        self.assertEqual(
            observed_inputs["synthesize"],
            {
                "ticker",
                "years",
                "industry",
                "fundamentals",
                "valuation",
                "risk",
            },
        )

    def test_valuation_waits_for_both_upstreams_and_runs_once(self) -> None:
        valuation_inputs: list[set[str]] = []

        def industry(_state: dict) -> dict:
            return {
                "industry": IndustryOutput(
                    narrative="industry",
                    evidence=[],
                )
            }

        def fundamentals(_state: dict) -> dict:
            return {
                "fundamentals": FundamentalsOutput(
                    narrative="fundamentals",
                    key_metrics={},
                    concerns=[],
                )
            }

        def valuation(state: dict) -> dict:
            valuation_inputs.append(set(state))
            return {
                "valuation": ValuationOutput(
                    narrative="valuation",
                    pe_ratio=None,
                    pb_ratio=None,
                    ps_ratio=None,
                )
            }

        def risk(_state: dict) -> dict:
            return {
                "risk": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                )
            }

        def synthesize(_state: dict) -> dict:
            return {"final_report": "# Report"}

        graph = build_analysis_graph(
            AnalysisNodes(
                industry=industry,
                fundamentals=fundamentals,
                valuation=valuation,
                risk=risk,
                synthesize=synthesize,
            )
        )

        graph.invoke({"ticker": "AAPL", "years": 3})

        self.assertEqual(len(valuation_inputs), 1)
        self.assertTrue(
            {"industry", "fundamentals"}.issubset(valuation_inputs[0])
        )


if __name__ == "__main__":
    unittest.main()
