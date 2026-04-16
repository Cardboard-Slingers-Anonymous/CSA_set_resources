"""
Authentication helpers — Email OTP + OAuth (Google, GitHub).

Usage in any auth-gated page:
    from supabase_client import get_client
    from auth import require_auth

    client = get_client()
    user = require_auth(client)   # stops here if not logged in

In app.py, call handle_oauth_callback(client) before pg.run() so that
OAuth redirects are caught on every page, including public ones.
"""

import streamlit as st
from supabase import Client


def handle_oauth_callback(client: Client) -> None:
    """
    Exchange an OAuth authorisation code for a session.

    Call this ONCE at the top of app.py (before pg.run()) so it fires on
    every page load, including public pages that never call require_auth.
    """
    code = st.query_params.get("code")
    if not code:
        return
    # Remove only OAuth callback params so unrelated query params are preserved  
    st.query_params.pop("code", None)  
    st.query_params.pop("state", None)
    try:
        response = client.auth.exchange_code_for_session({"auth_code": code})
        st.session_state["user"] = response.user
        st.session_state.pop("_login_dialog_open", None)
        st.rerun()
    except Exception as e:
        st.error(f"OAuth sign-in failed: {e}")


def require_auth(client: Client):
    """
    Gate an auth-required page.
    Returns the Supabase user if authenticated, otherwise shows a prompt and stops.
    """
    # Defence: handle callback in case app.py missed it
    handle_oauth_callback(client)

    if "user" in st.session_state:
        return st.session_state["user"]

    st.info("Please sign in using the button in the top-right to access this page.")
    st.stop()


def render_auth_widget(client: Client) -> None:
    """
    Render sign-in / sign-out controls in the top-right of every page.
    Call this from app.py so it is visible on every page.
    """
    _, col = st.columns([6, 1])
    with col:
        if "user" in st.session_state:
            user = st.session_state["user"]
            email = getattr(user, "email", "")
            st.caption(email)
            if st.button("Log out", key="header_logout", width="stretch"):
                try:
                    client.auth.sign_out()
                except Exception:
                    pass
                st.session_state.pop("user", None)
                st.session_state.pop("supabase_client", None)
                st.rerun()
        else:
            if st.button("Sign in", key="header_signin", width="stretch"):
                st.session_state["_login_dialog_open"] = True

    # Keep the dialog open as long as the flag is set and the user is not yet
    # authenticated. Placing this outside the column ensures it renders at
    # page level. The flag is only cleared on successful sign-in, so the
    # dialog survives intermediate reruns (OTP steps, errors, resends).
    if st.session_state.get("_login_dialog_open") and "user" not in st.session_state:
        _login_dialog(client)


def _start_oauth(client: Client, provider: str) -> None:
    """Initiate a PKCE OAuth flow for the given provider and redirect the browser."""
    # Configure [app] url in .streamlit/secrets.toml for production.
    # Example:  [app]\n  url = "https://yourapp.streamlit.app"
    redirect_to = st.secrets.get("app", {}).get("url", "http://localhost:8501")
    try:
        response = client.auth.sign_in_with_oauth({
            "provider": provider,
            "options": {"redirect_to": redirect_to},
        })
        # Redirect the browser via JavaScript
        st.html(f'<script>window.top.location.href = "{response.url}";</script>')
        st.info(
            f"Redirecting to {provider.title()}…  "
            f"[Click here if you are not redirected automatically.]({response.url})"
        )
        st.stop()
    except Exception as e:
        st.error(f"Could not start {provider.title()} sign-in: {e}")


@st.dialog("Sign in")
def _login_dialog(client: Client) -> None:
    """Modal dialog containing OAuth buttons and email OTP flow."""

    # OAuth buttons
    if st.button("Sign in with Google", width="stretch", key="dlg_google"):
        _start_oauth(client, "google")
    if st.button("Sign in with GitHub", width="stretch", key="dlg_github"):
        _start_oauth(client, "github")

    st.divider()
    st.write("**Or sign in with email:**")

    if "otp_email" not in st.session_state:
        # Step 1: request a code
        with st.form("dlg_email_form"):
            email = st.text_input("Email address", key="dlg_email_input")
            submitted = st.form_submit_button("Send code", width="stretch")
        if submitted:
            if not email.strip():
                st.warning("Please enter an email address.")
            else:
                try:
                    client.auth.sign_in_with_otp({
                        "email": email.strip(),
                        "options": {"should_create_user": True},
                    })
                    st.session_state["otp_email"] = email.strip()
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not send code: {e}")
    else:
        # Step 2: verify the code
        email = st.session_state["otp_email"]
        st.caption(f"Code sent to **{email}**")
        with st.form("dlg_otp_form"):
            code = st.text_input("6-digit code", max_chars=6, key="dlg_otp_input")
            col1, col2 = st.columns(2)
            verified = col1.form_submit_button("Verify")
            resend   = col2.form_submit_button("Resend")
        if verified:
            if not code.strip():
                st.warning("Please enter the code.")
            else:
                try:
                    response = client.auth.verify_otp({
                        "email": email,
                        "token": code.strip(),
                        "type": "email",
                    })
                    st.session_state["user"] = response.user
                    st.session_state.pop("_login_dialog_open", None)
                    del st.session_state["otp_email"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Invalid or expired code: {e}")
        if resend:
            try:
                client.auth.sign_in_with_otp({
                    "email": email,
                    "options": {"should_create_user": True},
                })
                st.success("New code sent.")
            except Exception as e:
                st.error(f"Could not resend: {e}")
        if st.button("Use a different email", key="dlg_diff_email"):
            del st.session_state["otp_email"]
            st.rerun()
