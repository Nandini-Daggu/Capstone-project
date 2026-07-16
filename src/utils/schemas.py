"""
src/utils/schemas.py
=====================
FastAPI request/response schemas (separate from domain models
to allow independent API versioning).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class BriefingRequest(BaseModel):
    """Request body for POST /generate."""

    industry: str = Field(..., min_length=2, max_length=200, examples=["SaaS / CRM"])
    competitors: List[str] = Field(
        ..., min_length=1, max_length=10, examples=[["Salesforce", "HubSpot", "Pipedrive"]]
    )
    region: str = Field(default="Global", max_length=100, examples=["North America"])
    time_period: str = Field(
        default="last 7 days",
        max_length=50,
        examples=["last 7 days", "last 30 days"],
    )
    max_sources: int = Field(default=15, ge=1, le=15)
    max_steps: int = Field(default=25, ge=1, le=25)
    human_review_enabled: bool = Field(default=True)
    export_formats: List[str] = Field(
        default=["markdown"],
        examples=[["markdown", "pdf", "pptx"]],
    )

    @field_validator("competitors")
    @classmethod
    def validate_competitors(cls, v: List[str]) -> List[str]:
        cleaned = [c.strip() for c in v if c.strip()]
        if not cleaned:
            raise ValueError("At least one competitor is required")
        return cleaned


class BriefingResponse(BaseModel):
    """Response body for POST /generate."""

    run_id: str
    status: str
    message: str
    estimated_duration_seconds: Optional[int] = None


class RunStatusResponse(BaseModel):
    """Response for GET /status/{run_id}."""

    run_id: str
    status: str
    progress_percent: int = 0
    current_step: str = ""
    sources_collected: int = 0
    steps_used: int = 0
    estimated_cost_usd: float = 0.0
    error_message: Optional[str] = None


class ReportResponse(BaseModel):
    """Response for GET /report/{run_id}."""

    run_id: str
    title: str
    generated_at: str
    industry: str
    competitors: List[str]
    full_markdown: str
    sources_count: int
    evaluation_score: Optional[float] = None
    approved: bool = False


class ExportRequest(BaseModel):
    """Request body for POST /export."""

    run_id: str
    format: str = Field(..., pattern="^(markdown|pdf|pptx|html|json)$")


class ExportResponse(BaseModel):
    """Response for POST /export."""

    run_id: str
    format: str
    file_path: str
    file_size_bytes: int


class EvaluationResponse(BaseModel):
    """Response for GET /evaluate/{run_id}."""

    run_id: str
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    hallucination_score: float = 0.0
    citation_coverage: float = 0.0
    overall_score: float = 0.0
    passed: bool = False
    notes: List[str] = Field(default_factory=list)


class HumanReviewRequest(BaseModel):
    """Request body for POST /review/{run_id}."""

    approved: bool
    feedback: str = ""
    edited_sections: Dict[str, str] = Field(default_factory=dict)
    reviewer_id: str = "human_reviewer"


class MetricsResponse(BaseModel):
    """Response for GET /metrics."""

    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    cache_stats: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    database: str = "ok"
    cache: str = "ok"


__all__ = [
    "BriefingRequest",
    "BriefingResponse",
    "RunStatusResponse",
    "ReportResponse",
    "ExportRequest",
    "ExportResponse",
    "EvaluationResponse",
    "HumanReviewRequest",
    "MetricsResponse",
    "HealthResponse",
]
