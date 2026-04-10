"""
Dashboard page — auth-gated.
Shows per-user rating histograms and a sortable community summary table.
(Full implementation coming in next step.)
"""

import streamlit as st
from supabase_client import get_client
from auth import require_auth

st.set_page_config(page_title="Ratings Dashboard", page_icon="📊", layout="wide")

client = get_client()
user = require_auth(client)

st.title("📊 Ratings Dashboard")
st.info("Dashboard UI coming soon.")
