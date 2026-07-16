"""
src/utils/llm_router.py
========================
make_cascade_llm() returns a genuine crewai.llm.LLM instance whose call()
method is patched to automatically cascade through a list of models on:
  - 429 rate-limit errors
  - 400 invalid-model errors (model may have been deprecated)

How the cascade works
---------------------
CrewAI stores the model in llm.model WITHOUT the "openrouter/" prefix.
e.g.  LLM(model="openrouter/google/gemma-4-31b-it:free") → llm.model == "google/gemma-4-31b-it:free"
The base_url routes the call to OpenRouter regardless of what llm.model says.

So when we switch models we MUST set llm.model to the STRIPPED name, then also
update the internal client so the HTTP request uses the right model slug.

Cascade logic
--------------
Per-call iteration:
1. Walk the ordered cascade list from the start.
2. Skip any model whose cooldown hasn't expired yet.
3. Try the first non-cooling model.
4. On 429/400 → mark unavailable → restart loop (so we skip it next iteration).
5. If ALL models are cooling → wait for the soonest cooldown to expire, then retry.
6. A model is only considered "exhausted for this call" after it gets a permanent
   error (e.g. 404 model-not-found). 429 errors are cooldown-based and retriable.
"""

from __future__ import annotations

import os
import re
import threading
import time
import types
from typing import Any, Dict, List, Optional, Set

from crewai.llm import LLM

from src.utils.logger import get_logger

log = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── Error classification ──────────────────────────────────────────────────────

_RATE_LIMIT_SIGNALS = (
    "429",
    "rate limit",
    "rate_limit",
    "ratelimit",
    "too many requests",
    "temporarily rate-limited",
    "quota exceeded",
    "resource_exhausted",
    "provider returned error",
    "retry_after",
)

_PERMANENT_FAILURE_SIGNALS = (
    "not a valid model id",
    "model not found",
    "no endpoints found",
    "unavailable for free",
    "invalid model",
    "404",
)


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _RATE_LIMIT_SIGNALS)


def _is_permanent_failure(exc: Exception) -> bool:
    """Return True if the model is permanently invalid (should not retry at all)."""
    msg = str(exc).lower()
    return any(s in msg for s in _PERMANENT_FAILURE_SIGNALS)


def _should_cascade(exc: Exception) -> bool:
    return _is_rate_limit(exc) or _is_permanent_failure(exc)


def _parse_retry_after(exc: Exception) -> float:
    """Parse Retry-After seconds from error message. Default: 35s."""
    text = str(exc)
    # Try exact retry_after_seconds field first
    m = re.search(r"retry_after_seconds['\"]?\s*[:\s]+([0-9.]+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 3.0
    # Try Retry-After header value
    m = re.search(r"Retry-After['\"]?\s*[:\s]+([0-9]+)", text)
    if m:
        return float(m.group(1)) + 3.0
    return 35.0


def _strip_prefix(model: str) -> str:
    """
    Strip 'openrouter/' prefix if present.
    'openrouter/google/gemma-4-31b-it:free' -> 'google/gemma-4-31b-it:free'
    'google/gemma-4-31b-it:free'             -> 'google/gemma-4-31b-it:free'
    """
    if model.startswith("openrouter/"):
        return model[len("openrouter/") :]
    return model


def _ensure_prefix(model: str) -> str:
    """
    Ensure the model has the 'openrouter/' prefix.
    'google/gemma-4-31b-it:free'             -> 'openrouter/google/gemma-4-31b-it:free'
    'openrouter/google/gemma-4-31b-it:free'  -> unchanged
    """
    if not model.startswith("openrouter/"):
        return f"openrouter/{model}"
    return model


# ── Cascade state ─────────────────────────────────────────────────────────────


class _CascadeState:
    """
    Thread-safe cooldown tracker for the model cascade.

    Stores FULL model names (with 'openrouter/' prefix) as keys for clarity.
    The cascade list is the authoritative order.
    """

    def __init__(self, full_cascade: List[str]) -> None:
        # Deduplicate while preserving order
        seen: Set[str] = set()
        deduped = []
        for m in full_cascade:
            normalized = _ensure_prefix(m)
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        self.cascade: List[str] = deduped  # full names e.g. "openrouter/google/..."
        self.cooldowns: Dict[str, float] = {}
        self._permanent_failures: Set[str] = set()
        self.lock = threading.Lock()

    def mark_rate_limited(self, full_model: str, wait: float) -> None:
        with self.lock:
            self.cooldowns[full_model] = time.monotonic() + wait
        log.warning(
            f"[Cascade] '{full_model}' rate-limited for {wait:.0f}s. " "Will try next model."
        )

    def mark_permanent_failure(self, full_model: str) -> None:
        with self.lock:
            self._permanent_failures.add(full_model)
            # Also set a very long cooldown so next_available skips it
            self.cooldowns[full_model] = time.monotonic() + 86400.0  # 24h
        log.error(f"[Cascade] '{full_model}' permanently invalid — removed from cascade.")

    def is_available(self, full_model: str) -> bool:
        """True if the model is not in cooldown and not permanently failed."""
        with self.lock:
            if full_model in self._permanent_failures:
                return False
            return self.cooldowns.get(full_model, 0.0) <= time.monotonic()

    def next_available(self) -> Optional[str]:
        """
        Return the FIRST available model in cascade order, or None if all are cooling.
        Uses the ordered cascade list — always walks from the beginning so the
        highest-priority non-cooling model is returned.
        """
        now = time.monotonic()
        with self.lock:
            for m in self.cascade:
                if m in self._permanent_failures:
                    continue
                if self.cooldowns.get(m, 0.0) <= now:
                    return m
        return None

    def soonest_available_wait(self) -> float:
        """Return seconds until the next model exits cooldown."""
        now = time.monotonic()
        with self.lock:
            # Only consider non-permanently-failed models
            candidates = [
                self.cooldowns.get(m, 0.0)
                for m in self.cascade
                if m not in self._permanent_failures
            ]
        if not candidates:
            return 0.0
        earliest = min(candidates)
        return max(0.0, earliest - now)

    def all_permanently_failed(self) -> bool:
        with self.lock:
            return all(m in self._permanent_failures for m in self.cascade)

    @property
    def available_count(self) -> int:
        with self.lock:
            return sum(1 for m in self.cascade if m not in self._permanent_failures)


# ── Factory ───────────────────────────────────────────────────────────────────


def make_cascade_llm(cascade: Optional[List[str]] = None) -> LLM:
    """
    Return a crewai.llm.LLM instance that auto-cascades on 429 / 400 errors.

    The LLM is initialised with the primary (first) model.
    On every call() invocation the wrapper:
      1. Finds the highest-priority non-cooling model.
      2. Patches llm.model (stripped) and the underlying client model field.
      3. Calls the original LLM.call().
      4. On 429  → marks the model rate-limited and retries immediately with next.
      5. On 400  → marks the model as permanently failed and retries with next.
      6. On any other error → propagates unchanged.
      7. If all models cooling → waits for the soonest to become available.

    Args:
        cascade: Ordered list of model IDs (with or without "openrouter/" prefix).
                 Defaults to settings.model_cascade.

    Returns:
        A genuine crewai.llm.LLM instance.

    Raises:
        EnvironmentError: OPENROUTER_API_KEY is missing.
        ValueError: No models in cascade.
    """
    from config.settings import settings

    # ── Validate API key ─────────────────────────────────────
    api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set.\n"
            "Add it to your .env file:  OPENROUTER_API_KEY=sk-or-v1-..."
        )

    # ── Build cascade ─────────────────────────────────────────
    raw_cascade = list(cascade or settings.model_cascade)
    if not raw_cascade:
        raise ValueError("Cascade is empty. Check MODEL_PRIMARY in .env.")

    # Normalise all names to have the openrouter/ prefix
    full_cascade = [_ensure_prefix(m) for m in raw_cascade]
    primary_full = full_cascade[0]  # e.g. "openrouter/google/gemma-4-31b-it:free"

    # ── Startup log ───────────────────────────────────────────
    log.info("[LLM] ===== LLM Initialisation =====")
    log.info(f"[LLM]   Primary model  : {primary_full}")
    log.info(f"[LLM]   Base URL       : {OPENROUTER_BASE_URL}")
    log.info(f"[LLM]   API key        : found ({api_key[:8]}...)")
    log.info(f"[LLM]   Cascade ({len(full_cascade)} models):")
    for i, m in enumerate(full_cascade, 1):
        log.info(f"[LLM]     {i}. {m}")
    log.info("[LLM] ==================================")

    # ── Create the primary LLM instance ──────────────────────
    # CrewAI's LLM.__init__ strips the "openrouter/" prefix and stores the
    # remainder in llm.model. The base_url routes HTTP to OpenRouter.
    llm = LLM(
        model=primary_full,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )
    log.info(f"[LLM]   llm.model stored as: {llm.model!r}")

    # ── Cascade state ─────────────────────────────────────────
    state = _CascadeState(full_cascade)
    llm._cascade_state = state

    # ── Patch .call() ─────────────────────────────────────────
    original_call = llm.call

    def _switch_model(target_stripped: str) -> None:
        """
        Switch the LLM instance to a different model.
        target_stripped: model name WITHOUT 'openrouter/' prefix.
        """
        if llm.model == target_stripped:
            return

        log.info(f"[LLM] Cascade switch: '{llm.model}' → '{target_stripped}'")
        llm.model = target_stripped

        # Also patch the underlying client's model field so the HTTP request
        # uses the correct slug. CrewAI/LiteLLM may cache this in various places.
        for attr in ("client", "_client", "completion_kwargs"):
            obj = getattr(llm, attr, None)
            if obj is not None and hasattr(obj, "model"):
                try:
                    obj.model = target_stripped
                except Exception:
                    pass

    def _cascade_call(messages: Any, **kwargs: Any) -> Any:
        """
        Wraps LLM.call() to cascade to the next model on 429/400 errors.

        Algorithm:
        - Loop indefinitely (broken by success or exhaustion).
        - On each iteration, find the best available model via state.next_available().
        - If nothing available yet, wait for the soonest cooldown.
        - Try the call. On failure mark and continue.
        - Track permanently-failed models separately; when ALL are permanently
          failed, raise RuntimeError.
        """
        MAX_WAIT_TOTAL = 300  # 5 minutes max total wait before giving up
        total_waited = 0.0

        while True:
            # Check if all models have permanently failed (no hope)
            if state.all_permanently_failed():
                raise RuntimeError(
                    "[LLM] All models in cascade permanently unavailable.\n"
                    "Check your OpenRouter account or model IDs in .env."
                )

            # Find the next available model
            full_model = state.next_available()

            if full_model is None:
                # All non-permanently-failed models are in cooldown — wait
                wait_sec = state.soonest_available_wait()
                if total_waited + wait_sec > MAX_WAIT_TOTAL:
                    raise RuntimeError(
                        f"[LLM] All {state.available_count} cascade models rate-limited. "
                        f"Waited {total_waited:.0f}s total. Giving up.\n"
                        "Try again in a few minutes."
                    )
                log.warning(
                    f"[LLM] All models cooling. Waiting {wait_sec:.1f}s "
                    f"(total waited: {total_waited:.0f}s)…"
                )
                time.sleep(wait_sec + 0.5)
                total_waited += wait_sec + 0.5
                continue

            # Switch to the selected model (stripped name for crewai internals)
            stripped = _strip_prefix(full_model)
            _switch_model(stripped)

            log.info(f"[LLM] Calling model: '{full_model}'")
            try:
                result = original_call(messages, **kwargs)
                if llm.model != (
                    full_cascade[0]
                    if not full_cascade[0].startswith("openrouter/")
                    else _strip_prefix(full_cascade[0])
                ):
                    log.info(f"[LLM] ✓ Succeeded with fallback model: '{full_model}'")
                return result

            except Exception as exc:
                if _is_rate_limit(exc):
                    wait = _parse_retry_after(exc)
                    state.mark_rate_limited(full_model, wait)
                    log.warning(
                        f"[LLM] '{full_model}' rate-limited ({wait:.0f}s) — trying next model"
                    )
                    # Don't count this as waited time toward MAX_WAIT_TOTAL yet;
                    # we'll try other models first and only wait if all are cooling.
                    continue

                elif _is_permanent_failure(exc):
                    state.mark_permanent_failure(full_model)
                    log.warning(f"[LLM] '{full_model}' permanently failed — trying next model")
                    continue

                # All other errors (network issues, auth, etc.) propagate
                raise

    # Bind the patched call at instance level
    llm.call = types.MethodType(
        lambda self, messages, **kw: _cascade_call(messages, **kw),
        llm,
    )

    return llm


__all__ = ["make_cascade_llm"]
