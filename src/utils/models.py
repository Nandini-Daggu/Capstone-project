"""
src/utils/models.py
====================
Core Pydantic domain models used across the application.
These are the canonical data structures that flow between agents and tools.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Enums ────────────────────────────────────────────────────────────────────


class ResearchCategory(str, Enum):
    NEWS = "news"
    PRICING = "pricing"
    PRODUCT = "product"
    FUNDING = "funding"
    ACQUISITION = "acquisition"
    EXECUTIVE = "executive"
    SENTIMENT = "sentiment"
    TREND = "trend"
    REGULATORY = "regulatory"
    TECHNOLOGY = "technology"


class ConfidenceLevel(str, Enum):
    HIGH = "high"  # >= 0.8
    MEDIUM = "medium"  # 0.6 - 0.79
    LOW = "low"  # < 0.6


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    PENDING = "pending"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_REVIEW = "awaiting_review"


# ── Source / Citation ─────────────────────────────────────────────────────────


class CitedSource(BaseModel):
    """A verifiable source with full citation metadata."""

    source_id: int = 0
    url: str
    title: str
    source_name: str
    published_date: Optional[str] = None
    accessed_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    snippet: Optional[str] = None
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_primary_source: bool = False

    @field_validator("url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Source URL cannot be empty")
        return v.strip()


# ── Research ──────────────────────────────────────────────────────────────────


class ResearchItem(BaseModel):
    """A single piece of intelligence collected by the Research Agent."""

    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    competitor: str
    category: ResearchCategory
    title: str
    summary: str
    source_url: str
    source_name: str
    published_date: Optional[str] = None
    snippet: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    verified: bool = False
    citation_index: Optional[int] = None  # Set by Writer after indexing
    raw_data: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def set_confidence_level(self) -> "ResearchItem":
        if self.confidence >= 0.8:
            self.confidence_level = ConfidenceLevel.HIGH
        elif self.confidence >= 0.6:
            self.confidence_level = ConfidenceLevel.MEDIUM
        else:
            self.confidence_level = ConfidenceLevel.LOW
        return self


class ResearchOutput(BaseModel):
    """Full output from the Research Agent."""

    run_id: str
    items: List[ResearchItem] = Field(default_factory=list)
    sources_used: int = 0
    steps_used: int = 0
    search_queries: List[str] = Field(default_factory=list)
    failed_sources: List[str] = Field(default_factory=list)
    rag_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def by_competitor(self) -> Dict[str, List[ResearchItem]]:
        result: Dict[str, List[ResearchItem]] = {}
        for item in self.items:
            result.setdefault(item.competitor, []).append(item)
        return result

    @property
    def by_category(self) -> Dict[str, List[ResearchItem]]:
        result: Dict[str, List[ResearchItem]] = {}
        for item in self.items:
            result.setdefault(item.category.value, []).append(item)
        return result


# ── Analysis ──────────────────────────────────────────────────────────────────


class SwotQuadrant(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    name: str
    pricing_summary: Optional[str] = None
    product_highlights: List[str] = Field(default_factory=list)
    recent_news: List[str] = Field(default_factory=list)
    funding_status: Optional[str] = None
    market_position: Optional[str] = None
    growth_signals: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    citations: List[int] = Field(default_factory=list)


class AnalysisOutput(BaseModel):
    """Structured output from the Analyst Agent."""

    run_id: str
    competitor_profiles: List[CompetitorProfile] = Field(default_factory=list)
    swot: SwotQuadrant = Field(default_factory=SwotQuadrant)
    market_trends: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    comparison_matrix: str = ""  # Markdown table
    verified_claims: int = 0
    rejected_claims: int = 0
    low_confidence_flags: List[str] = Field(default_factory=list)
    all_citations: List[CitedSource] = Field(default_factory=list)
    analysis_text: str = ""
    duration_seconds: float = 0.0


# ── Evaluation ────────────────────────────────────────────────────────────────


class EvaluationResult(BaseModel):
    """Evaluation scores from RAGAS / DeepEval / custom metrics."""

    run_id: str
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    hallucination_score: float = 0.0
    answer_correctness: float = 0.0
    citation_coverage: float = 0.0
    tool_accuracy: float = 0.0
    overall_score: float = 0.0
    passed: bool = False
    notes: List[str] = Field(default_factory=list)
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def compute_overall(self) -> "EvaluationResult":
        scores = [
            self.faithfulness,
            self.answer_relevancy,
            self.context_precision,
            self.citation_coverage,
        ]
        valid = [s for s in scores if s > 0]
        self.overall_score = sum(valid) / len(valid) if valid else 0.0
        self.passed = (
            self.overall_score >= 0.7
            and self.hallucination_score <= 0.1
            and self.citation_coverage >= 0.9
        )
        return self


# ── Human Review ──────────────────────────────────────────────────────────────


class HumanReviewDecision(BaseModel):
    """Decision and feedback from a human reviewer."""

    run_id: str
    decision: ReviewDecision = ReviewDecision.PENDING
    approved: bool = False
    feedback: str = ""
    edited_sections: Dict[str, str] = Field(default_factory=dict)
    reviewer_id: str = "human_reviewer"
    reviewed_at: Optional[str] = None

    @model_validator(mode="after")
    def set_reviewed_at(self) -> "HumanReviewDecision":
        if self.decision != ReviewDecision.PENDING and not self.reviewed_at:
            self.reviewed_at = datetime.now(timezone.utc).isoformat()
        return self


# ── Run Metadata ──────────────────────────────────────────────────────────────


class RunMetadata(BaseModel):
    """Metadata captured for a complete crew run."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.PENDING
    industry: str = ""
    competitors: List[str] = Field(default_factory=list)
    region: str = ""
    time_period: str = "last 7 days"
    max_sources: int = 15
    max_steps: int = 25
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    sources_used: int = 0
    steps_used: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model_used: str = ""
    error_message: Optional[str] = None


# ── Briefing Report ───────────────────────────────────────────────────────────


class BriefingReport(BaseModel):
    """The final deliverable: a complete competitive intelligence briefing."""

    run_id: str
    title: str = "Competitive Intelligence Briefing"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    industry: str = ""
    competitors: List[str] = Field(default_factory=list)
    region: str = ""
    time_period: str = ""

    # Report sections (Markdown strings)
    executive_summary: str = ""
    competitor_pricing: str = ""
    product_updates: str = ""
    market_signals: str = ""
    industry_trends: str = ""
    swot_analysis: str = ""
    risk_analysis: str = ""
    opportunities: str = ""
    recommendations: str = ""
    references: str = ""
    full_markdown: str = ""

    # Supporting data
    sources: List[CitedSource] = Field(default_factory=list)
    metadata: RunMetadata = Field(default_factory=RunMetadata)
    evaluation: Optional[EvaluationResult] = None
    review: Optional[HumanReviewDecision] = None
    analysis: Optional[AnalysisOutput] = None

    def to_full_markdown(self) -> str:
        """Assemble the full briefing as a single Markdown document."""
        sections = [
            f"# {self.title}",
            f"**Industry:** {self.industry} | **Period:** {self.time_period} | "
            f"**Region:** {self.region} | **Generated:** {self.generated_at[:10]}",
            "---",
            "## Executive Summary",
            self.executive_summary,
            "---",
            "## Competitor Pricing Analysis",
            self.competitor_pricing,
            "---",
            "## Product & Feature Updates",
            self.product_updates,
            "---",
            "## Market Signals",
            self.market_signals,
            "---",
            "## Industry Trends",
            self.industry_trends,
            "---",
            "## SWOT Analysis",
            self.swot_analysis,
            "---",
            "## Risk Analysis",
            self.risk_analysis,
            "---",
            "## Opportunities",
            self.opportunities,
            "---",
            "## Strategic Recommendations",
            self.recommendations,
            "---",
            "## References",
            self.references,
            "---",
            "## Run Metadata",
            self._metadata_section(),
        ]
        if self.evaluation:
            sections.extend(["---", "## Evaluation Summary", self._eval_section()])
        return "\n\n".join(s for s in sections if s)

    def _metadata_section(self) -> str:
        m = self.metadata
        return (
            f"| Metric | Value |\n|--------|-------|\n"
            f"| Sources Used | {m.sources_used} |\n"
            f"| Steps Used | {m.steps_used} |\n"
            f"| Total Tokens | {m.total_tokens} |\n"
            f"| Estimated Cost | ${m.estimated_cost_usd:.4f} |\n"
            f"| Duration | {m.duration_seconds:.1f}s |\n"
            f"| Model | {m.model_used} |\n"
        )

    def _eval_section(self) -> str:
        e = self.evaluation
        if not e:
            return ""
        return (
            f"| Metric | Score |\n|--------|-------|\n"
            f"| Faithfulness | {e.faithfulness:.2f} |\n"
            f"| Answer Relevancy | {e.answer_relevancy:.2f} |\n"
            f"| Citation Coverage | {e.citation_coverage:.2f} |\n"
            f"| Hallucination Score | {e.hallucination_score:.2f} |\n"
            f"| Overall Score | {e.overall_score:.2f} |\n"
            f"| **Passed** | {'✅' if e.passed else '❌'} |\n"
        )


__all__ = [
    "ResearchCategory",
    "ConfidenceLevel",
    "ReviewDecision",
    "RunStatus",
    "CitedSource",
    "ResearchItem",
    "ResearchOutput",
    "SwotQuadrant",
    "CompetitorProfile",
    "AnalysisOutput",
    "EvaluationResult",
    "HumanReviewDecision",
    "RunMetadata",
    "BriefingReport",
]
