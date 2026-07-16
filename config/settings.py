"""
config/settings.py
==================
Central application settings using Pydantic BaseSettings.
All values are read from environment variables / .env file.

Model configuration
-------------------
The single source of truth for the LLM model is:

    MODEL_NAME=openrouter/google/gemma-4-31b-it:free   # in .env

MODEL_PRIMARY / MODEL_FALLBACK / MODEL_LAST_RESORT define the cascade that
make_cascade_llm() uses when a model returns a 429 rate-limit error.

Valid free model IDs (confirmed against OpenRouter /models API, July 2026)
--------------------------------------------------------------------------
  openrouter/google/gemma-4-31b-it:free           ctx=262k  Google AI Studio
  openrouter/meta-llama/llama-3.3-70b-instruct:free ctx=131k Venice/Meta
  openrouter/qwen/qwen3-coder:free                ctx=1M    Qwen/Venice
  openrouter/nvidia/nemotron-3-ultra-550b-a55b:free ctx=1M  NVIDIA
  openrouter/google/gemma-4-26b-a4b-it:free       ctx=262k  Google AI Studio
  openrouter/meta-llama/llama-3.2-3b-instruct:free ctx=131k Meta

LiteLLM model-string convention
---------------------------------
  litellm format  : openrouter/<provider>/<slug>:<tier>
  OpenRouter slug : <provider>/<slug>:<tier>   (strip the leading "openrouter/")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_log = logging.getLogger(__name__)

# ── Verified valid free model IDs (confirmed July 2026) ──────────────────────
# These are the ONLY model IDs that should appear in this project.
# Format: openrouter/<provider>/<slug>:<tier>
#
# nvidia/nemotron-3-ultra-550b-a55b confirmed working (from run logs Jul 2026).
# Put nvidia FIRST as primary — it consistently succeeded where google/llama failed.
VALID_FREE_MODELS: List[str] = [
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",   # CONFIRMED WORKING
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "openrouter/google/gemma-4-31b-it:free",
    "openrouter/meta-llama/llama-3.2-3b-instruct:free",
    "openrouter/qwen/qwen3-coder:free",
    "openrouter/google/gemma-4-26b-a4b-it:free",
]

# Default fallback used when .env is missing or model is invalid
_DEFAULT_PRIMARY      = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
_DEFAULT_FALLBACK     = "openrouter/meta-llama/llama-3.3-70b-instruct:free"
_DEFAULT_LAST_RESORT  = "openrouter/meta-llama/llama-3.2-3b-instruct:free"

# ── OpenRouter base URL ───────────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _normalize_model_id(model: str) -> str:
    """
    Normalise a model string to the LiteLLM openrouter/ convention.

    Handles:
      google/gemma-4-31b-it:free        → openrouter/google/gemma-4-31b-it:free
      openrouter/google/gemma-4-31b-it:free → unchanged
      gemma-4-31b-it:free (bad slug)    → raises ValueError
    """
    model = model.strip()
    if not model:
        raise ValueError("Model ID must not be empty")
    if model.startswith("openrouter/"):
        return model
    # If it contains a slash it's likely a valid provider/slug pair
    if "/" in model:
        return f"openrouter/{model}"
    raise ValueError(
        f"Invalid model ID '{model}'. "
        "Use format: openrouter/<provider>/<slug>:<tier>  "
        f"Valid examples: {VALID_FREE_MODELS[:2]}"
    )


def _validate_model(model: str, context: str = "model") -> str:
    """
    Validate a model string and log a warning if it is not in the known-valid list.
    Does NOT raise — unknown models may still work (OpenRouter adds new ones regularly).
    """
    try:
        normalized = _normalize_model_id(model)
    except ValueError as exc:
        _log.error(f"[Settings] Invalid {context}: {exc}")
        _log.error(f"[Settings] Falling back to default: {_DEFAULT_PRIMARY}")
        return _DEFAULT_PRIMARY

    if normalized not in VALID_FREE_MODELS:
        _log.warning(
            f"[Settings] {context}='{normalized}' is not in the known-valid list. "
            "It may still work if OpenRouter has added it recently."
        )
    return normalized


# ── Settings class ────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    """Application-wide configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── LLM ─────────────────────────────────────────────────────────────────
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openai_api_base: str = Field(
        default=OPENROUTER_BASE_URL,
        alias="OPENAI_API_BASE",
    )

    # Single model config variable — the primary/default model
    # Loaded from MODEL_NAME in .env (falls back to MODEL_PRIMARY for compat)
    model_name: str = Field(
        default=_DEFAULT_PRIMARY,
        alias="MODEL_NAME",
    )

    # Cascade models
    model_primary: str = Field(
        default=_DEFAULT_PRIMARY,
        alias="MODEL_PRIMARY",
    )
    model_fallback: str = Field(
        default=_DEFAULT_FALLBACK,
        alias="MODEL_FALLBACK",
    )
    model_last_resort: str = Field(
        default=_DEFAULT_LAST_RESORT,
        alias="MODEL_LAST_RESORT",
    )

    # ── Search ───────────────────────────────────────────────────────────────
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")

    # ── Embeddings ───────────────────────────────────────────────────────────
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./database/intelligence.db",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # ── Cache ────────────────────────────────────────────────────────────────
    cache_dir: Path = Field(default=Path("./cache"), alias="CACHE_DIR")
    cache_ttl_seconds: int = Field(default=3600, alias="CACHE_TTL_SECONDS")
    llm_cache_enabled: bool = Field(default=True, alias="LLM_CACHE_ENABLED")
    search_cache_enabled: bool = Field(default=True, alias="SEARCH_CACHE_ENABLED")
    embedding_cache_enabled: bool = Field(default=True, alias="EMBEDDING_CACHE_ENABLED")

    # ── Vector Store ─────────────────────────────────────────────────────────
    vectorstore_dir: Path = Field(
        default=Path("./knowledge_base/vectorstore"),
        alias="VECTORSTORE_DIR",
    )
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP")
    top_k_results: int = Field(default=5, alias="TOP_K_RESULTS")

    # ── Run Limits ───────────────────────────────────────────────────────────
    # Reduced defaults for faster output (overridable via .env)
    max_sources: int = Field(default=5, alias="MAX_SOURCES")
    max_steps: int = Field(default=10, alias="MAX_STEPS")
    max_runtime_seconds: int = Field(default=300, alias="MAX_RUNTIME_SECONDS")
    max_cost_usd: float = Field(default=0.02, alias="MAX_COST_USD")

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: Path = Field(default=Path("./logs"), alias="LOG_DIR")
    audit_log_file: Path = Field(
        default=Path("./logs/audit.jsonl"),
        alias="AUDIT_LOG_FILE",
    )
    trace_log_file: Path = Field(
        default=Path("./logs/trace.jsonl"),
        alias="TRACE_LOG_FILE",
    )

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_reload: bool = Field(default=True, alias="API_RELOAD")
    api_secret_key: str = Field(
        default="change-me-in-production",
        alias="API_SECRET_KEY",
    )

    # ── Export ───────────────────────────────────────────────────────────────
    output_dir: Path = Field(default=Path("./outputs"), alias="OUTPUT_DIR")
    report_template: str = Field(default="mckinsey", alias="REPORT_TEMPLATE")

    # ── Evaluation ───────────────────────────────────────────────────────────
    evaluation_enabled: bool = Field(default=True, alias="EVALUATION_ENABLED")
    ragas_enabled: bool = Field(default=True, alias="RAGAS_ENABLED")
    deepeval_enabled: bool = Field(default=True, alias="DEEPEVAL_ENABLED")

    # ── Human Review ─────────────────────────────────────────────────────────
    human_review_enabled: bool = Field(default=True, alias="HUMAN_REVIEW_ENABLED")
    auto_approve_threshold: float = Field(
        default=0.85,
        alias="AUTO_APPROVE_THRESHOLD",
    )

    # ── Observability ────────────────────────────────────────────────────────
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_endpoint: str = Field(
        default="http://localhost:4317",
        alias="OTEL_ENDPOINT",
    )

    # ── Security / Governance ────────────────────────────────────────────────
    prompt_injection_guard: bool = Field(
        default=True,
        alias="PROMPT_INJECTION_GUARD",
    )
    misinformation_guard: bool = Field(default=True, alias="MISINFORMATION_GUARD")
    uncited_claim_guard: bool = Field(default=True, alias="UNCITED_CLAIM_GUARD")

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("cache_dir", "vectorstore_dir", "log_dir", "output_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        return Path(v)

    # ── Directory creation ────────────────────────────────────────────────────

    def ensure_directories(self) -> None:
        """Create all required runtime directories."""
        for d in [
            self.cache_dir,
            self.vectorstore_dir,
            self.log_dir,
            self.output_dir,
            Path("./database"),
            Path("./knowledge_base/reports"),
            Path("./knowledge_base/news"),
            Path("./knowledge_base/pricing"),
            Path("./knowledge_base/competitors"),
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # ── Model helpers ─────────────────────────────────────────────────────────

    @property
    def active_model(self) -> str:
        """
        The single active model — loaded from MODEL_NAME env var.
        Falls back to model_primary for backwards compatibility.
        """
        # MODEL_NAME takes precedence; fall back to MODEL_PRIMARY
        m = self.model_name if self.model_name else self.model_primary
        return _validate_model(m, "MODEL_NAME")

    @property
    def model_cascade(self) -> List[str]:
        """
        Ordered list of valid models for cascade fallback routing.

        nvidia/nemotron is first — confirmed working in prod logs (Jul 2026)
        while Google and Meta models were frequently rate-limited.

        Models spread across DIFFERENT upstream providers so one provider
        rate-limiting doesn't kill the entire cascade:
          nemotron-550b       → NVIDIA           (primary — most reliable)
          llama-3.3-70b       → Venice / Meta
          gemma-4-31b-it      → Google AI Studio
          llama-3.2-3b        → Meta             (small/fast)
          qwen3-coder         → Venice / Qwen
          gemma-4-26b         → Google AI Studio (separate quota)
        """
        # Full ordered cascade — all 6 diverse models
        ordered = [
            "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/google/gemma-4-31b-it:free",
            "openrouter/meta-llama/llama-3.2-3b-instruct:free",
            "openrouter/qwen/qwen3-coder:free",
            "openrouter/google/gemma-4-26b-a4b-it:free",
        ]

        # Honour .env overrides: if MODEL_PRIMARY differs, put it first
        primary = _validate_model(self.model_primary, "MODEL_PRIMARY")
        if primary not in ordered:
            ordered.insert(0, primary)
        elif ordered[0] != primary:
            ordered.remove(primary)
            ordered.insert(0, primary)

        return ordered

    # ── Startup log ───────────────────────────────────────────────────────────

    def log_config(self) -> None:
        """
        Print a startup summary of the LLM configuration to the logger.
        Requirements: log selected model, base URL, API key presence.
        """
        api_key_status = (
            f"found ({self.openrouter_api_key[:8]}...)"
            if len(self.openrouter_api_key) > 10
            else "MISSING — set OPENROUTER_API_KEY in .env"
        )
        _log.info("=" * 60)
        _log.info("[Config] LLM Configuration")
        _log.info(f"[Config]   Selected model : {self.active_model}")
        _log.info(f"[Config]   Base URL       : {OPENROUTER_BASE_URL}")
        _log.info(f"[Config]   API key        : {api_key_status}")
        _log.info(f"[Config]   Model cascade  : {self.model_cascade}")
        _log.info(f"[Config]   Max runtime    : {self.max_runtime_seconds}s")
        _log.info(f"[Config]   Max cost       : ${self.max_cost_usd}")
        _log.info("=" * 60)

        if not self.openrouter_api_key:
            _log.error(
                "[Config] OPENROUTER_API_KEY is not set. "
                "Add it to your .env file and restart."
            )


# ── Singleton ────────────────────────────────────────────────────────────────

settings = Settings()
settings.ensure_directories()
settings.log_config()
