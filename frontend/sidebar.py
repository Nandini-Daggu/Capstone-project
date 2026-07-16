"""
frontend/sidebar.py
====================
Polished sidebar configuration panel for the Competitive Intelligence Dashboard.
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from .styles import INDUSTRIES, REGIONS, TIME_PERIODS, EXPORT_FORMATS


def render_sidebar() -> Dict[str, Any]:
    """
    Render the sidebar and return config dict with all user selections.
    """
    # ── Force sidebar wider ───────────────────────────────────
    st.markdown(
        """
        <style>
        section[data-testid='stSidebar'] {
            min-width: 340px !important;
            max-width: 340px !important;
            width: 340px !important;
        }
        section[data-testid='stSidebar'] > div:first-child {
            min-width: 340px !important;
            width: 340px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:

        # ── Logo block ────────────────────────────────────────
        st.markdown(
            """
            <div style="
                text-align: center;
                padding: 18px 0 14px 0;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                margin-bottom: 6px;
            ">
                <div style="font-size: 2.2rem; line-height: 1.1;">🔍</div>
                <div style="
                    font-size: 1.05rem;
                    font-weight: 700;
                    color: #FFFFFF;
                    letter-spacing: 0.02em;
                    margin-top: 6px;
                ">CI Briefing Crew</div>
                <div style="
                    font-size: 0.75rem;
                    color: #94B8D8;
                    margin-top: 3px;
                    letter-spacing: 0.01em;
                ">Powered by CrewAI + OpenRouter</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Industry ─────────────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:16px;margin-bottom:4px;'
            '">🏭 &nbsp;Industry</div>',
            unsafe_allow_html=True,
        )
        industry_choice = st.selectbox(
            "Industry",
            options=INDUSTRIES,
            index=0,
            label_visibility="collapsed",
            key="industry_select",
        )
        if industry_choice == "Custom...":
            industry = st.text_input(
                "Custom industry",
                placeholder="e.g.  Logistics SaaS",
                label_visibility="collapsed",
                key="industry_custom_input",
            )
        else:
            industry = industry_choice

        # ── Competitors ──────────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:20px;padding-top:16px;'
            'border-top:1px solid rgba(255,255,255,0.08);'
            'margin-bottom:4px;'
            '">🏢 &nbsp;Competitors</div>',
            unsafe_allow_html=True,
        )
        # Inject CSS to style the textarea placeholder lighter and ensure scroll/full-width
        st.markdown(
            """
            <style>
            textarea[aria-label="competitors_area"],
            div[data-testid="stTextArea"] textarea {
                overflow-y: auto !important;
                resize: vertical !important;
                color: #FFFFFF !important;
            }
            div[data-testid="stTextArea"] textarea::placeholder {
                color: rgba(148, 184, 216, 0.45) !important;
                font-style: italic;
            }
            div[data-testid="stTextArea"] {
                width: 100% !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        competitors_text = st.text_area(
            "Competitors",
            value="Salesforce\nHubSpot\nPipedrive",
            height=160,
            label_visibility="collapsed",
            help="One competitor per line — max 5.",
            placeholder="e.g.\nSalesforce\nHubSpot\nPipedrive",
            key="competitors_input",
        )
        competitors = [c.strip() for c in competitors_text.strip().splitlines() if c.strip()][:5]

        # Chip badges for each entered competitor
        if competitors:
            chips_html = (
                '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">'
                + "".join(
                    f'<span style="'
                    f'background:rgba(138,184,232,0.15);'
                    f'border:1px solid rgba(138,184,232,0.28);'
                    f'border-radius:20px;'
                    f'padding:3px 10px;'
                    f'font-size:0.68rem;'
                    f'font-weight:600;'
                    f'color:#8ab8e8;'
                    f'display:inline-block;'
                    f'white-space:nowrap;'
                    f'">{c}</span>'
                    for c in competitors
                )
                + "</div>"
            )
            st.markdown(chips_html, unsafe_allow_html=True)
        else:
            st.markdown(
                '<span style="font-size:0.75rem;color:#e57373;margin-top:4px;display:block;">'
                "⚠ Enter at least one competitor</span>",
                unsafe_allow_html=True,
            )

        # ── Region ───────────────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:20px;padding-top:16px;'
            'border-top:1px solid rgba(255,255,255,0.08);'
            'margin-bottom:4px;'
            '">🌍 &nbsp;Region</div>',
            unsafe_allow_html=True,
        )
        region = st.selectbox(
            "Region",
            options=REGIONS,
            index=0,
            label_visibility="collapsed",
            key="region_select",
        )

        # ── Time Period ───────────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:20px;padding-top:16px;'
            'border-top:1px solid rgba(255,255,255,0.08);'
            'margin-bottom:4px;'
            '">📅 &nbsp;Time Period</div>',
            unsafe_allow_html=True,
        )
        time_period = st.selectbox(
            "Time period",
            options=TIME_PERIODS,
            index=0,
            label_visibility="collapsed",
            key="time_select",
        )

        # ── Governance Limits ─────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:20px;padding-top:16px;'
            'border-top:1px solid rgba(255,255,255,0.08);'
            'margin-bottom:4px;'
            '">⚙️ &nbsp;Governance Limits</div>',
            unsafe_allow_html=True,
        )
        col_s, col_st = st.columns(2)
        with col_s:
            max_sources = st.slider(
                "Max Sources",
                min_value=3,
                max_value=15,
                value=10,
                step=1,
                help="Max sources the research agent may consult.",
            )
        with col_st:
            max_steps = st.slider(
                "Max Steps",
                min_value=5,
                max_value=25,
                value=20,
                step=1,
                help="Max tool calls across all agents.",
            )

        # ── Export Formats ────────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:20px;padding-top:16px;'
            'border-top:1px solid rgba(255,255,255,0.08);'
            'margin-bottom:4px;'
            '">📄 &nbsp;Export Formats</div>',
            unsafe_allow_html=True,
        )
        export_formats = st.multiselect(
            "Formats",
            options=EXPORT_FORMATS,
            default=["markdown"],
            label_visibility="collapsed",
            key="export_formats_select",
        )
        if not export_formats:
            export_formats = ["markdown"]

        # ── Options ───────────────────────────────────────────
        st.markdown(
            '<div style="'
            'font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#94B8D8;'
            'margin-top:20px;padding-top:16px;'
            'border-top:1px solid rgba(255,255,255,0.08);'
            'margin-bottom:4px;'
            '">🔧 &nbsp;Options</div>',
            unsafe_allow_html=True,
        )
        human_review = st.toggle(
            "Human Review Gate",
            value=True,
            help="Pause for reviewer approval before finalising.",
        )
        show_raw_output = st.toggle(
            "Show Debug Logs",
            value=False,
            help="Display raw CrewAI agent logs.",
        )

        # ── Advanced ──────────────────────────────────────────
        with st.expander("🧠 Advanced", expanded=False):
            model_choice = st.selectbox(
                "LLM Model",
                options=[
                    # Recommended: auto-cascade handles rate-limits automatically
                    "🔄 Auto-cascade (recommended)",
                    # ── Valid free models (confirmed July 2026) ───────────
                    # Google AI Studio — different quota from Venice models
                    "openrouter/google/gemma-4-31b-it:free",
                    "openrouter/google/gemma-4-26b-a4b-it:free",
                    # Venice / Meta
                    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                    "openrouter/meta-llama/llama-3.2-3b-instruct:free",
                    # Venice / Qwen
                    "openrouter/qwen/qwen3-coder:free",
                    # NVIDIA
                    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
                    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
                    # NousResearch
                    "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
                ],
                index=0,
                help=(
                    "Auto-cascade tries each model in order and switches "
                    "instantly on 429 rate-limit errors. "
                    "All models verified against OpenRouter /models API."
                ),
                key="model_select",
            )
            model_override = None if model_choice.startswith("🔄") else model_choice
            if model_override:
                slug = model_override.split("/")[-1]
                st.markdown(
                    f'<div style="font-size:0.7rem;color:#93C5FD;margin-top:4px;">'
                    f"⚡ Fixed model: <code style='color:#BFDBFE'>{slug}</code>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="font-size:0.7rem;color:#6EE7B7;margin-top:4px;">'
                    "✅ Auto-cascade active — switches models on 429s automatically"
                    "</div>",
                    unsafe_allow_html=True,
                )

        # ── Divider + Generate ────────────────────────────────
        st.markdown(
            "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:1.2rem 0 0.9rem 0;'>",
            unsafe_allow_html=True,
        )

        can_generate = bool(industry and competitors)
        generate_clicked = st.button(
            "🚀  Generate Report",
            type="primary",
            use_container_width=True,
            disabled=not can_generate,
            key="generate_btn",
        )

        if not can_generate:
            st.markdown(
                '<div style="text-align:center;font-size:0.72rem;color:#4d8ab5;margin-top:4px;">'
                "Fill in industry + competitors to enable</div>",
                unsafe_allow_html=True,
            )

        # ── Footer ────────────────────────────────────────────
        st.markdown(
            '<div style="'
            'text-align:center;font-size:0.68rem;color:#4d8ab5;'
            'margin-top:1rem;padding-top:0.6rem;'
            'border-top:1px solid rgba(255,255,255,0.06);'
            '">v1.0 · CrewAI · OpenRouter · FAISS</div>',
            unsafe_allow_html=True,
        )

    return {
        "industry": industry,
        "competitors": competitors,
        "region": region,
        "time_period": time_period,
        "max_sources": max_sources,
        "max_steps": max_steps,
        "export_formats": export_formats,
        "human_review_enabled": human_review,
        "show_raw_output": show_raw_output,
        "model_override": model_override,
        "generate_clicked": generate_clicked,
    }
