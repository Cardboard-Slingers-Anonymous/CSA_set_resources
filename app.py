"""
MTGA Set Resources — Entry point.
Redirects to the Viewer page on load.
"""

import streamlit as st

st.set_page_config(
    page_title="MTGA Set Resources",
    page_icon="🃏",
    layout="wide",
)

st.switch_page("pages/1_Viewer.py")
