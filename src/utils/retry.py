"""
src/utils/retry.py
===================
Retry, timeout, and circuit-breaker utilities.
Built on Tenacity for battle-tested retry logic.
"""

from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple, Type

from tenacity import (
    RetryError,
    Retrying,
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
)

from .logger import get_logger

log = get_logger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class RetryConfig:
    """Retry/circuit-breaker configuration."""

    max_attempts: int = 3
    wait_min_seconds: float = 1.0
    wait_max_seconds: float = 30.0
    wait_multiplier: float = 2.0
    timeout_seconds: Optional[float] = 60.0
    retry_on: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )
    reraise: bool = True


# ── Sync retry decorator ──────────────────────────────────────────────────────

def with_retry(config: Optional[RetryConfig] = None) -> Callable:
    """
    Decorator factory for sync functions with retry + exponential back-off.

    Usage:
        @with_retry(RetryConfig(max_attempts=3))
        def fetch_data():
            ...
    """
    cfg = config or RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            attempt = 0
            last_exc: Optional[Exception] = None

            for attempt_state in Retrying(
                stop=stop_after_attempt(cfg.max_attempts),
                wait=wait_exponential(
                    multiplier=cfg.wait_multiplier,
                    min=cfg.wait_min_seconds,
                    max=cfg.wait_max_seconds,
                ),
                retry=retry_if_exception_type(cfg.retry_on),
                reraise=cfg.reraise,
            ):
                with attempt_state:
                    attempt += 1
                    elapsed = time.monotonic() - start
                    if cfg.timeout_seconds and elapsed > cfg.timeout_seconds:
                        raise TimeoutError(
                            f"{func.__name__} exceeded {cfg.timeout_seconds}s timeout"
                        )
                    try:
                        return func(*args, **kwargs)
                    except Exception as exc:
                        last_exc = exc
                        log.warning(
                            f"[Retry] {func.__name__} attempt {attempt}/{cfg.max_attempts} "
                            f"failed: {exc}"
                        )
                        raise

        return wrapper

    return decorator


# ── Async retry decorator ─────────────────────────────────────────────────────

def with_async_retry(config: Optional[RetryConfig] = None) -> Callable:
    """
    Decorator factory for async functions with retry + exponential back-off.
    """
    cfg = config or RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            attempt = 0

            async for attempt_state in AsyncRetrying(
                stop=stop_after_attempt(cfg.max_attempts),
                wait=wait_exponential(
                    multiplier=cfg.wait_multiplier,
                    min=cfg.wait_min_seconds,
                    max=cfg.wait_max_seconds,
                ),
                retry=retry_if_exception_type(cfg.retry_on),
                reraise=cfg.reraise,
            ):
                with attempt_state:
                    attempt += 1
                    elapsed = time.monotonic() - start
                    if cfg.timeout_seconds and elapsed > cfg.timeout_seconds:
                        raise TimeoutError(
                            f"{func.__name__} exceeded {cfg.timeout_seconds}s timeout"
                        )
                    try:
                        return await func(*args, **kwargs)
                    except Exception as exc:
                        log.warning(
                            f"[AsyncRetry] {func.__name__} attempt {attempt}/{cfg.max_attempts} "
                            f"failed: {exc}"
                        )
                        raise

        return wrapper

    return decorator


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Simple circuit breaker with three states: CLOSED, OPEN, HALF-OPEN.

    - CLOSED: normal operation
    - OPEN: failing fast after threshold exceeded
    - HALF-OPEN: testing recovery after cool-down
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
                log.info(f"[CircuitBreaker:{self.name}] OPEN → HALF_OPEN")
        return self._state

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""
        current_state = self.state

        if current_state == self.OPEN:
            raise RuntimeError(
                f"Circuit breaker '{self.name}' is OPEN — failing fast"
            )

        if current_state == self.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise RuntimeError(
                    f"Circuit breaker '{self.name}' is HALF_OPEN — max probe calls reached"
                )
            self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        if self._state == self.HALF_OPEN:
            log.info(f"[CircuitBreaker:{self.name}] HALF_OPEN → CLOSED (recovered)")
        self._state = self.CLOSED
        self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            log.warning(
                f"[CircuitBreaker:{self.name}] CLOSED → OPEN "
                f"(failures={self._failure_count})"
            )


# ── Global circuit breakers per external service ──────────────────────────────
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a named service."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name)
    return _circuit_breakers[name]


__all__ = [
    "RetryConfig",
    "with_retry",
    "with_async_retry",
    "CircuitBreaker",
    "get_circuit_breaker",
]
