"""
src/tools/market_tool.py
=========================
Market intelligence tool for extracting structured competitive data.
Searches for funding, acquisitions, financial news, and market reports.
"""

from __future__ import annotations

from typing import Dict, List, Type

from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

from src.utils.cache import cache_manager
from src.utils.logger import get_logger
from src.utils.retry import get_circuit_breaker

log = get_logger(__name__)

_market_breaker = get_circuit_breaker("market_tool")


class MarketInput(BaseModel):
    company: str = Field(..., description="Company name to research")
    data_type: str = Field(
        default="all",
        description=(
            "Type of market data: "
            "'funding', 'acquisition', 'financial', 'executive', 'product', 'all'"
        ),
    )
    days_back: int = Field(default=30, ge=1, le=365)


# Search query templates per data type
QUERY_TEMPLATES: Dict[str, List[str]] = {
    "funding": [
        "{company} funding round 2024 2025",
        "{company} investment series venture capital",
        "{company} raised million billion",
    ],
    "acquisition": [
        "{company} acquisition merger 2024 2025",
        "{company} acquires acquired",
        "{company} partnership strategic alliance",
    ],
    "financial": [
        "{company} revenue earnings quarterly results",
        "{company} financial results annual report",
        "{company} IPO stock market valuation",
    ],
    "executive": [
        "{company} CEO CTO CFO appointment leadership",
        "{company} executive hire fired resigned",
        "{company} management changes",
    ],
    "product": [
        "{company} product launch new feature announcement",
        "{company} release update beta launch",
        "{company} pricing change update",
    ],
}


class MarketIntelligenceTool(BaseTool):
    """
    Market intelligence tool that gathers structured competitive data
    from public sources: funding, acquisitions, financial news, executive
    changes, and product launches.
    """

    name: str = "market_intelligence"
    description: str = (
        "Gather structured market intelligence about a specific company. "
        "Searches for funding rounds, acquisitions, financial results, executive changes, "
        "and product launches. Input: company name and optional data type."
    )
    args_schema: Type[BaseModel] = MarketInput

    def _run(
        self,
        company: str,
        data_type: str = "all",
        days_back: int = 30,
    ) -> str:
        """Execute market intelligence search."""
        cache_key = f"market:{company}:{data_type}:{days_back}"
        cached = cache_manager.get_search(cache_key, "market")
        if cached:
            log.debug(f"[Market] Cache HIT: {company}")
            return self._format_intelligence(cached, company)

        # Determine query templates
        if data_type == "all":
            templates = []
            for k, v in QUERY_TEMPLATES.items():
                templates.extend(v[:1])  # Take first query per category
        else:
            templates = QUERY_TEMPLATES.get(data_type, QUERY_TEMPLATES["product"])

        all_results = []
        time_filter = "m" if days_back <= 30 else "y"

        for template in templates[:5]:  # Max 5 queries per company
            query = template.format(company=company)
            try:
                results = _market_breaker.call(self._search, query, time_filter)
                for r in results:
                    r["data_type"] = data_type
                    r["company"] = company
                all_results.extend(results)
            except Exception as exc:
                log.warning(f"[Market] Query failed '{query}': {exc}")
                continue

        # Deduplicate
        seen = set()
        deduped = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                deduped.append(r)

        if deduped:
            cache_manager.set_search(cache_key, deduped, "market")

        return (
            self._format_intelligence(deduped, company)
            if deduped
            else f"No market intelligence found for {company}"
        )

    def _search(self, query: str, time_filter: str) -> List[Dict]:
        """Execute a single DuckDuckGo search."""
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(keywords=query, max_results=5, timelimit=time_filter):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", r.get("href", "")),
                        "snippet": r.get("body", r.get("summary", ""))[:400],
                        "source_name": r.get("source", "Unknown"),
                        "published_date": r.get("date", ""),
                        "query": query,
                    }
                )
        return results

    def _format_intelligence(self, results: List[Dict], company: str) -> str:
        """Format market intelligence as structured Markdown."""
        if not results:
            return f"No intelligence data found for {company}."

        lines = [f"## Market Intelligence: {company}\n"]
        lines.append(f"Found {len(results)} intelligence items:\n")

        for i, r in enumerate(results, 1):
            lines.append(
                f"**[{i}] {r.get('title', 'No title')}**\n"
                f"- Source: {r.get('source_name', 'Unknown')}\n"
                f"- Date: {r.get('published_date', 'Unknown')}\n"
                f"- URL: {r.get('url', '')}\n"
                f"- Summary: {r.get('snippet', '')}\n"
                f"- Type: {r.get('data_type', 'general')}"
            )

        return "\n\n".join(lines)


# Singleton
market_tool = MarketIntelligenceTool()

__all__ = ["MarketIntelligenceTool", "market_tool"]
