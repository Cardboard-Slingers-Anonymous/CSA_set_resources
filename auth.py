"""
Email OTP authentication helpers.

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
    # Already authenticated this session — just render the sidebar and continue
    if "user" in st.session_state:
        _render_sidebar_user(client)
        return st.session_state["user"]

    _render_login_form(client)
    st.stop()


def _render_login_form(client: Client) -> None:
    st.title("Sign in")

    # Step 1: collect email and send OTP
    if "otp_email" not in st.session_state:
        st.write("Enter your email to receive a one-time sign-in code.")
        with st.form("email_form"):
            email = st.text_input("Email address")
            submitted = st.form_submit_button("Send code")

        if submitted:
            if not email.strip():
                st.warning("Please enter an email address.")
                return
            try:
                client.auth.sign_in_with_otp({
                    "email": email.strip(),
                    "options": {"should_create_user": True},
                })
                st.session_state["otp_email"] = email.strip()
                st.rerun()
            except Exception as e:
                st.error(f"Could not send code: {e}")
        return

    # Step 2: collect the 6-digit code
    email = st.session_state["otp_email"]
    st.write(f"A 6-digit code was sent to **{email}**. Enter it below.")

    with st.form("otp_form"):
        code = st.text_input("6-digit code", max_chars=6)
        col1, col2 = st.columns([1, 3])
        verified = col1.form_submit_button("Verify")
        resend = col2.form_submit_button("Re-send code")

    if resend:
        try:
            client.auth.sign_in_with_otp({
                "email": email,
                "options": {"should_create_user": True},
            })
            st.success("New code sent.")
        except Exception as e:
            st.error(f"Could not resend: {e}")

    if verified:
        if not code.strip():
            st.warning("Please enter the code.")
            return
        try:
            response = client.auth.verify_otp({
                "email": email,
                "token": code.strip(),
                "type": "email",
            })
            st.session_state["user"] = response.user
            del st.session_state["otp_email"]
            st.rerun()
        except Exception as e:
            st.error(f"Invalid or expired code: {e}")

    if st.button("Use a different email"):
        del st.session_state["otp_email"]
        st.rerun()


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
        st.session_state.pop("user", None)
        st.session_state.pop("supabase_client", None)
        st.rerun()
