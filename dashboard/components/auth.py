"""Supabase Auth integration for Streamlit dashboard.

Handles login/logout and session management. Each recruiter logs in
with their email/password and only sees their own data.
"""

import streamlit as st
from supabase import create_client


def init_supabase():
    """Initialize Supabase client from Streamlit secrets."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_supabase():
    """Get or create the Supabase client (cached in session state)."""
    if "supabase" not in st.session_state:
        st.session_state.supabase = init_supabase()
    return st.session_state.supabase


def login_form():
    """Display branded login form. Returns True if user is logged in."""
    if "user_id" in st.session_state and st.session_state.user_id:
        return True

    # Centered login card
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div class="login-container">
            <div class="login-logo">
                <div style="font-size:48px; margin-bottom:8px;">&#127769;</div>
                <h1>Lunar Recruitment</h1>
                <p>Recruiter Intelligence Platform</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@company.com")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted and email and password:
            sb = get_supabase()
            try:
                resp = sb.auth.sign_in_with_password({
                    "email": email,
                    "password": password,
                })
                if resp.user:
                    st.session_state.user_id = resp.user.id
                    st.session_state.user_email = resp.user.email
                    st.session_state.access_token = resp.session.access_token
                    st.rerun()
            except Exception as e:
                error_msg = str(e)
                if "Invalid login" in error_msg or "invalid" in error_msg.lower():
                    st.error("Invalid email or password.")
                else:
                    st.error(f"Login error: {error_msg}")

    return False


def logout():
    """Clear session state (logout)."""
    for key in ["user_id", "user_email", "access_token"]:
        st.session_state.pop(key, None)
    st.rerun()


def get_user_id() -> str:
    """Get the current logged-in user's ID."""
    return st.session_state.get("user_id", "")


def get_user_email() -> str:
    """Get the current logged-in user's email."""
    return st.session_state.get("user_email", "")


def require_auth():
    """Require authentication. Shows login form if not logged in."""
    return login_form()


def sidebar_user_info():
    """Display user info and logout button in sidebar."""
    if "user_email" in st.session_state:
        email = st.session_state.user_email
        initial = email[0].upper() if email else "?"
        st.sidebar.markdown(
            f'<div style="display:flex; align-items:center; gap:10px; '
            f'padding:8px 12px; background:rgba(99,102,241,0.1); '
            f'border-radius:10px; margin:8px 0;">'
            f'<div style="width:32px; height:32px; border-radius:50%; '
            f'background:linear-gradient(135deg,#6366f1,#818cf8); '
            f'display:flex; align-items:center; justify-content:center; '
            f'color:white; font-weight:700; font-size:14px;">{initial}</div>'
            f'<div style="font-size:13px; color:#e2e8f0; '
            f'overflow:hidden; text-overflow:ellipsis;">{email}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Sign Out", use_container_width=True):
            logout()
