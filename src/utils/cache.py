"""
src/utils/cache.py
===================
Multi-tier cache manager for LLM responses, search results, and embeddings.
Uses diskcache for persistence across restarts + in-memory LRU for hot paths.
Drastically reduces OpenRouter API costs.
"""

from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import diskcache

from config.settings import settings
from .logger import get_logger

log = get_logger(__name__)


def _make_key(*args: Any, **kwargs: Any) -> str:
    """Create a deterministic cache key from arbitrary arguments."""
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class CacheManager:
    """
    Layered cache manager.

    Tiers:
        1. In-memory dict (fastest, lost on restart)
        2. DiskCache (persistent, survives restarts)
    """

    def __init__(self) -> None:
        settings.cache_dir.mkdir(parents=True, exist_ok=True)

        self._llm_cache: Optional[diskcache.Cache] = None
        self._search_cache: Optional[diskcache.Cache] = None
        self._embedding_cache: Optional[diskcache.Cache] = None

        self._hot: Dict[str, Any] = {}       # In-memory hot tier
        self._hot_ttl: Dict[str, float] = {} # Expiry timestamps

        self._stats = {
            "llm_hits": 0,
            "llm_misses": 0,
            "search_hits": 0,
            "search_misses": 0,
            "embedding_hits": 0,
            "embedding_misses": 0,
        }

    # ── Lazy initialisation ──────────────────────────────────

    @property
    def llm(self) -> diskcache.Cache:
        if self._llm_cache is None and settings.llm_cache_enabled:
            self._llm_cache = diskcache.Cache(
                str(settings.cache_dir / "llm"),
                timeout=settings.cache_ttl_seconds,
            )
        return self._llm_cache  # type: ignore[return-value]

    @property
    def search(self) -> diskcache.Cache:
        if self._search_cache is None and settings.search_cache_enabled:
            self._search_cache = diskcache.Cache(
                str(settings.cache_dir / "search"),
                timeout=settings.cache_ttl_seconds,
            )
        return self._search_cache  # type: ignore[return-value]

    @property
    def embedding(self) -> diskcache.Cache:
        if self._embedding_cache is None and settings.embedding_cache_enabled:
            self._embedding_cache = diskcache.Cache(
                str(settings.cache_dir / "embedding"),
                timeout=86400 * 7,   # Embeddings expire after 7 days
            )
        return self._embedding_cache  # type: ignore[return-value]

    # ── LLM Cache ────────────────────────────────────────────

    def get_llm(self, prompt: str, model: str) -> Optional[str]:
        """Return cached LLM response or None."""
        if not settings.llm_cache_enabled:
            return None
        key = _make_key(prompt, model)
        result = self._hot_get(key)
        if result is not None:
            self._stats["llm_hits"] += 1
            return result
        if self.llm and key in self.llm:
            self._stats["llm_hits"] += 1
            val = self.llm[key]
            self._hot_set(key, val)
            return val
        self._stats["llm_misses"] += 1
        return None

    def set_llm(self, prompt: str, model: str, response: str) -> None:
        """Cache an LLM response."""
        if not settings.llm_cache_enabled:
            return
        key = _make_key(prompt, model)
        self._hot_set(key, response)
        if self.llm:
            self.llm.set(key, response, expire=settings.cache_ttl_seconds)

    # ── Search Cache ─────────────────────────────────────────

    def get_search(self, query: str, source: str = "duckduckgo") -> Optional[List[Dict]]:
        """Return cached search results or None."""
        if not settings.search_cache_enabled:
            return None
        key = _make_key(query, source)
        if self.search and key in self.search:
            self._stats["search_hits"] += 1
            return self.search[key]
        self._stats["search_misses"] += 1
        return None

    def set_search(self, query: str, results: List[Dict], source: str = "duckduckgo") -> None:
        """Cache search results."""
        if not settings.search_cache_enabled:
            return
        key = _make_key(query, source)
        if self.search:
            self.search.set(key, results, expire=settings.cache_ttl_seconds)

    # ── Embedding Cache ───────────────────────────────────────

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Return cached embedding vector or None."""
        if not settings.embedding_cache_enabled:
            return None
        key = _make_key(text)
        if self.embedding and key in self.embedding:
            self._stats["embedding_hits"] += 1
            return self.embedding[key]
        self._stats["embedding_misses"] += 1
        return None

    def set_embedding(self, text: str, vector: List[float]) -> None:
        """Cache an embedding vector."""
        if not settings.embedding_cache_enabled:
            return
        key = _make_key(text)
        if self.embedding:
            self.embedding.set(key, vector, expire=86400 * 7)

    # ── Generic Cache ─────────────────────────────────────────

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Generic get from a named cache namespace."""
        hot_key = f"{namespace}:{key}"
        val = self._hot_get(hot_key)
        if val is not None:
            return val
        # Use search cache as generic backing store
        if self.search and hot_key in self.search:
            return self.search[hot_key]
        return None

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Generic set in a named namespace."""
        hot_key = f"{namespace}:{key}"
        self._hot_set(hot_key, value, ttl=ttl)
        if self.search:
            self.search.set(hot_key, value, expire=ttl or settings.cache_ttl_seconds)

    # ── Stats ─────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return cache hit/miss statistics."""
        total = sum(self._stats.values())
        hits = self._stats["llm_hits"] + self._stats["search_hits"] + self._stats["embedding_hits"]
        return {
            **self._stats,
            "hit_rate": hits / total if total > 0 else 0.0,
            "hot_tier_size": len(self._hot),
        }

    def clear_all(self) -> None:
        """Clear all caches (useful for testing)."""
        self._hot.clear()
        self._hot_ttl.clear()
        for c in [self._llm_cache, self._search_cache, self._embedding_cache]:
            if c:
                c.clear()
        log.info("All caches cleared")

    # ── Hot tier helpers ──────────────────────────────────────

    def _hot_get(self, key: str) -> Optional[Any]:
        if key in self._hot:
            if time.monotonic() < self._hot_ttl.get(key, float("inf")):
                return self._hot[key]
            del self._hot[key]
            self._hot_ttl.pop(key, None)
        return None

    def _hot_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if len(self._hot) > 1000:
            # Evict oldest 200 entries
            sorted_keys = sorted(self._hot_ttl, key=lambda k: self._hot_ttl[k])
            for k in sorted_keys[:200]:
                del self._hot[k]
                del self._hot_ttl[k]
        self._hot[key] = value
        self._hot_ttl[key] = time.monotonic() + (ttl or settings.cache_ttl_seconds)


# Singleton
cache_manager = CacheManager()

__all__ = ["CacheManager", "cache_manager", "_make_key"]
