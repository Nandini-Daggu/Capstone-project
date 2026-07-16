"""
tests/conftest.py
==================
Shared pytest fixtures for the test suite.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment variables BEFORE any imports
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-real")
os.environ.setdefault("DATABASE_URL", "sqlite:///./database/test_intelligence.db")
os.environ.setdefault("CACHE_DIR", "./cache/test")
os.environ.setdefault("LOG_DIR", "./logs/test")
os.environ.setdefault("EVALUATION_ENABLED", "false")
os.environ.setdefault("LLM_CACHE_ENABLED", "true")
os.environ.setdefault("SEARCH_CACHE_ENABLED", "true")


@pytest.fixture(scope="session", autouse=True)
def setup_test_dirs():
    """Create required test directories."""
    dirs = ["./logs/test", "./cache/test", "./outputs", "./database"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup test DB
    test_db = Path("./database/test_intelligence.db")
    if test_db.exists():
        try:
            test_db.unlink()
        except Exception:
            pass


@pytest.fixture
def sample_briefing() -> str:
    """Return a sample completed briefing for testing."""
    return """# Competitive Intelligence Briefing: SaaS CRM

**Industry:** SaaS / CRM | **Period:** last 7 days | **Region:** North America

---

## Executive Summary

Salesforce reported strong Q3 2024 earnings with revenue up 11% year-over-year [1].
HubSpot launched a new AI-powered CRM assistant targeting SMBs [2].
Pipedrive expanded its European operations with a new Berlin office [3].

---

## Competitor Pricing Analysis

| Competitor | Entry Plan | Professional | Enterprise |
|-----------|-----------|--------------|------------|
| Salesforce | $25/user/mo [1] | $75/user/mo [1] | Custom [1] |
| HubSpot | Free tier [2] | $45/user/mo [2] | $1,200/mo [2] |
| Pipedrive | $14/user/mo [3] | $34/user/mo [3] | $64/user/mo [3] |

---

## Product & Feature Updates

Salesforce released Einstein AI Co-pilot in beta [1].
HubSpot acquired a customer data platform startup [2].

---

## Market Signals

- AI integration is now table-stakes for CRM vendors [4]
- SMB market share growing 15% annually [4]

---

## Industry Trends

1. **AI-First CRM**: All major vendors are embedding AI copilots [1][2][4]
2. **Vertical SaaS**: Sector-specific CRM gaining traction [5]

---

## SWOT Analysis

| | Strengths | Weaknesses |
|---|-----------|------------|
| Internal | Brand, ecosystem [1] | Price point [1] |

---

## Risk Analysis

| Risk | Severity | Source |
|------|---------|--------|
| AI commoditisation | HIGH | [4] |

---

## Opportunities

| Opportunity | Impact | Evidence |
|------------|--------|---------|
| SMB segment | HIGH | [2][4] |

---

## Strategic Recommendations

1. **Accelerate AI features**: Competitors are moving fast [1][2]
2. **Target SMB**: Growing market with lower competition [4]

---

## References

[1] Salesforce Inc. (2024-11-20). *Q3 FY2025 Earnings Release*. https://investor.salesforce.com
[2] HubSpot Inc. (2024-11-15). *HubSpot Launches AI CRM Assistant*. https://blog.hubspot.com
[3] Pipedrive (2024-11-10). *Pipedrive Opens Berlin Office*. https://www.pipedrive.com/blog
[4] Gartner (2024-10-01). *CRM Market Guide 2024*. https://www.gartner.com
[5] Forrester (2024-09-15). *Vertical SaaS Trends*. https://www.forrester.com

---

## Run Metadata

| Metric | Value |
|--------|-------|
| Sources Used | 5 |
| Steps Used | 12 |
| Total Tokens | 4500 |
| Estimated Cost | $0.0000 |
| Duration | 45.2s |
| Model | openrouter/google/gemma-4-31b-it:free |

---

## Evaluation Summary

Evaluation pending.
"""


@pytest.fixture
def sample_research_items() -> list:
    """Return sample research items."""
    from src.utils.models import ResearchCategory, ResearchItem

    return [
        ResearchItem(
            competitor="Salesforce",
            category=ResearchCategory.NEWS,
            title="Salesforce Q3 Earnings Beat",
            summary="Salesforce reported 11% revenue growth in Q3 2024.",
            source_url="https://investor.salesforce.com/q3-2024",
            source_name="Salesforce Investor Relations",
            published_date="2024-11-20",
            snippet="Revenue increased 11% year-over-year to $9.4 billion.",
            confidence=0.95,
        ),
        ResearchItem(
            competitor="HubSpot",
            category=ResearchCategory.PRODUCT,
            title="HubSpot AI CRM Launch",
            summary="HubSpot launched AI-powered CRM assistant.",
            source_url="https://blog.hubspot.com/ai-crm",
            source_name="HubSpot Blog",
            published_date="2024-11-15",
            snippet="HubSpot announces Breeze AI for all CRM users.",
            confidence=0.90,
        ),
    ]


@pytest.fixture
def sample_run_config() -> Dict[str, Any]:
    return {
        "industry": "SaaS / CRM",
        "competitors": ["Salesforce", "HubSpot"],
        "region": "North America",
        "time_period": "last 7 days",
        "max_sources": 5,
        "max_steps": 10,
    }
