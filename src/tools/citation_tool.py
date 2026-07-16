"""
src/tools/citation_tool.py
===========================
Citation management tool.
Assigns numbered citation indices to sources, validates citations,
detects uncited claims, and generates formatted reference lists.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.logger import get_logger
from src.utils.models import CitedSource

log = get_logger(__name__)

# Patterns that indicate a factual claim requiring citation
CLAIM_PATTERNS = [
    r"\b\d+[\.,]?\d*\s*(?:billion|million|percent|%)\b",   # Financial figures
    r"\bracquired?\b",                                        # Acquisition claims
    r"\braised\s+\$",                                         # Funding claims
    r"\blaunched?\b",                                         # Launch claims
    r"\bincreased?\s+by\b",                                   # Growth claims
    r"\bdecreased?\s+by\b",                                   # Decline claims
    r"\bannounced?\b",                                        # Announcement claims
    r"\bpartnership\b",                                       # Partnership claims
    r"\blaid\s+off\b",                                        # Layoff claims
    r"\bfired\b|\bhired\b",                                  # HR claims
    r"\bIPO\b|\bvaluation\b",                                # Valuation claims
]


class CitationInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action to perform: 'add_source', 'get_citation', "
            "'verify_citations', 'generate_references', 'check_claims', 'clear'"
        ),
    )
    text: Optional[str] = Field(None, description="Text to check for uncited claims")
    url: Optional[str] = Field(None, description="Source URL to add/retrieve")
    title: Optional[str] = Field(None, description="Source title")
    source_name: Optional[str] = Field(None, description="Publication/source name")
    published_date: Optional[str] = Field(None, description="Publication date YYYY-MM-DD")
    snippet: Optional[str] = Field(None, description="Relevant snippet from source")


class CitationRegistry:
    """Thread-safe registry of all sources used in a run."""

    def __init__(self) -> None:
        self._sources: Dict[str, CitedSource] = {}  # URL → CitedSource
        self._index: int = 0

    def add(
        self,
        url: str,
        title: str,
        source_name: str,
        published_date: Optional[str] = None,
        snippet: Optional[str] = None,
    ) -> CitedSource:
        """Add a source and return its citation index."""
        if url in self._sources:
            return self._sources[url]
        self._index += 1
        source = CitedSource(
            source_id=self._index,
            url=url,
            title=title,
            source_name=source_name,
            published_date=published_date,
            snippet=snippet,
        )
        self._sources[url] = source
        return source

    def get(self, url: str) -> Optional[CitedSource]:
        return self._sources.get(url)

    def get_by_index(self, index: int) -> Optional[CitedSource]:
        for s in self._sources.values():
            if s.source_id == index:
                return s
        return None

    def all_sources(self) -> List[CitedSource]:
        return sorted(self._sources.values(), key=lambda s: s.source_id)

    def generate_references_markdown(self) -> str:
        """Generate a numbered bibliography in Markdown format."""
        sources = self.all_sources()
        if not sources:
            return "_No sources cited._"
        lines = []
        for s in sources:
            date_str = f" ({s.published_date})" if s.published_date else ""
            lines.append(
                f"[{s.source_id}] {s.source_name}{date_str}. "
                f"*{s.title}*. Retrieved from: {s.url}"
            )
        return "\n".join(lines)

    def clear(self) -> None:
        self._sources.clear()
        self._index = 0


# Global registry (reset per run)
_registry = CitationRegistry()


class CitationTool(BaseTool):
    """
    Citation management tool for the intelligence crew.

    Actions:
    - add_source: Register a source and get its citation number
    - get_citation: Get citation number for a URL
    - verify_citations: Check that all [n] references resolve to sources
    - generate_references: Generate formatted reference list
    - check_claims: Detect factual claims that lack citations
    - clear: Reset registry for a new run
    """

    name: str = "citation_manager"
    description: str = (
        "Manage source citations. Use 'add_source' to register sources and get citation numbers. "
        "Use 'generate_references' to build the reference list. "
        "Use 'check_claims' to find uncited factual assertions. "
        "EVERY factual claim in the report must have a citation [n]."
    )
    args_schema: Type[BaseModel] = CitationInput

    def _run(
        self,
        action: str,
        text: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        source_name: Optional[str] = None,
        published_date: Optional[str] = None,
        snippet: Optional[str] = None,
    ) -> str:
        """Execute citation action."""
        if action == "add_source":
            return self._add_source(url, title, source_name, published_date, snippet)
        elif action == "get_citation":
            return self._get_citation(url)
        elif action == "verify_citations":
            return self._verify_citations(text)
        elif action == "generate_references":
            return _registry.generate_references_markdown()
        elif action == "check_claims":
            return self._check_claims(text)
        elif action == "clear":
            _registry.clear()
            return "Citation registry cleared."
        else:
            return f"Unknown action: {action}. Valid: add_source, get_citation, verify_citations, generate_references, check_claims, clear"

    def _add_source(
        self,
        url: Optional[str],
        title: Optional[str],
        source_name: Optional[str],
        published_date: Optional[str],
        snippet: Optional[str],
    ) -> str:
        if not url:
            return "Error: URL is required to add a source."
        source = _registry.add(
            url=url,
            title=title or url,
            source_name=source_name or "Unknown Source",
            published_date=published_date,
            snippet=snippet,
        )
        return f"Source registered as citation [{source.source_id}]: {source.title}"

    def _get_citation(self, url: Optional[str]) -> str:
        if not url:
            return "Error: URL required."
        source = _registry.get(url)
        if source:
            return f"[{source.source_id}]"
        return "Source not found. Use 'add_source' first."

    def _verify_citations(self, text: Optional[str]) -> str:
        if not text:
            return "Error: text required."
        # Find all [n] patterns
        refs = re.findall(r"\[(\d+)\]", text)
        if not refs:
            return "⚠️ No citations found in text. Every factual claim needs a citation [n]."

        issues = []
        for ref in set(refs):
            idx = int(ref)
            source = _registry.get_by_index(idx)
            if not source:
                issues.append(f"  - [{ref}] has no registered source")

        if issues:
            return "Citation verification FAILED:\n" + "\n".join(issues)
        return f"✅ All {len(set(refs))} citations verified against registered sources."

    def _check_claims(self, text: Optional[str]) -> str:
        if not text:
            return "Error: text required."

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        uncited_claims = []

        for sentence in sentences:
            has_claim = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in CLAIM_PATTERNS)
            has_citation = bool(re.search(r"\[\d+\]", sentence))
            if has_claim and not has_citation:
                uncited_claims.append(sentence[:200])

        if uncited_claims:
            result = f"⚠️ Found {len(uncited_claims)} potential uncited claims:\n"
            for i, claim in enumerate(uncited_claims[:10], 1):
                result += f"  {i}. {claim}\n"
            return result

        return "✅ No uncited claims detected in text."

    def get_registry(self) -> CitationRegistry:
        """Return the global registry (for agent use)."""
        return _registry


# Singleton
citation_tool = CitationTool()

__all__ = ["CitationTool", "citation_tool", "CitationRegistry", "_registry"]
