"""
src/tools/report_export.py
===========================
Multi-format report export tool.
Handles Markdown, HTML, JSON, and delegates to PDF/PPT tools.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class ReportExportInput(BaseModel):
    content: str = Field(..., description="Report content (Markdown)")
    format: str = Field(
        default="markdown",
        description="Export format: 'markdown', 'html', 'json'",
    )
    run_id: Optional[str] = Field(None, description="Run ID for file naming")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for JSON export")


class ReportExportTool(BaseTool):
    """
    Multi-format report export tool.
    Supports Markdown, HTML, and JSON exports.
    """

    name: str = "report_export"
    description: str = (
        "Export the intelligence briefing in various formats: markdown, html, or json. "
        "Returns the path to the exported file."
    )
    args_schema: Type[BaseModel] = ReportExportInput

    def _run(
        self,
        content: str,
        format: str = "markdown",
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Export report in the specified format."""
        filename_base = f"briefing_{run_id}" if run_id else f"briefing_{int(time.time())}"
        settings.output_dir.mkdir(parents=True, exist_ok=True)

        if format == "markdown":
            return self._export_markdown(content, filename_base)
        elif format == "html":
            return self._export_html(content, filename_base)
        elif format == "json":
            return self._export_json(content, filename_base, metadata)
        else:
            return f"Unknown format: {format}. Use: markdown, html, json"

    def _export_markdown(self, content: str, filename: str) -> str:
        """Save as Markdown file."""
        path = settings.output_dir / f"{filename}.md"
        path.write_text(content, encoding="utf-8")
        size = path.stat().st_size
        log.info(f"[Export] Markdown: {path} ({size} bytes)")
        return f"Markdown exported: {path}"

    def _export_html(self, content: str, filename: str) -> str:
        """Convert Markdown to styled HTML."""
        try:
            import markdown as md_lib
            html_body = md_lib.markdown(
                content,
                extensions=["tables", "fenced_code", "toc"],
            )
        except ImportError:
            html_body = f"<pre>{content}</pre>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Competitive Intelligence Briefing</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 900px; margin: 40px auto;
               padding: 20px; color: #1a1a2e; line-height: 1.7; }}
        h1 {{ color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: 8px; }}
        h2 {{ color: #0f3460; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th {{ background: #16213e; color: white; padding: 8px 12px; text-align: left; }}
        td {{ padding: 7px 12px; border-bottom: 1px solid #e0e0e0; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        blockquote {{ border-left: 4px solid #0f3460; padding: 8px 16px; background: #e8f4fd; }}
        .footer {{ text-align: center; font-size: 0.8em; color: #999; margin-top: 40px;
                   border-top: 1px solid #e0e0e0; padding-top: 12px; }}
    </style>
</head>
<body>
{html_body}
<div class="footer">
    Competitive Intelligence Briefing &mdash; Confidential &mdash; AI-Generated with Human Review
</div>
</body>
</html>"""

        path = settings.output_dir / f"{filename}.html"
        path.write_text(html, encoding="utf-8")
        size = path.stat().st_size
        log.info(f"[Export] HTML: {path} ({size} bytes)")
        return f"HTML exported: {path}"

    def _export_json(
        self,
        content: str,
        filename: str,
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        """Export as structured JSON."""
        # Parse sections from Markdown
        sections = self._parse_markdown_sections(content)
        data = {
            "title": "Competitive Intelligence Briefing",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sections": sections,
            "full_content": content,
            "metadata": metadata or {},
        }
        path = settings.output_dir / f"{filename}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        size = path.stat().st_size
        log.info(f"[Export] JSON: {path} ({size} bytes)")
        return f"JSON exported: {path}"

    def _parse_markdown_sections(self, markdown: str) -> Dict[str, str]:
        """Extract H2 sections from Markdown into a dict."""
        sections: Dict[str, str] = {}
        current_key = "preamble"
        current_lines = []

        for line in markdown.split("\n"):
            if line.startswith("## "):
                if current_lines:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = line[3:].strip().lower().replace(" ", "_")
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections


# Singleton
report_export_tool = ReportExportTool()

__all__ = ["ReportExportTool", "report_export_tool"]
