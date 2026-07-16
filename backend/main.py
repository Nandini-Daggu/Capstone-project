"""
backend/main.py
================
FastAPI backend for the Competitive Intelligence Briefing Crew.
Provides REST API endpoints for the Streamlit frontend and external clients.

Endpoints:
- POST /generate      - Start a new intelligence briefing run
- GET  /status/{id}   - Check run status
- GET  /report/{id}   - Retrieve completed report
- POST /export        - Export report in a specific format
- GET  /history       - List recent runs
- GET  /logs/{id}     - Get audit logs for a run
- GET  /metrics       - Get aggregate metrics
- GET  /evaluate/{id} - Run evaluation on a report
- POST /review/{id}   - Submit human review decision
- GET  /health        - Health check
"""

from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config.settings import settings
from crew.workflow import IntelligenceWorkflow
from evaluation.test_suite import evaluation_manager
from src.utils.audit import audit_logger
from src.utils.cache import cache_manager
from src.utils.database import db_manager
from src.utils.logger import get_logger
from src.utils.models import HumanReviewDecision, ReviewDecision, RunStatus
from src.utils.schemas import (
    BriefingRequest,
    BriefingResponse,
    EvaluationResponse,
    ExportRequest,
    ExportResponse,
    HealthResponse,
    HumanReviewRequest,
    MetricsResponse,
    ReportResponse,
    RunStatusResponse,
)

log = get_logger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Competitive Intelligence Briefing Crew API",
    description=(
        "Production-ready multi-agent competitive intelligence system. "
        "Automates weekly strategic briefings with citations, governance, and evaluation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for CPU-bound work
_executor = ThreadPoolExecutor(max_workers=4)

# In-memory run status cache (augments DB)
_run_status: Dict[str, Dict[str, Any]] = {}


# ── Startup / Shutdown ────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise resources on startup."""
    settings.ensure_directories()
    log.info("🚀 Competitive Intelligence API started")
    log.info(f"   Database: {settings.database_url}")
    log.info(f"   Model: {settings.model_primary}")
    log.info(f"   Docs: http://{settings.api_host}:{settings.api_port}/docs")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    log.info("Shutting down API server")


# ── Health ────────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """System health check."""
    db_status = "ok"
    try:
        db_manager.get_metrics_summary()
    except Exception:
        db_status = "error"

    cache_status = "ok"
    try:
        cache_manager.get_stats()
    except Exception:
        cache_status = "error"

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        database=db_status,
        cache=cache_status,
    )


# ── Generate ──────────────────────────────────────────────────────────────────


@app.post("/generate", response_model=BriefingResponse, tags=["Intelligence"])
async def generate_briefing(
    request: BriefingRequest,
    background_tasks: BackgroundTasks,
) -> BriefingResponse:
    """
    Start a competitive intelligence briefing run.
    The run executes asynchronously. Poll /status/{run_id} for progress.
    """
    run_id = str(uuid.uuid4())
    log.info(f"[API] /generate → run_id={run_id[:8]} industry={request.industry}")

    # Validate
    if len(request.competitors) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 competitors allowed")

    # Initialise status
    _run_status[run_id] = {
        "status": RunStatus.PENDING.value,
        "progress_percent": 0,
        "current_step": "Queued",
        "sources_collected": 0,
        "steps_used": 0,
        "estimated_cost_usd": 0.0,
    }

    # Start background run
    background_tasks.add_task(
        _run_workflow,
        run_id=run_id,
        industry=request.industry,
        competitors=request.competitors,
        region=request.region,
        time_period=request.time_period,
        max_sources=request.max_sources,
        max_steps=request.max_steps,
        export_formats=request.export_formats,
    )

    return BriefingResponse(
        run_id=run_id,
        status="started",
        message=f"Briefing run started. Monitor at /status/{run_id}",
        estimated_duration_seconds=settings.max_runtime_seconds,
    )


async def _run_workflow(
    run_id: str,
    industry: str,
    competitors: List[str],
    region: str,
    time_period: str,
    max_sources: int,
    max_steps: int,
    export_formats: List[str],
) -> None:
    """Execute the workflow in a thread pool (async-friendly)."""
    loop = asyncio.get_event_loop()

    def _progress_callback(msg: str, pct: int) -> None:
        _run_status[run_id] = {
            **_run_status.get(run_id, {}),
            "status": RunStatus.RUNNING.value,
            "progress_percent": pct,
            "current_step": msg,
        }

    def _run() -> None:
        try:
            _run_status[run_id]["status"] = RunStatus.RUNNING.value
            workflow = IntelligenceWorkflow(on_progress=_progress_callback)
            result = workflow.run(
                industry=industry,
                competitors=competitors,
                region=region,
                time_period=time_period,
                max_sources=max_sources,
                max_steps=max_steps,
                export_formats=export_formats,
                run_id=run_id,
            )
            _run_status[run_id] = {
                "status": result.status,
                "progress_percent": 100,
                "current_step": "Complete",
                "error": result.error,
                "sources_collected": result.report.metadata.sources_used if result.report else 0,
                "steps_used": result.report.metadata.steps_used if result.report else 0,
                "estimated_cost_usd": (
                    result.report.metadata.estimated_cost_usd if result.report else 0.0
                ),
            }
        except Exception as exc:
            log.error(f"[API] Background run {run_id[:8]} failed: {exc}")
            _run_status[run_id] = {
                "status": RunStatus.FAILED.value,
                "progress_percent": 0,
                "current_step": "Failed",
                "error": str(exc),
            }

    await loop.run_in_executor(_executor, _run)


# ── Status ────────────────────────────────────────────────────────────────────


@app.get("/status/{run_id}", response_model=RunStatusResponse, tags=["Intelligence"])
async def get_run_status(run_id: str) -> RunStatusResponse:
    """Get the current status of a running or completed briefing."""
    status = _run_status.get(run_id)
    if status:
        return RunStatusResponse(
            run_id=run_id,
            status=status.get("status", "unknown"),
            progress_percent=status.get("progress_percent", 0),
            current_step=status.get("current_step", ""),
            sources_collected=status.get("sources_collected", 0),
            steps_used=status.get("steps_used", 0),
            estimated_cost_usd=status.get("estimated_cost_usd", 0.0),
            error_message=status.get("error"),
        )

    # Check DB
    run = db_manager.get_run(run_id)
    if run:
        return RunStatusResponse(
            run_id=run_id,
            status=run.status,
            progress_percent=100 if run.status in ["completed", "failed"] else 50,
            current_step=run.status.capitalize(),
            sources_collected=run.sources_used or 0,
            steps_used=run.steps_used or 0,
            estimated_cost_usd=run.estimated_cost_usd or 0.0,
            error_message=run.error_message,
        )

    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


# ── Report ────────────────────────────────────────────────────────────────────


@app.get("/report/{run_id}", response_model=ReportResponse, tags=["Intelligence"])
async def get_report(run_id: str) -> ReportResponse:
    """Retrieve the completed briefing report."""
    report = db_manager.get_report(run_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Report for run {run_id} not found. Run may still be in progress.",
        )

    sources = []
    try:
        sources = json.loads(report.sources_json or "[]")
    except Exception:
        pass

    eval_score = None
    try:
        if report.evaluation_json:
            eval_data = json.loads(report.evaluation_json)
            eval_score = eval_data.get("overall_score")
    except Exception:
        pass

    return ReportResponse(
        run_id=run_id,
        title=report.title,
        generated_at=str(report.created_at),
        industry=report.industry or "",
        competitors=json.loads(report.competitors or "[]"),
        full_markdown=report.full_markdown or "",
        sources_count=len(sources),
        evaluation_score=eval_score,
        approved=report.approved or False,
    )


# ── Export ────────────────────────────────────────────────────────────────────


@app.post("/export", response_model=ExportResponse, tags=["Export"])
async def export_report(request: ExportRequest) -> ExportResponse:
    """Export a completed report in the specified format."""
    report = db_manager.get_report(request.run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {request.run_id} not found")

    briefing = report.full_markdown or ""
    run_id = request.run_id

    from src.tools.pdf_export import pdf_export_tool
    from src.tools.ppt_export import ppt_export_tool
    from src.tools.report_export import report_export_tool

    try:
        if request.format == "pdf":
            result = pdf_export_tool._run(briefing, run_id=run_id)
        elif request.format == "pptx":
            result = ppt_export_tool._run(briefing, run_id=run_id)
        elif request.format == "html":
            result = report_export_tool._run(briefing, "html", run_id)
        elif request.format == "json":
            result = report_export_tool._run(briefing, "json", run_id)
        else:  # markdown
            result = report_export_tool._run(briefing, "markdown", run_id)

        # Find the file path from result string
        file_path = ""
        for word in result.split():
            p = Path(word.strip("(),."))
            if p.exists():
                file_path = str(p)
                break

        if not file_path:
            file_path = str(settings.output_dir / f"briefing_{run_id}.{request.format}")

        size = Path(file_path).stat().st_size if Path(file_path).exists() else 0

        return ExportResponse(
            run_id=run_id,
            format=request.format,
            file_path=file_path,
            file_size_bytes=size,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")


@app.get("/export/download/{run_id}/{format}", tags=["Export"])
async def download_export(run_id: str, format: str) -> FileResponse:
    """Download an exported file directly."""
    ext_map = {"pdf": "pdf", "pptx": "pptx", "markdown": "md", "html": "html", "json": "json"}
    ext = ext_map.get(format, format)
    path = settings.output_dir / f"briefing_{run_id}.{ext}"

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Export file not found: {path}")

    return FileResponse(
        path=str(path),
        filename=f"competitive-intelligence-{run_id[:8]}.{ext}",
        media_type="application/octet-stream",
    )


# ── History ───────────────────────────────────────────────────────────────────


@app.get("/history", tags=["Intelligence"])
async def get_history(limit: int = Query(default=20, ge=1, le=100)) -> List[Dict]:
    """List recent briefing runs."""
    runs = db_manager.list_runs(limit=limit)
    return [
        {
            "run_id": r.run_id,
            "status": r.status,
            "industry": r.industry,
            "competitors": r.competitors,
            "started_at": str(r.started_at) if r.started_at else None,
            "duration_seconds": r.duration_seconds,
            "sources_used": r.sources_used,
            "estimated_cost_usd": r.estimated_cost_usd,
        }
        for r in runs
    ]


# ── Logs ──────────────────────────────────────────────────────────────────────


@app.get("/logs/{run_id}", tags=["Observability"])
async def get_logs(run_id: str) -> List[Dict]:
    """Get audit logs for a specific run."""
    records = db_manager.get_audit_logs(run_id)
    return [
        {
            "record_id": r.record_id,
            "timestamp": r.timestamp,
            "event_type": r.event_type,
            "agent": r.agent,
            "tool": r.tool,
            "model": r.model,
            "latency_ms": r.latency_ms,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "estimated_cost_usd": r.estimated_cost_usd,
            "success": r.success,
            "error_message": r.error_message,
            "citation_count": r.citation_count,
        }
        for r in records
    ]


# ── Metrics ───────────────────────────────────────────────────────────────────


@app.get("/metrics", response_model=MetricsResponse, tags=["Observability"])
async def get_metrics() -> MetricsResponse:
    """Get aggregate system metrics."""
    db_metrics = db_manager.get_metrics_summary()
    cache_stats = cache_manager.get_stats()

    return MetricsResponse(
        total_runs=db_metrics.get("total_runs", 0),
        completed_runs=db_metrics.get("completed_runs", 0),
        failed_runs=db_metrics.get("failed_runs", 0),
        success_rate=db_metrics.get("success_rate", 0.0),
        avg_duration_seconds=db_metrics.get("avg_duration_seconds", 0.0),
        total_cost_usd=db_metrics.get("total_cost_usd", 0.0),
        total_tokens=db_metrics.get("total_tokens", 0),
        cache_stats=cache_stats,
    )


# ── Evaluate ──────────────────────────────────────────────────────────────────


@app.get("/evaluate/{run_id}", response_model=EvaluationResponse, tags=["Evaluation"])
async def evaluate_report(run_id: str) -> EvaluationResponse:
    """Run evaluation on a completed report."""
    report = db_manager.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {run_id} not found")

    competitors = []
    try:
        competitors = json.loads(report.competitors or "[]")
    except Exception:
        pass

    result = evaluation_manager.evaluate_briefing(
        run_id=run_id,
        briefing=report.full_markdown or "",
        industry=report.industry or "",
        competitors=competitors,
    )

    # Store evaluation in DB
    try:
        db_manager.save_report(
            {
                "run_id": run_id,
                "evaluation_json": result.model_dump_json(),
            }
        )
    except Exception:
        pass

    return EvaluationResponse(
        run_id=run_id,
        faithfulness=result.faithfulness,
        answer_relevancy=result.answer_relevancy,
        context_precision=result.context_precision,
        context_recall=result.context_recall,
        hallucination_score=result.hallucination_score,
        citation_coverage=result.citation_coverage,
        overall_score=result.overall_score,
        passed=result.passed,
        notes=result.notes[:10],
    )


# ── Human Review ──────────────────────────────────────────────────────────────


@app.post("/review/{run_id}", tags=["Review"])
async def submit_review(
    run_id: str,
    review_request: HumanReviewRequest,
) -> Dict[str, Any]:
    """Submit a human review decision for a briefing."""
    decision = HumanReviewDecision(
        run_id=run_id,
        decision=ReviewDecision.APPROVED if review_request.approved else ReviewDecision.REJECTED,
        approved=review_request.approved,
        feedback=review_request.feedback,
        edited_sections=review_request.edited_sections,
        reviewer_id=review_request.reviewer_id,
    )

    audit_logger.log_human_review(
        run_id=run_id,
        approved=review_request.approved,
        feedback=review_request.feedback,
    )

    # If there are edits, update the stored report
    if review_request.edited_sections:
        report = db_manager.get_report(run_id)
        if report:
            import re

            updated_markdown = report.full_markdown or ""
            for section, content in review_request.edited_sections.items():
                pattern = rf"(## {re.escape(section)}.*?\n)(.*?)(?=\n## |\Z)"
                updated_markdown = re.sub(
                    pattern, rf"\g<1>{content}\n", updated_markdown, flags=re.DOTALL | re.IGNORECASE
                )
            db_manager.save_report(
                {
                    "run_id": run_id,
                    "full_markdown": updated_markdown,
                    "approved": review_request.approved,
                    "review_json": decision.model_dump_json(),
                }
            )

    return {
        "run_id": run_id,
        "decision": decision.decision.value,
        "message": "Review recorded",
    }


# ── Traces ────────────────────────────────────────────────────────────────────


@app.get("/traces/{run_id}", tags=["Observability"])
async def get_trace(run_id: str) -> Dict[str, Any]:
    """Get the full execution trace for a run."""
    from src.utils.observability import obs_tracker

    summary = obs_tracker.get_trace_summary(run_id)
    spans = obs_tracker.get_run_spans(run_id)

    return {
        "run_id": run_id,
        "summary": summary,
        "spans": [
            {
                "span_id": s.span_id[:8],
                "agent": s.agent,
                "operation": s.operation,
                "duration_ms": s.duration_ms,
                "success": s.success,
                "tokens": s.total_tokens,
                "cost": s.estimated_cost_usd,
            }
            for s in spans[:100]
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
