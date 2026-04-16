"""
Supabase client — one instance per browser session.
Storing in st.session_state (rather than st.cache_resource) keeps
each user's PKCE auth state isolated.
"""

import streamlit as st
from supabase import create_client, Client


def get_client() -> Client:
    if "supabase_client" not in st.session_state:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        # flow_type="pkce" ensures sign_in_with_oauth populates code_verifier on
        # the OAuthResponse, which we embed in the redirect_to URL to survive the
        # cross-origin redirect without relying on session state.
        try:
            from supabase.lib.client_options import ClientOptions
            client = create_client(url, key, options=ClientOptions(flow_type="pkce"))
        except Exception:
            # Older supabase-py versions — fall back gracefully
            client = create_client(url, key)
        st.session_state["supabase_client"] = client
    return st.session_state["supabase_client"]
