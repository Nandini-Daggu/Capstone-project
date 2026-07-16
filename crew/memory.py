"""
crew/memory.py
===============
Crew-level shared memory management.
Stores intermediate results between agent steps so context is not lost.
Uses the CacheManager for persistence across restarts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.utils.cache import cache_manager
from src.utils.logger import get_logger

log = get_logger(__name__)


class CrewMemory:
    """
    Shared memory store for a single crew run.
    Agents can read/write intermediate results without passing huge context.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._store: Dict[str, Any] = {}

    # ── Write ─────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        """Store a value in run memory."""
        self._store[key] = value
        cache_manager.set(
            namespace=f"memory:{self.run_id}",
            key=key,
            value=value,
        )
        log.debug(f"[Memory:{self.run_id}] SET {key}")

    def set_research_output(self, output: str) -> None:
        self.set("research_output", output)

    def set_rag_context(self, context: str) -> None:
        self.set("rag_context", context)

    def set_analysis_output(self, output: str) -> None:
        self.set("analysis_output", output)

    def set_draft_briefing(self, draft: str) -> None:
        self.set("draft_briefing", draft)

    def set_final_briefing(self, final: str) -> None:
        self.set("final_briefing", final)

    def set_sources(self, sources: List[Dict]) -> None:
        self.set("sources", sources)

    def append_source(self, source: Dict) -> None:
        sources = self.get_sources()
        sources.append(source)
        self.set_sources(sources)

    # ── Read ──────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from run memory."""
        if key in self._store:
            return self._store[key]
        cached = cache_manager.get(namespace=f"memory:{self.run_id}", key=key)
        if cached is not None:
            self._store[key] = cached
            return cached
        return default

    def get_research_output(self) -> Optional[str]:
        return self.get("research_output")

    def get_rag_context(self) -> Optional[str]:
        return self.get("rag_context")

    def get_analysis_output(self) -> Optional[str]:
        return self.get("analysis_output")

    def get_draft_briefing(self) -> Optional[str]:
        return self.get("draft_briefing")

    def get_final_briefing(self) -> Optional[str]:
        return self.get("final_briefing")

    def get_sources(self) -> List[Dict]:
        return self.get("sources", [])

    # ── Counters ──────────────────────────────────────────────

    def increment(self, counter: str, by: int = 1) -> int:
        """Increment a counter and return new value."""
        current = self.get(counter, 0)
        new_value = current + by
        self.set(counter, new_value)
        return new_value

    def get_sources_count(self) -> int:
        return self.get("sources_count", 0)

    def get_steps_count(self) -> int:
        return self.get("steps_count", 0)

    def increment_sources(self, by: int = 1) -> int:
        return self.increment("sources_count", by)

    def increment_steps(self, by: int = 1) -> int:
        return self.increment("steps_count", by)

    # ── Summary ───────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a summary of current memory state."""
        return {
            "run_id": self.run_id,
            "keys_stored": list(self._store.keys()),
            "sources_count": self.get_sources_count(),
            "steps_count": self.get_steps_count(),
            "has_research": self.get_research_output() is not None,
            "has_analysis": self.get_analysis_output() is not None,
            "has_draft": self.get_draft_briefing() is not None,
            "has_final": self.get_final_briefing() is not None,
        }

    def clear(self) -> None:
        """Clear all run memory."""
        self._store.clear()
        log.info(f"[Memory:{self.run_id}] Cleared")


# ── Registry of active run memories ──────────────────────────────────────────

_memory_registry: Dict[str, CrewMemory] = {}


def get_run_memory(run_id: str) -> CrewMemory:
    """Get or create memory for a run."""
    if run_id not in _memory_registry:
        _memory_registry[run_id] = CrewMemory(run_id)
    return _memory_registry[run_id]


def clear_run_memory(run_id: str) -> None:
    """Clear and remove memory for a run."""
    if run_id in _memory_registry:
        _memory_registry[run_id].clear()
        del _memory_registry[run_id]


__all__ = ["CrewMemory", "get_run_memory", "clear_run_memory"]
