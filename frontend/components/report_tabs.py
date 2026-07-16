"""
frontend/components/report_tabs.py
====================================
Rich multi-tab report viewer.
Tabs: Full Report | Summary | Research | Analysis | Sources | Evaluation | Logs | Metrics
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def render_report_tabs(
    report_data: Dict[str, Any],
    evaluation_data: Optional[Dict[str, Any]] = None,
    audit_logs: Optional[List[Dict]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    """Render the full 8-tab report viewer."""
    full_md = report_data.get("full_markdown", "")
    sections = _parse_sections(full_md)

    tabs = st.tabs(
        [
            "📄 Full Report",
            "📋 Summary",
            "🔬 Research",
            "📊 Analysis",
            "🔗 Sources",
            "📈 Evaluation",
            "📜 Logs",
            "📉 Metrics",
        ]
    )

    with tabs[0]:
        _render_full_report_tab(full_md)

    with tabs[1]:
        _render_executive_summary(sections, report_data)

    with tabs[2]:
        _render_research_tab(sections)

    with tabs[3]:
        _render_analysis_tab(sections)

    with tabs[4]:
        _render_sources_tab(report_data.get("sources", []), sections)

    with tabs[5]:
        _render_evaluation_tab(evaluation_data)

    with tabs[6]:
        _render_logs_tab(audit_logs or [])

    with tabs[7]:
        _render_metrics_tab(metrics or {})


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_sections(markdown: str) -> Dict[str, str]:
    """Split markdown by ## headings into a keyed dict."""
    sections: Dict[str, str] = {"full": markdown}
    current_key = "_preamble"
    current_lines: List[str] = []
    for line in markdown.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip().lower()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def _get_section(sections: Dict[str, str], *keywords: str) -> str:
    """Return the first section whose key matches any of the keyword regexes."""
    for key, value in sections.items():
        for kw in keywords:
            if re.search(kw, key, re.IGNORECASE):
                return value
    return ""


def _section_header(icon: str, title: str) -> None:
    """Render a styled section-header bar (uses .section-header CSS class)."""
    st.markdown(
        f'<div class="section-header">'
        f'<span class="sh-icon">{icon}</span>'
        f'<span class="sh-title">{title}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _badge(text: str, color: str = "#2563EB") -> str:
    """Return an inline HTML badge span."""
    return (
        f'<span style="display:inline-block;background:{color};color:#fff;'
        f"padding:2px 10px;border-radius:9999px;font-size:0.78rem;"
        f'font-weight:600;letter-spacing:0.02em;">{text}</span>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 0 — Full Report
# ─────────────────────────────────────────────────────────────────────────────


def _render_full_report_tab(full_md: str) -> None:
    _section_header("📄", "Complete Briefing Report")

    if not full_md:
        st.info("Report content will appear here once generation completes.")
        return

    # ── Stat row ─────────────────────────────────────────────────────────────
    words = len(full_md.split())
    secs = len(re.findall(r"^## ", full_md, re.MULTILINE))
    citations = len(re.findall(r"\[\d+\]", full_md))

    m1, m2, m3 = st.columns(3)
    m1.metric("📝 Word Count", f"{words:,}")
    m2.metric("🗂️ Sections", secs)
    m3.metric("🔖 Citations", citations)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Full markdown in report-card ──────────────────────────────────────────
    st.markdown(
        f'<div class="report-card">{full_md}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 — Summary
# ─────────────────────────────────────────────────────────────────────────────


def _render_executive_summary(sections: Dict, report_data: Dict) -> None:
    _section_header("📋", "Executive Summary & Key Findings")

    industry = report_data.get("industry", "")
    competitors = report_data.get("competitors", [])
    sources_count = len(report_data.get("sources", []))
    meta = report_data.get("metadata", {})
    duration = meta.get("duration_seconds", 0) if meta else 0

    # ── 4-metric top row ─────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏭 Industry", industry or "—")
    c2.metric("🏢 Competitors", len(competitors))
    c3.metric("🔗 Sources", sources_count)
    c4.metric("⏱️ Duration", f"{duration:.0f}s")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Executive summary in report-card ─────────────────────────────────────
    _section_header("📋", "Executive Summary")
    summary = _get_section(sections, r"executive\s+summary")
    if summary:
        st.markdown(
            f'<div class="report-card">{summary}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Executive summary not yet generated.")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Pricing + Products side-by-side ───────────────────────────────────────
    pricing = _get_section(sections, r"pricing")
    products = _get_section(sections, r"product")
    if pricing or products:
        _section_header("💰", "Pricing & Products")
        cp, cpr = st.columns(2, gap="large")
        if pricing:
            with cp:
                st.markdown(
                    '<div class="section-header">'
                    '<span class="sh-icon">💰</span>'
                    '<span class="sh-title">Competitor Pricing</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(pricing)
        if products:
            with cpr:
                st.markdown(
                    '<div class="section-header">'
                    '<span class="sh-icon">🚀</span>'
                    '<span class="sh-title">Product & Feature Updates</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(products)

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = _get_section(sections, r"recommend")
    if recs:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        _section_header("🎯", "Strategic Recommendations")
        st.markdown(recs)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 — Research
# ─────────────────────────────────────────────────────────────────────────────


def _render_research_tab(sections: Dict) -> None:
    _section_header("🔬", "Research Findings")

    market = _get_section(sections, r"market\s+signals?")
    trends = _get_section(sections, r"industry\s+trends?")

    if market:
        _section_header("📡", "Market Signals")
        st.markdown(market)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if trends:
        _section_header("📈", "Industry Trends")
        st.markdown(trends)

    if not market and not trends:
        full = sections.get("full", "")
        if full:
            with st.expander("📄 View Raw Report Content", expanded=True):
                st.markdown(full[:5000] + ("…" if len(full) > 5000 else ""))
        else:
            st.info("Research data will appear here after the report is generated.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3 — Analysis
# ─────────────────────────────────────────────────────────────────────────────


def _render_analysis_tab(sections: Dict) -> None:
    _section_header("📊", "Competitive Analysis")

    swot = _get_section(sections, r"swot")
    risk = _get_section(sections, r"risk")
    opp = _get_section(sections, r"opportunit")

    # ── SWOT full width ───────────────────────────────────────────────────────
    if swot:
        _section_header("🔀", "SWOT Analysis")
        st.markdown(swot)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Risk + Opportunities in two columns ───────────────────────────────────
    if risk or opp:
        cr, co = st.columns(2, gap="large")
        if risk:
            with cr:
                _section_header("⚠️", "Risk Analysis")
                st.markdown(risk)
        if opp:
            with co:
                _section_header("💡", "Opportunities")
                st.markdown(opp)

    if not swot and not risk and not opp:
        st.info("Analysis sections will appear here after generation.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4 — Sources
# ─────────────────────────────────────────────────────────────────────────────


def _render_sources_tab(sources: List, sections: Dict) -> None:
    _section_header("🔗", "Sources & References")

    refs = _get_section(sections, r"references?")

    if not sources and not refs:
        st.info("Source list appears after report generation.")
        return

    if sources:
        # ── Count badge ───────────────────────────────────────────────────────
        st.markdown(
            _badge(f"  {len(sources)} sources collected  ", color="#2563EB"),
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Filter input ──────────────────────────────────────────────────────
        search_q = st.text_input(
            "🔍 Filter sources",
            placeholder="Search title, domain, or URL…",
            label_visibility="collapsed",
            key="sources_filter_input",
        )

        filtered = [
            s
            for s in sources
            if not search_q
            or (
                search_q.lower() in str(s.get("title", "")).lower()
                or search_q.lower() in str(s.get("url", "")).lower()
                or search_q.lower() in str(s.get("source_name", "")).lower()
            )
        ]

        # Cap at 60
        capped = filtered[:60]
        capped_n = len(capped)
        st.caption(
            f"Showing {capped_n} of {len(sources)}"
            + (" (capped at 60)" if len(filtered) > 60 else "")
        )
        st.markdown("")

        for src in capped:
            if isinstance(src, dict):
                sid = src.get("source_id", "?")
                title = src.get("title") or src.get("url", "Unknown source")
                url = src.get("url", "")
                sname = src.get("source_name", "")
                date = src.get("published_date", "")
                snip = src.get("snippet", "")

                meta_parts = []
                if sname:
                    meta_parts.append(sname)
                if date:
                    meta_parts.append(date)
                meta_str = " · ".join(meta_parts)

                with st.expander(f"[{sid}] {title[:75]}", expanded=False):
                    if url:
                        st.markdown(f"**🔗 URL:** [{url[:80]}…]({url})")
                    if meta_str:
                        st.markdown(f"**📰 {meta_str}**")
                    if snip:
                        st.markdown(f"> _{snip[:400]}_")

    if refs:
        st.markdown("---")
        _section_header("📚", "Formatted References")
        st.markdown(refs)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 5 — Evaluation
# ─────────────────────────────────────────────────────────────────────────────


def _render_evaluation_tab(evaluation_data: Optional[Dict]) -> None:
    _section_header("📈", "Evaluation Results (RAGAS + DeepEval)")

    if not evaluation_data:
        st.markdown(
            '<div class="info-box">'
            '<div class="ib-icon">ℹ️</div>'
            '<div class="ib-text">'
            "No evaluation run yet.<br>"
            "Click <strong>📊 Run Evaluation</strong> above to score faithfulness, "
            "citation coverage, and hallucination rate."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    try:
        import pandas as pd
        import plotly.graph_objects as go
    except ImportError:
        st.warning("Install plotly & pandas to see evaluation charts.")
        st.json(evaluation_data)
        return

    overall = evaluation_data.get("overall_score", 0)
    hallucin = evaluation_data.get("hallucination_score", 0)
    passed = evaluation_data.get("passed", False)

    # ── 4-metric top row ─────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏆 Overall Score", f"{overall:.0%}")
    c2.metric("🤝 Faithfulness", f"{evaluation_data.get('faithfulness', 0):.0%}")
    c3.metric("📎 Citation Coverage", f"{evaluation_data.get('citation_coverage', 0):.0%}")
    c4.metric(
        "🧠 Hallucination",
        f"{hallucin:.0%}",
        delta_color="inverse",
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Passed / Failed banner ────────────────────────────────────────────────
    result_text = "✅  PASSED" if passed else "❌  NEEDS REVIEW"
    result_bg = "#dcfce7" if passed else "#fee2e2"
    result_color = "#15803d" if passed else "#dc2626"
    st.markdown(
        f'<div style="text-align:center;padding:0.65rem 1rem;margin:0.6rem 0 1rem 0;'
        f"background:{result_bg};border-radius:10px;font-weight:700;font-size:1.05rem;"
        f'color:{result_color};letter-spacing:0.04em;">{result_text}</div>',
        unsafe_allow_html=True,
    )

    # ── Radar chart (left) + Score table (right) ──────────────────────────────
    radar_metrics: Dict[str, float] = {
        "Faithfulness": evaluation_data.get("faithfulness", 0),
        "Answer Relevancy": evaluation_data.get("answer_relevancy", 0),
        "Context Precision": evaluation_data.get("context_precision", 0),
        "Citation Coverage": evaluation_data.get("citation_coverage", 0),
        "Tool Accuracy": evaluation_data.get("tool_accuracy", 0),
    }
    cats = list(radar_metrics.keys())
    vals = list(radar_metrics.values())

    chart_col, table_col = st.columns([3, 2], gap="large")

    with chart_col:
        _section_header("📡", "Score Radar")
        fig = go.Figure(
            data=go.Scatterpolar(
                r=vals + [vals[0]],
                theta=cats + [cats[0]],
                fill="toself",
                line=dict(color="#1e3a5f", width=2),
                fillcolor="rgba(30,58,95,0.18)",
                name="Score",
            )
        )
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    tickformat=".0%",
                    tickfont=dict(size=10),
                ),
                angularaxis=dict(tickfont=dict(size=11)),
            ),
            showlegend=False,
            margin=dict(l=50, r=50, t=30, b=30),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with table_col:
        _section_header("📋", "Score Breakdown")
        rows = [(k, f"{v:.2f}", "✅" if v >= 0.7 else "⚠️") for k, v in radar_metrics.items()]
        rows.append(
            (
                "Hallucination",
                f"{hallucin:.2f}",
                "✅" if hallucin <= 0.1 else "❌",
            )
        )
        df = pd.DataFrame(rows, columns=["Metric", "Score", "Status"])
        st.dataframe(df, use_container_width=True, hide_index=True, height=260)

    # ── Notes expander ────────────────────────────────────────────────────────
    notes = evaluation_data.get("notes", [])
    if notes:
        with st.expander("📝 Evaluator Notes"):
            for n in notes[:8]:
                st.caption(f"• {n}")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 6 — Logs
# ─────────────────────────────────────────────────────────────────────────────


def _render_logs_tab(audit_logs: List[Dict]) -> None:
    _section_header("📜", "Audit Logs")

    if not audit_logs:
        st.info("Audit logs appear here after a run completes.")
        return

    try:
        import pandas as pd
    except ImportError:
        st.json(audit_logs[:20])
        return

    # ── Filter dropdowns ──────────────────────────────────────────────────────
    col_type, col_agent, col_err = st.columns([1, 1, 1])

    event_types = sorted({r.get("event_type", "") for r in audit_logs} - {""})
    agent_names = sorted({r.get("agent", "") for r in audit_logs} - {""})

    selected_type = col_type.selectbox(
        "Filter by event type",
        ["All"] + event_types,
        key="log_filter_type",
    )
    selected_agent = col_agent.selectbox(
        "Filter by agent",
        ["All"] + agent_names,
        key="log_filter_agent",
    )
    errors_only = col_err.checkbox(
        "Errors only",
        value=False,
        key="log_errors_only",
    )

    filtered = audit_logs
    if selected_type != "All":
        filtered = [r for r in filtered if r.get("event_type") == selected_type]
    if selected_agent != "All":
        filtered = [r for r in filtered if r.get("agent") == selected_agent]
    if errors_only:
        filtered = [r for r in filtered if not r.get("success", True)]

    st.caption(f"Showing {len(filtered)} / {len(audit_logs)} records")

    if filtered:
        safe_cols = [
            "timestamp",
            "event_type",
            "agent",
            "tool",
            "latency_ms",
            "total_tokens",
            "estimated_cost_usd",
            "success",
        ]
        available = [c for c in safe_cols if any(c in r for r in filtered)]
        df_rows = [{col: r.get(col, "") for col in available} for r in filtered]
        df = pd.DataFrame(df_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 7 — Metrics
# ─────────────────────────────────────────────────────────────────────────────


def _render_metrics_tab(metrics: Dict) -> None:
    _section_header("📉", "System Metrics & Performance")

    if not metrics:
        st.info("Metrics load after first run completes.")
        return

    try:
        import plotly.graph_objects as go
    except ImportError:
        st.json(metrics)
        return

    # ── 4-metric top row ─────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔁 Total Runs", metrics.get("total_runs", 0))
    c2.metric("✅ Success Rate", f"{metrics.get('success_rate', 0):.0%}")
    c3.metric("⏱️ Avg Duration", f"{metrics.get('avg_duration_seconds', 0):.0f}s")
    c4.metric("💵 Total Cost", f"${metrics.get('total_cost_usd', 0):.4f}")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Cache performance + progress bar ─────────────────────────────────────
    cache = metrics.get("cache_stats", {})
    if cache:
        _section_header("🗄️", "Cache Performance")
        hit_rate = float(cache.get("hit_rate", 0))
        st.progress(hit_rate, text=f"Overall cache hit rate: **{hit_rate:.0%}**")
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("LLM Hits", cache.get("llm_hits", 0))
        cc2.metric("Search Hits", cache.get("search_hits", 0))
        cc3.metric("Embedding Hits", cache.get("embedding_hits", 0))
        cc4.metric("Hot Tier Size", cache.get("hot_tier_size", 0))

    # ── Run outcomes bar chart ────────────────────────────────────────────────
    total = metrics.get("total_runs", 0)
    success = metrics.get("completed_runs", 0)
    failed = metrics.get("failed_runs", 0)

    if total > 0:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        _section_header("📊", "Run Outcomes")
        fig = go.Figure(
            data=[
                go.Bar(
                    name="Completed",
                    x=["Runs"],
                    y=[success],
                    marker_color="#22c55e",
                    text=[success],
                    textposition="auto",
                ),
                go.Bar(
                    name="Failed",
                    x=["Runs"],
                    y=[failed],
                    marker_color="#ef4444",
                    text=[failed],
                    textposition="auto",
                ),
            ]
        )
        fig.update_layout(
            barmode="stack",
            height=220,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(showgrid=False, zeroline=False),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
