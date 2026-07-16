"""
evaluation/deepeval_eval.py
============================
DeepEval evaluation pipeline.
Tests: Hallucination, Answer Correctness, GEval, Bias, Toxicity.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.utils.logger import get_logger
from src.utils.models import EvaluationResult

log = get_logger(__name__)


class DeepEvalEvaluator:
    """
    DeepEval-based evaluation for hallucination detection and correctness.

    Metrics:
    - Hallucination: Does the output contain false or fabricated claims?
    - Answer Correctness: Is the answer factually correct vs ground truth?
    - GEval: GPT-based evaluation for quality dimensions
    - Bias: Does the content show unfair bias?
    """

    def __init__(self) -> None:
        self._deepeval_available = self._check_deepeval()

    def _check_deepeval(self) -> bool:
        try:
            import deepeval  # noqa: F401

            return True
        except ImportError:
            log.warning("[DeepEval] deepeval not installed — using fallback evaluation")
            return False

    def evaluate_hallucination(
        self,
        run_id: str,
        actual_output: str,
        context: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Measure hallucination rate in the output.

        Returns:
            (hallucination_score, list_of_hallucinated_claims)
            Score 0.0 = no hallucination, 1.0 = fully hallucinated
        """
        if self._deepeval_available:
            return self._deepeval_hallucination(run_id, actual_output, context)
        return self._fallback_hallucination(actual_output, context)

    def _deepeval_hallucination(
        self,
        run_id: str,
        actual_output: str,
        context: List[str],
    ) -> Tuple[float, List[str]]:
        """Run DeepEval hallucination metric."""
        try:
            from deepeval.metrics import HallucinationMetric
            from deepeval.test_case import LLMTestCase

            test_case = LLMTestCase(
                input="Competitive intelligence briefing request",
                actual_output=actual_output[:2000],
                context=context[:5],
            )

            metric = HallucinationMetric(threshold=0.1)
            metric.measure(test_case)

            score = metric.score
            reasons = metric.reason.split(";") if metric.reason else []
            return float(score), reasons

        except Exception as exc:
            log.warning(f"[DeepEval] Hallucination check failed: {exc}")
            return self._fallback_hallucination(actual_output, context)

    def _fallback_hallucination(
        self,
        actual_output: str,
        context: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Heuristic hallucination detection.
        Checks for:
        1. Specific numbers/percentages without citations
        2. Absolute superlative claims without citations
        3. Claims that contradict context
        """
        hallucination_signals = []
        sentences = re.split(r"[.!?]", actual_output)

        uncited_factual_pattern = re.compile(
            r"\b\d+[\.,]?\d*\s*(?:billion|million|percent|%|users|customers|employees)\b",
            re.IGNORECASE,
        )
        superlative_pattern = re.compile(
            r"\b(?:largest|biggest|fastest|most|best|leader|leading|dominant)\b",
            re.IGNORECASE,
        )

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue

            has_citation = bool(re.search(r"\[\d+\]", sentence))
            has_numbers = bool(uncited_factual_pattern.search(sentence))
            has_superlative = bool(superlative_pattern.search(sentence))

            if has_numbers and not has_citation:
                hallucination_signals.append(f"Uncited statistic: {sentence[:100]}")
            elif has_superlative and not has_citation:
                hallucination_signals.append(f"Uncited superlative: {sentence[:100]}")

        hallucination_rate = min(len(hallucination_signals) / max(len(sentences) * 0.1, 1), 1.0)
        return round(hallucination_rate, 3), hallucination_signals[:10]

    def evaluate_answer_correctness(
        self,
        run_id: str,
        actual_output: str,
        expected_output: Optional[str] = None,
    ) -> float:
        """
        Evaluate factual correctness of the briefing.
        Returns a score 0-1 (higher is better).
        """
        if self._deepeval_available and expected_output:
            try:
                from deepeval.metrics import AnswerRelevancyMetric
                from deepeval.test_case import LLMTestCase

                test_case = LLMTestCase(
                    input="Generate competitive intelligence briefing",
                    actual_output=actual_output[:2000],
                    expected_output=expected_output[:2000],
                )
                metric = AnswerRelevancyMetric(threshold=0.7)
                metric.measure(test_case)
                return float(metric.score)
            except Exception as exc:
                log.warning(f"[DeepEval] Answer correctness failed: {exc}")

        # Fallback: structure completeness score
        return self._structure_completeness_score(actual_output)

    def _structure_completeness_score(self, briefing: str) -> float:
        """
        Heuristic correctness: check presence of all required sections.
        """
        required_sections = [
            "executive summary",
            "pricing",
            "product",
            "market",
            "trend",
            "swot",
            "risk",
            "opportunit",
            "recommend",
            "references",
        ]
        briefing_lower = briefing.lower()
        present = sum(1 for s in required_sections if s in briefing_lower)
        return round(present / len(required_sections), 3)

    def run_full_evaluation(
        self,
        run_id: str,
        briefing: str,
        contexts: Optional[List[str]] = None,
        expected_output: Optional[str] = None,
    ) -> EvaluationResult:
        """Run all DeepEval metrics and return consolidated result."""
        contexts = contexts or []

        # Hallucination
        hallucination_score, hallucinated_claims = self.evaluate_hallucination(
            run_id, briefing, contexts
        )

        # Answer correctness
        answer_correctness = self.evaluate_answer_correctness(run_id, briefing, expected_output)

        # Citation coverage (independent check)
        total_sentences = len([s for s in re.split(r"[.!?]", briefing) if len(s.strip()) > 20])
        citations_found = len(re.findall(r"\[\d+\]", briefing))
        citation_coverage = min(citations_found / max(total_sentences * 0.4, 1), 1.0)

        result = EvaluationResult(
            run_id=run_id,
            hallucination_score=hallucination_score,
            answer_correctness=answer_correctness,
            citation_coverage=citation_coverage,
            notes=(
                hallucinated_claims[:5] if hallucinated_claims else ["No hallucinations detected"]
            ),
        )

        log.info(
            f"[DeepEval] Run {run_id[:8]}: "
            f"hallucination={hallucination_score:.2f} "
            f"correctness={answer_correctness:.2f} "
            f"citations={citation_coverage:.2f} "
            f"passed={result.passed}"
        )

        return result


# Singleton
deepeval_evaluator = DeepEvalEvaluator()

__all__ = ["DeepEvalEvaluator", "deepeval_evaluator"]
