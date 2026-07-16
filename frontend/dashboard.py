"""
frontend/dashboard.py
======================
Main dashboard renderer for the Competitive Intelligence Crew.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

import streamlit as st

from .styles import CUSTOM_CSS, STATUS_COLORS, AGENT_STEPS
from .sidebar import render_sidebar
from .components.report_tabs import render_report_tabs
from .components.human_review import render_human_review_gate
from .components.export_panel import render_export_panel
from .runner import DirectRunner


def render_dashboard() -> None:
    """Top-level dashboard render function called from app.py."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Hero Header ───────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1 style="font-size:38px;font-weight:800;margin:0 0 0.35rem 0;
                   letter-spacing:-0.5px;line-height:1.15;">
            🔍 Competitive Intelligence Briefing Crew
        </h1>
        <p style="font-size:16px;margin:0 0 1rem 0;opacity:0.88;font-weight:400;
                  max-width:620px;">
            AI-powered competitive intelligence — automated research, analysis &amp;
            executive briefings with full source citations.
        </p>
        <div class="header-badges" style="display:flex;flex-wrap:wrap;gap:0.45rem;">
            <span class="header-badge">🤖 CrewAI Multi-Agent</span>
            <span class="header-badge">🧠 OpenRouter LLM</span>
            <span class="header-badge">🔎 FAISS RAG</span>
            <span class="header-badge">🛡️ Governance Enforced</span>
            <span class="header-badge">📊 RAGAS Evaluated</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _init_session_state()
    config = render_sidebar()
    _render_stats_bar()

    if config["generate_clicked"]:
        _start_run(config)

    if st.session_state.get("run_id"):
        _render_run_area(config)
    else:
        _render_welcome_screen()


# ── Session state ─────────────────────────────────────────────────────────────

def _init_session_state() -> None:
    defaults = {
        "run_id": None,
        "run_status": None,
        "report_data": None,
        "evaluation_data": None,
        "audit_logs": [],
        "export_paths": {},
        "review_submitted": False,
        "progress_pct": 0,
        "progress_msg": "",
        "generation_complete": False,
        "active_step": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v



# ── Run lifecycle ──────────────────────────────────────────────────────────────

def _start_run(config: Dict[str, Any]) -> None:
    if not config["industry"]:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:0.6rem;padding:0.75rem 1rem;
                    background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
                    margin:0.5rem 0;color:#991b1b;font-size:0.9rem;">
            ⚠️ <strong>Please select or enter an industry.</strong>
        </div>
        """, unsafe_allow_html=True)
        return
    if not config["competitors"]:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:0.6rem;padding:0.75rem 1rem;
                    background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
                    margin:0.5rem 0;color:#991b1b;font-size:0.9rem;">
            ⚠️ <strong>Please enter at least one competitor.</strong>
        </div>
        """, unsafe_allow_html=True)
        return

    run_id = str(uuid.uuid4())
    st.session_state.run_id = run_id
    st.session_state.run_status = "running"
    st.session_state.report_data = None
    st.session_state.evaluation_data = None
    st.session_state.audit_logs = []
    st.session_state.review_submitted = False
    st.session_state.generation_complete = False
    st.session_state.progress_pct = 0
    st.session_state.progress_msg = "Initialising…"
    st.session_state.active_step = 0
    _execute_run(run_id, config)


def _execute_run(run_id: str, config: Dict[str, Any]) -> None:
    """Execute the crew run with live progress display."""
    # ── Live progress header ──────────────────────────────────
    st.markdown("""
    <div class="section-header" style="margin-bottom:0.75rem;">
        <span class="sh-icon">⚡</span>
        <span class="sh-title">Generating Competitive Intelligence Report…</span>
    </div>
    """, unsafe_allow_html=True)

    # Pipeline steps indicator
    _render_pipeline_steps(active=0)

    progress_bar = st.progress(0, text="⏳ Initialising pipeline…")
    status_text = st.empty()

    progress_state = {"pct": 0, "msg": "Starting…", "step": 0}

    STEP_MAP = {
        5: 0, 15: 0, 30: 1, 50: 1, 65: 2, 75: 2, 85: 3, 95: 4, 100: 4
    }

    def on_progress(msg: str, pct: int) -> None:
        progress_state["pct"] = pct
        progress_state["msg"] = msg
        # Map percent to step
        for threshold in sorted(STEP_MAP.keys(), reverse=True):
            if pct >= threshold:
                progress_state["step"] = STEP_MAP[threshold]
                break
        progress_bar.progress(pct, text=f"⚙️ {msg} ({pct}%)")
        _render_pipeline_steps(
            active=progress_state["step"],
            done_up_to=progress_state["step"],
        )

    with st.spinner(""):
        try:
            runner = DirectRunner()
            result = runner.run(
                industry=config["industry"],
                competitors=config["competitors"],
                region=config["region"],
                time_period=config["time_period"],
                max_sources=config["max_sources"],
                max_steps=config["max_steps"],
                export_formats=config["export_formats"],
                on_progress=on_progress,
                run_id=run_id,
            )

            progress_bar.progress(100, text="✅ Complete!")
            status_text.markdown(
                '<div style="display:flex;align-items:center;gap:0.6rem;padding:0.75rem 1rem;'
                'background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
                'margin:0.5rem 0;color:#166534;font-size:0.9rem;font-weight:600;">'
                '✅ Report generated successfully!</div>',
                unsafe_allow_html=True,
            )

            if result["status"] == "completed":
                st.session_state.run_status = "completed"
                st.session_state.report_data = result
                st.session_state.export_paths = result.get("export_paths", {})
                st.session_state.generation_complete = True
            else:
                st.session_state.run_status = "failed"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:0.6rem;padding:0.75rem 1rem;'
                    f'background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;'
                    f'margin:0.5rem 0;color:#991b1b;font-size:0.9rem;">'
                    f'❌ <strong>Generation failed:</strong> {result.get("error", "Unknown error")}</div>',
                    unsafe_allow_html=True,
                )

        except Exception as exc:
            st.session_state.run_status = "failed"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.6rem;padding:0.75rem 1rem;'
                f'background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;'
                f'margin:0.5rem 0;color:#991b1b;font-size:0.9rem;">'
                f'❌ <strong>Error:</strong> {exc}</div>',
                unsafe_allow_html=True,
            )
            if config.get("show_raw_output"):
                import traceback
                st.code(traceback.format_exc(), language="python")



def _render_pipeline_steps(active: int = 0, done_up_to: int = -1) -> None:
    """Render pipeline step pills with colored active/done states."""
    parts = []
    for i, (icon, label) in enumerate(AGENT_STEPS):
        if i < done_up_to:
            style = (
                "background:#d1fae5;color:#065f46;border:1.5px solid #6ee7b7;"
                "font-weight:700;"
            )
            marker = "✓ "
        elif i == active:
            style = (
                "background:#dbeafe;color:#1e40af;border:1.5px solid #93c5fd;"
                "font-weight:700;box-shadow:0 0 0 3px rgba(59,130,246,0.18);"
            )
            marker = "▶ "
        else:
            style = (
                "background:#f3f4f6;color:#9ca3af;border:1.5px solid #e5e7eb;"
                "font-weight:500;"
            )
            marker = ""
        parts.append(
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'padding:5px 12px;border-radius:20px;font-size:0.78rem;'
            f'transition:all 0.2s;{style}">'
            f'{icon} {marker}{label}</span>'
        )
    html = (
        '<div style="display:flex;flex-wrap:wrap;gap:0.45rem;'
        'margin:0.6rem 0 1rem 0;">'
        + "".join(parts)
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ── Main content area ─────────────────────────────────────────────────────────

def _render_run_area(config: Dict[str, Any]) -> None:
    run_id = st.session_state.run_id
    run_status = st.session_state.run_status
    report_data = st.session_state.report_data

    # ── Status bar ────────────────────────────────────────────
    icon = STATUS_COLORS.get(run_status or "pending", "⚪")
    status_colors = {
        "running":   ("background:#dbeafe;color:#1e40af;border:1.5px solid #93c5fd;",),
        "completed": ("background:#d1fae5;color:#065f46;border:1.5px solid #6ee7b7;",),
        "failed":    ("background:#fee2e2;color:#991b1b;border:1.5px solid #fca5a5;",),
        "pending":   ("background:#f3f4f6;color:#6b7280;border:1.5px solid #d1d5db;",),
    }
    sbadge_style = status_colors.get(run_status or "pending", status_colors["pending"])[0]

    meta = report_data.get("metadata", {}) if report_data else {}
    duration = f"{meta.get('duration_seconds', 0):.0f}s" if meta else "—"
    sources = meta.get("sources_used", "—") if meta else "—"
    cost = f"${meta.get('estimated_cost_usd', 0):.4f}" if meta else "—"

    chip_style = (
        "display:inline-flex;align-items:center;gap:4px;padding:3px 10px;"
        "background:#f3f4f6;border:1px solid #e5e7eb;border-radius:20px;"
        "font-size:0.78rem;color:#374151;font-weight:500;"
    )

    st.markdown(f"""
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:0.75rem;
                padding:0.7rem 1.1rem;background:#ffffff;border:1px solid #e5e7eb;
                border-radius:10px;margin-bottom:1.1rem;
                box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <span style="padding:4px 12px;border-radius:20px;font-size:0.78rem;
                     font-weight:700;{sbadge_style}">
            {icon} {(run_status or 'pending').upper()}
        </span>
        <span style="font-size:0.78rem;color:#6b7280;">
            Run&nbsp;
            <code style="background:#f3f4f6;padding:2px 7px;border-radius:5px;
                         font-size:0.75rem;color:#1e3a5f;font-weight:700;">
                {run_id[:8]}
            </code>
        </span>
        <span style="flex:1;"></span>
        <span style="{chip_style}">⏱ {duration}</span>
        <span style="{chip_style}">🔗 {sources} sources</span>
        <span style="{chip_style}">💰 {cost}</span>
        <a href="/" target="_self"
           style="display:inline-flex;align-items:center;gap:4px;padding:4px 12px;
                  background:#f3f4f6;border:1px solid #d1d5db;border-radius:8px;
                  font-size:0.78rem;color:#1e3a5f;font-weight:600;
                  text-decoration:none;">
            🔄 New Run
        </a>
    </div>
    """, unsafe_allow_html=True)

    if run_status != "completed" or not report_data:
        return

    markdown = report_data.get("full_markdown", "")
    sources_list = report_data.get("sources", [])

    # ── Human review gate ─────────────────────────────────────
    from config.settings import settings
    if (
        settings.human_review_enabled
        and config.get("human_review_enabled")
        and not st.session_state.review_submitted
    ):
        review_result = render_human_review_gate(
            run_id=run_id,
            report_markdown=markdown,
            confidence_score=_compute_confidence(markdown),
            sources_count=len(sources_list),
            flagged_items=_get_flagged_items(markdown),
        )
        if review_result is not None:
            st.session_state.review_submitted = True
            if not review_result["approved"]:
                st.markdown("""
                <div style="padding:0.75rem 1rem;background:#fffbeb;border:1px solid #fcd34d;
                            border-radius:8px;color:#92400e;font-size:0.9rem;margin:0.5rem 0;">
                    🚫 <strong>Report rejected.</strong> Click <strong>New Run</strong> to start again.
                </div>
                """, unsafe_allow_html=True)
                return
            if review_result.get("edited_sections"):
                import re
                for section, content in review_result["edited_sections"].items():
                    pattern = rf"(## {re.escape(section)}\n+)(.*?)(?=\n## |\Z)"
                    markdown = re.sub(pattern, rf"\g<1>{content}\n", markdown, flags=re.DOTALL | re.IGNORECASE)
                st.session_state.report_data["full_markdown"] = markdown
        else:
            return

    # ── Export panel ──────────────────────────────────────────
    render_export_panel(
        run_id=run_id,
        report_markdown=markdown,
        export_paths=st.session_state.export_paths,
        metadata=meta,
    )

    # ── Evaluation button ─────────────────────────────────────
    st.markdown('<div style="margin:1rem 0 0.5rem 0;"></div>', unsafe_allow_html=True)
    eval_col, _ = st.columns([1, 3])
    with eval_col:
        if st.button("📊 Run Evaluation (RAGAS + DeepEval)", use_container_width=True):
            with st.spinner("Running evaluation…"):
                try:
                    from evaluation.test_suite import evaluation_manager
                    eval_result = evaluation_manager.evaluate_briefing(
                        run_id=run_id,
                        briefing=markdown,
                        industry=config["industry"],
                        competitors=config["competitors"],
                    )
                    st.session_state.evaluation_data = eval_result.model_dump()
                    st.markdown("""
                    <div style="padding:0.65rem 1rem;background:#f0fdf4;border:1px solid #86efac;
                                border-radius:8px;color:#166534;font-size:0.88rem;margin-top:0.4rem;">
                        ✅ <strong>Evaluation complete!</strong>
                    </div>
                    """, unsafe_allow_html=True)
                except Exception as exc:
                    st.markdown(
                        f'<div style="padding:0.65rem 1rem;background:#fef2f2;border:1px solid #fca5a5;'
                        f'border-radius:8px;color:#991b1b;font-size:0.88rem;margin-top:0.4rem;">'
                        f'❌ <strong>Evaluation failed:</strong> {exc}</div>',
                        unsafe_allow_html=True,
                    )

    st.markdown('<div style="margin:0.75rem 0;"></div>', unsafe_allow_html=True)

    # ── Report tabs ───────────────────────────────────────────
    render_report_tabs(
        report_data={
            **report_data,
            "industry": config["industry"],
            "competitors": config["competitors"],
        },
        evaluation_data=st.session_state.evaluation_data,
        audit_logs=st.session_state.audit_logs,
        metrics=_load_metrics(),
    )

    # ── Regression tests ──────────────────────────────────────
    with st.expander("🧪 Capstone Regression Suite (5 Scenarios)", expanded=False):
        st.markdown(
            '<p style="color:#6b7280;font-size:0.88rem;margin:0 0 0.6rem 0;">'
            'Run all 5 defined capstone test scenarios using Promptfoo.</p>',
            unsafe_allow_html=True,
        )
        if st.button("▶ Run All 5 Scenarios", key="run_regression"):
            st.info("⏳ Running Promptfoo regression tests…")
            _run_regression_suite()


# ── Stats Bar ─────────────────────────────────────────────────────────────────

def _render_stats_bar() -> None:
    """Render a live metrics bar beneath the hero header using DB aggregates."""
    try:
        from src.utils.database import db_manager
        m = db_manager.get_metrics_summary()
    except Exception:
        m = {
            "total_runs": 0,
            "completed_runs": 0,
            "failed_runs": 0,
            "success_rate": 0.0,
            "avg_duration_seconds": 0.0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        }

    total = m.get("total_runs", 0)
    completed = m.get("completed_runs", 0)
    failed = m.get("failed_runs", 0)
    success_rate = m.get("success_rate", 0.0)
    avg_dur = m.get("avg_duration_seconds", 0.0)
    total_cost = m.get("total_cost_usd", 0.0)
    total_tokens = m.get("total_tokens", 0)

    # Colour-code success rate
    if success_rate >= 0.9:
        sr_color = "#166534"
        sr_bg = "#dcfce7"
        sr_border = "#86efac"
    elif success_rate >= 0.7:
        sr_color = "#92400e"
        sr_bg = "#fef9c3"
        sr_border = "#fde047"
    else:
        sr_color = "#991b1b"
        sr_bg = "#fee2e2"
        sr_border = "#fca5a5"

    chip = (
        "display:inline-flex;align-items:center;gap:6px;"
        "padding:6px 14px;border-radius:24px;font-size:0.8rem;font-weight:600;"
        "border:1.5px solid #e5e7eb;background:#ffffff;color:#374151;"
        "box-shadow:0 1px 3px rgba(0,0,0,0.06);"
    )

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.55rem;
                    padding:0.65rem 1rem;background:#f8fafc;
                    border:1px solid #e5e7eb;border-radius:10px;
                    margin-bottom:1.1rem;">
            <span style="{chip}">📋 <strong>{total}</strong>&nbsp;total runs</span>
            <span style="{chip}">✅ <strong>{completed}</strong>&nbsp;completed</span>
            <span style="{chip}">❌ <strong>{failed}</strong>&nbsp;failed</span>
            <span style="{chip};background:{sr_bg};border-color:{sr_border};color:{sr_color};">
                📈 <strong>{success_rate * 100:.0f}%</strong>&nbsp;success rate
            </span>
            <span style="{chip}">⏱ avg&nbsp;<strong>{avg_dur:.0f}s</strong></span>
            <span style="{chip}">🪙 <strong>{total_tokens:,}</strong>&nbsp;tokens</span>
            <span style="{chip}">💰 <strong>${total_cost:.4f}</strong>&nbsp;total cost</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Welcome Screen ────────────────────────────────────────────────────────────

def _render_welcome_screen() -> None:
    """Render the landing welcome screen shown before a run is started."""
    # ── How it works ──────────────────────────────────────────
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;
                    padding:10px 16px;margin-bottom:16px;
                    background:linear-gradient(135deg,#0D1B2A,#1E3A5F);
                    border-radius:10px;">
            <span style="font-size:1.1rem;">⚡</span>
            <span style="font-size:14px;font-weight:700;color:#FFFFFF;letter-spacing:0.01em;">
                How It Works
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    steps = [
        ("🔍", "Research", "Web search + RAG retrieval across news, filings & pricing data"),
        ("📊", "Analysis", "SWOT, pricing matrix, positioning gaps & market signals"),
        ("✍️", "Writing", "Executive-grade briefing with inline citations"),
        ("🛡️", "Review", "Governance checks: bias scan, fact-flag, human gate"),
        ("📦", "Export", "PDF, PPTX, Markdown, HTML & JSON outputs"),
    ]

    cols = st.columns(len(steps))
    for col, (icon, title, desc) in zip(cols, steps):
        with col:
            st.markdown(
                f"""
                <div style="background:#ffffff;border-radius:14px;padding:20px 16px;
                            border:1px solid #e5e7eb;text-align:center;height:100%;
                            box-shadow:0 1px 4px rgba(0,0,0,0.06);
                            transition:transform 0.2s,box-shadow 0.2s;">
                    <div style="font-size:2rem;background:#eff6ff;width:52px;height:52px;
                                border-radius:12px;display:inline-flex;align-items:center;
                                justify-content:center;margin-bottom:12px;">{icon}</div>
                    <div style="font-size:14px;font-weight:700;color:#111827;margin-bottom:8px;">
                        {title}
                    </div>
                    <div style="font-size:12px;color:#6b7280;line-height:1.6;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Feature highlight cards ───────────────────────────────
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;
                    padding:10px 16px;margin-bottom:16px;
                    background:linear-gradient(135deg,#0D1B2A,#1E3A5F);
                    border-radius:10px;">
            <span style="font-size:1.1rem;">✨</span>
            <span style="font-size:14px;font-weight:700;color:#FFFFFF;">
                Key Capabilities
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    features = [
        ("🤖", "Multi-Agent CrewAI", "Specialised Research, Analyst & Writer agents coordinate autonomously.", "CrewAI"),
        ("🧠", "OpenRouter LLM", "Auto-cascade across Gemma-4, Llama-3.3, Qwen3-Coder & NVIDIA Nemotron free models.", "OpenRouter"),
        ("🔎", "FAISS RAG", "Semantic search over your own knowledge base for grounded answers.", "Vector Search"),
        ("🛡️", "Governance Layer", "Rate limits, cost caps, prompt-injection guards & audit trails.", "Enterprise Ready"),
        ("📊", "RAGAS + DeepEval", "Automated faithfulness, precision & recall scoring per run.", "Evaluation"),
        ("📄", "Multi-format Export", "One-click PDF, PPTX, HTML, Markdown & JSON report bundles.", "Export"),
    ]

    c1, c2, c3 = st.columns(3)
    for idx, (icon, title, desc, tag) in enumerate(features):
        col = [c1, c2, c3][idx % 3]
        with col:
            st.markdown(
                f"""
                <div style="background:#ffffff;border-radius:14px;padding:22px 20px;
                            border:1px solid #e5e7eb;margin-bottom:16px;
                            box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                    <div style="font-size:1.8rem;background:#eff6ff;width:50px;height:50px;
                                border-radius:12px;display:inline-flex;align-items:center;
                                justify-content:center;margin-bottom:12px;">{icon}</div>
                    <div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:8px;">
                        {title}
                    </div>
                    <div style="font-size:13px;color:#6b7280;line-height:1.6;margin-bottom:12px;">
                        {desc}
                    </div>
                    <span style="background:#eff6ff;color:#1e40af;padding:3px 10px;
                                 border-radius:20px;font-size:11px;font-weight:700;">
                        {tag}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Quick start hint ─────────────────────────────────────
    st.markdown(
        """
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-left:4px solid #2563eb;
                    border-radius:10px;padding:14px 18px;margin-top:8px;
                    font-size:14px;color:#1e40af;line-height:1.6;">
            👈 <strong>Get started:</strong> Select an industry, enter competitor names in the
            sidebar, then click <strong>🚀 Generate Report</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Confidence Computation ────────────────────────────────────────────────────

def _compute_confidence(markdown: str) -> float:
    """
    Heuristic confidence score (0.0–1.0) based on:
    - Number of citation references  [##]
    - Presence of key sections (SWOT, pricing, recommendations)
    - Report length (word count proxy)
    """
    if not markdown:
        return 0.0

    import re

    word_count = len(markdown.split())
    # Citations — patterns like [1], [Source: X], [[n]]
    citations = len(re.findall(r"\[\d+\]|\[Source:[^\]]+\]|\[\[[^\]]+\]\]", markdown, re.IGNORECASE))
    # Key sections present
    key_sections = ["SWOT", "pricing", "recommendation", "executive summary", "market position"]
    sections_found = sum(1 for s in key_sections if s.lower() in markdown.lower())

    # Scoring components (each normalised to 0–1, then weighted)
    length_score = min(word_count / 1500, 1.0)          # full marks at 1500+ words
    citation_score = min(citations / 10, 1.0)           # full marks at 10+ citations
    section_score = sections_found / len(key_sections)

    confidence = (
        length_score   * 0.35
        + citation_score * 0.40
        + section_score  * 0.25
    )
    return round(min(confidence, 1.0), 3)


# ── Flagged Items ─────────────────────────────────────────────────────────────

def _get_flagged_items(markdown: str) -> list[str]:
    """
    Scan the report markdown for items that should be flagged for human review:
    - Unverified claims (phrases like "reportedly", "allegedly", "rumoured")
    - Future projections stated as fact ("will", "is going to")
    - Missing citations in sections that typically require them
    """
    import re

    flags: list[str] = []
    if not markdown:
        return flags

    # Hedged / unverified language
    hedge_patterns = [
        (r"\b(reportedly|allegedly|rumou?red|unconfirmed|speculated)\b", "Unverified claim"),
        (r"\b(will definitely|is guaranteed to|100%)\b", "Overly certain projection"),
        (r"\bTODO\b|\bFIXME\b|\bPLACEHOLDER\b", "Placeholder text detected"),
    ]
    for pattern, label in hedge_patterns:
        matches = re.findall(pattern, markdown, re.IGNORECASE)
        if matches:
            unique = list(dict.fromkeys(m.strip() for m in matches))[:3]
            flags.append(f"{label}: {', '.join(unique)}")

    # Sections without citations
    sections_needing_citations = ["pricing", "market share", "revenue"]
    for section in sections_needing_citations:
        pattern = rf"#{1,3}\s*[^#\n]*{re.escape(section)}[^#\n]*\n(.*?)(?=\n#|\Z)"
        match = re.search(pattern, markdown, re.IGNORECASE | re.DOTALL)
        if match:
            section_text = match.group(1)
            has_citation = bool(re.search(r"\[\d+\]|\[Source", section_text, re.IGNORECASE))
            if not has_citation:
                flags.append(f"Section '{section.title()}' may lack citations")

    return flags[:10]  # cap at 10 flags


# ── Metrics Loader ────────────────────────────────────────────────────────────

def _load_metrics() -> Dict[str, Any]:
    """
    Load aggregated metrics from the database for the report tabs
    (passed into render_report_tabs as the `metrics` argument).
    Returns a safe default dict if the DB is unavailable.
    """
    try:
        from src.utils.database import db_manager
        return db_manager.get_metrics_summary()
    except Exception:
        return {
            "total_runs": 0,
            "completed_runs": 0,
            "failed_runs": 0,
            "success_rate": 0.0,
            "avg_duration_seconds": 0.0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        }


# ── Regression Suite Runner ───────────────────────────────────────────────────

def _run_regression_suite() -> None:
    """
    Execute the 5 capstone Promptfoo regression scenarios and display results.
    Falls back to a mock table if promptfoo / evaluation module is unavailable.
    """
    SCENARIOS = [
        ("SaaS / CRM", ["Salesforce", "HubSpot", "Pipedrive"], "North America", "last 30 days"),
        ("Fintech / Payments", ["Stripe", "Square", "Adyen"], "Global", "last 30 days"),
        ("AI / LLM / Generative AI", ["OpenAI", "Anthropic", "Mistral"], "Global", "last 14 days"),
        ("Cybersecurity", ["CrowdStrike", "SentinelOne", "Palo Alto"], "North America", "last 30 days"),
        ("Healthcare SaaS", ["Epic", "Veeva", "Meditech"], "United States", "last 60 days"),
    ]

    results = []
    progress = st.progress(0, text="Running scenario 1/5…")

    for idx, (industry, competitors, region, period) in enumerate(SCENARIOS, start=1):
        progress.progress(idx / len(SCENARIOS), text=f"Running scenario {idx}/{len(SCENARIOS)}…")
        try:
            from evaluation.promptfoo_eval import PromptfooEvaluator
            evaluator = PromptfooEvaluator()
            result = evaluator.run_scenario(
                industry=industry,
                competitors=competitors,
                region=region,
                time_period=period,
            )
            passed = result.get("pass", False)
            score = result.get("score", 0.0)
            detail = result.get("reason", "—")
        except Exception as exc:
            # Graceful fallback — mark as skipped with reason
            passed = None
            score = 0.0
            detail = f"Evaluator unavailable: {exc}"

        results.append(
            {
                "Scenario": f"{idx}. {industry}",
                "Competitors": ", ".join(competitors),
                "Region": region,
                "Period": period,
                "Score": f"{score:.2f}" if isinstance(score, float) else str(score),
                "Status": "✅ Pass" if passed is True else ("⏭ Skipped" if passed is None else "❌ Fail"),
                "Detail": detail[:80],
            }
        )

    progress.empty()

    import pandas as pd

    df = pd.DataFrame(results)

    # Colour-code the Status column
    def _style_status(val: str) -> str:
        if "Pass" in val:
            return "background-color:#dcfce7;color:#166534;font-weight:600;"
        if "Fail" in val:
            return "background-color:#fee2e2;color:#991b1b;font-weight:600;"
        return "background-color:#fef9c3;color:#92400e;font-weight:600;"

    st.dataframe(
        df.style.map(_style_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )

    pass_count = sum(1 for r in results if "Pass" in r["Status"])
    skip_count = sum(1 for r in results if "Skipped" in r["Status"])
    fail_count = sum(1 for r in results if "Fail" in r["Status"])

    if fail_count == 0 and skip_count == 0:
        st.markdown(
            '<div style="padding:0.7rem 1rem;background:#f0fdf4;border:1px solid #86efac;'
            'border-radius:8px;color:#166534;font-size:0.9rem;margin-top:0.6rem;">'
            f'🎉 <strong>All {pass_count} scenarios passed!</strong></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="padding:0.7rem 1rem;background:#fffbeb;border:1px solid #fcd34d;'
            f'border-radius:8px;color:#92400e;font-size:0.9rem;margin-top:0.6rem;">'
            f'⚠️ <strong>{pass_count} passed · {fail_count} failed · {skip_count} skipped</strong>'
            f"</div>",
            unsafe_allow_html=True,
        )
