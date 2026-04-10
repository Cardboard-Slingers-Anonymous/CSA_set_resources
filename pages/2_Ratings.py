"""
Card Ratings page — auth-gated.
Lets logged-in users rate cards (LSV 0.0–5.0) and add notes.
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
# Load card + rating data
# ---------------------------------------------------------------------------

cards_df     = load_set(csv_filename, set_code)
user_ratings = get_user_ratings(client, user_id, set_code)

def merge_ratings(df, user_ratings):
    df = df.copy()
    df["my_rating"] = pd.to_numeric(
        df["collector_number"].map(lambda cn: user_ratings.get(cn, {}).get("rating", None)),
        errors="coerce",
    )
    df["my_notes"] = df["collector_number"].map(
        lambda cn: user_ratings.get(cn, {}).get("notes", "")
    )
    return df

display_df = merge_ratings(cards_df, user_ratings)

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
    f"Click any image to expand it"
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
        "image_normal": st.column_config.ImageColumn("Card", width="medium"),
        "collector_number": st.column_config.TextColumn("#", disabled=True, width="small"),
        "name":     st.column_config.TextColumn("Name", disabled=True),
        "mana_cost":st.column_config.TextColumn("Mana", disabled=True, width="small"),
        "type_line":st.column_config.TextColumn("Type", disabled=True),
        "rarity":   st.column_config.TextColumn("Rarity", disabled=True, width="small"),
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
# Save
# ---------------------------------------------------------------------------

if st.button("Save ratings", type="primary"):
    changes = []
    for idx in edited_df.index:
        orig = editor_df.loc[idx]
        edit = edited_df.loc[idx]
        if (edit["my_rating"] != orig["my_rating"] or
                str(edit["my_notes"]) != str(orig["my_notes"])):
            if pd.notna(edit["my_rating"]):
                changes.append(edit)

    if not changes:
        st.info("No changes to save.")
    else:
        errors = []
        for row in changes:
            try:
                card_name = cards_df.loc[
                    cards_df["collector_number"] == row["collector_number"], "name"
                ].iloc[0]
                upsert_rating(
                    client=client,
                    user_id=user_id,
                    set_code=set_code,
                    collector_number=row["collector_number"],
                    card_name=card_name,
                    rating=float(row["my_rating"]),
                    notes=str(row["my_notes"]),
                )
            except Exception as e:
                errors.append(f"{row['name']}: {e}")

        if errors:
            st.error("Some ratings failed to save:\n" + "\n".join(errors))
        else:
            st.success(f"Saved {len(changes)} rating(s).")
            st.rerun()
