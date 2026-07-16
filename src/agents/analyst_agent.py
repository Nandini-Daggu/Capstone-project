"""
src/agents/analyst_agent.py
============================
Analyst Agent — transforms raw research into structured intelligence.

Responsibilities:
- Competitor comparison matrix
- SWOT analysis
- Market trend extraction
- Risk identification
- Opportunity mapping
- Fact verification (reject uncited claims)
- Confidence scoring
"""

from __future__ import annotations

from typing import List, Optional

from crewai import Agent, Task
from crewai.tools import BaseTool

from config.settings import settings
from src.tools.cache_tool import cache_tool
from src.tools.citation_tool import citation_tool
from src.tools.rag_tool import rag_tool
from src.utils.logger import get_logger

log = get_logger(__name__)


ANALYST_SYSTEM_PROMPT = """You are a Principal Competitive Intelligence Analyst with 12 years at McKinsey.

MISSION: Transform raw research into actionable strategic intelligence.

ANALYTICAL FRAMEWORK:
1. COMPETITOR COMPARISON: Build a matrix comparing all competitors on key dimensions
2. SWOT ANALYSIS: Identify strengths, weaknesses, opportunities, threats
3. TREND IDENTIFICATION: Extract 5-10 market trends supported by multiple sources
4. RISK ANALYSIS: Rank competitive risks by severity and likelihood
5. OPPORTUNITY MAPPING: Identify market gaps and competitor weaknesses

FACT VERIFICATION RULES (CRITICAL):
- Every claim must be traceable to a cited source
- Claims appearing in only ONE source → mark as LOW CONFIDENCE
- Claims with NO citation → REJECT and exclude from output
- Contradictory claims → note both versions and assign LOW CONFIDENCE
- Financial figures must match source data exactly

CITATION PROTOCOL:
- Use citation_manager tool with action='add_source' for every source
- Tag every factual claim with [n] (the citation number)
- Generate the reference list at the end using action='generate_references'

OUTPUT STRUCTURE:
1. Competitor Comparison Matrix (Markdown table)
2. SWOT Analysis (4-quadrant grid)
3. Market Trends (numbered list with citations)
4. Risk Register (by severity: HIGH/MEDIUM/LOW)
5. Opportunity Map (by impact: HIGH/MEDIUM/LOW)
6. Verification Report (claims checked, rejected, confidence distribution)
"""


class AnalystAgent:
    """CrewAI Analyst Agent factory."""

    def __init__(
        self,
        model=None,  # str model name OR a crewai.llm.LLM instance
        verbose: bool = False,
        max_iter: int = 5,
        additional_tools: Optional[List[BaseTool]] = None,
    ) -> None:
        self.model = model if model is not None else settings.model_primary
        self.verbose = verbose
        self.max_iter = max_iter
        self.additional_tools = additional_tools or []
        self._agent: Optional[Agent] = None

    def build(self) -> Agent:
        """Create and return the CrewAI Agent."""
        tools = [
            citation_tool,
            rag_tool,
            cache_tool,
            *self.additional_tools,
        ]

        self._agent = Agent(
            role="Principal Competitive Intelligence Analyst",
            goal=(
                "Transform raw research data into structured, verified intelligence. "
                "Build competitor comparison matrices, SWOT analyses, and trend reports. "
                "REJECT every uncited claim. Every fact must have a [n] citation. "
                "Flag LOW CONFIDENCE items rather than excluding them — let the writer decide."
            ),
            backstory=(
                "You have an MBA from Wharton and 12 years of experience at McKinsey's "
                "Technology Practice. You have a zero-tolerance policy for unsourced claims. "
                "You think in frameworks and you document your reasoning meticulously."
            ),
            tools=tools,
            verbose=self.verbose,
            allow_delegation=False,
            max_iter=self.max_iter,
            memory=False,  # disabled — no embedder overhead, faster execution
            llm=self.model,
        )
        return self._agent

    def create_analysis_task(
        self,
        research_output: str,
        industry: str,
        competitors: List[str],
        run_id: str,
    ) -> Task:
        """Create the analysis task."""
        competitors_str = ", ".join(competitors)

        description = f"""
Analyse the research data provided below for:
- Industry: {industry}
- Competitors: {competitors_str}
- Run ID: {run_id}

STEP 1: Register all sources using citation_manager (action='add_source') for each URL found in the research.

STEP 2: Build a COMPETITOR COMPARISON TABLE:
| Competitor | Pricing | Key Products | Recent News | Funding | Growth Signal |
|-----------|---------|-------------|-------------|---------|---------------|
(Fill in for each competitor, with [n] citations)

STEP 3: Perform SWOT ANALYSIS:
**Strengths:** (market leader advantages)
**Weaknesses:** (gaps or vulnerabilities)
**Opportunities:** (market gaps, competitor weaknesses)
**Threats:** (competitive risks, market changes)

STEP 4: Extract MARKET TRENDS (minimum 5):
1. [Trend name]: description [citation(s)]
...

STEP 5: Build RISK REGISTER:
| Risk | Severity | Likelihood | Citation |
|------|---------|-----------|---------|

STEP 6: Map OPPORTUNITIES:
| Opportunity | Impact | Evidence | Citation |
|------------|--------|---------|---------|

STEP 7: Run fact verification using citation_manager (action='check_claims') on your analysis.

STEP 8: Generate references using citation_manager (action='generate_references').

RESEARCH DATA:
{research_output[:8000]}
"""

        return Task(
            description=description,
            expected_output=(
                "A complete structured analysis document containing: "
                "1) Competitor comparison matrix with citations. "
                "2) SWOT analysis. "
                "3) 5-10 market trends with citations. "
                "4) Risk register ranked by severity. "
                "5) Opportunity map ranked by impact. "
                "6) Verification report. "
                "7) Complete reference list. "
                "All factual claims tagged with [n] citations."
            ),
            agent=self._agent,
        )


def create_analyst_agent(
    model: Optional[str] = None,
    verbose: bool = True,
) -> Agent:
    """Convenience factory function."""
    factory = AnalystAgent(model=model, verbose=verbose)
    return factory.build()


__all__ = ["AnalystAgent", "create_analyst_agent"]
