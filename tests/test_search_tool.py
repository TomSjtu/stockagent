from __future__ import annotations

import json
import os
import sys
import types
import unittest
from unittest.mock import Mock

from stockagent.tools.search import web_search


class SearchToolTest(unittest.TestCase):
    def test_web_search_passes_simple_tavily_parameters(self) -> None:
        old_key = os.environ.get("TAVILY_API_KEY")
        old_module = sys.modules.get("tavily")
        client = Mock()
        client.search.return_value = {
            "query": "AAPL industry",
            "answer": None,
            "results": [
                {
                    "title": "Result",
                    "url": "https://example.test",
                    "content": "Summary",
                    "score": 0.9,
                    "published_date": "2026-07-01",
                }
            ],
        }
        module = types.SimpleNamespace(TavilyClient=Mock(return_value=client))

        try:
            os.environ["TAVILY_API_KEY"] = "test-key"
            sys.modules["tavily"] = module

            payload = json.loads(
                web_search(
                    "AAPL industry",
                    max_results=7,
                    topic="news",
                    time_range="month",
                )
            )
        finally:
            if old_key is None:
                os.environ.pop("TAVILY_API_KEY", None)
            else:
                os.environ["TAVILY_API_KEY"] = old_key
            if old_module is None:
                sys.modules.pop("tavily", None)
            else:
                sys.modules["tavily"] = old_module

        module.TavilyClient.assert_called_once_with(api_key="test-key")
        client.search.assert_called_once_with(
            query="AAPL industry",
            max_results=7,
            topic="news",
            search_depth="basic",
            include_raw_content=False,
            timeout=30,
            time_range="month",
        )
        self.assertEqual(payload["results"][0]["published_date"], "2026-07-01")


if __name__ == "__main__":
    unittest.main()
