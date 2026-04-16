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
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

DEBUG_AUTH = True  # Set to False to silence OAuth diagnostics


def _dbg(msg: str) -> None:
    if DEBUG_AUTH:
        print(f"[AUTH DEBUG] {msg}", flush=True)


def handle_oauth_callback(client: Client) -> None:
    """
    Exchange an OAuth authorisation code for a session.

    Call this ONCE at the top of app.py (before pg.run()) so it fires on
    every page load, including public pages that never call require_auth.

    PKCE note: supabase-py stores the code_verifier in its in-memory storage
    after sign_in_with_oauth. Since session state is lost across the browser
    redirect, _start_oauth reads it immediately and embeds it inside the
    redirect_to URL so it arrives back as ?cv= on the callback.
    """
    code = st.query_params.get("code")
    if not code:
        _dbg(f"handle_oauth_callback fired. Query params: {list(st.query_params.keys())} — no code, skipping.")
        return

    _dbg(f"handle_oauth_callback fired. Query params: {list(st.query_params.keys())}")
    _dbg(f"OAuth code found (first 10 chars): {code[:10]}…")

    verifier = st.query_params.get("cv")
    if not verifier:
        _dbg("ERROR: No 'cv' param in callback URL — verifier was not embedded in redirect_to.")
        st.error("Sign-in failed: missing PKCE verifier. Please try again.")
        return

    _dbg(f"code_verifier found (first 10 chars): {verifier[:10]}…")
    _dbg("Clearing callback query params and calling exchange_code_for_session…")
    st.query_params.pop("code", None)
    st.query_params.pop("state", None)
    st.query_params.pop("cv", None)
    try:
        response = client.auth.exchange_code_for_session(
            {"auth_code": code, "code_verifier": verifier}
        )
        _dbg(f"exchange_code_for_session succeeded. User: {getattr(response.user, 'email', response.user)}")
        st.session_state["user"] = response.user
        st.session_state.pop("_login_dialog_open", None)
        _dbg("Session state updated — calling st.rerun()")
        st.rerun()
    except Exception as e:
        _dbg(f"exchange_code_for_session FAILED: {e}")
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
                st.rerun()

    # The rerun() above ensures this check fires in a clean render pass where
    # @st.dialog reliably opens on the first click. The flag also keeps the
    # dialog alive across intermediate reruns (OTP steps, errors, resends).
    if st.session_state.get("_login_dialog_open") and "user" not in st.session_state:
        _login_dialog(client)


def _start_oauth(client: Client, provider: str) -> None:
    """Initiate a PKCE OAuth flow for the given provider and redirect the browser."""
    # Configure [app] url in .streamlit/secrets.toml for production.
    # Example:  [app]\n  url = "https://yourapp.streamlit.app"
    redirect_to = st.secrets.get("app", {}).get("url", "http://localhost:8501")
    _dbg(f"_start_oauth called for provider='{provider}', redirect_to='{redirect_to}'")
    try:
        response = client.auth.sign_in_with_oauth({
            "provider": provider,
            "options": {"redirect_to": redirect_to},
        })
        _dbg(f"sign_in_with_oauth response received. URL present: {bool(response.url)}")

        # supabase-py (PKCE mode) stores the verifier in its in-memory storage.
        # Session state is lost across the browser redirect, so we read it now
        # and embed it inside the redirect_to param in the OAuth URL so Supabase
        # echoes it back as ?cv= when it redirects to our callback.
        _VERIFIER_KEY = "supabase.auth.token-code-verifier"
        try:
            code_verifier = client.auth._storage.storage.get(_VERIFIER_KEY, "")
        except Exception:
            code_verifier = ""
        _dbg(f"code_verifier from storage: present={bool(code_verifier)} len={len(code_verifier)}")

        if code_verifier:
            parsed = urlparse(response.url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            if "redirect_to" in params:
                original_redirect = params["redirect_to"][0]
                sep = "&" if "?" in original_redirect else "?"
                params["redirect_to"] = [f"{original_redirect}{sep}cv={code_verifier}"]
                _dbg(f"Embedded cv into redirect_to: {params['redirect_to'][0][:80]}…")
            else:
                _dbg("WARNING: 'redirect_to' not found in OAuth URL — cv not embedded.")
            oauth_url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
        else:
            _dbg("WARNING: code_verifier empty — cannot complete PKCE exchange.")
            oauth_url = response.url

        st.html(f'<script>window.top.location.href = "{oauth_url}";</script>')
        st.info(
            f"Redirecting to {provider.title()}…  "
            f"[Click here if you are not redirected automatically.]({oauth_url})"
        )
        st.stop()
    except Exception as e:
        _dbg(f"_start_oauth FAILED: {e}")
        st.error(f"Could not start {provider.title()} sign-in: {e}")
        st.html(
            f"<script>"
            f"localStorage.setItem('supabase_pkce_verifier', '{code_verifier}');"
            f"window.top.location.href = '{response.url}';"
            f"</script>"
        )
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
