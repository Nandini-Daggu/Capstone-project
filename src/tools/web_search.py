"""
src/tools/web_search.py
========================
DuckDuckGo web search tool with caching, retry, and circuit-breaker.
Falls back to Tavily if available and DuckDuckGo fails.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.cache import cache_manager
from src.utils.logger import get_logger
from src.utils.retry import get_circuit_breaker

log = get_logger(__name__)

_ddg_breaker = get_circuit_breaker("duckduckgo")


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query string")
    max_results: int = Field(default=5, ge=1, le=15)
    region: str = Field(default="wt-wt", description="DuckDuckGo region code")
    time_filter: Optional[str] = Field(
        default=None,
        description="Time filter: d=day, w=week, m=month, y=year",
    )


class WebSearchTool(BaseTool):
    """
    Web search tool using DuckDuckGo.

    Returns a list of {title, url, snippet, source} dicts.
    Results are cached to minimise duplicate API calls.
    Falls back to Tavily if DuckDuckGo is unavailable.
    """

    name: str = "web_search"
    description: str = (
        "Search the web for recent information. Use for finding competitor news, "
        "pricing, product updates, press releases, and market data. "
        "Input: a descriptive search query string."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(
        self,
        query: str,
        max_results: int = 5,
        region: str = "wt-wt",
        time_filter: Optional[str] = None,
    ) -> str:
        """Execute web search with caching and fallback."""
        # Check cache first
        cache_key = f"{query}:{max_results}:{region}:{time_filter}"
        cached = cache_manager.get_search(cache_key, "duckduckgo")
        if cached:
            log.debug(f"[WebSearch] Cache HIT for: {query[:50]}")
            return self._format_results(cached)

        # Try DuckDuckGo via circuit breaker
        results = []
        try:
            results = _ddg_breaker.call(self._search_ddg, query, max_results, region, time_filter)
        except Exception as ddg_exc:
            log.warning(f"[WebSearch] DuckDuckGo failed: {ddg_exc}")
            # Fallback to Tavily
            if settings.tavily_api_key:
                try:
                    results = self._search_tavily(query, max_results)
                except Exception as tavily_exc:
                    log.error(f"[WebSearch] Tavily fallback also failed: {tavily_exc}")
                    return (
                        f"Search failed for query: {query}. Both DuckDuckGo and Tavily unavailable."
                    )

        if results:
            cache_manager.set_search(cache_key, results, "duckduckgo")

        return self._format_results(results) if results else f"No results found for: {query}"

    def _search_ddg(
        self,
        query: str,
        max_results: int,
        region: str,
        time_filter: Optional[str],
    ) -> List[Dict[str, str]]:
        """Execute DuckDuckGo search."""
        results = []
        with DDGS() as ddgs:
            kwargs: Dict[str, Any] = {
                "keywords": query,
                "region": region,
                "max_results": max_results,
            }
            if time_filter:
                kwargs["timelimit"] = time_filter

            for r in ddgs.text(**kwargs):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", r.get("url", "")),
                        "snippet": r.get("body", r.get("snippet", "")),
                        "source": "duckduckgo",
                        "published_date": r.get("published", ""),
                    }
                )
        return results

    def _search_tavily(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Tavily fallback search."""
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query=query, max_results=max_results)
        results = []
        for r in response.get("results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "source": "tavily",
                    "published_date": r.get("published_date", ""),
                }
            )
        return results

    def _format_results(self, results: List[Dict[str, str]]) -> str:
        """Format results as numbered Markdown list."""
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   URL: {r.get('url', '')}\n"
                f"   {r.get('snippet', '')[:300]}\n"
                f"   Source: {r.get('source', '')} | Date: {r.get('published_date', 'unknown')}"
            )
        return "\n\n".join(lines)


# Singleton tool instance for agent registration
web_search_tool = WebSearchTool()

__all__ = ["WebSearchTool", "web_search_tool"]
