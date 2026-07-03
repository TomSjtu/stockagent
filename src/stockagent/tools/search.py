from __future__ import annotations

import json
import os
from typing import Any
from typing import Literal

from stockagent.errors import ConfigurationError


def web_search(
    query: str,
    max_results: int = 10,
    topic: Literal["general", "news", "finance"] = "finance",
    time_range: Literal["day", "week", "month", "year"] | None = None,
) -> str:
    """Search the web for industry news, company updates, and market trends."""
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        raise ConfigurationError("TAVILY_API_KEY is required for web_search.")

    from tavily import TavilyClient

    client = TavilyClient(api_key=tavily_api_key)
    search_kwargs: dict[str, Any] = {
        "query": query,
        "max_results": max_results,
        "topic": topic,
        "search_depth": "basic",
        "include_raw_content": False,
        "timeout": 30,
    }
    if time_range:
        search_kwargs["time_range"] = time_range

    result = client.search(**search_kwargs)
    return json.dumps(_compact_search_result(result), ensure_ascii=False, indent=2)


def _compact_search_result(result: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for item in result.get("results", []):
        items.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score"),
                "published_date": item.get("published_date"),
            }
        )

    return {
        "query": result.get("query"),
        "answer": result.get("answer"),
        "results": items,
    }
