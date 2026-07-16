"""
src/tools/web_scraper.py
=========================
Web scraper tool using requests + BeautifulSoup.
Extracts clean text content from web pages including pricing pages,
blog posts, press releases, and annual reports.
"""

from __future__ import annotations

import hashlib
import re
from typing import Type
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.cache import cache_manager
from src.utils.logger import get_logger
from src.utils.retry import get_circuit_breaker

log = get_logger(__name__)

_scraper_breaker = get_circuit_breaker("web_scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CompetitiveIntelligenceBot/1.0; " "+https://github.com/ci-crew)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Tags to remove (navigation, ads, etc.)
NOISE_TAGS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
    "noscript",
    "advertisement",
]


class WebScraperInput(BaseModel):
    url: str = Field(..., description="URL to scrape")
    extract_type: str = Field(
        default="text",
        description="What to extract: 'text', 'pricing', 'product', 'press_release'",
    )
    max_chars: int = Field(
        default=5000,
        ge=100,
        le=20000,
        description="Maximum characters to return",
    )


class WebScraperTool(BaseTool):
    """
    Web scraper that extracts clean, structured text from web pages.

    Supports extraction modes:
    - text: General text extraction
    - pricing: Focused on pricing tables and plans
    - product: Focused on product features and descriptions
    - press_release: Focused on press release content
    """

    name: str = "web_scraper"
    description: str = (
        "Scrape and extract text content from a web page URL. "
        "Use for reading competitor pricing pages, product pages, blog posts, "
        "press releases, and annual reports. Input: the URL to scrape."
    )
    args_schema: Type[BaseModel] = WebScraperInput

    def _run(
        self,
        url: str,
        extract_type: str = "text",
        max_chars: int = 5000,
    ) -> str:
        """Scrape URL with caching and error handling."""
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return f"Invalid URL: {url}"

        # Check cache
        cache_key = f"scrape:{url}:{extract_type}"
        cached = cache_manager.get(
            namespace="scraper", key=hashlib.sha256(cache_key.encode()).hexdigest()
        )
        if cached:
            log.debug(f"[Scraper] Cache HIT: {url[:60]}")
            return cached[:max_chars]

        # Scrape
        try:
            result = _scraper_breaker.call(self._scrape_url, url, extract_type, max_chars)
        except Exception as exc:
            log.warning(f"[Scraper] Failed to scrape {url}: {exc}")
            return f"Could not scrape {url}: {str(exc)[:200]}"

        if result:
            cache_manager.set(
                namespace="scraper",
                key=hashlib.sha256(cache_key.encode()).hexdigest(),
                value=result,
                ttl=settings.cache_ttl_seconds,
            )

        return result

    def _scrape_url(self, url: str, extract_type: str, max_chars: int) -> str:
        """Perform the actual HTTP request and content extraction."""
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        # Handle PDFs
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return self._extract_pdf_text(response.content, max_chars)

        soup = BeautifulSoup(response.content, "lxml")

        # Remove noise elements
        for tag in NOISE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()

        # Extract based on type
        if extract_type == "pricing":
            text = self._extract_pricing(soup)
        elif extract_type == "product":
            text = self._extract_product(soup)
        elif extract_type == "press_release":
            text = self._extract_press_release(soup)
        else:
            text = self._extract_text(soup)

        # Clean whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = text.strip()

        # Add source metadata
        title = soup.find("title")
        title_text = title.get_text().strip() if title else url
        result = f"Source: {url}\nTitle: {title_text}\n\n{text}"

        return result[:max_chars]

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """General text extraction from main content area."""
        # Try common content selectors
        for selector in ["main", "article", ".content", "#content", ".post-content"]:
            content = soup.select_one(selector)
            if content:
                return content.get_text(separator="\n", strip=True)
        # Fallback to body
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)

    def _extract_pricing(self, soup: BeautifulSoup) -> str:
        """Extract pricing-specific content."""
        lines = []
        # Look for pricing tables, plans, cost mentions
        pricing_selectors = [
            "table",
            ".pricing",
            ".price",
            ".plan",
            "[class*='price']",
            "[class*='plan']",
            "[class*='tier']",
            "[class*='cost']",
        ]
        found_pricing = False
        for selector in pricing_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(separator=" | ", strip=True)
                if text and len(text) > 10:
                    lines.append(text)
                    found_pricing = True

        if not found_pricing:
            lines.append(self._extract_text(soup))

        return "\n\n".join(lines[:20])

    def _extract_product(self, soup: BeautifulSoup) -> str:
        """Extract product feature content."""
        lines = []
        for selector in [
            ".features",
            ".product-features",
            "h1",
            "h2",
            "h3",
            ".feature-list",
            "[class*='feature']",
        ]:
            for elem in soup.select(selector):
                text = elem.get_text(separator=" ", strip=True)
                if text and len(text) > 5:
                    lines.append(text)
        return "\n".join(lines[:50]) or self._extract_text(soup)

    def _extract_press_release(self, soup: BeautifulSoup) -> str:
        """Extract press release content."""
        for selector in ["article", ".press-release", ".news-content", "main"]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(separator="\n", strip=True)
        return self._extract_text(soup)

    def _extract_pdf_text(self, content: bytes, max_chars: int) -> str:
        """Extract text from PDF binary content."""
        try:
            import io

            import pdfplumber

            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages_text = []
                for page in pdf.pages[:10]:  # Max 10 pages
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
            return "\n\n".join(pages_text)[:max_chars]
        except ImportError:
            return "PDF extraction requires pdfplumber. Install: pip install pdfplumber"
        except Exception as exc:
            return f"PDF extraction failed: {exc}"


# Singleton
web_scraper_tool = WebScraperTool()

__all__ = ["WebScraperTool", "web_scraper_tool"]
