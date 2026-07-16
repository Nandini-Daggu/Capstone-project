"""
crew/crew.py
=============
Main CrewAI crew assembly using a cascade-patched LLM for automatic 429 fallback.

A single shared LLM instance (returned by make_cascade_llm) is passed to every
agent. When any LLM call returns a 429 / rate-limit error the LLM's patched
call() method immediately switches to the next model in the cascade and retries
— transparently, before CrewAI's own retry logic runs.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from crewai import Crew, Process, Task
from crewai.llm import LLM

from config.settings import settings
from src.agents.research_agent import ResearchAgent
from src.agents.analyst_agent import AnalystAgent
from src.agents.writer_agent import WriterAgent
from src.agents.supervisor import SupervisorAgent
from src.utils.audit import audit_logger
from src.utils.database import db_manager
from src.utils.llm_router import make_cascade_llm
from src.utils.logger import get_logger
from src.utils.models import RunMetadata, RunStatus
from src.utils.observability import obs_tracker
from .memory import get_run_memory

log = get_logger(__name__)


class IntelligenceCrew:
    """
    The Competitive Intelligence Briefing Crew.

    Pipeline: Research → Analysis → Writing
    All agents share one cascade-patched LLM that handles 429 fallback automatically.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        model_cascade: Optional[List[str]] = None,
        verbose: bool = True,
    ) -> None:
        cascade = list(model_cascade or settings.model_cascade)
        if model and model not in cascade:
            cascade.insert(0, model)

        # One shared LLM — all agents use this same object
        # make_cascade_llm returns a genuine crewai.llm.LLM with cascade patched in
        self._llm: LLM = make_cascade_llm(cascade)
        self._verbose = verbose

        self._research_factory = ResearchAgent(model=self._llm, verbose=verbose)
        self._analyst_factory = AnalystAgent(model=self._llm, verbose=verbose)
        self._writer_factory = WriterAgent(model=self._llm, verbose=verbose)
        self._supervisor_factory = SupervisorAgent(model=self._llm, verbose=verbose)

        log.info(f"[Crew] Ready | cascade={cascade}")

    @property
    def model(self) -> str:
        """
        Return the currently active model name.
        llm.model holds the STRIPPED name (no 'openrouter/' prefix) internally.
        We restore the full name for display/logging purposes.
        """
        stripped = self._llm.model or ""
        if stripped and not stripped.startswith("openrouter/"):
            return f"openrouter/{stripped}"
        return stripped

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _upsert_run_record(
        self,
        run_id: str,
        industry: str,
        competitors: List[str],
        region: str,
        time_period: str,
        max_sources: int,
        max_steps: int,
    ) -> None:
        """Insert on first call, update on subsequent calls (cascade retries)."""
        try:
            db_manager.create_run({
                "run_id": run_id,
                "status": RunStatus.RUNNING.value,
                "industry": industry,
                "competitors": str(competitors),
                "region": region,
                "time_period": time_period,
                "max_sources": max_sources,
                "max_steps": max_steps,
                "started_at": datetime.now(timezone.utc),
                "model_used": self.model,
            })
        except Exception as exc:
            if "unique" in str(exc).lower():
                try:
                    db_manager.update_run(run_id, {
                        "status": RunStatus.RUNNING.value,
                        "model_used": self.model,
                    })
                except Exception:
                    pass
            else:
                log.warning(f"[Crew] DB upsert failed (non-fatal): {exc}")

    # ── Public entry-point ────────────────────────────────────────────────────

    def run(
        self,
        industry: str,
        competitors: List[str],
        region: str = "Global",
        time_period: str = "last 7 days",
        max_sources: int = 15,
        max_steps: int = 25,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the pipeline. The cascade LLM handles 429 fallback internally.
        Returns: run_id, status, briefing, metadata, sources, error, model_used
        """
        run_id = run_id or str(uuid.uuid4())
        memory = get_run_memory(run_id)
        start_time = time.monotonic()

        log.info(
            f"[Crew] Starting {run_id[:8]} | "
            f"industry={industry} | competitors={competitors}"
        )

        self._upsert_run_record(
            run_id, industry, competitors, region, time_period, max_sources, max_steps
        )

        # ── Validate request ──────────────────────────────────
        valid, reason = self._supervisor_factory.validate_request(
            industry, competitors, region, run_id
        )
        if not valid:
            return {"run_id": run_id, "status": "failed", "error": reason, "briefing": ""}

        # ── Build agents ──────────────────────────────────────
        with obs_tracker.span(run_id, "crew", "build_agents"):
            research_agent = self._research_factory.build()
            analyst_agent = self._analyst_factory.build()
            writer_agent = self._writer_factory.build()

        # ── Build tasks ───────────────────────────────────────
        research_task = self._research_factory.create_research_task(
            industry=industry,
            competitors=competitors,
            region=region,
            time_period=time_period,
            run_id=run_id,
        )

        analysis_task = Task(
            description=(
                f"Analyse research for {industry} competitors "
                f"({', '.join(competitors)}). Run ID: {run_id}. "
                "Build competitor comparison matrix, SWOT, trends, risks, opportunities. "
                "Register all sources using citation_manager. Verify all citations."
            ),
            expected_output=(
                "Structured analysis with competitor matrix, SWOT, trends, risks, "
                "opportunities, and complete reference list with citations."
            ),
            agent=analyst_agent,
            context=[research_task],
        )

        writing_task = Task(
            description=(
                f"Write the complete executive briefing for {industry} competitors. "
                f"Industry: {industry}, Region: {region}, Period: {time_period}. "
                f"Run ID: {run_id}. "
                "Include ALL 12 sections. Every claim must have a [n] citation. "
                "Language must be board-ready McKinsey/BCG quality."
            ),
            expected_output=(
                "Complete Markdown briefing with all 12 sections: "
                "Executive Summary, Competitor Pricing, Product Updates, Market Signals, "
                "Industry Trends, SWOT, Risk Analysis, Opportunities, Recommendations, "
                "References, Run Metadata, Evaluation Summary."
            ),
            agent=writer_agent,
            context=[research_task, analysis_task],
        )

        # ── Assemble and run ──────────────────────────────────
        crew = Crew(
            agents=[research_agent, analyst_agent, writer_agent],
            tasks=[research_task, analysis_task, writing_task],
            process=Process.sequential,
            verbose=self._verbose,
            memory=False,   # disabled — avoids embedder 429s
        )

        try:
            with obs_tracker.span(run_id, "crew", "kickoff"):
                raw_result = crew.kickoff()
                elapsed = time.monotonic() - start_time

            # Extract text from various result shapes CrewAI may return
            if hasattr(raw_result, "raw"):
                briefing_text = raw_result.raw or str(raw_result)
            elif hasattr(raw_result, "final_output"):
                briefing_text = raw_result.final_output or str(raw_result)
            elif isinstance(raw_result, str):
                briefing_text = raw_result
            else:
                briefing_text = str(raw_result)

            memory.set_final_briefing(briefing_text)
            log.info(f"[Crew] {run_id[:8]} done in {elapsed:.1f}s | model={self.model}")

            metrics = obs_tracker.get_run_metrics(run_id)
            try:
                db_manager.update_run(run_id, {
                    "status": RunStatus.COMPLETED.value,
                    "completed_at": datetime.now(timezone.utc),
                    "duration_seconds": elapsed,
                    "sources_used": memory.get_sources_count(),
                    "steps_used": memory.get_steps_count(),
                    "total_tokens": int(metrics.get("total_tokens", 0)),
                    "estimated_cost_usd": float(metrics.get("estimated_cost_usd", 0.0)),
                    "model_used": self.model,
                })
            except Exception as db_exc:
                log.warning(f"[Crew] DB update failed (non-fatal): {db_exc}")

            run_metadata = RunMetadata(
                run_id=run_id,
                status=RunStatus.COMPLETED,
                industry=industry,
                competitors=competitors,
                region=region,
                time_period=time_period,
                duration_seconds=elapsed,
                sources_used=memory.get_sources_count(),
                steps_used=memory.get_steps_count(),
                total_tokens=int(metrics.get("total_tokens", 0)),
                estimated_cost_usd=float(metrics.get("estimated_cost_usd", 0.0)),
                model_used=self.model,
            )

            return {
                "run_id": run_id,
                "status": "completed",
                "briefing": briefing_text,
                "metadata": run_metadata,
                "sources": memory.get_sources(),
                "model_used": self.model,
                "error": None,
            }

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            log.error(f"[Crew] {run_id[:8]} failed after {elapsed:.1f}s: {exc}")
            audit_logger.log_error(run_id=run_id, agent="crew", tool=None, error=str(exc))
            try:
                db_manager.update_run(run_id, {
                    "status": RunStatus.FAILED.value,
                    "completed_at": datetime.now(timezone.utc),
                    "duration_seconds": elapsed,
                    "error_message": str(exc)[:500],
                })
            except Exception:
                pass
            return {
                "run_id": run_id,
                "status": "failed",
                "briefing": "",
                "metadata": None,
                "sources": [],
                "model_used": self.model,
                "error": str(exc),
            }


__all__ = ["IntelligenceCrew"]
