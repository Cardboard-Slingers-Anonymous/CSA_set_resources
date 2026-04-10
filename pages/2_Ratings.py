"""
Ratings page — auth-gated.
Allows logged-in users to rate cards and add notes.
(Full implementation coming in next step.)
"""

import streamlit as st
from supabase_client import get_client
from auth import require_auth

st.set_page_config(page_title="Card Ratings", page_icon="⭐", layout="wide")

client = get_client()
user = require_auth(client)

st.title("⭐ Card Ratings")
st.info("Rating UI coming soon.")
