"""
src/tools/pdf_export.py
========================
PDF export tool for competitive intelligence briefings.
Uses WeasyPrint to convert Markdown → HTML → PDF with professional styling.
"""

from __future__ import annotations

import time
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

body {
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a2e;
    margin: 0;
    padding: 0;
}

.page-wrapper {
    max-width: 800px;
    margin: 0 auto;
    padding: 40px;
}

.cover-page {
    text-align: center;
    page-break-after: always;
    padding-top: 120px;
}

.cover-page h1 {
    font-size: 28pt;
    font-weight: 700;
    color: #16213e;
    margin-bottom: 16px;
}

.cover-page .subtitle {
    font-size: 14pt;
    color: #0f3460;
    margin-bottom: 8px;
}

.cover-page .meta {
    font-size: 10pt;
    color: #666;
    margin-top: 60px;
}

h1 { font-size: 20pt; color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: 8px; }
h2 { font-size: 16pt; color: #0f3460; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
h3 { font-size: 13pt; color: #16213e; }
h4 { font-size: 11pt; color: #333; }

table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 9pt;
}
th {
    background-color: #16213e;
    color: white;
    padding: 8px 12px;
    text-align: left;
}
td {
    padding: 7px 12px;
    border-bottom: 1px solid #e0e0e0;
}
tr:nth-child(even) { background-color: #f8f9fa; }

blockquote {
    background: #e8f4fd;
    border-left: 4px solid #0f3460;
    padding: 12px 20px;
    margin: 16px 0;
    font-style: italic;
}

code {
    background: #f4f4f4;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 9pt;
}

.footer {
    text-align: center;
    font-size: 8pt;
    color: #999;
    border-top: 1px solid #e0e0e0;
    padding-top: 12px;
    margin-top: 40px;
}

@page {
    size: A4;
    margin: 20mm 15mm 20mm 15mm;
    @bottom-center {
        content: "Competitive Intelligence Briefing | Confidential | Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        color: #999;
    }
}
"""


class PDFExportInput(BaseModel):
    markdown_content: str = Field(..., description="Markdown content to convert to PDF")
    output_filename: Optional[str] = Field(None, description="Output filename (without extension)")
    run_id: Optional[str] = Field(None, description="Run ID for file naming")


class PDFExportTool(BaseTool):
    """
    Export competitive intelligence briefing as a professional PDF.
    Converts Markdown to styled HTML and renders to PDF using WeasyPrint.
    """

    name: str = "pdf_export"
    description: str = (
        "Export the briefing report as a professional PDF document. "
        "Input: the full Markdown content of the briefing. "
        "Returns the path to the generated PDF file."
    )
    args_schema: Type[BaseModel] = PDFExportInput

    def _run(
        self,
        markdown_content: str,
        output_filename: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> str:
        """Convert Markdown to PDF and save to outputs directory."""
        try:
            import markdown as md_lib

            html_body = md_lib.markdown(
                markdown_content,
                extensions=["tables", "fenced_code", "toc", "attr_list"],
            )
        except Exception as exc:
            return f"Markdown conversion failed: {exc}"

        full_html = self._build_html(html_body)

        # Determine output path
        filename = output_filename or (
            f"briefing_{run_id}" if run_id else f"briefing_{int(time.time())}"
        )
        output_path = settings.output_dir / f"{filename}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from weasyprint import CSS, HTML

            HTML(string=full_html).write_pdf(
                str(output_path),
                stylesheets=[CSS(string=PDF_CSS)],
            )
            size_kb = output_path.stat().st_size // 1024
            log.info(f"[PDF] Generated: {output_path} ({size_kb} KB)")
            return f"PDF exported successfully: {output_path} ({size_kb} KB)"
        except ImportError:
            # Fallback: save as HTML with embedded CSS
            html_path = output_path.with_suffix(".html")
            html_path.write_text(full_html, encoding="utf-8")
            log.warning("[PDF] WeasyPrint not available. Saved as HTML instead.")
            return f"WeasyPrint unavailable. Saved as HTML: {html_path}"
        except Exception as exc:
            log.error(f"[PDF] Export failed: {exc}")
            return f"PDF export failed: {exc}"

    def _build_html(self, body: str) -> str:
        """Wrap HTML body with full document structure and CSS."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Competitive Intelligence Briefing</title>
    <style>{PDF_CSS}</style>
</head>
<body>
<div class="page-wrapper">
{body}
<div class="footer">
    Competitive Intelligence Briefing &mdash; Confidential &mdash; AI-Generated with Human Review
</div>
</div>
</body>
</html>"""


# Singleton
pdf_export_tool = PDFExportTool()

__all__ = ["PDFExportTool", "pdf_export_tool"]
