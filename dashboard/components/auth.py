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
    """Display login form and handle authentication.

    Returns True if user is logged in, False otherwise.
    """
    if "user_id" in st.session_state and st.session_state.user_id:
        return True

    st.markdown("## Recruiter Intelligence Tool")
    st.markdown("Log in to access your pipeline dashboard.")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", use_container_width=True)

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
    """Require authentication. Shows login form if not logged in.

    Returns True if authenticated.
    """
    return login_form()


def sidebar_user_info():
    """Display user info and logout button in sidebar."""
    if "user_email" in st.session_state:
        st.sidebar.markdown(f"**{st.session_state.user_email}**")
        if st.sidebar.button("Logout"):
            logout()
