"""
Card Ratings page — auth-gated.
Ratings and notes auto-save on change — no Save button needed.
Click any card image to expand it full-size.
"""

import pandas as pd
import streamlit as st
from auth import require_auth
from ratings_db import get_user_ratings, upsert_rating
from set_data import (
    SET_DISPLAY_NAMES, SET_LOOKUP,
    RARITY_ORDER, COLOR_OPTIONS, COLOR_LABELS,
    load_set,
)
from supabase_client import get_client

RATING_OPTIONS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

# ---------------------------------------------------------------------------
# Page setup & auth
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Card Ratings", page_icon="⭐", layout="wide")

client  = get_client()
user    = require_auth(client)
user_id = user.id

# ---------------------------------------------------------------------------
# Set selector
# ---------------------------------------------------------------------------

selected_display = st.selectbox("Select a set", SET_DISPLAY_NAMES)
set_code, csv_filename = SET_LOOKUP[selected_display]

# ---------------------------------------------------------------------------
# Load card data and seed the in-session baseline from DB
#
# The baseline (stored in session_state, keyed by collector_number) tracks
# what was last saved. On each rerun we diff the editor against the baseline
# and auto-save any changes, then update the baseline so we don't re-save.
# ---------------------------------------------------------------------------

cards_df     = load_set(csv_filename, set_code)
user_ratings = get_user_ratings(client, user_id, set_code)

baseline_key = f"baseline_{user_id}_{set_code}"
if baseline_key not in st.session_state:
    st.session_state[baseline_key] = {
        cn: {"my_rating": info.get("rating"), "my_notes": info.get("notes", "")}
        for cn, info in user_ratings.items()
    }
baseline = st.session_state[baseline_key]

def build_display_df(df, baseline):
    df = df.copy()
    df["my_rating"] = pd.to_numeric(
        df["collector_number"].map(lambda cn: baseline.get(cn, {}).get("my_rating")),
        errors="coerce",
    )
    df["my_notes"] = df["collector_number"].map(
        lambda cn: baseline.get(cn, {}).get("my_notes", "")
    )
    return df

display_df = build_display_df(cards_df, baseline)

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

name_query = st.sidebar.text_input("Search card name", placeholder="e.g. Dragon")

rarities_in_set = [r for r in RARITY_ORDER if r in display_df["rarity"].unique()]
selected_rarities = st.sidebar.multiselect(
    "Rarity", options=rarities_in_set, default=rarities_in_set,
)

colors_in_set = [c for c in COLOR_OPTIONS if display_df["color_identity"].str.contains(c).any()]
selected_colors = st.sidebar.multiselect(
    "Color identity (include colorless if none selected)",
    options=colors_in_set,
    format_func=lambda c: COLOR_LABELS[c],
)

show_unrated = st.sidebar.checkbox("Show only unrated cards", value=False)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

filtered = display_df.copy()

if name_query.strip():
    filtered = filtered[filtered["name"].str.contains(name_query.strip(), case=False, na=False)]

if selected_rarities:
    filtered = filtered[filtered["rarity"].isin(selected_rarities)]

if selected_colors:
    color_mask = filtered["color_identity"].apply(
        lambda ci: any(c in ci for c in selected_colors)
    )
    filtered = filtered[color_mask]

if show_unrated:
    filtered = filtered[filtered["my_rating"].isna()]

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

rated_count = display_df["my_rating"].notna().sum()
st.caption(
    f"**{len(filtered):,}** cards shown · "
    f"**{rated_count}** of **{len(display_df)}** rated in {selected_display} · "
    f"Click any image to expand · Ratings save automatically"
)

# ---------------------------------------------------------------------------
# Ratings table
# ---------------------------------------------------------------------------

editor_df = filtered[[
    "image_normal", "collector_number", "name", "mana_cost",
    "type_line", "rarity", "my_rating", "my_notes",
]].copy()

edited_df = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "image_normal":    st.column_config.ImageColumn("Card", width="medium"),
        "collector_number":st.column_config.TextColumn("#", disabled=True, width="small"),
        "name":            st.column_config.TextColumn("Name", disabled=True),
        "mana_cost":       st.column_config.TextColumn("Mana", disabled=True, width="small"),
        "type_line":       st.column_config.TextColumn("Type", disabled=True),
        "rarity":          st.column_config.TextColumn("Rarity", disabled=True, width="small"),
        "my_rating": st.column_config.SelectboxColumn(
            "My Rating",
            options=RATING_OPTIONS,
            required=False,
            width="small",
        ),
        "my_notes": st.column_config.TextColumn("My Notes", width="large"),
    },
)

# ---------------------------------------------------------------------------
# Auto-save: diff edited_df against baseline and upsert any changes
# ---------------------------------------------------------------------------

for _, row in edited_df.iterrows():
    cn = row["collector_number"]

    edit_rating = float(row["my_rating"]) if pd.notna(row["my_rating"]) else None
    edit_notes  = str(row["my_notes"]) if row["my_notes"] else ""

    saved = baseline.get(cn, {})
    saved_rating = float(saved["my_rating"]) if pd.notna(saved.get("my_rating")) else None
    saved_notes  = str(saved.get("my_notes", ""))

    if edit_rating is None:
        continue  # don't save unrated cards
    if edit_rating == saved_rating and edit_notes == saved_notes:
        continue  # nothing changed

    try:
        card_name = cards_df.loc[cards_df["collector_number"] == cn, "name"].iloc[0]
        upsert_rating(
            client=client,
            user_id=user_id,
            set_code=set_code,
            collector_number=cn,
            card_name=card_name,
            rating=edit_rating,
            notes=edit_notes,
        )
        baseline[cn] = {"my_rating": edit_rating, "my_notes": edit_notes}
        st.toast(f"{card_name} saved — {edit_rating}", icon="✅")
    except Exception as e:
        st.toast(f"Failed to save {row['name']}: {e}", icon="❌")
