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
        st.session_state["supabase_client"] = create_client(url, key)
    return st.session_state["supabase_client"]
