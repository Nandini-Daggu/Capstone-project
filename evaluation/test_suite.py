"""
evaluation/test_suite.py
=========================
Integrated evaluation test suite.
Combines RAGAS + DeepEval + Promptfoo into a single evaluation run.
Also provides the EvaluationManager class used by the API and frontend.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger
from src.utils.models import EvaluationResult
from .ragas_eval import ragas_evaluator
from .deepeval_eval import deepeval_evaluator
from .promptfoo_eval import promptfoo_evaluator

log = get_logger(__name__)


class EvaluationManager:
    """
    Unified evaluation manager.
    Runs all three evaluation frameworks and aggregates results.
    """

    def evaluate_briefing(
        self,
        run_id: str,
        briefing: str,
        industry: str,
        competitors: List[str],
        contexts: Optional[List[str]] = None,
        expected_output: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Run comprehensive evaluation on a generated briefing.

        Combines:
        - RAGAS: faithfulness, answer_relevancy, context_precision
        - DeepEval: hallucination, answer_correctness
        - Heuristics: citation_coverage, structure_completeness

        Returns merged EvaluationResult.
        """
        from config.settings import settings

        if not settings.evaluation_enabled:
            return EvaluationResult(
                run_id=run_id,
                notes=["Evaluation disabled in settings"],
            )

        log.info(f"[Eval] Starting evaluation for run {run_id[:8]}")
        start = time.monotonic()

        # ── RAGAS evaluation ──────────────────────────────────
        ragas_result = EvaluationResult(run_id=run_id, notes=["RAGAS skipped"])
        if settings.ragas_enabled:
            try:
                ragas_result = ragas_evaluator.evaluate_briefing(
                    run_id=run_id,
                    briefing=briefing,
                    industry=industry,
                    competitors=competitors,
                    contexts=contexts or [],
                )
            except Exception as exc:
                log.warning(f"[Eval] RAGAS failed: {exc}")

        # ── DeepEval evaluation ───────────────────────────────
        deepeval_result = EvaluationResult(run_id=run_id, notes=["DeepEval skipped"])
        if settings.deepeval_enabled:
            try:
                deepeval_result = deepeval_evaluator.run_full_evaluation(
                    run_id=run_id,
                    briefing=briefing,
                    contexts=contexts or [],
                    expected_output=expected_output,
                )
            except Exception as exc:
                log.warning(f"[Eval] DeepEval failed: {exc}")

        # ── Merge results ─────────────────────────────────────
        merged = EvaluationResult(
            run_id=run_id,
            faithfulness=ragas_result.faithfulness,
            answer_relevancy=ragas_result.answer_relevancy,
            context_precision=ragas_result.context_precision,
            context_recall=ragas_result.context_recall,
            hallucination_score=deepeval_result.hallucination_score,
            answer_correctness=deepeval_result.answer_correctness,
            citation_coverage=max(
                ragas_result.citation_coverage,
                deepeval_result.citation_coverage,
            ),
            tool_accuracy=self._compute_tool_accuracy(briefing),
            notes=ragas_result.notes + deepeval_result.notes,
        )

        elapsed = time.monotonic() - start
        log.info(
            f"[Eval] Run {run_id[:8]} evaluated in {elapsed:.1f}s: "
            f"overall={merged.overall_score:.2f} passed={merged.passed}"
        )

        return merged

    def _compute_tool_accuracy(self, briefing: str) -> float:
        """
        Heuristic tool accuracy score.
        Checks if all expected sections are present and citations are valid.
        """
        import re

        required = [
            "executive summary", "pricing", "product", "market",
            "swot", "risk", "opportunit", "recommend", "references",
        ]
        briefing_lower = briefing.lower()
        present = sum(1 for s in required if s in briefing_lower)
        section_score = present / len(required)

        # Citation check
        citation_count = len(re.findall(r"\[\d+\]", briefing))
        citation_score = min(citation_count / 10, 1.0)

        return round((section_score * 0.6 + citation_score * 0.4), 3)

    def run_regression_suite(
        self,
        run_callback,
    ) -> Dict[str, Any]:
        """
        Run the full 5-scenario regression suite via Promptfoo evaluator.
        """
        return promptfoo_evaluator.run_all_tests(run_callback)

    def generate_summary_markdown(self, result: EvaluationResult) -> str:
        """Generate a Markdown evaluation summary section."""
        status = "✅ PASSED" if result.passed else "❌ NEEDS REVIEW"
        return f"""## Evaluation Summary

**Status:** {status}

| Metric | Score | Threshold |
|--------|-------|-----------|
| Faithfulness | {result.faithfulness:.2f} | ≥ 0.70 |
| Answer Relevancy | {result.answer_relevancy:.2f} | ≥ 0.70 |
| Context Precision | {result.context_precision:.2f} | ≥ 0.60 |
| Citation Coverage | {result.citation_coverage:.2f} | ≥ 0.90 |
| Hallucination Score | {result.hallucination_score:.2f} | ≤ 0.10 |
| Tool Accuracy | {result.tool_accuracy:.2f} | ≥ 0.70 |
| **Overall Score** | **{result.overall_score:.2f}** | ≥ 0.70 |

**Notes:**
{chr(10).join(f"- {n}" for n in result.notes[:5])}

_Evaluated at: {result.evaluated_at[:19]}_
"""


# Singleton
evaluation_manager = EvaluationManager()

__all__ = ["EvaluationManager", "evaluation_manager"]
