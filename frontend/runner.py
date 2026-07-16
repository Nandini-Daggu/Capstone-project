"""
frontend/runner.py
===================
Direct in-process crew runner for Streamlit.
Used when running app.py standalone (no separate FastAPI server).
Also provides an API client for when the backend is running separately.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from config.settings import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class DirectRunner:
    """
    Runs the intelligence workflow directly in-process.
    Used for standalone streamlit run app.py deployments.
    """

    def run(
        self,
        industry: str,
        competitors: List[str],
        region: str,
        time_period: str,
        max_sources: int,
        max_steps: int,
        export_formats: List[str],
        on_progress: Optional[Callable[[str, int], None]] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the workflow and return results."""
        from crew.workflow import IntelligenceWorkflow

        run_id = run_id or str(uuid.uuid4())

        def _progress(msg: str, pct: int) -> None:
            if on_progress:
                on_progress(msg, pct)

        workflow = IntelligenceWorkflow(on_progress=_progress)
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

        if result.status == "completed" and result.report:
            return {
                "run_id": run_id,
                "status": "completed",
                "full_markdown": result.report.full_markdown or result.report.to_full_markdown(),
                "sources": [s.model_dump() for s in result.report.sources],
                "metadata": result.report.metadata.model_dump() if result.report.metadata else {},
                "export_paths": result.export_paths,
                "error": None,
            }
        else:
            return {
                "run_id": run_id,
                "status": "failed",
                "full_markdown": "",
                "sources": [],
                "metadata": {},
                "export_paths": {},
                "error": result.error or "Unknown error",
            }


class APIClient:
    """
    HTTP client for the FastAPI backend.
    Used when running with docker-compose or separate processes.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """POST /generate"""
        import requests as req

        resp = req.post(f"{self.base_url}/generate", json=request, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def poll_status(self, run_id: str) -> Dict[str, Any]:
        """GET /status/{run_id}"""
        import requests as req

        resp = req.get(f"{self.base_url}/status/{run_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_report(self, run_id: str) -> Dict[str, Any]:
        """GET /report/{run_id}"""
        import requests as req

        resp = req.get(f"{self.base_url}/report/{run_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_metrics(self) -> Dict[str, Any]:
        """GET /metrics"""
        import requests as req

        resp = req.get(f"{self.base_url}/metrics", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def evaluate(self, run_id: str) -> Dict[str, Any]:
        """GET /evaluate/{run_id}"""
        import requests as req

        resp = req.get(f"{self.base_url}/evaluate/{run_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def submit_review(self, run_id: str, review: Dict[str, Any]) -> Dict[str, Any]:
        """POST /review/{run_id}"""
        import requests as req

        resp = req.post(f"{self.base_url}/review/{run_id}", json=review, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def is_available(self) -> bool:
        """Check if the backend is reachable."""
        try:
            import requests as req

            resp = req.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


def get_runner(api_base_url: Optional[str] = None) -> Any:
    """
    Return the appropriate runner based on environment.
    Prefers API client if backend is available, falls back to direct runner.
    """
    if api_base_url:
        client = APIClient(api_base_url)
        if client.is_available():
            return client
    return DirectRunner()
