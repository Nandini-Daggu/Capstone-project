"""
src/tools/cache_tool.py
========================
Cache management tool for agents.
Allows agents to check/store intermediate results to avoid redundant LLM calls.
"""

from __future__ import annotations

from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.cache import cache_manager
from src.utils.logger import get_logger

log = get_logger(__name__)


class CacheInput(BaseModel):
    action: str = Field(
        ...,
        description="Action: 'get', 'set', 'stats', 'clear_namespace'",
    )
    namespace: str = Field(default="agent", description="Cache namespace")
    key: str = Field(default="", description="Cache key")
    value: Optional[str] = Field(None, description="Value to cache (for 'set')")
    ttl: Optional[int] = Field(None, description="TTL in seconds")


class CacheTool(BaseTool):
    """
    Cache management tool for agent use.
    Enables agents to persist intermediate results and avoid
    costly redundant LLM calls or search queries.
    """

    name: str = "cache_manager"
    description: str = (
        "Manage the agent cache. Use 'get' to retrieve cached results, "
        "'set' to store results, 'stats' to check hit rates."
    )
    args_schema: Type[BaseModel] = CacheInput

    def _run(
        self,
        action: str,
        namespace: str = "agent",
        key: str = "",
        value: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> str:
        if action == "get":
            result = cache_manager.get(namespace, key)
            if result is not None:
                return f"Cache HIT: {str(result)[:500]}"
            return "Cache MISS"
        elif action == "set":
            if not value:
                return "Error: value required for set"
            cache_manager.set(namespace, key, value, ttl)
            return f"Cached '{key}' in namespace '{namespace}'"
        elif action == "stats":
            stats = cache_manager.get_stats()
            return (
                f"Cache stats: hit_rate={stats['hit_rate']:.1%} | "
                f"llm_hits={stats['llm_hits']} | search_hits={stats['search_hits']} | "
                f"hot_tier_size={stats['hot_tier_size']}"
            )
        elif action == "clear_namespace":
            return f"Namespace '{namespace}' clear requested (use cache_manager.clear_all() for full clear)"
        else:
            return f"Unknown action: {action}"


# Singleton
cache_tool = CacheTool()

__all__ = ["CacheTool", "cache_tool"]
