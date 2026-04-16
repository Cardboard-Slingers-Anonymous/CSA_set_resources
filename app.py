"""
MTGA Set Resources — Entry point.
"""

import streamlit as st
from auth import handle_oauth_callback, render_auth_widget
from supabase_client import get_client

st.set_page_config(
    page_title="MTGA Set Resources",
    page_icon="🃏",
    layout="wide",
)

# Handle OAuth redirects and render the persistent sign-in widget
_client = get_client()
handle_oauth_callback(_client)
render_auth_widget(_client)

pg = st.navigation([
    st.Page("pages/1_Viewer.py", title="Viewer", icon="🔍"),
    st.Page("pages/2_Ratings.py", title="Ratings", icon="⭐"),
    st.Page("pages/3_Dashboard.py", title="Dashboard", icon="📊"),
])
pg.run()
