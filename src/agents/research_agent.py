"""
src/agents/research_agent.py
=============================
Research Agent — collects competitive intelligence from public sources.

Responsibilities:
- Web search for competitor news, pricing, products, funding, acquisitions
- Google News RSS crawling
- Website scraping (pricing pages, press releases, blogs)
- RAG retrieval from knowledge base
- Source validation and citation collection
- Respects MAX_SOURCES and MAX_STEPS limits
- Handles partial failures gracefully (skips bad sources, continues)
"""

from __future__ import annotations

from typing import List, Optional

from crewai import Agent, Task
from crewai.tools import BaseTool

from config.settings import settings
from src.tools.cache_tool import cache_tool
from src.tools.market_tool import market_tool
from src.tools.news_search import news_search_tool
from src.tools.rag_tool import rag_tool
from src.tools.web_scraper import web_scraper_tool
from src.tools.web_search import web_search_tool
from src.utils.logger import get_logger

log = get_logger(__name__)


RESEARCH_SYSTEM_PROMPT = """You are a Senior Competitive Intelligence Researcher.

MISSION: Collect comprehensive, factual intelligence about the specified competitors.

STRICT RULES:
1. NEVER fabricate information. Only report what you find in search results.
2. ALWAYS include the source URL for every piece of information.
3. RESPECT the MAX_SOURCES limit ({max_sources}).
4. RESPECT the MAX_STEPS limit ({max_steps}).
5. If a source is unreachable, skip it and move on. Do not fail.
6. Prioritise recency — focus on the last {time_period}.
7. For each competitor, search for:
   - Recent news and press releases
   - Pricing changes or announcements
   - New product/feature launches
   - Funding rounds or financial events
   - Partnerships or acquisitions
   - Executive changes

SEARCH STRATEGY:
- Start with broad news searches
- Then focus on specific categories
- Use web scraper for pricing pages and press releases
- Query RAG knowledge base for historical context

OUTPUT FORMAT:
Return structured data with these fields per item:
- competitor name
- category (news/pricing/product/funding/acquisition/executive/sentiment)
- title
- summary (2-3 sentences)
- source_url
- source_name
- published_date (YYYY-MM-DD if known)
- snippet (verbatim quote from source)
- confidence (0.0-1.0)
"""


class ResearchAgent:
    """
    CrewAI Research Agent factory with governance enforcement.
    """

    def __init__(
        self,
        model=None,  # str model name OR a crewai.llm.LLM instance
        verbose: bool = False,
        max_iter: int = 5,
        additional_tools: Optional[List[BaseTool]] = None,
    ) -> None:
        # Accept either a plain string or a pre-built LLM object (e.g. CascadeLLM)
        self.model = model if model is not None else settings.model_primary
        self.verbose = verbose
        self.max_iter = max_iter
        self.additional_tools = additional_tools or []
        self._agent: Optional[Agent] = None

    def build(self) -> Agent:
        """Create and return the CrewAI Agent."""
        tools = [
            web_search_tool,
            news_search_tool,
            web_scraper_tool,
            market_tool,
            rag_tool,
            cache_tool,
            *self.additional_tools,
        ]

        self._agent = Agent(
            role="Senior Competitive Intelligence Researcher",
            goal=(
                "Systematically collect competitor intelligence from authoritative public sources. "
                "Every item must include its source URL, publication date, and a verbatim snippet. "
                "Never exceed {max_sources} sources or {max_steps} tool calls. "
                "Skip unreachable sources and continue."
            ).format(
                max_sources=settings.max_sources,
                max_steps=settings.max_steps,
            ),
            backstory=(
                "You are a former financial analyst and investigative journalist who spent "
                "a decade at Bloomberg and Reuters tracking technology markets. "
                "You are meticulous about source attribution and never report unverified claims."
            ),
            tools=tools,
            verbose=self.verbose,
            allow_delegation=False,
            max_iter=self.max_iter,
            memory=False,  # disabled — no embedder overhead, faster startup
            llm=self.model,
        )
        return self._agent

    def create_research_task(
        self,
        industry: str,
        competitors: List[str],
        region: str,
        time_period: str,
        run_id: str,
    ) -> Task:
        """Create the research task for this agent."""
        competitors_str = ", ".join(competitors)
        # Build a tightly-scoped query so the agent doesn't over-tool-call.
        # One combined search covers all competitors at once; individual
        # scrapes are only done for the most important URLs found.
        primary = competitors[0] if competitors else "company"
        all_competitors_query = " OR ".join(f'"{c}"' for c in competitors)

        description = (
            f"Research competitive intelligence for the {industry} industry.\n"
            f"Competitors: {competitors_str}\n"
            f"Region: {region} | Period: {time_period} | Run ID: {run_id}\n\n"
            "STEPS — execute in order, stop early if limit is reached:\n"
            f'1. web_search("{all_competitors_query} {industry} news {time_period}") '
            f"— ONE call covering ALL competitors at once.\n"
            f'2. news_search("{industry} {primary} pricing product update {time_period}") '
            "— ONE combined news call.\n"
            f'3. market_intelligence(company="{primary}", data_type="all") '
            "— market data for the primary competitor only.\n"
            "4. For each URL returned above, call web_scraper ONLY on the 3 most relevant "
            "URLs (skip the rest). These 3 fetches run in parallel internally — do NOT call "
            "web_scraper in a loop for all URLs.\n"
            f'5. rag_search(action="search", query="{industry} {primary}") '
            "— knowledge base lookup.\n\n"
            f"HARD LIMITS: max {settings.max_sources} sources, "
            f"max {settings.max_steps} total tool calls. Stop immediately when reached.\n"
            "For every item include: competitor, category, title, summary, "
            "source_url, source_name, published_date, snippet, confidence.\n"
            "Skip any source that fails to load. Do NOT invent data."
        )

        return Task(
            description=description,
            expected_output=(
                "A concise structured list of competitive intelligence items. "
                "Each item: competitor, category, title, summary, "
                "source_url, source_name, published_date, snippet, confidence. "
                f"Cover all {len(competitors)} competitors. "
                "Maximum 15 items total — quality over quantity."
            ),
            agent=self._agent,
        )


def create_research_agent(
    model: Optional[str] = None,
    verbose: bool = True,
) -> Agent:
    """Convenience factory function."""
    factory = ResearchAgent(model=model, verbose=verbose)
    return factory.build()


__all__ = ["ResearchAgent", "create_research_agent"]
