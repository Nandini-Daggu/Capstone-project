"""
tests/test_tools.py
====================
Unit tests for all tool modules.
"""

from __future__ import annotations

import pytest


class TestCitationTool:
    """Tests for citation_tool.py"""

    def setup_method(self):
        from src.tools.citation_tool import CitationRegistry, CitationTool

        self.tool = CitationTool()
        # Reset registry
        self.tool._run(action="clear")

    def test_add_source(self):
        result = self.tool._run(
            action="add_source",
            url="https://example.com/article",
            title="Test Article",
            source_name="Example News",
            published_date="2024-01-15",
        )
        assert "[1]" in result

    def test_add_duplicate_source_returns_same_index(self):
        self.tool._run(action="add_source", url="https://example.com/a", title="A", source_name="S")
        result2 = self.tool._run(
            action="add_source", url="https://example.com/a", title="A", source_name="S"
        )
        assert "[1]" in result2

    def test_get_citation(self):
        self.tool._run(action="add_source", url="https://example.com/b", title="B", source_name="S")
        result = self.tool._run(action="get_citation", url="https://example.com/b")
        assert "[1]" in result

    def test_generate_references(self):
        self.tool._run(
            action="add_source",
            url="https://salesforce.com/q3",
            title="Q3 Earnings",
            source_name="Salesforce IR",
        )
        refs = self.tool._run(action="generate_references")
        assert "Salesforce IR" in refs
        assert "https://salesforce.com/q3" in refs

    def test_check_claims_detects_uncited_statistic(self):
        text = "The company grew 150% last year. Revenue increased to $5 billion."
        result = self.tool._run(action="check_claims", text=text)
        assert "uncited" in result.lower() or "⚠️" in result

    def test_check_claims_passes_cited_text(self):
        text = "The company grew 150% last year [1]. Revenue increased to $5 billion [2]."
        result = self.tool._run(action="check_claims", text=text)
        assert "✅" in result

    def test_verify_citations_detects_missing_source(self):
        self.tool._run(action="clear")
        text = "Growth was 20% [99]."
        result = self.tool._run(action="verify_citations", text=text)
        assert "FAILED" in result or "[99]" in result

    def test_clear(self):
        self.tool._run(action="add_source", url="https://x.com", title="X", source_name="X")
        self.tool._run(action="clear")
        result = self.tool._run(action="generate_references")
        assert "No sources" in result or "_No sources" in result


class TestCacheManager:
    """Tests for cache.py"""

    def setup_method(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        # Isolated temp directory - no shared disk state between tests.
        self._tmpdir = tempfile.mkdtemp()
        Path(self._tmpdir).mkdir(parents=True, exist_ok=True)

        self._mock_settings = MagicMock()
        self._mock_settings.llm_cache_enabled = True
        self._mock_settings.search_cache_enabled = True
        self._mock_settings.embedding_cache_enabled = True
        self._mock_settings.cache_dir = Path(self._tmpdir)
        self._mock_settings.cache_ttl_seconds = 3600

        self._patch = patch("src.utils.cache.settings", self._mock_settings)
        self._patch.start()

        # Import after patch so module globals pick up the mock
        import importlib

        import src.utils.cache as _mod

        importlib.reload(_mod)
        self.cache = _mod.CacheManager()

    def teardown_method(self):
        import importlib
        import shutil

        try:
            self._patch.stop()
        except RuntimeError:
            pass
        # Reload module with real settings restored
        try:
            import src.utils.cache as _mod

            importlib.reload(_mod)
        except Exception:
            pass
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_llm_cache_miss(self):
        result = self.cache.get_llm("unique_prompt_xyz", "model")
        assert result is None

    def test_llm_cache_set_get(self):
        self.cache.set_llm("test_prompt_123", "model-x", "cached response")
        result = self.cache.get_llm("test_prompt_123", "model-x")
        assert result == "cached response"

    def test_search_cache_miss(self):
        result = self.cache.get_search("nonexistent query xyzzy", "duckduckgo")
        assert result is None

    def test_search_cache_set_get(self):
        data = [{"title": "Test", "url": "https://test.com"}]
        self.cache.set_search("test query abc", data, "duckduckgo")
        result = self.cache.get_search("test query abc", "duckduckgo")
        assert result == data

    def test_stats(self):
        stats = self.cache.get_stats()
        assert "hit_rate" in stats
        assert isinstance(stats["hit_rate"], float)

    def test_generic_namespace(self):
        self.cache.set("test_ns", "key1", {"value": 42})
        result = self.cache.get("test_ns", "key1")
        assert result == {"value": 42}


class TestRAGTool:
    """Tests for rag_tool.py (unit — no FAISS needed for basic tests)"""

    def test_rag_tool_instantiates(self):
        from src.tools.rag_tool import RAGTool

        tool = RAGTool()
        assert tool is not None

    def test_document_loader_chunks_text(self):
        from src.tools.rag_tool import DocumentLoader

        loader = DocumentLoader()
        text = " ".join([f"word{i}" for i in range(600)])
        chunks = loader._chunk_text(text, "test_source", "test.txt")
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.text
            assert chunk.source_name == "test.txt"

    def test_document_chunk_model(self):
        from src.tools.rag_tool import DocumentChunk

        chunk = DocumentChunk(
            chunk_id="c1",
            document_id="d1",
            source_path="/test/doc.txt",
            source_name="doc.txt",
            text="This is a test chunk.",
            chunk_index=0,
        )
        assert chunk.text == "This is a test chunk."
        assert chunk.citation_metadata["source_name"] == "doc.txt"


class TestReportExport:
    """Tests for report_export.py"""

    def test_export_markdown(self, tmp_path, monkeypatch):
        from config.settings import settings
        from src.tools.report_export import ReportExportTool

        monkeypatch.setattr(settings, "output_dir", tmp_path)
        tool = ReportExportTool()
        result = tool._run("# Test Report\n\nContent here.", "markdown", "test-run-123")
        assert "exported" in result.lower()

    def test_export_json(self, tmp_path, monkeypatch):
        from config.settings import settings
        from src.tools.report_export import ReportExportTool

        monkeypatch.setattr(settings, "output_dir", tmp_path)
        tool = ReportExportTool()
        result = tool._run("# Test\n\n## Section One\n\nContent.", "json", "test-run-456")
        assert "exported" in result.lower() or "json" in result.lower()

    def test_parse_sections(self):
        from src.tools.report_export import ReportExportTool

        tool = ReportExportTool()
        md = "# Title\n\n## Section One\n\nContent one.\n\n## Section Two\n\nContent two."
        sections = tool._parse_markdown_sections(md)
        assert "section_one" in sections
        assert "Content one." in sections["section_one"]
