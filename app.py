"""
app.py
=======
Main Streamlit application entry point.
Runs the full Competitive Intelligence Dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

# Page config MUST be first Streamlit call
st.set_page_config(
    page_title="Competitive Intelligence Crew",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/ci-crew",
        "Report a bug": "https://github.com/ci-crew/issues",
        "About": "Competitive Intelligence Briefing Crew v1.0",
    },
)

from frontend.dashboard import render_dashboard

if __name__ == "__main__" or True:
    render_dashboard()
