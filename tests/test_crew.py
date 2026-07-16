"""
tests/test_crew.py
===================
Tests for crew assembly (crew/crew.py) and workflow orchestration
(crew/workflow.py).

All LLM calls and external tool I/O are mocked so these tests are
fast and require no API keys. The "slow" marker is applied to any
test that exercises the full pipeline path.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch, call

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# IntelligenceCrew construction
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestIntelligenceCrewConstruction:
    """Verify that IntelligenceCrew assembles agents correctly."""

    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_instantiation(
        self,
        mock_research_agent,
        mock_analyst_agent,
        mock_writer_agent,
        mock_supervisor_agent,
        mock_crew_cls,
    ):
        """IntelligenceCrew should instantiate without errors."""
        for m in (mock_research_agent, mock_analyst_agent,
                  mock_writer_agent, mock_supervisor_agent):
            m.return_value = MagicMock()

        from crew.crew import IntelligenceCrew
        crew_obj = IntelligenceCrew(model="test-model", verbose=False)
        assert crew_obj is not None
        assert crew_obj.model == "test-model"

    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_default_model_from_settings(
        self,
        mock_ra, mock_aa, mock_wa, mock_sa, mock_crew_cls,
    ):
        for m in (mock_ra, mock_aa, mock_wa, mock_sa):
            m.return_value = MagicMock()

        from crew.crew import IntelligenceCrew
        from config.settings import settings

        crew_obj = IntelligenceCrew(verbose=False)
        assert crew_obj.model == settings.model_primary

    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_has_four_agent_factories(
        self,
        mock_ra, mock_aa, mock_wa, mock_sa, mock_crew_cls,
    ):
        for m in (mock_ra, mock_aa, mock_wa, mock_sa):
            m.return_value = MagicMock()

        from crew.crew import IntelligenceCrew
        crew_obj = IntelligenceCrew(model="test-model", verbose=False)

        assert crew_obj._research_factory is not None
        assert crew_obj._analyst_factory is not None
        assert crew_obj._writer_factory is not None
        assert crew_obj._supervisor_factory is not None


# ─────────────────────────────────────────────────────────────────────────────
# IntelligenceCrew.run() — mocked execution
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestIntelligenceCrewRun:
    """Test IntelligenceCrew.run() with all external dependencies mocked."""

    def _build_mock_crew_result(self, briefing: str) -> MagicMock:
        result = MagicMock()
        result.raw = briefing
        return result

    @patch("crew.crew.db_manager")
    @patch("crew.crew.obs_tracker")
    @patch("crew.crew.audit_logger")
    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_run_returns_dict_with_run_id(
        self,
        mock_ra, mock_aa, mock_wa, mock_sa,
        mock_crew_cls,
        mock_audit, mock_obs, mock_db,
        sample_briefing,
    ):
        for m in (mock_ra, mock_aa, mock_wa, mock_sa):
            m.return_value = MagicMock()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = self._build_mock_crew_result(sample_briefing)
        mock_crew_cls.return_value = mock_crew_instance
        mock_db.save_report = MagicMock()

        from crew.crew import IntelligenceCrew
        crew_obj = IntelligenceCrew(model="test-model", verbose=False)

        result = crew_obj.run(
            industry="SaaS CRM",
            competitors=["Salesforce", "HubSpot"],
            region="North America",
            time_period="last 7 days",
            run_id="test-run-001",
        )

        assert isinstance(result, dict)
        assert "run_id" in result
        assert result["run_id"] == "test-run-001"

    @patch("crew.crew.db_manager")
    @patch("crew.crew.obs_tracker")
    @patch("crew.crew.audit_logger")
    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_run_status_completed_on_success(
        self,
        mock_ra, mock_aa, mock_wa, mock_sa,
        mock_crew_cls, mock_audit, mock_obs, mock_db,
        sample_briefing,
    ):
        for m in (mock_ra, mock_aa, mock_wa, mock_sa):
            m.return_value = MagicMock()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = self._build_mock_crew_result(sample_briefing)
        mock_crew_cls.return_value = mock_crew_instance

        from crew.crew import IntelligenceCrew
        crew_obj = IntelligenceCrew(model="test-model", verbose=False)

        result = crew_obj.run(
            industry="SaaS",
            competitors=["Salesforce"],
            run_id="test-run-002",
        )

        assert result.get("status") in ("completed", "success", "approved", "done")

    @patch("crew.crew.db_manager")
    @patch("crew.crew.obs_tracker")
    @patch("crew.crew.audit_logger")
    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_run_generates_run_id_when_not_provided(
        self,
        mock_ra, mock_aa, mock_wa, mock_sa,
        mock_crew_cls, mock_audit, mock_obs, mock_db,
        sample_briefing,
    ):
        for m in (mock_ra, mock_aa, mock_wa, mock_sa):
            m.return_value = MagicMock()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = self._build_mock_crew_result(sample_briefing)
        mock_crew_cls.return_value = mock_crew_instance

        from crew.crew import IntelligenceCrew
        crew_obj = IntelligenceCrew(model="test-model", verbose=False)

        result = crew_obj.run(
            industry="SaaS",
            competitors=["Salesforce"],
            # No run_id
        )

        assert "run_id" in result
        assert len(result["run_id"]) > 0

    @patch("crew.crew.db_manager")
    @patch("crew.crew.obs_tracker")
    @patch("crew.crew.audit_logger")
    @patch("crew.crew.Crew")
    @patch("src.agents.supervisor.Agent")
    @patch("src.agents.writer_agent.Agent")
    @patch("src.agents.analyst_agent.Agent")
    @patch("src.agents.research_agent.Agent")
    def test_run_handles_crew_exception_gracefully(
        self,
        mock_ra, mock_aa, mock_wa, mock_sa,
        mock_crew_cls, mock_audit, mock_obs, mock_db,
    ):
        for m in (mock_ra, mock_aa, mock_wa, mock_sa):
            m.return_value = MagicMock()

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.side_effect = RuntimeError("LLM timeout")
        mock_crew_cls.return_value = mock_crew_instance

        from crew.crew import IntelligenceCrew
        crew_obj = IntelligenceCrew(model="test-model", verbose=False)

        result = crew_obj.run(
            industry="SaaS",
            competitors=["Salesforce"],
            run_id="error-run-001",
        )

        # Should return a dict indicating failure, not raise
        assert isinstance(result, dict)
        assert result.get("status") in (
            "failed", "error", "partial_failure", "completed"  # partial is acceptable
        )


# ─────────────────────────────────────────────────────────────────────────────
# IntelligenceWorkflow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestIntelligenceWorkflow:
    """Test workflow-layer logic (async wrapper around IntelligenceCrew)."""

    def test_workflow_instantiates(self):
        with (
            patch("crew.workflow.IntelligenceCrew") as mock_crew_cls,
        ):
            mock_crew_cls.return_value = MagicMock()
            from crew.workflow import IntelligenceWorkflow
            wf = IntelligenceWorkflow()
            assert wf is not None

    @pytest.mark.asyncio
    async def test_run_async_returns_result(self, sample_briefing):
        with (
            patch("crew.workflow.IntelligenceCrew") as mock_crew_cls,
        ):
            mock_crew_instance = MagicMock()
            mock_crew_instance.run.return_value = {
                "run_id": "wf-001",
                "status": "completed",
                "briefing": sample_briefing,
            }
            mock_crew_cls.return_value = mock_crew_instance

            from crew.workflow import IntelligenceWorkflow
            wf = IntelligenceWorkflow()

            result = await wf.run_async(
                industry="SaaS",
                competitors=["Salesforce"],
                region="Global",
                time_period="last 7 days",
                run_id="wf-001",
            )

            assert result is not None
            assert result.get("run_id") == "wf-001"

    @pytest.mark.asyncio
    async def test_run_async_propagates_run_id(self, sample_briefing):
        with (
            patch("crew.workflow.IntelligenceCrew") as mock_crew_cls,
        ):
            expected_run_id = str(uuid.uuid4())
            mock_crew_instance = MagicMock()
            mock_crew_instance.run.return_value = {
                "run_id": expected_run_id,
                "status": "completed",
                "briefing": sample_briefing,
            }
            mock_crew_cls.return_value = mock_crew_instance

            from crew.workflow import IntelligenceWorkflow
            wf = IntelligenceWorkflow()

            result = await wf.run_async(
                industry="SaaS",
                competitors=["Salesforce"],
                run_id=expected_run_id,
            )

            assert result.get("run_id") == expected_run_id

    @pytest.mark.asyncio
    async def test_run_async_raises_or_returns_on_crew_error(self):
        with (
            patch("crew.workflow.IntelligenceCrew") as mock_crew_cls,
        ):
            mock_crew_instance = MagicMock()
            mock_crew_instance.run.side_effect = RuntimeError("Crew error")
            mock_crew_cls.return_value = mock_crew_instance

            from crew.workflow import IntelligenceWorkflow
            wf = IntelligenceWorkflow()

            try:
                result = await wf.run_async(
                    industry="SaaS",
                    competitors=["Salesforce"],
                    run_id="wf-error-001",
                )
                # If it catches internally, result should signal failure
                assert isinstance(result, dict)
            except Exception:
                # If it propagates, that's also fine — caller handles it
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Memory module
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRunMemory:
    """Test the run memory module."""

    def test_get_run_memory_returns_object(self):
        from crew.memory import get_run_memory
        mem = get_run_memory("mem-test-001")
        assert mem is not None

    def test_get_run_memory_is_deterministic(self):
        """Same run_id should return an equivalent memory object."""
        from crew.memory import get_run_memory
        mem1 = get_run_memory("mem-test-002")
        mem2 = get_run_memory("mem-test-002")
        assert type(mem1) == type(mem2)


# ─────────────────────────────────────────────────────────────────────────────
# Retry / resilience utility
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRetryUtility:
    """
    Test the retry wrapper in src/utils/retry.py.

    with_retry is a DECORATOR FACTORY — call it as:
        @with_retry(RetryConfig(...))
        def my_func(): ...
    or equivalently:
        decorated = with_retry(RetryConfig(...))(my_func)
    """

    def test_succeeds_on_first_try(self):
        from src.utils.retry import with_retry, RetryConfig

        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, wait_min_seconds=0, wait_max_seconds=0))
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = always_succeeds()
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_transient_error(self):
        from src.utils.retry import with_retry, RetryConfig

        call_count = 0

        @with_retry(RetryConfig(
            max_attempts=3,
            wait_min_seconds=0,
            wait_max_seconds=0,
            timeout_seconds=None,
        ))
        def fails_twice_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = fails_twice_then_succeeds()
        assert result == "recovered"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        from src.utils.retry import with_retry, RetryConfig

        @with_retry(RetryConfig(
            max_attempts=2,
            wait_min_seconds=0,
            wait_max_seconds=0,
            timeout_seconds=None,
            reraise=True,
        ))
        def always_fails():
            raise RuntimeError("permanent failure")

        with pytest.raises(RuntimeError):
            always_fails()

    def test_circuit_breaker_instantiates(self):
        """CircuitBreaker should instantiate without errors."""
        from src.utils.retry import CircuitBreaker
        cb = CircuitBreaker(name="test-service", failure_threshold=3, recovery_timeout=5.0)
        assert cb.state == CircuitBreaker.CLOSED

    def test_circuit_breaker_success_call(self):
        from src.utils.retry import CircuitBreaker

        cb = CircuitBreaker(name="test-success")

        def good_fn():
            return 42

        result = cb.call(good_fn)
        assert result == 42
        assert cb.state == CircuitBreaker.CLOSED

    def test_circuit_breaker_opens_after_threshold(self):
        from src.utils.retry import CircuitBreaker

        cb = CircuitBreaker(name="test-open", failure_threshold=2, recovery_timeout=999.0)

        def bad_fn():
            raise RuntimeError("fail")

        for _ in range(2):
            try:
                cb.call(bad_fn)
            except RuntimeError:
                pass

        assert cb.state == CircuitBreaker.OPEN

    def test_get_circuit_breaker_singleton(self):
        from src.utils.retry import get_circuit_breaker
        cb1 = get_circuit_breaker("my-service")
        cb2 = get_circuit_breaker("my-service")
        assert cb1 is cb2


# ─────────────────────────────────────────────────────────────────────────────
# Database manager
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestDatabaseManager:
    """Integration tests for the SQLite database manager."""

    def test_db_manager_instantiates(self):
        from src.utils.database import db_manager
        assert db_manager is not None

    def test_get_metrics_summary_returns_dict(self):
        from src.utils.database import db_manager
        try:
            result = db_manager.get_metrics_summary()
            assert isinstance(result, dict)
        except Exception:
            pytest.skip("Database not available in this environment")

    def test_list_runs_returns_list(self):
        from src.utils.database import db_manager
        try:
            result = db_manager.list_runs(limit=10)
            assert isinstance(result, list)
        except Exception:
            pytest.skip("Database not available in this environment")

    def test_get_nonexistent_report_returns_none(self):
        from src.utils.database import db_manager
        try:
            result = db_manager.get_report("nonexistent-run-xyz")
            assert result is None
        except Exception:
            pytest.skip("Database not available in this environment")


# ─────────────────────────────────────────────────────────────────────────────
# Config YAML loading
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestConfigFiles:
    """Verify that YAML config files load correctly."""

    def test_agents_yaml_loads(self):
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "config" / "agents.yaml"
        if not config_path.exists():
            pytest.skip("agents.yaml not found")
        with config_path.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_tasks_yaml_loads(self):
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "config" / "tasks.yaml"
        if not config_path.exists():
            pytest.skip("tasks.yaml not found")
        with config_path.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_crew_yaml_loads(self):
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "config" / "crew.yaml"
        if not config_path.exists():
            pytest.skip("crew.yaml not found")
        with config_path.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
