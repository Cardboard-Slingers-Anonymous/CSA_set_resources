"""
Magic-link authentication helpers.

Usage in any auth-gated page:
    from supabase_client import get_client
    from auth import require_auth

    client = get_client()
    user = require_auth(client)   # stops here if not logged in
"""

import streamlit as st
from supabase import Client


def require_auth(client: Client):
    """
    Call at the top of any auth-gated page.
    Returns the Supabase user object if authenticated.
    Shows the login UI and calls st.stop() if not.
    """
    # 1. Already authenticated this session?
    if "user" in st.session_state:
        _render_sidebar_user(client)
        return st.session_state["user"]

    # 2. Returning from magic-link click? (PKCE code in query params)
    code = st.query_params.get("code")
    if code:
        try:
            response = client.auth.exchange_code_for_session({"auth_code": code})
            st.session_state["user"] = response.user
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
            st.stop()

    # 3. Show login form
    _render_login_form(client)
    st.stop()


def _render_login_form(client: Client) -> None:
    st.title("Sign in")
    st.write("Enter your email to receive a magic link. No password needed.")

    with st.form("login_form"):
        email = st.text_input("Email address")
        submitted = st.form_submit_button("Send magic link")

    if submitted:
        if not email.strip():
            st.warning("Please enter an email address.")
            return
        redirect_url = st.secrets.get("supabase", {}).get(
            "redirect_url", "http://localhost:8501"
        )
        try:
            client.auth.sign_in_with_otp({
                "email": email.strip(),
                "options": {"email_redirect_to": redirect_url},
            })
            st.success(f"Magic link sent to **{email}** — check your inbox and click the link.")
        except Exception as e:
            st.error(f"Could not send magic link: {e}")


def _render_sidebar_user(client: Client) -> None:
    user = st.session_state.get("user")
    if not user:
        return
    email = getattr(user, "email", "Unknown")
    st.sidebar.markdown(f"**Signed in as** {email}")
    if st.sidebar.button("Log out"):
        try:
            client.auth.sign_out()
        except Exception:
            pass
        del st.session_state["user"]
        if "supabase_client" in st.session_state:
            del st.session_state["supabase_client"]
        st.rerun()
