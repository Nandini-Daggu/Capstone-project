"""
frontend/components/human_review.py
=====================================
Polished human review gate component.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import streamlit as st


def render_human_review_gate(
    run_id: str,
    report_markdown: str,
    confidence_score: float = 0.0,
    sources_count: int = 0,
    flagged_items: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Render the human review gate.
    Returns None until decision is submitted, then returns dict with decision.
    """
    flagged_items = flagged_items or []

    st.markdown("---")

    # ── Dark navy review header ───────────────────────────────
    st.markdown("""
    <div class="review-header" style="
        background: linear-gradient(135deg, #0d1b2a 0%, #1e3a5f 100%);
        border-radius: 14px;
        padding: 1.4rem 1.8rem;
        display: flex;
        align-items: center;
        gap: 1.2rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 16px rgba(13,27,42,0.18);
    ">
        <div style="
            font-size: 2.2rem;
            background: rgba(255,255,255,0.10);
            border-radius: 12px;
            width: 52px; height: 52px;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        ">👤</div>
        <div>
            <div style="
                font-size: 1.15rem;
                font-weight: 700;
                color: #ffffff;
                letter-spacing: 0.01em;
            ">Human Review Gate</div>
            <div style="
                font-size: 0.85rem;
                color: #94B8D8;
                margin-top: 0.2rem;
            ">Review the AI-generated briefing before it is finalised</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 4 key-metric columns ──────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    # Confidence score with colour hint
    conf_pct    = f"{confidence_score:.0%}"
    conf_delta  = "High" if confidence_score >= 0.7 else ("Medium" if confidence_score >= 0.4 else "Low")
    c1.metric("Confidence Score", conf_pct, delta=conf_delta)
    c2.metric("Sources Used",     sources_count)
    c3.metric("Flagged Items",    len(flagged_items))

    if confidence_score >= 0.7:
        c4.metric("AI Recommendation", "✅ Approve")
    elif confidence_score >= 0.4:
        c4.metric("AI Recommendation", "⚠️ Review")
    else:
        c4.metric("AI Recommendation", "❌ Reject")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Flagged items — amber left-border cards ───────────────
    if flagged_items:
        with st.expander(
            f"⚠️ {len(flagged_items)} potentially uncited claim(s) flagged",
            expanded=True,
        ):
            for i, item in enumerate(flagged_items[:8], 1):
                st.markdown(
                    f'<div style="'
                    f'background:#fffbeb;'
                    f'border-left:4px solid #f59e0b;'
                    f'padding:8px 14px;'
                    f'border-radius:0 8px 8px 0;'
                    f'margin-bottom:6px;'
                    f'font-size:0.82rem;'
                    f'color:#92400e;'
                    f'line-height:1.5;'
                    f'">'
                    f'<strong>#{i}</strong> {item}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Executive summary preview — blue left-border blockquote ──
    exec_match = re.search(
        r"## Executive Summary\n+(.*?)(?=\n## |\Z)",
        report_markdown,
        re.DOTALL,
    )
    if exec_match:
        exec_text = exec_match.group(1).strip()[:700]
        trailing  = "…" if len(exec_match.group(1).strip()) > 700 else ""
        st.markdown(
            f'<div style="'
            f'background:#f0f5ff;'
            f'border-left:4px solid #1e3a5f;'
            f'border-radius:0 10px 10px 0;'
            f'padding:1rem 1.4rem;'
            f'margin:0.6rem 0 0.8rem 0;'
            f'">'
            f'<div style="'
            f'font-size:0.75rem;'
            f'color:#1e3a5f;'
            f'text-transform:uppercase;'
            f'letter-spacing:0.08em;'
            f'font-weight:700;'
            f'margin-bottom:0.5rem;'
            f'">📄 Executive Summary Preview</div>'
            f'<div style="'
            f'font-size:0.87rem;'
            f'color:#374151;'
            f'line-height:1.7;'
            f'">{exec_text}{trailing}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Full draft — collapsed expander ──────────────────────
    with st.expander("📄 View Full Draft Report", expanded=False):
        st.markdown(
            report_markdown[:10_000] + ("…" if len(report_markdown) > 10_000 else ""),
            unsafe_allow_html=False,
        )

    st.markdown("---")

    # ── Decision radio — horizontal, 3 options ────────────────
    st.markdown(
        '<div style="font-weight:600;color:#0d1b2a;font-size:0.95rem;'
        'margin-bottom:0.5rem;">✅ Your Decision</div>',
        unsafe_allow_html=True,
    )

    decision = st.radio(
        "Decision",
        options=["✅ Approve", "✏️ Approve with Edits", "❌ Reject"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"review_decision_{run_id}",
    )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Feedback textarea ─────────────────────────────────────
    feedback = st.text_area(
        "Feedback / Comments _(optional for approval, required for rejection)_",
        placeholder="Add your review comments here…",
        height=90,
        key=f"review_feedback_{run_id}",
    )

    # ── Edit sections — only when "Approve with Edits" chosen ─
    edited_sections: Dict[str, str] = {}

    if "Edits" in decision:
        st.markdown(
            '<div style="font-weight:600;color:#0d1b2a;font-size:0.9rem;'
            'margin:0.8rem 0 0.4rem 0;">✏️ Edit Sections</div>',
            unsafe_allow_html=True,
        )
        sections_to_edit = st.multiselect(
            "Select sections to edit",
            options=[
                "Executive Summary",
                "Competitor Pricing Analysis",
                "Product & Feature Updates",
                "Market Signals",
                "Strategic Recommendations",
            ],
            default=[],
            key=f"edit_sections_{run_id}",
        )
        for section in sections_to_edit:
            pattern = rf"## {re.escape(section)}\n+(.*?)(?=\n## |\Z)"
            match   = re.search(pattern, report_markdown, re.DOTALL)
            current = match.group(1).strip() if match else ""
            edited  = st.text_area(
                f"📝 Edit: {section}",
                value=current,
                height=180,
                key=f"edit_{section.replace(' ', '_')}_{run_id}",
            )
            if edited != current:
                edited_sections[section] = edited

    # ── Submit button + contextual info ──────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    btn_col, info_col = st.columns([1, 2])

    with btn_col:
        submitted = st.button(
            "Submit Review →",
            type="primary",
            use_container_width=True,
            key=f"review_submit_{run_id}",
        )

    with info_col:
        if "Reject" in decision:
            st.markdown(
                '<div class="warn-box"><div class="wb-text">'
                '❌ Rejection requires feedback explaining the reason.</div></div>',
                unsafe_allow_html=True,
            )
        elif confidence_score >= 0.7:
            st.markdown(
                '<div class="success-box" style="padding:0.7rem 1rem;">'
                '✅ High confidence — report looks good to approve.</div>',
                unsafe_allow_html=True,
            )

    # ── Post-submit confirmation banner ──────────────────────
    if submitted:
        # Validate: rejection must have feedback
        if "Reject" in decision and not feedback.strip():
            st.error("Please provide feedback explaining the rejection.")
            return None

        approved = "Reject" not in decision
        action   = "APPROVED" if approved else "REJECTED"
        color    = "#15803d" if approved else "#dc2626"
        bg       = "#dcfce7" if approved else "#fee2e2"
        icon     = "✅" if approved else "❌"

        st.markdown(
            f'<div style="'
            f'padding:1rem 1.4rem;'
            f'background:{bg};'
            f'border-radius:10px;'
            f'text-align:center;'
            f'font-weight:700;'
            f'font-size:1rem;'
            f'color:{color};'
            f'margin-top:0.8rem;'
            f'border:1.5px solid {color}30;'
            f'">'
            f'{icon} Review submitted — {action}'
            f'</div>',
            unsafe_allow_html=True,
        )

        return {
            "approved":        approved,
            "feedback":        feedback,
            "edited_sections": edited_sections,
            "reviewer_id":     st.session_state.get("reviewer_id", "streamlit_user"),
        }

    return None
