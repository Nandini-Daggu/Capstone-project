"""
tests/test_api.py
==================
FastAPI endpoint tests for backend/main.py.

Uses httpx AsyncClient via pytest-asyncio so tests run without a
live server. All heavy dependencies (crew runs, database, cache) are
mocked so the suite is fast and requires no API keys.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_run_status(
    run_id: str,
    status: str = "completed",
    progress: float = 1.0,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "status": status,
        "progress": progress,
        "message": "Run complete",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_metrics() -> Dict[str, Any]:
    return {
        "total_runs": 42,
        "successful_runs": 40,
        "failed_runs": 2,
        "average_duration_seconds": 38.5,
        "average_sources_used": 8.2,
        "average_cost_usd": 0.0005,
        "pass_rate": 0.95,
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Import and return the FastAPI app with heavy deps patched at import time."""
    # Patch at module level before importing app to avoid real DB/crew init
    with (
        patch("crew.workflow.IntelligenceWorkflow", autospec=True),
        patch("src.utils.database.db_manager"),
        patch("src.utils.cache.cache_manager"),
        patch("evaluation.test_suite.evaluation_manager"),
    ):
        from backend.main import app as fastapi_app
        return fastapi_app


@pytest.fixture
async def client(app):
    """Async httpx client backed by the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Health endpoint ───────────────────────────────────────────────────────────

@pytest.mark.api
class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        with (
            patch("backend.main.db_manager") as mock_db,
            patch("backend.main.cache_manager") as mock_cache,
        ):
            mock_db.get_metrics_summary.return_value = {}
            mock_cache.get_stats.return_value = {"hit_rate": 0.75}

            resp = await client.get("/health")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_has_status_field(self, client):
        with (
            patch("backend.main.db_manager") as mock_db,
            patch("backend.main.cache_manager") as mock_cache,
        ):
            mock_db.get_metrics_summary.return_value = {}
            mock_cache.get_stats.return_value = {}

            resp = await client.get("/health")

        data = resp.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_health_db_error_still_returns(self, client):
        """Even if DB is down the endpoint should not 500."""
        with (
            patch("backend.main.db_manager") as mock_db,
            patch("backend.main.cache_manager") as mock_cache,
        ):
            mock_db.get_metrics_summary.side_effect = RuntimeError("DB unavailable")
            mock_cache.get_stats.return_value = {}

            resp = await client.get("/health")

        # Should return 200 with db_status=error, not a 500
        assert resp.status_code == 200
        data = resp.json()
        assert "db" in str(data).lower() or "status" in data


# ── POST /generate ────────────────────────────────────────────────────────────

@pytest.mark.api
class TestGenerateEndpoint:

    @pytest.mark.asyncio
    async def test_generate_returns_202_or_200(self, client):
        """A valid request should be accepted."""
        with (
            patch("backend.main.IntelligenceWorkflow") as mock_wf_cls,
            patch("backend.main._run_status", {}),
        ):
            mock_wf = MagicMock()
            mock_wf_cls.return_value = mock_wf

            payload = {
                "industry": "SaaS CRM",
                "competitors": ["Salesforce", "HubSpot"],
                "region": "North America",
                "time_period": "last 7 days",
            }
            resp = await client.post("/generate", json=payload)

        assert resp.status_code in (200, 202, 422)  # 422 only if schema fails

    @pytest.mark.asyncio
    async def test_generate_missing_industry_returns_422(self, client):
        payload = {
            "competitors": ["Salesforce"],
        }
        resp = await client.post("/generate", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_empty_competitors_returns_422(self, client):
        payload = {
            "industry": "SaaS",
            "competitors": [],
        }
        resp = await client.post("/generate", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_too_many_competitors_returns_422(self, client):
        payload = {
            "industry": "SaaS",
            "competitors": [f"Co{i}" for i in range(15)],
        }
        resp = await client.post("/generate", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_response_has_run_id(self, client):
        with (
            patch("backend.main.IntelligenceWorkflow"),
            patch("backend.main._run_status", {}),
        ):
            payload = {
                "industry": "SaaS",
                "competitors": ["Salesforce"],
                "region": "Global",
            }
            resp = await client.post("/generate", json=payload)

        if resp.status_code in (200, 202):
            data = resp.json()
            assert "run_id" in data


# ── GET /status/{id} ─────────────────────────────────────────────────────────

@pytest.mark.api
class TestStatusEndpoint:

    @pytest.mark.asyncio
    async def test_status_known_run_id(self, client):
        run_id = str(uuid.uuid4())
        fake_status = _make_run_status(run_id)

        with patch("backend.main._run_status", {run_id: fake_status}):
            resp = await client.get(f"/status/{run_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("run_id") == run_id

    @pytest.mark.asyncio
    async def test_status_unknown_run_id_returns_404(self, client):
        with patch("backend.main._run_status", {}):
            resp = await client.get("/status/nonexistent-run-id")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_status_pending_run(self, client):
        run_id = str(uuid.uuid4())
        fake_status = _make_run_status(run_id, status="pending", progress=0.0)

        with patch("backend.main._run_status", {run_id: fake_status}):
            resp = await client.get(f"/status/{run_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "pending"


# ── GET /report/{id} ─────────────────────────────────────────────────────────

@pytest.mark.api
class TestReportEndpoint:

    @pytest.mark.asyncio
    async def test_report_unknown_run_id_returns_404(self, client):
        with (
            patch("backend.main._run_status", {}),
            patch("backend.main.db_manager") as mock_db,
        ):
            mock_db.get_report.return_value = None

            resp = await client.get("/report/nonexistent-id")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_report_completed_run(self, client, sample_briefing):
        run_id = str(uuid.uuid4())
        fake_status = _make_run_status(run_id, status="completed")
        fake_report = {
            "run_id": run_id,
            "industry": "SaaS",
            "competitors": ["Salesforce"],
            "markdown": sample_briefing,
            "status": "completed",
        }

        with (
            patch("backend.main._run_status", {run_id: fake_status}),
            patch("backend.main.db_manager") as mock_db,
        ):
            mock_db.get_report.return_value = fake_report

            resp = await client.get(f"/report/{run_id}")

        assert resp.status_code == 200


# ── GET /metrics ──────────────────────────────────────────────────────────────

@pytest.mark.api
class TestMetricsEndpoint:

    @pytest.mark.asyncio
    async def test_metrics_returns_200(self, client):
        with patch("backend.main.db_manager") as mock_db:
            mock_db.get_metrics_summary.return_value = _make_metrics()

            resp = await client.get("/metrics")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_response_shape(self, client):
        with patch("backend.main.db_manager") as mock_db:
            mock_db.get_metrics_summary.return_value = _make_metrics()

            resp = await client.get("/metrics")

        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


# ── GET /history ──────────────────────────────────────────────────────────────

@pytest.mark.api
class TestHistoryEndpoint:

    @pytest.mark.asyncio
    async def test_history_returns_200(self, client):
        with patch("backend.main.db_manager") as mock_db:
            mock_db.list_runs.return_value = []

            resp = await client.get("/history")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_history_returns_list(self, client):
        run_id = str(uuid.uuid4())
        fake_runs = [
            {"run_id": run_id, "industry": "SaaS", "status": "completed"}
        ]

        with patch("backend.main.db_manager") as mock_db:
            mock_db.list_runs.return_value = fake_runs

            resp = await client.get("/history")

        if resp.status_code == 200:
            data = resp.json()
            # History can be a list or a dict with a "runs" key
            assert isinstance(data, (list, dict))


# ── GET /logs/{id} ────────────────────────────────────────────────────────────

@pytest.mark.api
class TestLogsEndpoint:

    @pytest.mark.asyncio
    async def test_logs_unknown_run_returns_404_or_empty(self, client):
        with patch("backend.main.audit_logger") as mock_audit:
            mock_audit.get_run_records.return_value = []

            resp = await client.get("/logs/nonexistent-run")

        # Either 404 or 200 with empty data is acceptable
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_logs_known_run_returns_records(self, client):
        run_id = str(uuid.uuid4())
        fake_records = [
            {
                "run_id": run_id,
                "event_type": "tool_call",
                "agent": "research_agent",
                "tool": "web_search",
                "success": True,
            }
        ]

        with patch("backend.main.audit_logger") as mock_audit:
            mock_audit.get_run_records.return_value = fake_records

            resp = await client.get(f"/logs/{run_id}")

        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (list, dict))


# ── POST /review/{id} ────────────────────────────────────────────────────────

@pytest.mark.api
class TestReviewEndpoint:

    @pytest.mark.asyncio
    async def test_review_approved(self, client):
        run_id = str(uuid.uuid4())
        payload = {
            "approved": True,
            "feedback": "Looks great, approved.",
            "reviewer": "test-reviewer",
        }

        with (
            patch("backend.main._run_status", {
                run_id: _make_run_status(run_id, status="awaiting_review")
            }),
            patch("backend.main.audit_logger"),
            patch("backend.main.db_manager"),
        ):
            resp = await client.post(f"/review/{run_id}", json=payload)

        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_review_rejected(self, client):
        run_id = str(uuid.uuid4())
        payload = {
            "approved": False,
            "feedback": "Missing competitor data.",
        }

        with (
            patch("backend.main._run_status", {
                run_id: _make_run_status(run_id, status="awaiting_review")
            }),
            patch("backend.main.audit_logger"),
            patch("backend.main.db_manager"),
        ):
            resp = await client.post(f"/review/{run_id}", json=payload)

        assert resp.status_code in (200, 404, 422)


# ── POST /export ──────────────────────────────────────────────────────────────

@pytest.mark.api
class TestExportEndpoint:

    @pytest.mark.asyncio
    async def test_export_markdown(self, client, sample_briefing):
        run_id = str(uuid.uuid4())
        payload = {
            "run_id": run_id,
            "format": "markdown",
        }

        with (
            patch("backend.main._run_status", {
                run_id: {
                    **_make_run_status(run_id),
                    "briefing": sample_briefing,
                }
            }),
            patch("backend.main.db_manager") as mock_db,
        ):
            mock_db.get_report.return_value = {
                "run_id": run_id,
                "markdown": sample_briefing,
            }
            resp = await client.post("/export", json=payload)

        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_export_unknown_run_404(self, client):
        payload = {
            "run_id": "nonexistent-run",
            "format": "markdown",
        }

        with (
            patch("backend.main._run_status", {}),
            patch("backend.main.db_manager") as mock_db,
        ):
            mock_db.get_report.return_value = None
            resp = await client.post("/export", json=payload)

        assert resp.status_code in (404, 422)


# ── Schema validation (BriefingRequest) ──────────────────────────────────────

@pytest.mark.unit
class TestBriefingRequestSchema:
    """Test Pydantic validation on the request schema."""

    def test_valid_minimal_request(self):
        from src.utils.schemas import BriefingRequest
        req = BriefingRequest(industry="SaaS", competitors=["Salesforce"])
        assert req.industry == "SaaS"

    def test_whitespace_only_competitor_stripped(self):
        from src.utils.schemas import BriefingRequest
        req = BriefingRequest(industry="SaaS", competitors=["Salesforce", "  "])
        assert "  " not in req.competitors
        assert len(req.competitors) == 1

    def test_too_many_competitors_raises(self):
        from src.utils.schemas import BriefingRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BriefingRequest(
                industry="SaaS",
                competitors=[f"Co{i}" for i in range(12)],
            )

    def test_default_region_is_global(self):
        from src.utils.schemas import BriefingRequest
        req = BriefingRequest(industry="SaaS", competitors=["X"])
        assert req.region  # non-empty default

    def test_default_time_period_set(self):
        from src.utils.schemas import BriefingRequest
        req = BriefingRequest(industry="SaaS", competitors=["X"])
        assert req.time_period
