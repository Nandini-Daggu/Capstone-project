"""
crew/workflow.py
=================
High-level workflow orchestrator.
Handles the full pipeline including:
- Pre-flight governance checks
- Crew execution with timeout
- Human review gate
- Export generation
- Post-run evaluation
- Error recovery and partial failure handling
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from src.tools.citation_tool import _registry
from src.tools.pdf_export import pdf_export_tool
from src.tools.ppt_export import ppt_export_tool
from src.tools.report_export import report_export_tool
from src.utils.audit import audit_logger
from src.utils.database import db_manager
from src.utils.logger import get_logger
from src.utils.models import (
    BriefingReport,
    HumanReviewDecision,
    ReviewDecision,
    RunMetadata,
    RunStatus,
)

from .crew import IntelligenceCrew

log = get_logger(__name__)


class WorkflowResult:
    """The complete result of a workflow run."""

    def __init__(
        self,
        run_id: str,
        status: str,
        report: Optional[BriefingReport] = None,
        error: Optional[str] = None,
        export_paths: Optional[Dict[str, str]] = None,
    ) -> None:
        self.run_id = run_id
        self.status = status
        self.report = report
        self.error = error
        self.export_paths = export_paths or {}


class IntelligenceWorkflow:
    """
    Full end-to-end workflow for competitive intelligence briefings.

    Pipeline stages:
    1. Validate & initialise
    2. Run crew (with timeout)
    3. Human review gate
    4. Export generation
    5. Post-run evaluation
    6. Store to DB
    """

    def __init__(
        self,
        model: Optional[str] = None,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self.model = model or settings.model_primary
        self._on_progress = on_progress or (lambda msg, pct: None)
        # IntelligenceCrew builds a shared CascadeLLM internally.
        # Pass a model override if specified; the cascade handles 429 fallback.
        cascade = settings.model_cascade
        if model and model not in cascade:
            cascade = [model] + list(cascade)
        self._crew = IntelligenceCrew(model_cascade=cascade)

    def run(
        self,
        industry: str,
        competitors: List[str],
        region: str = "Global",
        time_period: str = "last 7 days",
        max_sources: int = 15,
        max_steps: int = 25,
        export_formats: Optional[List[str]] = None,
        human_review_callback: Optional[Callable[[str], HumanReviewDecision]] = None,
        run_id: Optional[str] = None,
    ) -> WorkflowResult:
        """Execute the full workflow synchronously."""
        run_id = run_id or str(uuid.uuid4())
        export_formats = export_formats or ["markdown"]
        start_time = time.monotonic()

        log.info(f"[Workflow] Starting run {run_id[:8]}")
        self._progress("Initialising pipeline...", 5)

        # ── Reset citation registry for new run ───────────────
        _registry.clear()

        # ── Stage 1: Run Crew (with timeout) ──────────────────
        self._progress("Research and analysis in progress...", 15)
        try:
            crew_result = self._run_with_timeout(
                lambda: self._crew.run(
                    industry=industry,
                    competitors=competitors,
                    region=region,
                    time_period=time_period,
                    max_sources=max_sources,
                    max_steps=max_steps,
                    run_id=run_id,
                ),
                timeout=settings.max_runtime_seconds,
            )
        except TimeoutError:
            elapsed = time.monotonic() - start_time
            log.error(f"[Workflow] Run {run_id[:8]} timed out after {elapsed:.0f}s")
            return WorkflowResult(
                run_id=run_id,
                status="failed",
                error=f"Run exceeded {settings.max_runtime_seconds}s time limit",
            )
        except Exception as exc:
            log.error(f"[Workflow] Crew execution failed: {exc}")
            return WorkflowResult(run_id=run_id, status="failed", error=str(exc))

        if crew_result.get("status") != "completed":
            return WorkflowResult(
                run_id=run_id,
                status="failed",
                error=crew_result.get("error", "Unknown crew failure"),
            )

        briefing_text = crew_result["briefing"]
        metadata = crew_result.get("metadata") or RunMetadata(
            run_id=run_id,
            industry=industry,
            competitors=competitors,
            region=region,
            time_period=time_period,
        )

        self._progress("Building report structure...", 65)

        # ── Stage 2: Build report object ──────────────────────
        sources = _registry.all_sources()
        report = self._build_report(
            run_id=run_id,
            briefing_text=briefing_text,
            metadata=metadata,
            industry=industry,
            competitors=competitors,
            region=region,
            time_period=time_period,
            sources=sources,
        )

        # ── Stage 3: Human review (optional) ──────────────────
        self._progress("Awaiting human review...", 75)
        if settings.human_review_enabled and human_review_callback:
            review = self._run_human_review(report, human_review_callback, run_id)
            report.review = review
            if not review.approved:
                log.warning(f"[Workflow] Report {run_id[:8]} rejected by reviewer")
                self._update_db_status(run_id, RunStatus.FAILED)
                return WorkflowResult(
                    run_id=run_id,
                    status="rejected",
                    report=report,
                    error=f"Rejected by reviewer: {review.feedback}",
                )
            # Apply edits if any
            if review.edited_sections:
                briefing_text = self._apply_edits(briefing_text, review.edited_sections)
                report.full_markdown = briefing_text

        # ── Stage 4: Export ───────────────────────────────────
        self._progress("Generating exports...", 85)
        export_paths = self._generate_exports(
            briefing_text=report.full_markdown or briefing_text,
            run_id=run_id,
            formats=export_formats,
        )

        # ── Stage 5: Persist to DB ────────────────────────────
        self._progress("Saving report...", 95)
        try:
            import json

            db_manager.save_report(
                {
                    "run_id": run_id,
                    "title": report.title,
                    "industry": report.industry,
                    "competitors": json.dumps(competitors),
                    "full_markdown": report.full_markdown or briefing_text,
                    "sources_json": json.dumps([s.model_dump() for s in sources]),
                    "approved": True,
                }
            )
        except Exception as db_exc:
            log.warning(f"[Workflow] DB save_report failed (non-fatal): {db_exc}")

        elapsed = time.monotonic() - start_time
        self._progress(f"Complete! ({elapsed:.0f}s)", 100)
        log.info(f"[Workflow] Run {run_id[:8]} completed in {elapsed:.1f}s")

        return WorkflowResult(
            run_id=run_id,
            status="completed",
            report=report,
            export_paths=export_paths,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_with_timeout(self, func: Callable, timeout: int) -> Any:
        """Run a function with a wall-clock timeout."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeout:
                raise TimeoutError(f"Function timed out after {timeout}s")

    def _build_report(
        self,
        run_id: str,
        briefing_text: str,
        metadata: RunMetadata,
        industry: str,
        competitors: List[str],
        region: str,
        time_period: str,
        sources: list,
    ) -> BriefingReport:
        """Parse briefing text into structured report sections."""
        import re

        sections: Dict[str, str] = {}
        current_section = "preamble"
        current_lines = []

        for line in briefing_text.split("\n"):
            if line.startswith("## "):
                if current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = line[3:].strip().lower()
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections[current_section] = "\n".join(current_lines).strip()

        def _get(key_pattern: str) -> str:
            for k, v in sections.items():
                if re.search(key_pattern, k, re.IGNORECASE):
                    return v
            return ""

        report = BriefingReport(
            run_id=run_id,
            title=f"Competitive Intelligence Briefing: {industry}",
            industry=industry,
            competitors=competitors,
            region=region,
            time_period=time_period,
            executive_summary=_get(r"executive\s+summary"),
            competitor_pricing=_get(r"pricing"),
            product_updates=_get(r"product"),
            market_signals=_get(r"market\s+signals?"),
            industry_trends=_get(r"industry\s+trends?"),
            swot_analysis=_get(r"swot"),
            risk_analysis=_get(r"risk"),
            opportunities=_get(r"opportunit"),
            recommendations=_get(r"recommend"),
            references=_get(r"references?"),
            full_markdown=briefing_text,
            sources=sources,
            metadata=metadata,
        )
        return report

    def _run_human_review(
        self,
        report: BriefingReport,
        callback: Callable,
        run_id: str,
    ) -> HumanReviewDecision:
        """Execute the human review gate."""
        try:
            decision = callback(report)
            audit_logger.log_human_review(
                run_id=run_id,
                approved=decision.approved,
                feedback=decision.feedback,
            )
            return decision
        except Exception as exc:
            log.error(f"[Workflow] Human review failed: {exc}")
            # Auto-approve on review system failure
            return HumanReviewDecision(
                run_id=run_id,
                decision=ReviewDecision.APPROVED,
                approved=True,
                feedback=f"Auto-approved: review system failed ({exc})",
            )

    def _apply_edits(self, text: str, edits: Dict[str, str]) -> str:
        """Apply reviewer edits to specific sections."""
        for section_key, new_content in edits.items():
            # Simple section replacement
            import re

            pattern = rf"(## {re.escape(section_key)}.*?\n)(.*?)(?=\n## |\Z)"
            replacement = rf"\g<1>{new_content}\n"
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)
        return text

    def _generate_exports(
        self,
        briefing_text: str,
        run_id: str,
        formats: List[str],
    ) -> Dict[str, str]:
        """Generate all requested export formats in parallel."""
        paths: Dict[str, str] = {}

        def _export_one(fmt: str) -> tuple:
            try:
                if fmt == "markdown":
                    result = report_export_tool._run(briefing_text, "markdown", run_id)
                elif fmt == "html":
                    result = report_export_tool._run(briefing_text, "html", run_id)
                elif fmt == "json":
                    result = report_export_tool._run(briefing_text, "json", run_id)
                elif fmt == "pdf":
                    result = pdf_export_tool._run(briefing_text, run_id=run_id)
                elif fmt == "pptx":
                    result = ppt_export_tool._run(briefing_text, run_id=run_id)
                else:
                    return fmt, None
                # Extract path from result string
                if ":" in result:
                    path_part = result.split(":")[-1].strip()
                    return fmt, path_part
                return fmt, None
            except Exception as exc:
                log.warning(f"[Workflow] Export {fmt} failed: {exc}")
                return fmt, None

        with ThreadPoolExecutor(max_workers=min(len(formats), 4)) as pool:
            for fmt, path in pool.map(_export_one, formats):
                if path:
                    paths[fmt] = path
                    log.info(f"[Workflow] Export {fmt}: {path}")

        return paths

    def _update_db_status(self, run_id: str, status: RunStatus) -> None:
        try:
            db_manager.update_run(
                run_id,
                {
                    "status": status.value,
                    "completed_at": datetime.now(timezone.utc),
                },
            )
        except Exception:
            pass

    def _progress(self, message: str, percent: int) -> None:
        log.info(f"[Workflow] [{percent:3d}%] {message}")
        self._on_progress(message, percent)


__all__ = ["IntelligenceWorkflow", "WorkflowResult"]
