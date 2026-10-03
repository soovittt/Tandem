"""
Web search as a tool, behind a swappable provider.

The `SearchProvider` protocol is the seam: Tavily today, Parallel/Exa/Brave later,
each a ~30-line adapter. `WebSearchTool` depends only on the protocol, so the
agent never knows or cares which search engine is underneath. This is the same
strategy pattern we use for the LLM backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from tandem.domain.tool import Source, ToolResult
from tandem.tools.base import Tool


@dataclass(frozen=True)
class SearchHit:
    """One search result: enough text for the model + a URL to cite."""

    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    """Anything that can turn a query into ranked hits."""

    name: str

    def search(self, query: str, *, max_results: int = 5) -> list[SearchHit]: ...


class TavilyProvider:
    """SearchProvider backed by the Tavily API (has a free tier)."""

    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, *, max_results: int = 5) -> list[SearchHit]:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return [
            SearchHit(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in results
        ]


class WebSearchTool(Tool):
    """Let the model search the web and get back cited, LLM-ready snippets."""

    name = "web_search"
    description = (
        "Search the web for current information. Returns titles, snippets, and "
        "source URLs. Cite the sources in your answer."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
            "max_results": {
                "type": "integer",
                "description": "How many results (default 5).",
            },
        },
        "required": ["query"],
    }

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    def run(self, **kwargs: Any) -> ToolResult:
        hits = self._provider.search(
            kwargs["query"], max_results=kwargs.get("max_results", 5)
        )
        if not hits:
            return ToolResult(content="No results found.")
        blocks = [
            f"[{i}] {hit.title}\n{hit.snippet}\nSource: {hit.url}"
            for i, hit in enumerate(hits, start=1)
        ]
        sources = [Source(title=hit.title, url=hit.url) for hit in hits]
        return ToolResult(content="\n\n".join(blocks), sources=sources)
