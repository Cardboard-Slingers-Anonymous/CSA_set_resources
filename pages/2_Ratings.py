"""
Card Ratings page — auth-gated.
Lets logged-in users rate cards (LSV 0.0–5.0) and add notes.
Shows community average alongside personal ratings.
"""

import pandas as pd
import streamlit as st
from auth import require_auth
from ratings_db import get_user_ratings, get_community_ratings, upsert_rating
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

client = get_client()
user   = require_auth(client)
user_id = user.id

# ---------------------------------------------------------------------------
# Set selector
# ---------------------------------------------------------------------------

selected_display = st.selectbox("Select a set", SET_DISPLAY_NAMES)
set_code, csv_filename = SET_LOOKUP[selected_display]

# ---------------------------------------------------------------------------
# Load card + rating data
# ---------------------------------------------------------------------------

# Bust the ratings cache when the set changes so stale data isn't shown
cache_key = f"ratings_loaded_{user_id}_{set_code}"
if cache_key not in st.session_state:
    st.session_state[cache_key] = False

cards_df = load_set(csv_filename, set_code)
user_ratings    = get_user_ratings(client, user_id, set_code)
community_ratings = get_community_ratings(client, set_code)

# Merge ratings into card dataframe
def merge_ratings(df, user_ratings, community_ratings):
    df = df.copy()
    df["my_rating"] = df["collector_number"].map(
        lambda cn: user_ratings.get(cn, {}).get("rating", None)
    )
    df["my_notes"] = df["collector_number"].map(
        lambda cn: user_ratings.get(cn, {}).get("notes", "")
    )
    df["avg_rating"] = df["collector_number"].map(
        lambda cn: community_ratings.get(cn, {}).get("avg_rating", None)
    )
    df["rating_count"] = df["collector_number"].map(
        lambda cn: community_ratings.get(cn, {}).get("count", 0)
    )
    df["my_rating"] = pd.to_numeric(df["my_rating"], errors="coerce")
    df["avg_rating"] = pd.to_numeric(df["avg_rating"], errors="coerce")
    df["rating_count"] = pd.to_numeric(df["rating_count"], errors="coerce").fillna(0).astype(int)
    return df

display_df = merge_ratings(cards_df, user_ratings, community_ratings)

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
    f"**{rated_count}** of **{len(display_df)}** rated in {selected_display}"
)

# ---------------------------------------------------------------------------
# Ratings table
# ---------------------------------------------------------------------------

st.markdown("Edit **My Rating** and **My Notes** inline, then click **Save ratings**.")

editor_df = filtered[[
    "image_small", "collector_number", "name", "mana_cost",
    "type_line", "rarity", "my_rating", "my_notes", "avg_rating", "rating_count",
]].copy()

edited_df = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    column_order=[
        "image_small", "collector_number", "name", "mana_cost",
        "type_line", "rarity", "my_rating", "my_notes", "avg_rating", "rating_count",
    ],
    column_config={
        "image_small": st.column_config.ImageColumn("Card", width="small"),
        "collector_number": st.column_config.TextColumn("#", disabled=True, width="small"),
        "name": st.column_config.TextColumn("Name", disabled=True),
        "mana_cost": st.column_config.TextColumn("Mana", disabled=True, width="small"),
        "type_line": st.column_config.TextColumn("Type", disabled=True),
        "rarity": st.column_config.TextColumn("Rarity", disabled=True, width="small"),
        "my_rating": st.column_config.SelectboxColumn(
            "My Rating",
            options=RATING_OPTIONS,
            required=False,
            width="small",
        ),
        "my_notes": st.column_config.TextColumn("My Notes", width="large"),
        "avg_rating": st.column_config.NumberColumn(
            "Avg Rating", disabled=True, format="%.1f", width="small"
        ),
        "rating_count": st.column_config.NumberColumn(
            "# Ratings", disabled=True, width="small"
        ),
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
        rating_changed = edit["my_rating"] != orig["my_rating"]
        notes_changed  = str(edit["my_notes"]) != str(orig["my_notes"])
        if (rating_changed or notes_changed) and pd.notna(edit["my_rating"]):
            changes.append(edit)

    if not changes:
        st.info("No changes to save.")
    else:
        errors = []
        for row in changes:
            try:
                upsert_rating(
                    client=client,
                    user_id=user_id,
                    set_code=set_code,
                    collector_number=row["collector_number"],
                    card_name=row["name"],
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
