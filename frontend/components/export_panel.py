"""
frontend/components/export_panel.py
=====================================
Polished export download panel with card-based layout.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st


def render_export_panel(
    run_id: str,
    report_markdown: str,
    export_paths: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Render the export download panel."""
    export_paths = export_paths or {}
    metadata = metadata or {}

    # ── Section header ────────────────────────────────────────
    st.markdown(
        """
    <div class="section-header">
        <span class="sh-icon">📥</span>
        <span class="sh-title">Download Report</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ── Run metadata summary ──────────────────────────────────
    if metadata:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("⏱ Duration", f"{metadata.get('duration_seconds', 0):.0f}s")
        m2.metric("🔗 Sources", metadata.get("sources_used", 0))
        m3.metric("🔄 Steps Used", metadata.get("steps_used", 0))
        m4.metric("💰 Est. Cost", f"${metadata.get('estimated_cost_usd', 0):.4f}")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Format definitions ────────────────────────────────────
    FORMATS = [
        {
            "key": "markdown",
            "icon": "📝",
            "label": "Markdown",
            "ext": ".md",
            "mime": "text/markdown",
            "desc": "Raw .md file",
            "always": True,
        },
        {
            "key": "html",
            "icon": "🌐",
            "label": "HTML",
            "ext": ".html",
            "mime": "text/html",
            "desc": "Web-ready page",
            "always": False,
        },
        {
            "key": "pdf",
            "icon": "📕",
            "label": "PDF",
            "ext": ".pdf",
            "mime": "application/pdf",
            "desc": "Print-ready PDF",
            "always": False,
        },
        {
            "key": "pptx",
            "icon": "📊",
            "label": "PowerPoint",
            "ext": ".pptx",
            "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "desc": "Presentation deck",
            "always": False,
        },
        {
            "key": "json",
            "icon": "🗂️",
            "label": "JSON",
            "ext": ".json",
            "mime": "application/json",
            "desc": "Machine-readable",
            "always": True,
        },
    ]

    # ── 5 format columns ──────────────────────────────────────
    cols = st.columns(5, gap="small")

    for col, fmt in zip(cols, FORMATS):
        with col:
            key = fmt["key"]
            file_path = export_paths.get(key)
            available = fmt["always"] or (file_path and Path(file_path).exists())
            short_id = run_id[:8]

            # Card header — large emoji, bold name, small desc
            st.markdown(
                f'<div style="'
                f"text-align:center;"
                f"padding:0.9rem 0.4rem 0.5rem 0.4rem;"
                f"background:#ffffff;"
                f"border-radius:12px;"
                f"border:1px solid #E5E7EB;"
                f"box-shadow:0 1px 3px rgba(0,0,0,0.07);"
                f"margin-bottom:0.5rem;"
                f'">'
                f'<div style="font-size:2rem;line-height:1.2;">{fmt["icon"]}</div>'
                f'<div style="font-size:0.85rem;font-weight:700;color:#0d1b2a;'
                f'margin-top:0.3rem;">{fmt["label"]}</div>'
                f'<div style="font-size:0.72rem;color:#9ca3af;margin-top:0.15rem;'
                f'min-height:1.4rem;">{fmt["desc"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

            if available:
                # ── Build download data ───────────────────────
                if key == "markdown":
                    data = report_markdown.encode("utf-8")
                elif key == "json":
                    data = json.dumps(
                        {
                            "run_id": run_id,
                            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "metadata": metadata,
                            "content": report_markdown,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ).encode("utf-8")
                elif file_path and Path(file_path).exists():
                    data = Path(file_path).read_bytes()
                else:
                    data = report_markdown.encode("utf-8")

                # Show file size for non-inline formats when path exists
                if file_path and Path(file_path).exists() and key not in ("markdown", "json"):
                    size_kb = len(Path(file_path).read_bytes()) // 1024
                    st.markdown(
                        f'<div style="text-align:center;font-size:0.7rem;'
                        f'color:#6b7280;margin-bottom:0.3rem;">📦 {size_kb} KB ready</div>',
                        unsafe_allow_html=True,
                    )

                st.download_button(
                    label=f"⬇ Download",
                    data=data,
                    file_name=f"ci_briefing_{short_id}{fmt['ext']}",
                    mime=fmt["mime"],
                    use_container_width=True,
                    key=f"dl_{key}_{run_id}",
                )

            else:
                # ── Generate on demand ────────────────────────
                if st.button(
                    f"⚙ Generate",
                    use_container_width=True,
                    key=f"gen_{key}_{run_id}",
                ):
                    _generate_format(run_id, report_markdown, key)

                st.markdown(
                    '<div style="text-align:center;font-size:0.7rem;color:#9ca3af;'
                    'margin-top:0.25rem;">Not yet generated</div>',
                    unsafe_allow_html=True,
                )


def _generate_format(run_id: str, markdown: str, fmt: str) -> None:
    """Generate a specific export format on demand."""
    with st.spinner(f"Generating {fmt.upper()}…"):
        try:
            if fmt == "html":
                from src.tools.report_export import report_export_tool

                result = report_export_tool._run(markdown, "html", run_id)
                st.success(f"✅ HTML generated! {result}")
            elif fmt == "pdf":
                from src.tools.pdf_export import pdf_export_tool

                result = pdf_export_tool._run(markdown, run_id=run_id)
                st.success(f"✅ PDF generated! {result}")
            elif fmt == "pptx":
                from src.tools.ppt_export import ppt_export_tool

                result = ppt_export_tool._run(markdown, run_id=run_id)
                st.success(f"✅ PPTX generated! {result}")
            else:
                st.info(f"{fmt.upper()} generation not supported on demand.")
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to generate {fmt}: {exc}")
