"""Recruiter Intelligence Tool — Streamlit Dashboard.

Main entry point. Handles authentication, theming, and page navigation.

Run locally:  streamlit run dashboard/app.py
Deploy:       Push to GitHub, connect to Streamlit Community Cloud
"""

import sys
from pathlib import Path

# Ensure the repo root is on the Python path so imports like
# "from dashboard.components.auth" work whether Streamlit runs
# from the repo root or from inside the dashboard/ folder.
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

st.set_page_config(
    page_title="Lunar Recruitment",
    page_icon="https://img.icons8.com/fluency/48/crescent-moon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Lunar Recruitment brand theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ---------- Fonts ---------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    color: #e2e8f0;
    border-right: 1px solid #334155;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stMarkdown li {
    color: #cbd5e1;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #f1f5f9;
}
section[data-testid="stSidebar"] .stRadio > label {
    color: #94a3b8 !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    color: #e2e8f0 !important;
    padding: 8px 12px;
    border-radius: 8px;
    margin: 2px 0;
    transition: background 0.2s;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
    background: rgba(99, 102, 241, 0.15);
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio div[data-checked="true"] {
    background: rgba(99, 102, 241, 0.25);
    border-left: 3px solid #818cf8;
}
section[data-testid="stSidebar"] hr {
    border-color: #334155;
}
section[data-testid="stSidebar"] button {
    color: #e2e8f0 !important;
    border-color: #475569 !important;
}
section[data-testid="stSidebar"] button:hover {
    background: rgba(239, 68, 68, 0.15) !important;
    border-color: #ef4444 !important;
    color: #fca5a5 !important;
}

/* ---------- Main content ---------- */
.main .block-container {
    padding-top: 2rem;
    max-width: 1200px;
}

/* ---------- Metric cards ---------- */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: transform 0.15s, box-shadow 0.15s;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
div[data-testid="stMetric"] label {
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #0f172a !important;
    font-size: 28px !important;
    font-weight: 800 !important;
}

/* ---------- Expanders → Cards ---------- */
div[data-testid="stExpander"] {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin-bottom: 8px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    transition: box-shadow 0.15s;
}
div[data-testid="stExpander"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
div[data-testid="stExpander"] summary {
    font-weight: 600;
    padding: 12px 16px;
}

/* ---------- Buttons ---------- */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.15s;
    border: 1px solid #e2e8f0;
}
.stButton > button[kind="primary"],
.stButton > button:first-child {
    background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
    color: white;
    border: none;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 2px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 20px;
    font-weight: 600;
    color: #64748b;
}
.stTabs [aria-selected="true"] {
    color: #6366f1 !important;
    border-bottom-color: #6366f1 !important;
}

/* ---------- Selectbox / text input ---------- */
div[data-baseweb="select"] > div,
.stTextInput > div > div > input {
    border-radius: 8px;
    border-color: #e2e8f0;
}
div[data-baseweb="select"] > div:focus-within,
.stTextInput > div > div > input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 1px #6366f1;
}

/* ---------- Info / success / warning boxes ---------- */
div[data-testid="stAlert"] {
    border-radius: 10px;
}

/* ---------- Dividers ---------- */
hr {
    border-color: #f1f5f9;
    margin: 1.5rem 0;
}

/* ---------- Custom card component ---------- */
.lunar-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.15s, transform 0.15s;
}
.lunar-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    transform: translateY(-1px);
}
.lunar-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}
.lunar-card-title {
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
}

/* ---------- Status badges ---------- */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-new { background: #f1f5f9; color: #64748b; }
.badge-researching { background: #fef3c7; color: #92400e; }
.badge-qualified { background: #dbeafe; color: #1e40af; }
.badge-active { background: #dcfce7; color: #166534; }
.badge-paused { background: #f3e8ff; color: #6b21a8; }
.badge-dead { background: #fee2e2; color: #991b1b; }

/* ---------- Score pill ---------- */
.score-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}
.score-high { background: #dcfce7; color: #166534; }
.score-mid { background: #fef3c7; color: #92400e; }
.score-low { background: #f1f5f9; color: #64748b; }

/* ---------- Login page ---------- */
.login-container {
    max-width: 400px;
    margin: 60px auto;
    padding: 40px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.1);
    border: 1px solid #e2e8f0;
}
.login-logo {
    text-align: center;
    margin-bottom: 24px;
}
.login-logo h1 {
    font-size: 28px;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.login-logo p {
    color: #94a3b8;
    font-size: 14px;
    margin-top: 4px;
}

/* ---------- Section headers ---------- */
.section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
}
.section-header h2 {
    font-size: 20px;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
}
.section-icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}

/* ---------- Data table override ---------- */
.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

from dashboard.components.auth import require_auth, sidebar_user_info

# --- Authentication ---
if not require_auth():
    st.stop()

# --- Sidebar ---
st.sidebar.markdown("""
<div style="text-align:center; padding: 16px 0 8px 0;">
    <div style="font-size: 32px; margin-bottom: 4px;">&#127769;</div>
    <h2 style="font-size: 20px; font-weight: 800; margin: 0;
        background: linear-gradient(135deg, #818cf8, #c084fc);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        Lunar Recruitment
    </h2>
    <p style="font-size: 12px; color: #64748b; margin: 4px 0 0 0;">
        Recruiter Intelligence Platform
    </p>
</div>
""", unsafe_allow_html=True)

sidebar_user_info()

st.sidebar.markdown("---")

NAV_ITEMS = {
    "Pipeline": "&#128200;",
    "Call Sheet": "&#128222;",
    "Companies": "&#127970;",
    "Contacts": "&#128101;",
    "Candidates": "&#128188;",
    "LinkedIn": "&#128279;",
    "Analytics": "&#128202;",
    "Run Pipeline": "&#9889;",
}

page = st.sidebar.radio(
    "Navigation",
    list(NAV_ITEMS.keys()),
    label_visibility="collapsed",
    format_func=lambda x: f"  {x}",
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    '<p style="text-align:center; font-size:11px; color:#475569;">'
    'Lunar Recruitment v2.0<br>'
    '<span style="color:#64748b;">Powered by AI</span>'
    '</p>',
    unsafe_allow_html=True,
)

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
elif page == "Candidates":
    from dashboard.pages.candidates import render
    render()
elif page == "LinkedIn":
    from dashboard.pages.linkedin import render
    render()
elif page == "Analytics":
    from dashboard.pages.analytics import render
    render()
elif page == "Run Pipeline":
    from dashboard.pages.run_pipeline import render
    render()
