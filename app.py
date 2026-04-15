"""
MTGA Set Resources — Entry point.
"""

import streamlit as st

st.set_page_config(
    page_title="MTGA Set Resources",
    page_icon="🃏",
    layout="wide",
)

pg = st.navigation([
    st.Page("pages/1_Viewer.py", title="Viewer", icon="🔍"),
    st.Page("pages/2_Ratings.py", title="Ratings", icon="⭐"),
    st.Page("pages/3_Dashboard.py", title="Dashboard", icon="📊"),
])
pg.run()
