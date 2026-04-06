"""
MTGA Set Tracking Viewer
Streamlit app to browse card lists for tracked MTG Arena sets.
"""

import os
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SETS = [
    ("tmt", "MTG_TeenageMutantNinjaTurtles", "Teenage Mutant Ninja Turtles"),
    ("tla", "Avatar_TheLastAirbender",        "Avatar: The Last Airbender"),
    ("om1", "Through_the_Omenpaths",          "Through the Omenpaths"),
    ("eoe", "Edge_of_Eternities",             "Edge of Eternities"),
    ("fin", "Final_Fantasy",                  "Final Fantasy"),
    ("tdm", "Tarkir_Dragonstorm",             "Tarkir: Dragonstorm"),
    ("dft", "Aetherdrift",                    "Aetherdrift"),
    ("inr", "Innistrad_Remastered",           "Innistrad Remastered"),
    ("fdn", "MTG_Foundations",                "MTG Foundations"),
    ("dsk", "Duskmourn_House_of_Horror",      "Duskmourn: House of Horror"),
]

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

RARITY_ORDER = ["common", "uncommon", "rare", "mythic"]
COLOR_OPTIONS = ["W", "U", "B", "R", "G"]
COLOR_LABELS  = {
    "W": "White (W)",
    "U": "Blue (U)",
    "B": "Black (B)",
    "R": "Red (R)",
    "G": "Green (G)",
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_set(csv_filename: str, set_code: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{csv_filename}.csv")
    df = pd.read_csv(path, dtype=str).fillna("")
    # Build inline image URL using Scryfall API
    df["image"] = df["collector_number"].apply(
        lambda n: f"https://api.scryfall.com/cards/{set_code}/{n}?format=image&version=small"
        if n else ""
    )
    return df

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTGA Set Tracker",
    page_icon="🃏",
    layout="wide",
)

st.title("🃏 MTGA Set Card Viewer")

# ---------------------------------------------------------------------------
# Set selector (top)
# ---------------------------------------------------------------------------

set_display_names = [display for _, _, display in SETS]
set_lookup = {display: (code, fname) for code, fname, display in SETS}

selected_display = st.selectbox("Select a set", set_display_names)
set_code, csv_filename = set_lookup[selected_display]

df = load_set(csv_filename, set_code)

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

# Name search
name_query = st.sidebar.text_input("Search card name", placeholder="e.g. Dragon")

# Rarity filter
rarities_in_set = [r for r in RARITY_ORDER if r in df["rarity"].unique()]
selected_rarities = st.sidebar.multiselect(
    "Rarity",
    options=rarities_in_set,
    default=rarities_in_set,
)

# Color filter
colors_in_set = [c for c in COLOR_OPTIONS if df["color_identity"].str.contains(c).any()]
selected_colors = st.sidebar.multiselect(
    "Color identity (include colorless if none selected)",
    options=colors_in_set,
    format_func=lambda c: COLOR_LABELS[c],
)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

filtered = df.copy()

if name_query.strip():
    filtered = filtered[filtered["name"].str.contains(name_query.strip(), case=False, na=False)]

if selected_rarities:
    filtered = filtered[filtered["rarity"].isin(selected_rarities)]

if selected_colors:
    color_mask = filtered["color_identity"].apply(
        lambda ci: any(c in ci for c in selected_colors)
    )
    filtered = filtered[color_mask]

# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------

st.caption(
    f"**{len(filtered):,}** cards shown "
    f"({'all' if len(filtered) == len(df) else f'{len(df):,} total'}) "
    f"· Set: {selected_display}"
)

# ---------------------------------------------------------------------------
# Display table
# ---------------------------------------------------------------------------

DISPLAY_COLS = [
    "image",
    "collector_number",
    "name",
    "mana_cost",
    "cmc",
    "type_line",
    "rarity",
    "colors",
    "color_identity",
    "oracle_text",
    "power",
    "toughness",
    "loyalty",
    "keywords",
    "set_name",
    "released_at",
    "scryfall_uri",
]

column_config = {
    "image": st.column_config.ImageColumn(
        "Card Image",
        width="small",
        help="Card art from Scryfall",
    ),
    "collector_number": st.column_config.TextColumn("#", width="small"),
    "name":             st.column_config.TextColumn("Name", width="medium"),
    "mana_cost":        st.column_config.TextColumn("Mana Cost", width="small"),
    "cmc":              st.column_config.TextColumn("CMC", width="small"),
    "type_line":        st.column_config.TextColumn("Type", width="medium"),
    "rarity":           st.column_config.TextColumn("Rarity", width="small"),
    "colors":           st.column_config.TextColumn("Colors", width="small"),
    "color_identity":   st.column_config.TextColumn("Color Identity", width="small"),
    "oracle_text":      st.column_config.TextColumn("Rules Text", width="large"),
    "power":            st.column_config.TextColumn("Power", width="small"),
    "toughness":        st.column_config.TextColumn("Toughness", width="small"),
    "loyalty":          st.column_config.TextColumn("Loyalty", width="small"),
    "keywords":         st.column_config.TextColumn("Keywords", width="medium"),
    "set_name":         st.column_config.TextColumn("Set Name", width="medium"),
    "released_at":      st.column_config.TextColumn("Released", width="small"),
    "scryfall_uri": st.column_config.LinkColumn(
        "Scryfall Page",
        width="small",
        help="Click to view the card on Scryfall",
        display_text="View card ↗",
    ),
}

st.dataframe(
    filtered[DISPLAY_COLS],
    column_config=column_config,
    width="stretch",
    hide_index=True,
    height=700,
)
