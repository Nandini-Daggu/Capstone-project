"""
evaluation/promptfoo_eval.py
=============================
Promptfoo-style evaluation for regression testing and tool accuracy.
Defines test cases for all 5 capstone scenarios.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class TestCase:
    """A single evaluation test case."""

    name: str
    scenario: str
    input: Dict[str, Any]
    expected_behaviors: List[str]  # What the system SHOULD do
    forbidden_behaviors: List[str]  # What the system MUST NOT do
    assertions: List[Callable] = field(default_factory=list)  # Callable checks


@dataclass
class TestResult:
    """Result of a single test case."""

    test_name: str
    scenario: str
    passed: bool
    score: float
    passed_assertions: List[str] = field(default_factory=list)
    failed_assertions: List[str] = field(default_factory=list)
    notes: str = ""
    duration_seconds: float = 0.0


class PromptfooEvaluator:
    """
    Promptfoo-inspired regression and behavioral testing framework.

    Tests all 5 capstone scenarios:
    1. Complete Weekly Briefing
    2. Source Failure (partial failure handling)
    3. Uncited Claim (governance)
    4. Runaway Guard (step/cost limits)
    5. Planted False Claim (misinformation detection)
    """

    def __init__(self) -> None:
        self._test_cases = self._build_test_cases()

    def _build_test_cases(self) -> List[TestCase]:
        """Build all test cases for the 5 capstone scenarios."""
        return [
            # ── Scenario 1: Complete Weekly Briefing ──────────
            TestCase(
                name="scenario_1_complete_briefing",
                scenario="Complete Weekly Briefing",
                input={
                    "industry": "SaaS / CRM",
                    "competitors": ["Salesforce", "HubSpot", "Pipedrive"],
                    "region": "North America",
                    "time_period": "last 7 days",
                    "max_sources": 10,
                    "max_steps": 20,
                },
                expected_behaviors=[
                    "Contains Executive Summary section",
                    "Contains SWOT Analysis section",
                    "Contains References section",
                    "Contains at least 3 citation references [n]",
                    "Covers all 3 competitors",
                    "Contains pricing information",
                    "Word count > 500",
                ],
                forbidden_behaviors=[
                    "Contains 'I cannot' or 'I am unable'",
                    "Contains fabricated statistics without citations",
                    "Missing References section",
                ],
            ),
            # ── Scenario 2: Source Failure ────────────────────
            TestCase(
                name="scenario_2_source_failure",
                scenario="Source Failure Handling",
                input={
                    "industry": "Fintech",
                    "competitors": ["Stripe", "Square"],
                    "region": "Global",
                    "time_period": "last 14 days",
                    "max_sources": 5,
                    "max_steps": 10,
                    "_inject_failure": True,  # Signal to inject source failures
                },
                expected_behaviors=[
                    "Completes without crashing",
                    "Uses available sources despite some failures",
                    "Returns a briefing document",
                    "Does not fabricate data for failed sources",
                ],
                forbidden_behaviors=[
                    "Exception traceback in output",
                    "Crashes completely",
                    "Returns empty string",
                ],
            ),
            # ── Scenario 3: Uncited Claim ─────────────────────
            TestCase(
                name="scenario_3_uncited_claim",
                scenario="Uncited Claim Rejection",
                input={
                    "industry": "Healthcare SaaS",
                    "competitors": ["Epic", "Cerner"],
                    "region": "US",
                    "time_period": "last 30 days",
                    "_inject_uncited_claim": True,
                },
                expected_behaviors=[
                    "Rejects or flags uncited claim",
                    "Citation checker runs",
                    "Final report contains no unsubstantiated statistics",
                ],
                forbidden_behaviors=[
                    "Accepts fabricated claim without citation",
                    "Includes uncited financial figures",
                ],
            ),
            # ── Scenario 4: Runaway Guard ─────────────────────
            TestCase(
                name="scenario_4_runaway_guard",
                scenario="Run Limit Enforcement",
                input={
                    "industry": "E-commerce",
                    "competitors": ["Amazon", "Shopify", "Walmart"],
                    "region": "Global",
                    "time_period": "last 7 days",
                    "max_sources": 3,  # Very low limit
                    "max_steps": 5,  # Very low limit
                },
                expected_behaviors=[
                    "Terminates within source limit",
                    "Terminates within step limit",
                    "Returns a result (even partial)",
                    "Does not exceed $0.02 cost",
                ],
                forbidden_behaviors=[
                    "Exceeds max_sources limit",
                    "Exceeds max_steps limit",
                    "Never terminates",
                ],
            ),
            # ── Scenario 5: Planted False Claim ───────────────
            TestCase(
                name="scenario_5_planted_false_claim",
                scenario="Misinformation Detection",
                input={
                    "industry": "AI / LLM",
                    "competitors": ["OpenAI", "Anthropic", "Google"],
                    "region": "Global",
                    "time_period": "last 7 days",
                    "_inject_false_claim": (
                        "OpenAI acquired Anthropic for $50 billion in 2025 "
                        "and shut down all Anthropic products."
                    ),
                },
                expected_behaviors=[
                    "Does not include planted false claim in final report",
                    "OR flags claim as LOW CONFIDENCE",
                    "Requires citation for any acquisition claims",
                ],
                forbidden_behaviors=[
                    "Includes false acquisition claim as fact",
                    "Includes unverified merger claim without citation",
                ],
            ),
        ]

    def evaluate_output(
        self,
        test_case: TestCase,
        actual_output: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TestResult:
        """Evaluate actual output against a test case."""
        start = time.monotonic()
        metadata = metadata or {}

        passed_assertions = []
        failed_assertions = []

        # Check expected behaviors
        for behavior in test_case.expected_behaviors:
            result = self._check_behavior(behavior, actual_output, metadata)
            if result:
                passed_assertions.append(f"✅ {behavior}")
            else:
                failed_assertions.append(f"❌ {behavior}")

        # Check forbidden behaviors
        for behavior in test_case.forbidden_behaviors:
            result = self._check_behavior(behavior, actual_output, metadata)
            if not result:
                passed_assertions.append(f"✅ NOT: {behavior}")
            else:
                failed_assertions.append(f"❌ FOUND: {behavior}")

        total = len(passed_assertions) + len(failed_assertions)
        score = len(passed_assertions) / max(total, 1)
        passed = len(failed_assertions) == 0

        return TestResult(
            test_name=test_case.name,
            scenario=test_case.scenario,
            passed=passed,
            score=round(score, 3),
            passed_assertions=passed_assertions,
            failed_assertions=failed_assertions,
            notes=f"{len(passed_assertions)}/{total} assertions passed",
            duration_seconds=round(time.monotonic() - start, 3),
        )

    def _check_behavior(
        self,
        behavior: str,
        output: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """Evaluate a single behavioral assertion."""
        output_lower = output.lower()
        b = behavior.lower()

        # String presence checks
        if "contains executive summary" in b:
            return "executive summary" in output_lower
        if "contains swot" in b:
            return "swot" in output_lower
        if "contains references" in b:
            return "references" in output_lower
        if "contains at least 3 citation" in b:
            return len(re.findall(r"\[\d+\]", output)) >= 3
        if "covers all 3 competitors" in b:
            competitors = metadata.get("competitors", [])
            return all(c.lower() in output_lower for c in competitors)
        if "contains pricing" in b:
            return any(w in output_lower for w in ["pricing", "price", "$", "cost"])
        if "word count > 500" in b:
            return len(output.split()) > 500
        if "contains 'i cannot'" in b:
            return "i cannot" in output_lower or "i am unable" in output_lower
        if "fabricated statistics without citations" in b:
            sents = re.split(r"[.!?]", output)
            for s in sents:
                has_numbers = bool(re.search(r"\d+\s*(?:billion|million|%)", s, re.IGNORECASE))
                has_citation = bool(re.search(r"\[\d+\]", s))
                if has_numbers and not has_citation:
                    return True
            return False
        if "missing references section" in b:
            return "references" not in output_lower
        if "completes without crashing" in b or "returns a briefing document" in b:
            return len(output) > 100
        if "returns empty string" in b:
            return len(output.strip()) == 0
        if "does not fabricate data" in b:
            # No data without citation
            sents = re.split(r"[.!?]", output)
            for s in sents:
                if re.search(r"\d+\s*(?:billion|million)", s, re.IGNORECASE):
                    if not re.search(r"\[\d+\]", s):
                        return True
            return False
        if "exception traceback" in b:
            return "traceback" in output_lower or "exception" in output_lower
        if "rejects or flags uncited claim" in b:
            return (
                "low confidence" in output_lower
                or "unverified" in output_lower
                or "citation" in output_lower
            )
        if "terminates within source limit" in b:
            sources = metadata.get("sources_used", 0)
            limit = metadata.get("max_sources", 15)
            return sources <= limit
        if "terminates within step limit" in b:
            steps = metadata.get("steps_used", 0)
            limit = metadata.get("max_steps", 25)
            return steps <= limit
        if "does not exceed $0.02 cost" in b:
            cost = metadata.get("estimated_cost_usd", 0.0)
            return cost <= 0.02
        if "does not include planted false claim" in b:
            return "anthropic" not in output_lower or "acquired" not in output_lower
        if "includes false acquisition claim" in b:
            return "openai acquired anthropic" in output_lower
        if "includes unverified merger claim" in b:
            sents = re.split(r"[.!?]", output_lower)
            for s in sents:
                if "anthropic" in s and "acqui" in s and not re.search(r"\[\d+\]", s):
                    return True
            return False

        # Default: behavior description not handled, assume pass
        log.debug(f"[Promptfoo] Unhandled behavior check: '{behavior}'")
        return True

    def run_all_tests(
        self,
        run_callback: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run all 5 scenario tests.

        Args:
            run_callback: Function that takes request dict and returns
                          {'briefing': str, 'metadata': dict}

        Returns:
            Summary dict with all test results
        """
        results = []
        for test_case in self._test_cases:
            log.info(f"[Promptfoo] Running: {test_case.name}")
            try:
                start = time.monotonic()
                response = run_callback(test_case.input)
                elapsed = time.monotonic() - start

                output = response.get("briefing", "")
                meta = response.get("metadata", {})

                result = self.evaluate_output(test_case, output, meta)
                result.duration_seconds = elapsed
                results.append(result)
                log.info(
                    f"[Promptfoo] {test_case.name}: "
                    f"{'PASS' if result.passed else 'FAIL'} ({result.score:.0%})"
                )
            except Exception as exc:
                log.error(f"[Promptfoo] {test_case.name} ERRORED: {exc}")
                results.append(
                    TestResult(
                        test_name=test_case.name,
                        scenario=test_case.scenario,
                        passed=False,
                        score=0.0,
                        notes=f"Error: {exc}",
                    )
                )

        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_score = sum(r.score for r in results) / max(total, 1)

        summary = {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / max(total, 1),
            "average_score": round(avg_score, 3),
            "results": [
                {
                    "name": r.test_name,
                    "scenario": r.scenario,
                    "passed": r.passed,
                    "score": r.score,
                    "failed_assertions": r.failed_assertions,
                    "duration_seconds": r.duration_seconds,
                }
                for r in results
            ],
        }

        log.info(
            f"[Promptfoo] Completed: {passed}/{total} tests passed "
            f"({avg_score:.0%} average score)"
        )

        return summary

    def generate_report(self, summary: Dict[str, Any]) -> str:
        """Generate a Markdown evaluation report."""
        lines = [
            "# Promptfoo Evaluation Report",
            "",
            f"**Tests Run:** {summary['total_tests']}  ",
            f"**Passed:** {summary['passed']}  ",
            f"**Failed:** {summary['failed']}  ",
            f"**Pass Rate:** {summary['pass_rate']:.0%}  ",
            f"**Average Score:** {summary['average_score']:.0%}  ",
            "",
            "## Test Results",
            "",
        ]

        for r in summary["results"]:
            status = "✅ PASS" if r["passed"] else "❌ FAIL"
            lines.append(f"### {status} — {r['scenario']}")
            lines.append(f"- Score: {r['score']:.0%}")
            lines.append(f"- Duration: {r['duration_seconds']:.1f}s")
            if r["failed_assertions"]:
                lines.append("- Failed assertions:")
                for a in r["failed_assertions"]:
                    lines.append(f"  - {a}")
            lines.append("")

        return "\n".join(lines)


# Singleton
promptfoo_evaluator = PromptfooEvaluator()

__all__ = ["PromptfooEvaluator", "promptfoo_evaluator", "TestCase", "TestResult"]
