"""
Card Ratings page — auth-gated.
Hover over any card image to zoom. Single-click to change ratings inline.
Ratings auto-save on any filter interaction; click Save Changes to save immediately.
"""

import html
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

from auth import require_auth
from ratings_db import get_user_ratings, upsert_rating
from set_data import (
    COLOR_LABELS, COLOR_OPTIONS, RARITY_ORDER,
    SET_DISPLAY_NAMES, SET_LOOKUP, load_set,
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
# Set selector (must come before sessionStorage key is constructed)
# ---------------------------------------------------------------------------

selected_display = st.selectbox("Select a set", SET_DISPLAY_NAMES)
set_code, csv_filename = SET_LOOKUP[selected_display]

# ---------------------------------------------------------------------------
# Read pending changes from the browser's sessionStorage.
# Key is scoped to set_code so switching sets never mixes pending changes.
# streamlit_js_eval fires on every rerun and returns the current value.
# ---------------------------------------------------------------------------

storage_key = f"rating_pending_{set_code}"
raw_pending = streamlit_js_eval(
    js_expressions=f"window.parent.sessionStorage.getItem('{storage_key}') || '{{}}'",
    key=f"get_pending_{set_code}",
)

# ---------------------------------------------------------------------------
# Load card data and seed baseline from DB
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

# ---------------------------------------------------------------------------
# Auto-save: process any pending changes collected since the last rerun.
# The diff check makes this idempotent — already-saved rows are skipped.
# ---------------------------------------------------------------------------

if raw_pending and raw_pending not in ("{}", "null", ""):
    try:
        pending = json.loads(raw_pending)
    except (json.JSONDecodeError, TypeError):
        pending = {}

    for cn, data in pending.items():
        raw_rating = data.get("rating")
        edit_rating = float(raw_rating) if raw_rating is not None else None
        edit_notes  = str(data.get("notes", ""))

        saved        = baseline.get(cn, {})
        saved_rating = float(saved["my_rating"]) if pd.notna(saved.get("my_rating")) else None
        saved_notes  = str(saved.get("my_notes", ""))

        if edit_rating is None:
            continue
        if edit_rating == saved_rating and edit_notes == saved_notes:
            continue

        try:
            card_name = cards_df.loc[cards_df["collector_number"] == cn, "name"].iloc[0]
            upsert_rating(
                client=client, user_id=user_id, set_code=set_code,
                collector_number=cn, card_name=card_name,
                rating=edit_rating, notes=edit_notes,
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
    "Rarity", options=rarities_in_set, default=rarities_in_set,
)

colors_in_set = [c for c in COLOR_OPTIONS if cards_df["color_identity"].str.contains(c).any()]
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
    filtered = filtered[filtered["name"].str.contains(name_query.strip(), case=False, na=False)]

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
        f"Hover to zoom · Changes save on filter interaction or Save button"
    )
with col_btn:
    st.button("💾 Save Changes", type="primary")

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

    # JS: stores changes into window.parent.sessionStorage under the set-scoped key.
    # Both rating (onchange) and notes (onblur) merge into the same pending object.
    js = f"""
    <script>
    var SK = {json.dumps(storage_key)};
    function storePending(cn, field, val) {{
        try {{
            var pending = JSON.parse(window.parent.sessionStorage.getItem(SK) || '{{}}');
            if (!pending[cn]) pending[cn] = {{}};
            pending[cn][field] = val;
            window.parent.sessionStorage.setItem(SK, JSON.stringify(pending));
        }} catch(e) {{}}
    }}
    </script>
    """

    headers = ["Card", "#", "Name", "Mana", "Type", "Rarity", "My Rating", "My Notes"]
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"

    rows = []
    for _, r in df_rows.iterrows():
        cn = str(r["collector_number"])
        saved           = baseline.get(cn, {})
        current_rating  = saved.get("my_rating")
        current_notes   = saved.get("my_notes") or ""

        # Image hover-to-zoom
        thumb  = r.get("image_small", "")
        normal = r.get("image_normal", "")
        if thumb:
            img_html = (
                '<div class="thumb-wrap">'
                f'<img class="thumb" src="{thumb}" loading="lazy">'
                f'<img class="preview" src="{normal}" loading="lazy">'
                '</div>'
            )
        else:
            img_html = ""

        # Rating <select>: safe because options are numeric constants, cn is HTML-escaped
        safe_cn = html.escape(cn, quote=True)
        opts = '<option value="">—</option>'
        for opt in RATING_OPTIONS:
            sel = "selected" if current_rating is not None and abs(float(current_rating) - opt) < 0.01 else ""
            opts += f'<option value="{opt}" {sel}>{opt}</option>'
        rating_cell = (
            f'<select class="rating-select" '
            f'onchange="storePending({json.dumps(cn)}, \'rating\', '
            f'this.value === \'\' ? null : parseFloat(this.value))">'
            f'{opts}</select>'
        )

        # Notes <input>: value attribute uses HTML-escaped content
        safe_notes = html.escape(current_notes, quote=True)
        notes_cell = (
            f'<input class="notes-input" type="text" value="{safe_notes}" '
            f'onblur="storePending({json.dumps(cn)}, \'notes\', this.value)">'
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
        css + js
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
