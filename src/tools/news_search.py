"""
src/tools/news_search.py
=========================
News search tool combining DuckDuckGo News + Google News RSS.
Specialised for competitor news, press releases, and market updates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Type
from urllib.parse import quote_plus

import feedparser
from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

from src.utils.cache import cache_manager
from src.utils.logger import get_logger
from src.utils.retry import get_circuit_breaker

log = get_logger(__name__)

_news_breaker = get_circuit_breaker("news_search")


class NewsSearchInput(BaseModel):
    query: str = Field(..., description="News search query, e.g. 'Salesforce funding 2024'")
    max_results: int = Field(default=8, ge=1, le=20)
    days_back: int = Field(default=7, ge=1, le=90, description="How many days back to search")
    include_rss: bool = Field(default=True, description="Include Google News RSS results")


class NewsSearchTool(BaseTool):
    """
    News search tool combining multiple news sources:
    - DuckDuckGo News (real-time)
    - Google News RSS (structured, with dates)

    Returns structured news items with titles, URLs, snippets, and dates.
    """

    name: str = "news_search"
    description: str = (
        "Search for recent news articles about competitors, market trends, product launches, "
        "funding rounds, and industry events. Returns structured news results with dates and sources. "
        "Input: a news search query string."
    )
    args_schema: Type[BaseModel] = NewsSearchInput

    def _run(
        self,
        query: str,
        max_results: int = 8,
        days_back: int = 7,
        include_rss: bool = True,
    ) -> str:
        """Execute multi-source news search with deduplication."""
        cache_key = f"news:{query}:{max_results}:{days_back}"
        cached = cache_manager.get_search(cache_key, "news")
        if cached:
            log.debug(f"[NewsSearch] Cache HIT: {query[:50]}")
            return self._format_results(cached)

        all_results: List[Dict] = []

        # DuckDuckGo News
        try:
            ddg_results = _news_breaker.call(self._ddg_news, query, max_results, days_back)
            all_results.extend(ddg_results)
        except Exception as exc:
            log.warning(f"[NewsSearch] DuckDuckGo news failed: {exc}")

        # Google News RSS
        if include_rss:
            try:
                rss_results = self._google_news_rss(query, max_results)
                all_results.extend(rss_results)
            except Exception as exc:
                log.warning(f"[NewsSearch] Google News RSS failed: {exc}")

        # Deduplicate by URL
        seen_urls = set()
        deduped = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(r)

        # Sort by date (newest first), take top N
        deduped.sort(key=lambda x: x.get("published_date", ""), reverse=True)
        deduped = deduped[:max_results]

        if deduped:
            cache_manager.set_search(cache_key, deduped, "news")

        return self._format_results(deduped) if deduped else f"No news found for: {query}"

    def _ddg_news(self, query: str, max_results: int, days_back: int) -> List[Dict]:
        """Fetch news from DuckDuckGo News."""
        results = []
        time_filter = "w" if days_back <= 7 else ("m" if days_back <= 30 else "y")
        with DDGS() as ddgs:
            for r in ddgs.news(keywords=query, max_results=max_results, timelimit=time_filter):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("body", ""),
                        "source_name": r.get("source", "DuckDuckGo News"),
                        "published_date": r.get("date", ""),
                        "source": "duckduckgo_news",
                    }
                )
        return results

    def _google_news_rss(self, query: str, max_results: int) -> List[Dict]:
        """Fetch news from Google News RSS feed."""
        encoded_query = quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}" f"&hl=en-US&gl=US&ceid=US:en"
        results = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_results]:
                # Parse date
                published = ""
                if hasattr(entry, "published"):
                    try:
                        dt = datetime(*entry.published_parsed[:6])
                        published = dt.strftime("%Y-%m-%d")
                    except Exception:
                        published = entry.published

                results.append(
                    {
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "snippet": entry.get("summary", "")[:500],
                        "source_name": entry.get("source", {}).get("title", "Google News"),
                        "published_date": published,
                        "source": "google_news_rss",
                    }
                )
        except Exception as exc:
            log.debug(f"[NewsSearch] RSS parse error: {exc}")

        return results

    def _format_results(self, results: List[Dict]) -> str:
        """Format news results as structured Markdown."""
        if not results:
            return "No news articles found."

        lines = [f"Found {len(results)} news articles:\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"**[{i}] {r.get('title', 'No title')}**\n"
                f"- URL: {r.get('url', '')}\n"
                f"- Source: {r.get('source_name', 'Unknown')} | "
                f"Date: {r.get('published_date', 'Unknown')}\n"
                f"- Summary: {r.get('snippet', '')[:300]}"
            )
        return "\n\n".join(lines)


# Singleton
news_search_tool = NewsSearchTool()

__all__ = ["NewsSearchTool", "news_search_tool"]
