"""Recruiter Intelligence Tool — Streamlit Dashboard.

Main entry point. Handles authentication and page navigation.

Run locally:  streamlit run dashboard/app.py
Deploy:       Push to GitHub, connect to Streamlit Community Cloud
"""

import streamlit as st

st.set_page_config(
    page_title="Recruiter Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.components.auth import require_auth, sidebar_user_info

# --- Authentication ---
if not require_auth():
    st.stop()

# --- Sidebar ---
sidebar_user_info()

st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")

page = st.sidebar.radio(
    "Go to",
    ["Pipeline", "Call Sheet", "Companies", "Contacts", "Analytics"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption("Recruiter Intelligence Tool v1.0")

# --- Page routing ---
if page == "Pipeline":
    from dashboard.pages.pipeline import render
    render()
elif page == "Call Sheet":
    from dashboard.pages.call_sheet import render
    render()
elif page == "Companies":
    from dashboard.pages.companies import render
    render()
elif page == "Contacts":
    from dashboard.pages.contacts import render
    render()
elif page == "Analytics":
    from dashboard.pages.analytics import render
    render()
