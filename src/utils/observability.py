"""
src/utils/observability.py
===========================
Distributed tracing and observability.
Captures spans for every agent operation with timing, token usage,
cost estimation, and error details.
Also writes a JSONL trace file for offline analysis.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from pydantic import BaseModel, Field

from config.settings import settings

from .logger import get_logger

log = get_logger(__name__)


# ── Cost estimation (approximate OpenRouter rates for free models) ──────────

# Prices per 1k tokens in USD
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "default": {"input": 0.0001, "output": 0.0002},  # Very low for free models
    "gemma-4-31b-it": {"input": 0.0, "output": 0.0},
    "gemma-4-26b": {"input": 0.0, "output": 0.0},
    "llama-3.3-70b": {"input": 0.0, "output": 0.0},
    "llama-3.2-3b": {"input": 0.0, "output": 0.0},
    "qwen3-coder": {"input": 0.0, "output": 0.0},
    "nemotron-3-ultra": {"input": 0.0, "output": 0.0},
    "hermes-3-llama": {"input": 0.0, "output": 0.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for an LLM call."""
    for model_key, prices in MODEL_COSTS.items():
        if model_key in model.lower():
            return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1000.0
    prices = MODEL_COSTS["default"]
    return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1000.0


# ── Span model ────────────────────────────────────────────────────────────────


class TraceSpan(BaseModel):
    """A single traced operation span."""

    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    parent_span_id: Optional[str] = None
    agent: str
    operation: str
    model: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None
    duration_ms: float = 0.0

    # LLM metrics
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Status
    success: bool = True
    error: Optional[str] = None
    retries: int = 0

    # Extra context
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Observability tracker ──────────────────────────────────────────────────────


class ObservabilityTracker:
    """
    Manages trace spans, logs them to JSONL + SQLite, and tracks run-level
    budgets (cost, tokens, steps, time).
    """

    def __init__(self) -> None:
        self._trace_path: Path = settings.trace_log_file
        self._trace_path.parent.mkdir(parents=True, exist_ok=True)

        # Active spans by span_id
        self._active_spans: Dict[str, TraceSpan] = {}

        # Per-run accumulated metrics
        self._run_metrics: Dict[str, Dict[str, float]] = {}

        # Completed spans buffer (for in-memory queries)
        self._completed_spans: List[TraceSpan] = []

    # ── Span lifecycle ───────────────────────────────────────

    def start_span(
        self,
        run_id: str,
        agent: str,
        operation: str,
        model: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Open a new trace span."""
        span = TraceSpan(
            run_id=run_id,
            agent=agent,
            operation=operation,
            model=model,
            parent_span_id=parent_span_id,
            metadata=metadata or {},
        )
        self._active_spans[span.span_id] = span
        self._ensure_run_metrics(run_id)
        log.debug(f"[Trace] START span={span.span_id[:8]} op={operation} agent={agent}")
        return span

    def end_span(
        self,
        span: TraceSpan,
        success: bool = True,
        error: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        retries: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Close a trace span and persist it."""
        ended = datetime.now(timezone.utc)
        start = datetime.fromisoformat(span.started_at)
        span.ended_at = ended.isoformat()
        span.duration_ms = (ended - start).total_seconds() * 1000
        span.success = success
        span.error = error
        span.prompt_tokens = prompt_tokens
        span.completion_tokens = completion_tokens
        span.total_tokens = prompt_tokens + completion_tokens
        span.retries = retries
        if metadata:
            span.metadata.update(metadata)

        if span.model:
            span.estimated_cost_usd = estimate_cost(span.model, prompt_tokens, completion_tokens)

        # Accumulate run metrics
        m = self._run_metrics[span.run_id]
        m["total_tokens"] += span.total_tokens
        m["estimated_cost_usd"] += span.estimated_cost_usd
        m["total_spans"] += 1
        m["failed_spans"] += 0 if success else 1

        self._active_spans.pop(span.span_id, None)
        self._completed_spans.append(span)
        self._write_trace(span)

        log.debug(
            f"[Trace] END span={span.span_id[:8]} op={span.operation} "
            f"dur={span.duration_ms:.1f}ms tokens={span.total_tokens} "
            f"cost=${span.estimated_cost_usd:.6f}"
        )
        return span

    @contextlib.contextmanager
    def span(
        self,
        run_id: str,
        agent: str,
        operation: str,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Generator[TraceSpan, None, None]:
        """Context manager for a trace span."""
        s = self.start_span(run_id, agent, operation, model, **kwargs)
        try:
            yield s
            self.end_span(s, success=True)
        except Exception as exc:
            self.end_span(s, success=False, error=str(exc))
            raise

    # ── Budget checks ────────────────────────────────────────

    def check_cost_budget(self, run_id: str) -> bool:
        """Return True if run is within cost budget."""
        m = self._run_metrics.get(run_id, {})
        return m.get("estimated_cost_usd", 0.0) < settings.max_cost_usd

    def check_step_budget(self, run_id: str) -> bool:
        """Return True if run is within step budget."""
        m = self._run_metrics.get(run_id, {})
        return m.get("total_spans", 0) < settings.max_steps

    def get_run_metrics(self, run_id: str) -> Dict[str, Any]:
        """Return accumulated metrics for a run."""
        return self._run_metrics.get(run_id, {})

    def get_run_spans(self, run_id: str) -> List[TraceSpan]:
        """Return all completed spans for a run."""
        return [s for s in self._completed_spans if s.run_id == run_id]

    def get_trace_summary(self, run_id: str) -> Dict[str, Any]:
        """Return a human-readable trace summary."""
        spans = self.get_run_spans(run_id)
        metrics = self.get_run_metrics(run_id)
        return {
            "run_id": run_id,
            "total_spans": len(spans),
            "total_duration_ms": sum(s.duration_ms for s in spans),
            "total_tokens": metrics.get("total_tokens", 0),
            "estimated_cost_usd": metrics.get("estimated_cost_usd", 0.0),
            "failed_spans": metrics.get("failed_spans", 0),
            "agents_used": list({s.agent for s in spans}),
            "operations": [s.operation for s in spans],
        }

    # ── Private ──────────────────────────────────────────────

    def _ensure_run_metrics(self, run_id: str) -> None:
        if run_id not in self._run_metrics:
            self._run_metrics[run_id] = {
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "total_spans": 0,
                "failed_spans": 0,
            }

    def _write_trace(self, span: TraceSpan) -> None:
        """Append span to JSONL trace file."""
        try:
            with open(self._trace_path, "a", encoding="utf-8") as f:
                f.write(span.model_dump_json() + "\n")
        except Exception as exc:  # noqa: BLE001
            log.error(f"Failed to write trace span: {exc}")


# Singleton
obs_tracker = ObservabilityTracker()

__all__ = ["ObservabilityTracker", "obs_tracker", "TraceSpan", "estimate_cost"]
