"""
src/utils/logger.py
====================
Structured logging with Loguru + Rich.
Provides JSON-structured logs for JSONL audit trails and
human-readable console output with colour coding.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.logging import RichHandler

from config.settings import settings

# ── Console ───────────────────────────────────────────────────
console = Console(stderr=True)


def _configure_logger() -> None:
    """Configure Loguru with console + file sinks."""
    logger.remove()  # Remove default sink

    # Console sink (pretty, coloured)
    logger.add(
        RichHandler(console=console, rich_tracebacks=True, markup=True),
        format="{message}",
        level=settings.log_level,
        colorize=True,
    )

    # File sink — rotating plain-text
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(settings.log_dir / "app.log"),
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
        serialize=False,
    )

    # JSONL structured sink for machine parsing
    logger.add(
        str(settings.log_dir / "app.jsonl"),
        rotation="50 MB",
        retention="30 days",
        level=settings.log_level,
        serialize=True,          # Write as JSON records
    )


_configure_logger()


def get_logger(name: str):  # noqa: ANN001
    """Return a contextual logger bound with module name."""
    return logger.bind(module=name)


# Re-export for convenience
__all__ = ["logger", "get_logger", "console"]
