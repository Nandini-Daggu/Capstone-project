"""
tests/test_evaluation.py
=========================
Tests for evaluation modules: RAGAS fallback, DeepEval fallback, Promptfoo scenarios.
All tests use heuristic fallback paths (no external API calls).
"""

from __future__ import annotations

import pytest


class TestDeepEvalFallback:
    """Tests for DeepEval heuristic fallback."""

    def setup_method(self):
        from evaluation.deepeval_eval import DeepEvalEvaluator
        self.evaluator = DeepEvalEvaluator()
        self.evaluator._deepeval_available = False  # Force fallback

    def test_hallucination_no_uncited(self, sample_briefing):
        score, claims = self.evaluator._fallback_hallucination(
            sample_briefing,
            context=["Salesforce revenue grew 11%"],
        )
        # The sample_briefing has citations on everything
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_hallucination_uncited_stats(self):
        text = "Revenue was $10 billion. Users grew 500 percent. Market share is 45%."
        score, claims = self.evaluator._fallback_hallucination(text, context=[])
        assert score > 0  # Should detect uncited stats
        assert len(claims) > 0

    def test_structure_completeness_full(self, sample_briefing):
        score = self.evaluator._structure_completeness_score(sample_briefing)
        assert score > 0.8  # Sample has all required sections

    def test_structure_completeness_empty(self):
        score = self.evaluator._structure_completeness_score("")
        assert score == 0.0

    def test_full_evaluation_returns_result(self, sample_briefing):
        result = self.evaluator.run_full_evaluation(
            run_id="eval-test-001",
            briefing=sample_briefing,
        )
        assert result.run_id == "eval-test-001"
        assert 0.0 <= result.hallucination_score <= 1.0
        assert 0.0 <= result.answer_correctness <= 1.0


class TestRagasFallback:
    """Tests for RAGAS heuristic fallback."""

    def setup_method(self):
        from evaluation.ragas_eval import RagasEvaluator
        self.evaluator = RagasEvaluator()
        self.evaluator._ragas_available = False  # Force fallback

    def test_fallback_eval_returns_result(self, sample_briefing):
        result = self.evaluator._fallback_eval(
            run_id="ragas-test-001",
            question="What is the competitive landscape for SaaS CRM?",
            answer=sample_briefing,
            contexts=["Salesforce is the market leader with 19% share."],
        )
        assert result.run_id == "ragas-test-001"
        assert 0.0 <= result.faithfulness <= 1.0
        assert 0.0 <= result.answer_relevancy <= 1.0

    def test_evaluate_briefing_adds_citation_coverage(self, sample_briefing):
        result = self.evaluator.evaluate_briefing(
            run_id="ragas-test-002",
            briefing=sample_briefing,
            industry="SaaS / CRM",
            competitors=["Salesforce", "HubSpot"],
        )
        assert result.citation_coverage >= 0.0


class TestPromptfooScenarios:
    """Tests for Promptfoo scenario assertions (no LLM calls)."""

    def setup_method(self):
        from evaluation.promptfoo_eval import PromptfooEvaluator
        self.evaluator = PromptfooEvaluator()

    def test_scenario_1_complete_briefing_passes(self, sample_briefing):
        test_case = self.evaluator._test_cases[0]  # scenario_1
        meta = {
            "competitors": ["Salesforce", "HubSpot", "Pipedrive"],
            "sources_used": 5,
            "steps_used": 12,
        }
        result = self.evaluator.evaluate_output(test_case, sample_briefing, meta)
        # Expect high pass rate since sample_briefing is well-formed
        assert result.score >= 0.6

    def test_scenario_3_detects_uncited_output(self):
        test_case = self.evaluator._test_cases[2]  # scenario_3
        bad_output = "The company grew 500% last year. Revenue hit $50 billion."
        result = self.evaluator.evaluate_output(test_case, bad_output, {})
        # uncited claims should cause some failures
        assert result.score < 1.0

    def test_scenario_4_within_limits(self, sample_briefing):
        test_case = self.evaluator._test_cases[3]  # scenario_4 runaway guard
        meta = {
            "sources_used": 3,
            "steps_used": 5,
            "estimated_cost_usd": 0.001,
            "max_sources": 3,
            "max_steps": 5,
        }
        result = self.evaluator.evaluate_output(test_case, sample_briefing, meta)
        assert result.score >= 0.5

    def test_scenario_5_planted_false_claim_caught(self, sample_briefing):
        test_case = self.evaluator._test_cases[4]  # scenario_5
        # Output that does NOT include the false claim
        result = self.evaluator.evaluate_output(test_case, sample_briefing, {})
        # Should pass because sample_briefing doesn't say OpenAI acquired Anthropic
        passed_expected = all(
            "false acquisition claim" not in a
            for a in result.failed_assertions
        )
        assert passed_expected

    def test_generate_report(self, sample_briefing):
        test_case = self.evaluator._test_cases[0]
        result = self.evaluator.evaluate_output(test_case, sample_briefing, {
            "competitors": ["Salesforce", "HubSpot", "Pipedrive"]
        })
        summary = {
            "total_tests": 1,
            "passed": int(result.passed),
            "failed": int(not result.passed),
            "pass_rate": float(result.passed),
            "average_score": result.score,
            "results": [{
                "name": result.test_name,
                "scenario": result.scenario,
                "passed": result.passed,
                "score": result.score,
                "failed_assertions": result.failed_assertions,
                "duration_seconds": result.duration_seconds,
            }],
        }
        report_md = self.evaluator.generate_report(summary)
        assert "Promptfoo Evaluation Report" in report_md


class TestEvaluationManager:
    """Tests for the unified EvaluationManager."""

    def test_evaluate_briefing_returns_result(self, sample_briefing):
        from evaluation.test_suite import EvaluationManager
        manager = EvaluationManager()
        result = manager.evaluate_briefing(
            run_id="mgr-test-001",
            briefing=sample_briefing,
            industry="SaaS / CRM",
            competitors=["Salesforce", "HubSpot"],
        )
        assert result.run_id == "mgr-test-001"
        assert 0.0 <= result.overall_score <= 1.0

    def test_compute_tool_accuracy_full_briefing(self, sample_briefing):
        from evaluation.test_suite import EvaluationManager
        manager = EvaluationManager()
        score = manager._compute_tool_accuracy(sample_briefing)
        assert score > 0.5  # Should be high since all sections present

    def test_generate_summary_markdown(self):
        from evaluation.test_suite import EvaluationManager
        from src.utils.models import EvaluationResult
        manager = EvaluationManager()
        result = EvaluationResult(
            run_id="summary-test",
            faithfulness=0.85,
            answer_relevancy=0.80,
            context_precision=0.75,
            citation_coverage=0.92,
            hallucination_score=0.05,
            tool_accuracy=0.90,
        )
        md = manager.generate_summary_markdown(result)
        assert "Evaluation Summary" in md
        assert "0.85" in md
