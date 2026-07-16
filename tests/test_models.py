"""
tests/test_models.py
=====================
Unit tests for Pydantic domain models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestResearchItem:
    def test_valid_item(self):
        from src.utils.models import ResearchItem, ResearchCategory
        item = ResearchItem(
            competitor="Salesforce",
            category=ResearchCategory.NEWS,
            title="Salesforce Q3",
            summary="Q3 results.",
            source_url="https://salesforce.com",
            source_name="Salesforce IR",
        )
        assert item.competitor == "Salesforce"
        assert item.confidence_level.value == "high"

    def test_confidence_level_medium(self):
        from src.utils.models import ResearchItem, ResearchCategory, ConfidenceLevel
        item = ResearchItem(
            competitor="X",
            category=ResearchCategory.PRICING,
            title="T",
            summary="S",
            source_url="https://x.com",
            source_name="X",
            confidence=0.65,
        )
        assert item.confidence_level == ConfidenceLevel.MEDIUM

    def test_confidence_level_low(self):
        from src.utils.models import ResearchItem, ResearchCategory, ConfidenceLevel
        item = ResearchItem(
            competitor="X",
            category=ResearchCategory.PRICING,
            title="T",
            summary="S",
            source_url="https://x.com",
            source_name="X",
            confidence=0.4,
        )
        assert item.confidence_level == ConfidenceLevel.LOW


class TestCitedSource:
    def test_valid_source(self):
        from src.utils.models import CitedSource
        s = CitedSource(
            url="https://example.com",
            title="Example",
            source_name="Example News",
        )
        assert s.url == "https://example.com"

    def test_empty_url_raises(self):
        from src.utils.models import CitedSource
        with pytest.raises(ValidationError):
            CitedSource(url="", title="X", source_name="Y")

    def test_whitespace_url_raises(self):
        from src.utils.models import CitedSource
        with pytest.raises(ValidationError):
            CitedSource(url="   ", title="X", source_name="Y")


class TestEvaluationResult:
    def test_overall_score_computed(self):
        from src.utils.models import EvaluationResult
        r = EvaluationResult(
            run_id="test-run",
            faithfulness=0.9,
            answer_relevancy=0.85,
            context_precision=0.80,
            citation_coverage=0.95,
            hallucination_score=0.05,
        )
        assert r.overall_score > 0
        assert r.passed is True

    def test_fails_when_hallucination_high(self):
        from src.utils.models import EvaluationResult
        r = EvaluationResult(
            run_id="test-run",
            faithfulness=0.9,
            answer_relevancy=0.9,
            context_precision=0.9,
            citation_coverage=0.9,
            hallucination_score=0.5,  # Too high
        )
        assert r.passed is False

    def test_fails_when_citation_coverage_low(self):
        from src.utils.models import EvaluationResult
        r = EvaluationResult(
            run_id="test-run",
            faithfulness=0.9,
            answer_relevancy=0.9,
            context_precision=0.9,
            citation_coverage=0.3,   # Too low
            hallucination_score=0.05,
        )
        assert r.passed is False


class TestBriefingReport:
    def test_to_full_markdown(self, sample_briefing):
        from src.utils.models import BriefingReport, RunMetadata
        report = BriefingReport(
            run_id="test-001",
            industry="SaaS",
            competitors=["Salesforce"],
            region="Global",
            time_period="last 7 days",
            executive_summary="Strong quarter for Salesforce [1].",
            full_markdown=sample_briefing,
            metadata=RunMetadata(run_id="test-001"),
        )
        md = report.to_full_markdown()
        assert "# Competitive Intelligence Briefing" in md
        assert "Executive Summary" in md
        assert "Run Metadata" in md

    def test_metadata_section(self):
        from src.utils.models import BriefingReport, RunMetadata
        meta = RunMetadata(
            run_id="m-001",
            sources_used=8,
            steps_used=15,
            total_tokens=3000,
            estimated_cost_usd=0.001,
            duration_seconds=42.5,
            model_used="gemma-4-31b-it",
        )
        report = BriefingReport(run_id="m-001", metadata=meta)
        section = report._metadata_section()
        assert "8" in section
        assert "15" in section
        assert "42.5" in section


class TestRunMetadata:
    def test_default_run_id_generated(self):
        from src.utils.models import RunMetadata
        m = RunMetadata()
        assert len(m.run_id) == 36  # UUID format

    def test_status_pending_by_default(self):
        from src.utils.models import RunMetadata, RunStatus
        m = RunMetadata()
        assert m.status == RunStatus.PENDING


class TestSchemas:
    def test_briefing_request_valid(self):
        from src.utils.schemas import BriefingRequest
        req = BriefingRequest(
            industry="SaaS",
            competitors=["Salesforce", "HubSpot"],
            region="North America",
        )
        assert req.industry == "SaaS"
        assert len(req.competitors) == 2

    def test_briefing_request_empty_competitor_stripped(self):
        from src.utils.schemas import BriefingRequest
        req = BriefingRequest(
            industry="SaaS",
            competitors=["Salesforce", "  ", "HubSpot"],
        )
        assert len(req.competitors) == 2

    def test_briefing_request_too_many_competitors(self):
        from src.utils.schemas import BriefingRequest
        with pytest.raises(ValidationError):
            BriefingRequest(
                industry="SaaS",
                competitors=[f"Co{i}" for i in range(12)],  # > 10
            )
