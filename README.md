# Competitive Intelligence Briefing Crew

A production-ready multi-agent system that automates weekly competitive intelligence briefings. Built with CrewAI, LiteLLM, and Streamlit, it runs a three-agent pipeline (Research → Analysis → Writing) to produce board-ready strategic reports with full citations, governance controls, and export to PDF/PPTX/HTML/Markdown.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [API Reference](#api-reference)
- [Agent Pipeline](#agent-pipeline)
- [Features](#features)
- [Evaluation](#evaluation)
- [Export Formats](#export-formats)
- [Governance & Safety](#governance--safety)
- [Observability](#observability)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Competitive Intelligence Briefing Crew takes a company, a list of competitors, an industry, and a region as inputs and automatically produces a structured 12-section intelligence report including:

- Executive summary
- Competitor pricing analysis
- Product updates and roadmap signals
- Market signals and news
- Industry trends
- SWOT analysis
- Risk analysis
- Opportunities
- Strategic recommendations
- Full cited references

All claims in the report are backed by citations gathered from live web search and a local RAG knowledge base. Reports are scored by an automated evaluation suite (RAGAS / DeepEval) and can be gated through a human review step before being finalised.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit Dashboard                │
│               (frontend/dashboard.py)               │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              IntelligenceWorkflow                   │
│               (crew/workflow.py)                    │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │           IntelligenceCrew                   │   │
│  │            (crew/crew.py)                    │   │
│  │                                              │   │
│  │  ResearchAgent → AnalystAgent → WriterAgent  │   │
│  │         ↑ Shared CascadeLLM ↑               │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  Human Review Gate → Export Generation → DB Save    │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│           FastAPI Backend (backend/main.py)         │
│     REST API for external clients & monitoring      │
└─────────────────────────────────────────────────────┘
```

### LLM Cascade

All agents share a single `CascadeLLM` instance. When any call returns a 429 rate-limit error the LLM transparently switches to the next model in the cascade and retries — no manual intervention needed.

Default cascade order (most reliable first):

| Priority | Model | Provider | Context |
|---|---|---|---|
| 1 | `nvidia/nemotron-3-ultra-550b-a55b:free` | NVIDIA | 1M |
| 2 | `meta-llama/llama-3.3-70b-instruct:free` | Venice/Meta | 131k |
| 3 | `google/gemma-4-31b-it:free` | Google AI Studio | 262k |
| 4 | `meta-llama/llama-3.2-3b-instruct:free` | Meta | 131k |
| 5 | `qwen/qwen3-coder:free` | Venice/Qwen | 1M |
| 6 | `google/gemma-4-26b-a4b-it:free` | Google AI Studio | 262k |

All models are free-tier via [OpenRouter](https://openrouter.ai).

---

## Project Structure

```
competitive-intelligence-crew/
├── app.py                      # Streamlit entry point
├── requirements.txt
├── .env.example                # Copy to .env and fill in keys
│
├── config/
│   ├── settings.py             # Pydantic BaseSettings — all config
│   ├── agents.yaml             # Agent role/goal/backstory definitions
│   ├── tasks.yaml              # Task descriptions
│   └── crew.yaml               # Crew assembly config
│
├── crew/
│   ├── crew.py                 # IntelligenceCrew — assembles agents + tasks
│   ├── workflow.py             # IntelligenceWorkflow — full pipeline orchestration
│   └── memory.py               # Per-run in-memory state (sources, steps)
│
├── src/
│   ├── agents/
│   │   ├── research_agent.py   # Web search + RAG + news gathering
│   │   ├── analyst_agent.py    # Competitor matrix, SWOT, trend analysis
│   │   ├── writer_agent.py     # McKinsey-style report writing
│   │   └── supervisor.py       # Request validation + governance checks
│   ├── tools/
│   │   ├── web_search.py       # DuckDuckGo / Tavily search
│   │   ├── news_search.py      # RSS + news API search
│   │   ├── web_scraper.py      # BeautifulSoup page scraping
│   │   ├── market_tool.py      # Market data and pricing signals
│   │   ├── citation_tool.py    # Citation registry + reference management
│   │   ├── cache_tool.py       # Disk-based search result caching
│   │   ├── rag_tool.py         # FAISS vector store + semantic retrieval
│   │   ├── pdf_export.py       # WeasyPrint PDF generation
│   │   ├── ppt_export.py       # python-pptx PowerPoint generation
│   │   └── report_export.py    # Markdown / HTML / JSON export
│   └── utils/
│       ├── llm_router.py       # CascadeLLM with 429 fallback
│       ├── models.py           # Pydantic data models
│       ├── schemas.py          # FastAPI request/response schemas
│       ├── database.py         # SQLAlchemy DB manager
│       ├── cache.py            # CacheManager (diskcache)
│       ├── audit.py            # Append-only audit logger
│       ├── observability.py    # OpenTelemetry span tracking
│       ├── retry.py            # Tenacity retry utilities
│       └── logger.py           # Loguru structured logger
│
├── frontend/
│   ├── dashboard.py            # Main Streamlit dashboard page
│   ├── sidebar.py              # Sidebar controls + run configuration
│   ├── runner.py               # Async run execution + progress display
│   ├── styles.py               # CSS theme and styling
│   └── components/
│       ├── report_tabs.py      # Tabbed report section viewer
│       ├── human_review.py     # Human review gate UI
│       └── export_panel.py     # Export format selector + download
│
├── backend/
│   └── main.py                 # FastAPI REST API server
│
├── evaluation/
│   ├── test_suite.py           # EvaluationManager — orchestrates all evals
│   ├── ragas_eval.py           # RAGAS faithfulness / relevancy metrics
│   ├── deepeval_eval.py        # DeepEval hallucination detection
│   └── promptfoo_eval.py       # PromptFoo prompt regression testing
│
├── tests/
│   ├── conftest.py
│   ├── test_agents.py
│   ├── test_crew.py
│   ├── test_api.py
│   ├── test_tools.py
│   ├── test_models.py
│   ├── test_governance.py
│   └── test_evaluation.py
│
├── database/
│   └── intelligence.db         # SQLite database (auto-created)
├── cache/search/               # Disk cache for search results
├── logs/                       # app.log, audit.jsonl, trace.jsonl
├── outputs/                    # Generated PDF / PPTX / HTML / MD reports
└── knowledge_base/
    ├── vectorstore/            # FAISS index
    ├── competitors/            # Static competitor data
    ├── pricing/                # Historical pricing data
    ├── news/                   # Cached news articles
    └── reports/                # Archived past reports
```

---

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai/settings/keys) API key (free tier is sufficient)
- Optional: [Tavily](https://tavily.com) API key for higher-quality web search

---

## Installation

```bash
# Clone the repo
git clone <repo-url>
cd competitive-intelligence-crew

# Create and activate a virtual environment
python -m venv venv312
venv312\Scripts\activate        # Windows
# source venv312/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy the example environment file and fill in your keys:

```bash
cp .env.example .env
```

Minimum required settings:

```env
# Required — get a free key at https://openrouter.ai/settings/keys
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Primary model (default shown below — change to any valid free model)
MODEL_NAME=openrouter/google/gemma-4-31b-it:free

# Cascade fallback models (tried in order on 429 rate-limit errors)
MODEL_PRIMARY=openrouter/google/gemma-4-31b-it:free
MODEL_FALLBACK=openrouter/meta-llama/llama-3.3-70b-instruct:free
MODEL_LAST_RESORT=openrouter/qwen/qwen3-coder:free
```

Optional search enhancement:

```env
# Higher quality web search (recommended but not required)
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

All other settings have safe defaults. See `.env.example` for the full list.

### Valid Free Model IDs

Use the `openrouter/<provider>/<slug>:<tier>` format:

```
openrouter/nvidia/nemotron-3-ultra-550b-a55b:free
openrouter/google/gemma-4-31b-it:free
openrouter/google/gemma-4-26b-a4b-it:free
openrouter/meta-llama/llama-3.3-70b-instruct:free
openrouter/meta-llama/llama-3.2-3b-instruct:free
openrouter/qwen/qwen3-coder:free
```

---

## Running the App

### Streamlit Dashboard (recommended)

```bash
# From the project root, with the venv active
streamlit run app.py
```

Opens at **http://localhost:8501**

### FastAPI Backend (optional — for REST API access)

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs at **http://localhost:8000/docs**

### Run both together

```bash
# Terminal 1 — Streamlit UI
streamlit run app.py

# Terminal 2 — REST API
uvicorn backend.main:app --port 8000 --reload
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/generate` | Start a new intelligence briefing run |
| `GET` | `/status/{run_id}` | Poll run progress (0–100%) |
| `GET` | `/report/{run_id}` | Retrieve the completed report |
| `POST` | `/export` | Export report to PDF/PPTX/HTML/JSON/Markdown |
| `GET` | `/export/download/{run_id}/{format}` | Download export file directly |
| `GET` | `/history` | List recent runs |
| `GET` | `/logs/{run_id}` | Audit log for a specific run |
| `GET` | `/metrics` | Aggregate system metrics |
| `GET` | `/evaluate/{run_id}` | Run RAGAS/DeepEval scoring on a report |
| `POST` | `/review/{run_id}` | Submit human review decision |
| `GET` | `/traces/{run_id}` | Full execution trace with span timings |
| `GET` | `/health` | System health check |

### Example: generate a briefing

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Cloud Infrastructure",
    "competitors": ["AWS", "Azure", "Google Cloud"],
    "region": "Global",
    "time_period": "last 7 days",
    "max_sources": 15,
    "export_formats": ["markdown", "pdf"]
  }'
```

Response:
```json
{
  "run_id": "abc12345-...",
  "status": "started",
  "message": "Briefing run started. Monitor at /status/abc12345-..."
}
```

---

## Agent Pipeline

The crew runs three agents in sequence:

```
ResearchAgent
  ├── Web search (DuckDuckGo / Tavily)
  ├── News search (RSS feeds + news APIs)
  ├── Web scraping (competitor pages, press releases)
  ├── RAG retrieval (local knowledge base)
  └── Citation registration
        ↓
AnalystAgent
  ├── Competitor comparison matrix
  ├── SWOT analysis
  ├── Trend identification
  ├── Risk and opportunity mapping
  └── Citation verification
        ↓
WriterAgent
  ├── 12-section McKinsey/BCG-style report
  ├── Every claim linked to a [n] citation
  ├── Executive-ready language
  └── Full reference list
```

All three agents share a single `CascadeLLM` that handles 429 rate-limit errors automatically by switching to the next model in the configured cascade.

### Report Sections

1. Executive Summary
2. Competitor Pricing Analysis
3. Product Updates & Roadmap Signals
4. Market Signals
5. Industry Trends
6. SWOT Analysis
7. Risk Analysis
8. Opportunities
9. Strategic Recommendations
10. References (cited sources)
11. Run Metadata (model, tokens, cost, duration)
12. Evaluation Summary (RAGAS / DeepEval scores)

---

## Features

**Multi-model cascade** — Automatic failover across 6 free OpenRouter models. No paid API required.

**Full citation tracking** — Every claim carries a `[n]` reference. The citation registry tracks source URL, title, author, and date.

**RAG knowledge base** — FAISS vector store with `all-MiniLM-L6-v2` embeddings. Feed competitor data, past reports, and pricing sheets for richer context.

**Human review gate** — Reports can be paused for a human reviewer to approve, reject, or edit sections before finalisation.

**Disk cache** — Search results are cached (TTL configurable) to avoid redundant API calls on repeated runs.

**SQLite persistence** — All runs, reports, audit events, and evaluation scores are stored in `database/intelligence.db`.

**Structured audit log** — Append-only JSONL audit trail at `logs/audit.jsonl` capturing every agent action, tool call, token count, latency, and cost estimate.

---

## Evaluation

Each completed report is automatically scored by three frameworks:

| Framework | Metrics |
|---|---|
| **RAGAS** | Faithfulness, Answer Relevancy, Context Precision, Context Recall |
| **DeepEval** | Hallucination Score, Citation Coverage |
| **PromptFoo** | Prompt regression tests against expected output patterns |

Scores are stored in the database and surfaced in the Streamlit dashboard and via the `/evaluate/{run_id}` API endpoint.

Auto-approve threshold: reports with confidence ≥ `AUTO_APPROVE_THRESHOLD` (default `0.85`) are automatically approved without requiring human review.

---

## Export Formats

| Format | Tool | Output |
|---|---|---|
| Markdown | `report_export_tool` | `.md` file |
| HTML | `report_export_tool` | Styled `.html` file |
| JSON | `report_export_tool` | Structured `.json` |
| PDF | WeasyPrint | Formatted `.pdf` |
| PowerPoint | python-pptx | Slide deck `.pptx` |

Exports are saved to `./outputs/` and downloadable via the Streamlit export panel or the `/export/download/{run_id}/{format}` API endpoint.

---

## Governance & Safety

Three content guards run on every report before it is marked complete:

- **Prompt injection guard** — Detects and blocks prompt injection attempts in scraped web content
- **Misinformation guard** — Flags unsupported or contradicted claims
- **Uncited claim guard** — Rejects sections where claims lack a `[n]` citation

Guards are enabled by default. Disable individually in `.env`:

```env
PROMPT_INJECTION_GUARD=false
MISINFORMATION_GUARD=false
UNCITED_CLAIM_GUARD=false
```

Run limits (configurable):

| Setting | Default | Description |
|---|---|---|
| `MAX_SOURCES` | 15 | Maximum sources gathered per run |
| `MAX_STEPS` | 25 | Maximum agent steps per run |
| `MAX_RUNTIME_SECONDS` | 900 | Wall-clock timeout (15 min) |
| `MAX_COST_USD` | 0.02 | Estimated cost ceiling |

---

## Observability

**Structured logging** — Loguru writes JSON-structured logs to `logs/app.jsonl` and human-readable logs to `logs/app.log`.

**Audit trail** — Every agent action, tool call, token usage, latency, and cost estimate is appended to `logs/audit.jsonl`.

**Execution traces** — Each run produces a span tree (agent → tool → LLM call) queryable via `/traces/{run_id}`.

**OpenTelemetry** — Optional OTLP export to any compatible collector (Jaeger, Grafana Tempo, etc.):

```env
OTEL_ENABLED=true
OTEL_ENDPOINT=http://localhost:4317
```

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run a specific test module
pytest tests/test_agents.py -v
pytest tests/test_api.py -v
```

Test modules:

| File | Coverage |
|---|---|
| `test_agents.py` | Agent instantiation, task creation, tool access |
| `test_crew.py` | Crew assembly, run lifecycle, cascade fallback |
| `test_api.py` | All FastAPI endpoints (health, generate, status, export) |
| `test_tools.py` | Individual tool behaviour and caching |
| `test_models.py` | Pydantic model validation |
| `test_governance.py` | Guard triggering and blocking logic |
| `test_evaluation.py` | RAGAS / DeepEval / PromptFoo scoring |

---

## Troubleshooting

**`ImportError: cannot import name 'DEFAULT_EXCLUDED_CONTENT_TYPES'`**

Starlette version conflict between fastapi and streamlit. Fix:

```bash
pip install "fastapi>=0.116.0"
```

**`OPENROUTER_API_KEY is not set`**

Copy `.env.example` to `.env` and add your key:

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=sk-or-v1-...
```

**All models returning 429**

The free-tier models have per-minute rate limits. The cascade will retry across all 6 models before failing. If all 6 are exhausted, wait 60 seconds and retry. You can extend `MAX_RUNTIME_SECONDS` in `.env` to give the cascade more time.

**Database locked / WAL file present**

If the app crashed mid-run, the SQLite WAL file may be present. It is safe to leave in place — SQLite will reconcile it automatically on the next connection. If you need to force a clean state:

```bash
# Only do this if no run is active
del database\intelligence.db-wal
del database\intelligence.db-shm
```

**Streamlit shows blank page**

Ensure you are running from the project root directory:

```bash
cd competitive-intelligence-crew
streamlit run app.py
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | _(required)_ | OpenRouter API key |
| `MODEL_NAME` | `openrouter/google/gemma-4-31b-it:free` | Primary model |
| `MODEL_PRIMARY` | same as MODEL_NAME | Cascade model 1 |
| `MODEL_FALLBACK` | `llama-3.3-70b-instruct:free` | Cascade model 2 |
| `MODEL_LAST_RESORT` | `llama-3.2-3b-instruct:free` | Cascade model 3 |
| `TAVILY_API_KEY` | _(empty)_ | Tavily search API (optional) |
| `DATABASE_URL` | `sqlite:///./database/intelligence.db` | Database path |
| `CACHE_TTL_SECONDS` | `3600` | Search cache TTL |
| `MAX_SOURCES` | `15` | Max sources per run |
| `MAX_STEPS` | `25` | Max agent steps per run |
| `MAX_RUNTIME_SECONDS` | `900` | Run timeout |
| `MAX_COST_USD` | `0.02` | Cost ceiling |
| `HUMAN_REVIEW_ENABLED` | `true` | Enable human review gate |
| `AUTO_APPROVE_THRESHOLD` | `0.85` | Auto-approve confidence threshold |
| `EVALUATION_ENABLED` | `true` | Run RAGAS/DeepEval after each run |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry export |
| `OUTPUT_DIR` | `./outputs` | Export file destination |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

Full reference: see `.env.example`.
