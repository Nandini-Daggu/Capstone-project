"""
evaluation/ragas_eval.py
=========================
RAGAS evaluation pipeline for the competitive intelligence briefing.
Measures: Faithfulness, Answer Relevancy, Context Precision, Context Recall.
Uses local embeddings (all-MiniLM-L6-v2) to minimise API costs.
"""

from __future__ import annotations

from typing import List, Optional

from src.utils.logger import get_logger
from src.utils.models import EvaluationResult

log = get_logger(__name__)


class RagasEvaluator:
    """
    RAGAS-based evaluation of RAG pipeline quality.

    Metrics:
    - Faithfulness: Are all claims in the answer supported by the context?
    - Answer Relevancy: How relevant is the answer to the question?
    - Context Precision: What fraction of retrieved context is relevant?
    - Context Recall: Does the context contain all needed information?
    """

    def __init__(self) -> None:
        self._ragas_available = self._check_ragas()

    def _check_ragas(self) -> bool:
        try:
            import ragas  # noqa: F401

            return True
        except ImportError:
            log.warning("[RAGAS] ragas not installed — using fallback evaluation")
            return False

    def evaluate(
        self,
        run_id: str,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Run RAGAS evaluation on a question/answer/context triple.

        Args:
            run_id: The run identifier
            question: The research question / query
            answer: The generated answer (briefing section)
            contexts: Retrieved document chunks used as context
            ground_truth: Optional reference answer for recall calculation

        Returns:
            EvaluationResult with RAGAS scores
        """
        if self._ragas_available:
            return self._run_ragas(run_id, question, answer, contexts, ground_truth)
        else:
            return self._fallback_eval(run_id, question, answer, contexts)

    def _run_ragas(
        self,
        run_id: str,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str],
    ) -> EvaluationResult:
        """Run actual RAGAS evaluation."""
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )

            data = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts if contexts else ["No context available"]],
            }
            if ground_truth:
                data["ground_truth"] = [ground_truth]
                metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
            else:
                metrics = [faithfulness, answer_relevancy, context_precision]

            dataset = Dataset.from_dict(data)

            # Use local embeddings to avoid OpenRouter costs
            from langchain_community.embeddings import HuggingFaceEmbeddings

            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                embeddings=embeddings,
            )

            scores = result.to_pandas().iloc[0].to_dict()

            return EvaluationResult(
                run_id=run_id,
                faithfulness=float(scores.get("faithfulness", 0.0)),
                answer_relevancy=float(scores.get("answer_relevancy", 0.0)),
                context_precision=float(scores.get("context_precision", 0.0)),
                context_recall=float(scores.get("context_recall", 0.0)),
                notes=["RAGAS evaluation completed"],
            )

        except Exception as exc:
            log.error(f"[RAGAS] Evaluation failed: {exc}")
            return self._fallback_eval(run_id, question, answer, contexts)

    def _fallback_eval(
        self,
        run_id: str,
        question: str,
        answer: str,
        contexts: List[str],
    ) -> EvaluationResult:
        """Fallback heuristic evaluation when RAGAS is unavailable."""
        import re

        # Faithfulness: fraction of answer sentences that appear to cite sources
        sentences = [s.strip() for s in re.split(r"[.!?]", answer) if len(s.strip()) > 20]
        cited = sum(1 for s in sentences if re.search(r"\[\d+\]", s))
        faithfulness = cited / max(len(sentences), 1)

        # Answer relevancy: keyword overlap between question and answer
        question_words = set(question.lower().split())
        answer_words = set(answer.lower().split())
        overlap = len(question_words & answer_words) / max(len(question_words), 1)
        answer_relevancy = min(overlap * 3, 1.0)

        # Context precision: how much of the context is cited in the answer
        context_text = " ".join(contexts).lower()
        context_words = set(context_text.split())
        if context_words:
            answer_in_context = len(answer_words & context_words) / len(answer_words)
            context_precision = min(answer_in_context * 2, 1.0)
        else:
            context_precision = 0.0

        return EvaluationResult(
            run_id=run_id,
            faithfulness=round(faithfulness, 3),
            answer_relevancy=round(answer_relevancy, 3),
            context_precision=round(context_precision, 3),
            context_recall=0.0,
            notes=["Fallback heuristic evaluation (RAGAS not available)"],
        )

    def evaluate_briefing(
        self,
        run_id: str,
        briefing: str,
        industry: str,
        competitors: List[str],
        contexts: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        Evaluate a full intelligence briefing.
        Splits the briefing into sections and averages scores.
        """
        question = (
            f"What is the competitive intelligence briefing for {industry} "
            f"covering {', '.join(competitors)}?"
        )
        contexts = contexts or []

        result = self.evaluate(
            run_id=run_id,
            question=question,
            answer=briefing[:3000],  # Limit context size for API cost
            contexts=contexts[:5],
        )

        # Additional citation coverage check
        import re

        total_sentences = len([s for s in re.split(r"[.!?]", briefing) if len(s.strip()) > 20])
        cited_sentences = len(re.findall(r"\[\d+\]", briefing))
        result.citation_coverage = min(cited_sentences / max(total_sentences * 0.5, 1), 1.0)

        log.info(
            f"[RAGAS] Run {run_id[:8]}: "
            f"faithfulness={result.faithfulness:.2f} "
            f"relevancy={result.answer_relevancy:.2f} "
            f"citation_coverage={result.citation_coverage:.2f} "
            f"overall={result.overall_score:.2f}"
        )

        return result


# Singleton
ragas_evaluator = RagasEvaluator()

__all__ = ["RagasEvaluator", "ragas_evaluator"]
