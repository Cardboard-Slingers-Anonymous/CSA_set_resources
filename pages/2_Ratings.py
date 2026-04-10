"""
Card Ratings page — auth-gated.
Lets logged-in users rate cards (LSV 0.0–5.0) and add notes.
"""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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
    df["my_rating"] = df["collector_number"].map(
        lambda cn: user_ratings.get(cn, {}).get("rating", None)
    )
    df["my_notes"] = df["collector_number"].map(
        lambda cn: user_ratings.get(cn, {}).get("notes", "")
    )
    df["my_rating"] = pd.to_numeric(df["my_rating"], errors="coerce")
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
    f"**{rated_count}** of **{len(display_df)}** rated in {selected_display}"
)

# ---------------------------------------------------------------------------
# Tabs: Browse (hover zoom) | Edit ratings
# ---------------------------------------------------------------------------

tab_browse, tab_edit = st.tabs(["Browse Cards", "Edit Ratings"])

# ── Tab 1: Browse with hover-zoom ──────────────────────────────────────────

with tab_browse:
    def build_ratings_html_table(df_rows):
        css = """
        <style>
        .card-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .card-table th {
            background: #0e1117;
            color: #fafafa;
            padding: 8px 10px;
            text-align: left;
            border-bottom: 2px solid #444;
            white-space: nowrap;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .card-table td {
            padding: 6px 10px;
            border-bottom: 1px solid #2a2a2a;
            vertical-align: middle;
            color: #e0e0e0;
        }
        .card-table tr:hover td { background: #1a1f2e; }

        .thumb-wrap {
            position: relative;
            display: inline-block;
            width: 82px;
        }
        .thumb-wrap img.thumb {
            width: 80px;
            height: auto;
            border-radius: 5px;
            display: block;
            cursor: default;
        }
        .thumb-wrap .preview {
            display: none;
            position: absolute;
            left: 92px;
            top: -80px;
            width: 280px;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.9);
            z-index: 9999;
            pointer-events: none;
        }
        .thumb-wrap:hover .preview { display: block; }

        .rating-badge {
            display: inline-block;
            background: #2a3a5e;
            color: #7fbfff;
            border-radius: 6px;
            padding: 2px 8px;
            font-weight: bold;
            font-size: 13px;
            min-width: 36px;
            text-align: center;
        }
        .unrated { color: #555; font-style: italic; }
        </style>
        """

        headers = ["Card", "#", "Name", "Mana", "Type", "Rarity", "My Rating", "My Notes"]
        thead = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"

        rows = []
        for _, r in df_rows.iterrows():
            thumb  = r.get("image_small", "")
            normal = r.get("image_normal", "")
            img_html = (
                f'<div class="thumb-wrap">'
                f'<img class="thumb" src="{thumb}" loading="lazy">'
                f'<img class="preview" src="{normal}" loading="lazy">'
                f'</div>'
            ) if thumb else ""

            rating_val = r["my_rating"]
            if pd.notna(rating_val):
                rating_html = f'<span class="rating-badge">{rating_val:.1f}</span>'
            else:
                rating_html = '<span class="unrated">—</span>'

            notes = str(r["my_notes"]) if r["my_notes"] else ""

            rows.append(
                "<tr>"
                f"<td>{img_html}</td>"
                f"<td style='white-space:nowrap'>{r['collector_number']}</td>"
                f"<td><b>{r['name']}</b></td>"
                f"<td style='white-space:nowrap'>{r['mana_cost']}</td>"
                f"<td style='white-space:nowrap'>{r['type_line']}</td>"
                f"<td style='white-space:nowrap'>{r['rarity'].capitalize()}</td>"
                f"<td style='text-align:center'>{rating_html}</td>"
                f"<td style='font-size:11px;max-width:300px'>{notes}</td>"
                "</tr>"
            )

        tbody = "\n".join(rows)
        return (
            f"{css}"
            "<div style='overflow-x:auto;'>"
            "<table class='card-table'>"
            f"<thead>{thead}</thead>"
            f"<tbody>{tbody}</tbody>"
            "</table>"
            "</div>"
        )

    components.html(build_ratings_html_table(filtered), height=750, scrolling=True)

# ── Tab 2: Edit ratings ─────────────────────────────────────────────────────

with tab_edit:
    st.markdown("Edit **My Rating** and **My Notes** below, then click **Save ratings**.")

    editor_df = filtered[[
        "collector_number", "name", "rarity", "my_rating", "my_notes",
    ]].copy()

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "collector_number": st.column_config.TextColumn("#", disabled=True, width="small"),
            "name":    st.column_config.TextColumn("Name", disabled=True),
            "rarity":  st.column_config.TextColumn("Rarity", disabled=True, width="small"),
            "my_rating": st.column_config.SelectboxColumn(
                "My Rating",
                options=RATING_OPTIONS,
                required=False,
                width="small",
            ),
            "my_notes": st.column_config.TextColumn("My Notes", width="large"),
        },
    )

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
                    # Look up card name from cards_df using collector_number
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
