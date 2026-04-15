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
    ("sos", "Secrets_of_Strixhaven",           "Secrets of Strixhaven"),
    ("tmt", "MTG_TeenageMutantNinjaTurtles", "Teenage Mutant Ninja Turtles"),
    ("ecl", "Lorwyn_Eclipsed",                "Lorwyn Eclipsed"),
    ("tla", "Avatar_TheLastAirbender",        "Avatar: The Last Airbender"),
    ("om1", "Through_the_Omenpaths",          "Through the Omenpaths"),
    ("eoe", "Edge_of_Eternities",             "Edge of Eternities"),
    ("fin", "Final_Fantasy",                  "Final Fantasy"),
    ("tdm", "Tarkir_Dragonstorm",             "Tarkir: Dragonstorm"),
    ("dft", "Aetherdrift",                    "Aetherdrift"),
    ("inr", "Innistrad_Remastered",           "Innistrad Remastered"),
    ("fdn", "MTG_Foundations",                "MTG Foundations"),
    ("dsk", "Duskmourn_House_of_Horror",      "Duskmourn: House of Horror"),
    ("blb", "Bloomburrow",                    "Bloomburrow"),
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RATINGS_PATH = os.path.join(DATA_DIR, "user_ratings.csv")

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
    # Small thumbnail shown in table; normal (488px) shown on hover
    df["image_small"] = df["collector_number"].apply(
        lambda n: f"https://api.scryfall.com/cards/{set_code}/{n}?format=image&version=small"
        if n else ""
    )
    df["image_normal"] = df["collector_number"].apply(
        lambda n: f"https://api.scryfall.com/cards/{set_code}/{n}?format=image&version=normal"
        if n else ""
    )
    return df


def load_ratings() -> pd.DataFrame:
    """Load user ratings from the shared CSV, or return an empty frame."""
    if os.path.exists(RATINGS_PATH):
        return pd.read_csv(RATINGS_PATH, dtype=str).fillna("")
    return pd.DataFrame(columns=["set_code", "collector_number", "rating", "comment"])


def save_rating(set_code: str, collector_number: str, rating: int, comment: str) -> None:
    """Upsert a rating+comment for one card into the shared CSV."""
    ratings = load_ratings()
    mask = (ratings["set_code"] == set_code) & (ratings["collector_number"] == collector_number)
    ratings = ratings[~mask]
    new_row = pd.DataFrame([{
        "set_code": set_code,
        "collector_number": collector_number,
        "rating": str(rating),
        "comment": comment,
    }])
    ratings = pd.concat([ratings, new_row], ignore_index=True)
    ratings.to_csv(RATINGS_PATH, index=False)


def delete_rating(set_code: str, collector_number: str) -> None:
    """Remove a card's rating/comment row from the shared CSV."""
    ratings = load_ratings()
    mask = (ratings["set_code"] == set_code) & (ratings["collector_number"] == collector_number)
    ratings[~mask].to_csv(RATINGS_PATH, index=False)


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

# Merge persisted ratings/comments into the set dataframe
_ratings = load_ratings()
_set_ratings = _ratings[_ratings["set_code"] == set_code][["collector_number", "rating", "comment"]]
df = df.merge(_set_ratings, on="collector_number", how="left")
df["rating"]  = df["rating"].fillna("")
df["comment"] = df["comment"].fillna("")

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
# Display table  –  data_editor with inline Rating / Comment editing
# ---------------------------------------------------------------------------

# Build display dataframe: convert rating to numeric for the NumberColumn widget
display_df = filtered[[
    "image_small", "collector_number", "name", "mana_cost", "cmc",
    "type_line", "rarity", "colors", "oracle_text",
    "power", "toughness", "loyalty", "keywords",
    "rating", "comment", "scryfall_uri",
]].copy()
display_df["rating"] = pd.to_numeric(display_df["rating"], errors="coerce")

# Key changes whenever set or filters change to avoid stale edited_rows indices
_filter_sig = f"{set_code}|{name_query}|{'|'.join(selected_rarities)}|{'|'.join(selected_colors)}"
editor_key = f"card_editor_{hash(_filter_sig)}"

st.info(
    "Double-click any **Rating ⭐** or **Comment** cell to edit it inline. "
    "Changes are saved automatically when you press Enter or click away."
)

edited_df = st.data_editor(
    display_df,
    column_config={
        "image_small":       st.column_config.ImageColumn("Card",        width="small"),
        "collector_number":  st.column_config.TextColumn("#"),
        "name":              st.column_config.TextColumn("Name"),
        "mana_cost":         st.column_config.TextColumn("Mana"),
        "cmc":               st.column_config.TextColumn("CMC"),
        "type_line":         st.column_config.TextColumn("Type"),
        "rarity":            st.column_config.TextColumn("Rarity"),
        "colors":            st.column_config.TextColumn("Colors"),
        "oracle_text":       st.column_config.TextColumn("Rules Text",   width="large"),
        "power":             st.column_config.TextColumn("Power"),
        "toughness":         st.column_config.TextColumn("Toughness"),
        "loyalty":           st.column_config.TextColumn("Loyalty"),
        "keywords":          st.column_config.TextColumn("Keywords"),
        "rating":            st.column_config.NumberColumn(
                                "Rating ⭐", min_value=1, max_value=10, step=1,
                                help="Your personal rating (1–10). Double-click to edit.",
                             ),
        "comment":           st.column_config.TextColumn(
                                "Comment", max_chars=200, width="medium",
                                help="Short note about the card. Double-click to edit.",
                             ),
        "scryfall_uri":      st.column_config.LinkColumn("Scryfall", display_text="View ↗"),
    },
    disabled=[
        "image_small", "collector_number", "name", "mana_cost", "cmc",
        "type_line", "rarity", "colors", "oracle_text",
        "power", "toughness", "loyalty", "keywords", "scryfall_uri",
    ],
    hide_index=True,
    use_container_width=True,
    key=editor_key,
)

# Persist any inline edits made this render
_editor_state = st.session_state.get(editor_key, {})
for row_idx, changes in _editor_state.get("edited_rows", {}).items():
    if row_idx >= len(display_df):
        continue
    cn = str(display_df.iloc[row_idx]["collector_number"])
    new_rating  = changes.get("rating",  display_df.iloc[row_idx]["rating"])
    new_comment = changes.get("comment", display_df.iloc[row_idx]["comment"])
    if pd.isna(new_rating) or str(new_rating).strip() in ("", "nan"):
        delete_rating(set_code, cn)
    else:
        save_rating(set_code, cn, int(float(new_rating)), str(new_comment or ""))



