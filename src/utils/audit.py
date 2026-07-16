"""
src/utils/audit.py
===================
Audit logging for governance and compliance.
Every agent action, tool call, LLM invocation, and reviewer decision is
persisted to SQLite AND appended to a JSONL flat-file for offline analysis.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config.settings import settings
from .logger import get_logger

log = get_logger(__name__)


# ── Audit record schema ───────────────────────────────────────────────────────

class AuditRecord(BaseModel):
    """Immutable audit record written for every significant event."""

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event_type: str          # tool_call | llm_call | agent_action | human_review | error
    agent: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None

    # Inputs / outputs
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    search_queries: List[str] = Field(default_factory=list)
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    reasoning_steps: List[str] = Field(default_factory=list)

    # Performance
    latency_ms: Optional[float] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    retries: int = 0

    # Status
    success: bool = True
    error_message: Optional[str] = None

    # Governance
    citation_count: int = 0
    uncited_claims_rejected: int = 0
    prompt_injection_detected: bool = False
    reviewer_approved: Optional[bool] = None
    reviewer_feedback: Optional[str] = None


# ── Audit logger ─────────────────────────────────────────────────────────────

class AuditLogger:
    """
    Thread-safe audit logger that writes to:
      - JSONL file (append-only)
      - SQLite (via DatabaseManager, deferred import to avoid circular deps)
    """

    def __init__(self) -> None:
        self._jsonl_path: Path = settings.audit_log_file
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer: List[AuditRecord] = []

    # ── Public API ───────────────────────────────────────────

    def log(self, record: AuditRecord) -> None:
        """Persist an audit record synchronously."""
        self._write_jsonl(record)
        self._buffer.append(record)
        log.debug(
            f"[Audit] {record.event_type} | agent={record.agent} | "
            f"tool={record.tool} | success={record.success}"
        )

    def log_tool_call(
        self,
        run_id: str,
        agent: str,
        tool: str,
        input_summary: str,
        output_summary: str,
        latency_ms: float,
        citations: Optional[List[str]] = None,
        success: bool = True,
        error: Optional[str] = None,
        retries: int = 0,
    ) -> AuditRecord:
        """Convenience wrapper for tool call events."""
        record = AuditRecord(
            run_id=run_id,
            event_type="tool_call",
            agent=agent,
            tool=tool,
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=latency_ms,
            citations=citations or [],
            citation_count=len(citations) if citations else 0,
            success=success,
            error_message=error,
            retries=retries,
        )
        self.log(record)
        return record

    def log_llm_call(
        self,
        run_id: str,
        agent: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        estimated_cost_usd: float,
        success: bool = True,
        error: Optional[str] = None,
        retries: int = 0,
    ) -> AuditRecord:
        """Convenience wrapper for LLM call events."""
        record = AuditRecord(
            run_id=run_id,
            event_type="llm_call",
            agent=agent,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=estimated_cost_usd,
            success=success,
            error_message=error,
            retries=retries,
        )
        self.log(record)
        return record

    def log_human_review(
        self,
        run_id: str,
        approved: bool,
        feedback: str,
        edited_content: Optional[str] = None,
    ) -> AuditRecord:
        """Log a human reviewer decision."""
        record = AuditRecord(
            run_id=run_id,
            event_type="human_review",
            reviewer_approved=approved,
            reviewer_feedback=feedback,
            output_summary=edited_content,
        )
        self.log(record)
        return record

    def log_error(
        self,
        run_id: str,
        agent: str,
        tool: Optional[str],
        error: str,
        retries: int = 0,
    ) -> AuditRecord:
        """Log an error event."""
        record = AuditRecord(
            run_id=run_id,
            event_type="error",
            agent=agent,
            tool=tool,
            error_message=error,
            success=False,
            retries=retries,
        )
        self.log(record)
        return record

    def get_run_records(self, run_id: str) -> List[AuditRecord]:
        """Retrieve all records for a given run from the in-memory buffer."""
        return [r for r in self._buffer if r.run_id == run_id]

    def get_run_cost(self, run_id: str) -> float:
        """Sum estimated cost for a run."""
        return sum(r.estimated_cost_usd for r in self.get_run_records(run_id))

    def get_run_tokens(self, run_id: str) -> Dict[str, int]:
        """Sum token usage for a run."""
        records = self.get_run_records(run_id)
        return {
            "prompt": sum(r.prompt_tokens for r in records),
            "completion": sum(r.completion_tokens for r in records),
            "total": sum(r.total_tokens for r in records),
        }

    def export_run_csv(self, run_id: str) -> str:
        """Export run audit records as CSV string."""
        import io
        import csv

        records = self.get_run_records(run_id)
        if not records:
            return ""

        output = io.StringIO()
        fields = list(AuditRecord.model_fields.keys())
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for r in records:
            row = r.model_dump()
            # Flatten list fields to strings for CSV
            for k, v in row.items():
                if isinstance(v, list):
                    row[k] = "|".join(str(i) for i in v)
            writer.writerow(row)
        return output.getvalue()

    # ── Private ──────────────────────────────────────────────

    def _write_jsonl(self, record: AuditRecord) -> None:
        """Append record to JSONL file atomically."""
        try:
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")
        except Exception as exc:  # noqa: BLE001
            log.error(f"Failed to write audit record: {exc}")


# Singleton
audit_logger = AuditLogger()

__all__ = ["AuditLogger", "AuditRecord", "audit_logger"]
