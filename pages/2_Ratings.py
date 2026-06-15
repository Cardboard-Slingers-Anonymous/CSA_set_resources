"""
Card Ratings page — auth-gated.
Hover over any card image to zoom. Single-click to change ratings inline.
Click Save Changes to persist ratings to the database.
"""

import html
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

from auth import require_auth
from ratings_db import delete_rating, get_user_ratings, upsert_rating
from set_data import (
    COLOR_LABELS,
    COLOR_OPTIONS,
    RARITY_ORDER,
    get_active_sets,
    load_set,
)
from supabase_client import get_client

RATING_OPTIONS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

# ---------------------------------------------------------------------------
# Page setup & auth
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Card Ratings", page_icon="⭐", layout="wide")

client = get_client()
user = require_auth(client)
user_id = user.id

# ---------------------------------------------------------------------------
# Set selector
# ---------------------------------------------------------------------------

set_display_names, set_lookup = get_active_sets(client)
selected_display = st.selectbox("Select a set", set_display_names)
set_code, csv_filename = set_lookup[selected_display]

# ---------------------------------------------------------------------------
# JS → Python bridge via localStorage.
#
# components.html() renders in an iframe with allow-same-origin, so the
# table's JS can write pending changes directly to localStorage.
# Streamlit then reads those pending changes on Save:
#
#   1. The table JS stores pending edits under the set-specific localStorage key.
#   2. Clicking Save triggers streamlit_js_eval to read that localStorage value.
#   3. The returned value causes a rerun where raw_pending contains the current
#      pending changes.
#
# streamlit_js_eval only re-evaluates its JS when the expression STRING changes.
# We embed a save_counter as a JS comment so clicking Save produces a new string
# → forces a fresh localStorage read → component sends value → triggers a rerun
# where raw_pending contains the current pending changes.
# ---------------------------------------------------------------------------

storage_key = f"rating_pending_{set_code}"
save_counter = st.session_state.get("_save_counter", 0)

# Changing the KEY on each save forces streamlit_js_eval to create a fresh
# component instance with no stale cache, so it evaluates immediately and
# sends the current localStorage value in the same rerun.
raw_pending = streamlit_js_eval(
    js_expressions=f"localStorage.getItem('{storage_key}')",
    key=f"get_pending_{set_code}_{save_counter}",
)

# ---------------------------------------------------------------------------
# Load card data and seed baseline from DB
# ---------------------------------------------------------------------------

cards_df = load_set(csv_filename, set_code)
user_ratings = get_user_ratings(client, user_id, set_code)

baseline_key = f"baseline_{user_id}_{set_code}"
if baseline_key not in st.session_state:
    st.session_state[baseline_key] = {
        cn: {"my_rating": info.get("rating"), "my_notes": info.get("notes", "")}
        for cn, info in user_ratings.items()
    }
baseline = st.session_state[baseline_key]

# ---------------------------------------------------------------------------
# Process pending changes when Save was clicked (raw_pending comes back one
# rerun after the counter changes, once streamlit_js_eval re-evaluates).
# ---------------------------------------------------------------------------

if raw_pending and raw_pending not in ("{}", "null", "", None):
    try:
        pending = json.loads(raw_pending)
    except (json.JSONDecodeError, TypeError):
        pending = {}

    for cn, data in pending.items():
        raw_rating = data.get("rating")
        edit_rating = float(raw_rating) if raw_rating is not None else None
        edit_notes = str(data.get("notes", ""))

        saved = baseline.get(cn, {})
        saved_rating = (
            float(saved["my_rating"]) if pd.notna(saved.get("my_rating")) else None
        )
        saved_notes = str(saved.get("my_notes", ""))

        if edit_rating is None and saved_rating is None:
            continue
        if edit_rating == saved_rating and edit_notes == saved_notes:
            continue

        try:
            card_name = cards_df.loc[cards_df["collector_number"] == cn, "name"].iloc[0]
            if edit_rating is None:
                delete_rating(
                    client=client,
                    user_id=user_id,
                    set_code=set_code,
                    collector_number=cn,
                )
                baseline[cn] = {"my_rating": None, "my_notes": ""}
                st.toast(f"{card_name} — rating cleared", icon="🗑️")
            else:
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
                st.toast(f"{card_name} — {edit_rating}", icon="✅")
        except Exception as e:
            st.toast(f"Failed to save {cn}: {e}", icon="❌")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

name_query = st.sidebar.text_input("Search card name", placeholder="e.g. Dragon")

rarities_in_set = [r for r in RARITY_ORDER if r in cards_df["rarity"].unique()]
selected_rarities = st.sidebar.multiselect(
    "Rarity",
    options=rarities_in_set,
    default=rarities_in_set,
)

colors_in_set = [
    c for c in COLOR_OPTIONS if cards_df["color_identity"].str.contains(c).any()
]
selected_colors = st.sidebar.multiselect(
    "Color identity (include colorless if none selected)",
    options=colors_in_set,
    format_func=lambda c: COLOR_LABELS[c],
)

rated_count = sum(1 for v in baseline.values() if pd.notna(v.get("my_rating")))
show_unrated = st.sidebar.checkbox("Show only unrated cards", value=False)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

filtered = cards_df.copy()

if name_query.strip():
    filtered = filtered[
        filtered["name"].str.contains(name_query.strip(), case=False, na=False)
    ]

if selected_rarities:
    filtered = filtered[filtered["rarity"].isin(selected_rarities)]

if selected_colors:
    color_mask = filtered["color_identity"].apply(
        lambda ci: any(c in ci for c in selected_colors)
    )
    filtered = filtered[color_mask]

if show_unrated:
    filtered = filtered[
        filtered["collector_number"].map(
            lambda cn: pd.isna(baseline.get(cn, {}).get("my_rating"))
        )
    ]

# ---------------------------------------------------------------------------
# Summary + Save button
# ---------------------------------------------------------------------------

col_cap, col_btn = st.columns([5, 1])
with col_cap:
    st.caption(
        f"**{len(filtered):,}** cards shown · "
        f"**{rated_count}** of **{len(cards_df)}** rated in {selected_display} · "
        f"Hover to zoom · Click Save Changes after rating cards"
    )
with col_btn:
    if st.button("💾 Save Changes", type="primary"):
        st.session_state["_save_counter"] = save_counter + 1
        st.rerun()

# ---------------------------------------------------------------------------
# Build ratings HTML table
# ---------------------------------------------------------------------------


def build_ratings_table(df_rows, baseline, storage_key):
    css = """
    <style>
    body { margin: 0; background: transparent; }
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
        width: 62px;
    }
    .thumb-wrap img.thumb {
        width: 60px;
        height: auto;
        border-radius: 5px;
        display: block;
    }
    .thumb-wrap .preview {
        display: none;
        position: absolute;
        left: 72px;
        top: -80px;
        width: 260px;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.9);
        z-index: 9999;
        pointer-events: none;
    }
    .thumb-wrap:hover .preview { display: block; }
    select.rating-select {
        background: #1e2130;
        color: #e0e0e0;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 13px;
        cursor: pointer;
        width: 72px;
    }
    select.rating-select:focus { outline: 1px solid #4a9eff; }
    input.notes-input {
        background: #1e2130;
        color: #e0e0e0;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 13px;
        width: 100%;
        box-sizing: border-box;
    }
    input.notes-input:focus { outline: 1px solid #4a9eff; border-color: #4a9eff; }
    </style>
    """

    # components.html() iframes have allow-same-origin, so localStorage
    # is shared with the parent frame where streamlit_js_eval reads it.
    js = f"""
    <script>
    var SK = {json.dumps(storage_key)};
    function storePending(cn, field, val) {{
        try {{
            var pending = JSON.parse(localStorage.getItem(SK) || '{{}}');
            if (!pending[cn]) pending[cn] = {{}};
            pending[cn][field] = val;
            localStorage.setItem(SK, JSON.stringify(pending));
            console.log('[Ratings] storePending', cn, field, val, JSON.parse(localStorage.getItem(SK)));
        }} catch(e) {{ console.error('[Ratings] storePending error', e); }}
    }}
    </script>
    """

    headers = ["Card", "#", "Name", "Mana", "Type", "Rarity", "My Rating", "My Notes"]
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"

    rows = []
    for _, r in df_rows.iterrows():
        cn = str(r["collector_number"])
        saved = baseline.get(cn, {})
        current_rating = saved.get("my_rating")
        current_notes = saved.get("my_notes") or ""

        thumb = r.get("image_small", "")
        normal = r.get("image_normal", "")
        if thumb:
            img_html = (
                '<div class="thumb-wrap">'
                f'<img class="thumb" src="{thumb}" loading="lazy">'
                f'<img class="preview" src="{normal}" loading="lazy">'
                "</div>"
            )
        else:
            img_html = ""

        # cn passed via data-cn attribute — avoids quote conflict between
        # json.dumps(cn)'s double quotes and the onchange="..." delimiter.
        safe_cn = html.escape(cn, quote=True)
        opts = '<option value="">—</option>'
        for opt in RATING_OPTIONS:
            sel = (
                "selected"
                if current_rating is not None
                and abs(float(current_rating) - opt) < 0.01
                else ""
            )
            opts += f'<option value="{opt}" {sel}>{opt}</option>'
        rating_cell = (
            f'<select class="rating-select" data-cn="{safe_cn}" '
            f"onchange=\"storePending(this.dataset.cn, 'rating', "
            f"this.value === '' ? null : parseFloat(this.value))\">"
            f"{opts}</select>"
        )

        safe_notes = html.escape(current_notes, quote=True)
        notes_cell = (
            f'<input class="notes-input" type="text" value="{safe_notes}" '
            f'data-cn="{safe_cn}" '
            f"onblur=\"storePending(this.dataset.cn, 'notes', this.value)\">"
        )

        rows.append(
            "<tr>"
            f"<td>{img_html}</td>"
            f"<td style='white-space:nowrap'>{html.escape(cn)}</td>"
            f"<td><b>{html.escape(str(r['name']))}</b></td>"
            f"<td style='white-space:nowrap'>{html.escape(str(r['mana_cost']))}</td>"
            f"<td style='white-space:nowrap;font-size:11px'>{html.escape(str(r['type_line']))}</td>"
            f"<td style='white-space:nowrap'>{html.escape(str(r['rarity']).capitalize())}</td>"
            f"<td>{rating_cell}</td>"
            f"<td>{notes_cell}</td>"
            "</tr>"
        )

    tbody = "\n".join(rows)
    return (
        css
        + js
        + "<div style='overflow-x:auto'>"
        + "<table class='card-table'>"
        + f"<thead>{thead}</thead>"
        + f"<tbody>{tbody}</tbody>"
        + "</table></div>"
    )


components.html(
    build_ratings_table(filtered, baseline, storage_key),
    height=750,
    scrolling=True,
)
