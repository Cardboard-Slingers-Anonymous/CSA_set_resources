"""
MTGA Set Card Viewer
Public page — no authentication required.
"""

import streamlit as st
from set_data import (
    RARITY_ORDER,
    COLOR_OPTIONS,
    COLOR_LABELS,
    get_active_sets,
    load_set,
)
from supabase_client import get_client

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTGA Card Viewer",
    page_icon="🃏",
    layout="wide",
)

st.title("🃏 MTGA Set Card Viewer")

# ---------------------------------------------------------------------------
# Set selector
# ---------------------------------------------------------------------------

try:
    client = get_client()
    set_display_names, set_lookup = get_active_sets(client)
except Exception:
    from set_data import SET_DISPLAY_NAMES, SET_LOOKUP

    set_display_names, set_lookup = SET_DISPLAY_NAMES, SET_LOOKUP
selected_display = st.selectbox("Select a set", set_display_names)
set_code, csv_filename = set_lookup[selected_display]
df = load_set(csv_filename, set_code)

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

name_query = st.sidebar.text_input("Search card name", placeholder="e.g. Dragon")

rarities_in_set = [r for r in RARITY_ORDER if r in df["rarity"].unique()]
selected_rarities = st.sidebar.multiselect(
    "Rarity",
    options=rarities_in_set,
    default=rarities_in_set,
)

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

# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------

st.caption(
    f"**{len(filtered):,}** cards shown "
    f"({'all' if len(filtered) == len(df) else f'{len(df):,} total'}) "
    f"· Set: {selected_display}"
)

# ---------------------------------------------------------------------------
# HTML table with CSS hover-to-preview
# ---------------------------------------------------------------------------


def build_html_table(df_rows):
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
        width: 62px;
    }
    .thumb-wrap img.thumb {
        width: 60px;
        height: auto;
        border-radius: 5px;
        display: block;
        cursor: default;
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
    .card-table a { color: #d4a017; text-decoration: none; }
    .card-table a:hover { text-decoration: underline; }
    </style>
    """

    headers = [
        "Card",
        "#",
        "Name",
        "Mana",
        "CMC",
        "Type",
        "Rarity",
        "Colors",
        "Rules Text",
        "P / T",
        "Keywords",
        "Scryfall",
    ]
    thead = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"

    rows = []
    for _, r in df_rows.iterrows():
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

        if r["power"] or r["toughness"]:
            pt = f"{r['power']} / {r['toughness']}"
        elif r["loyalty"]:
            pt = f"\u2605 {r['loyalty']}"
        else:
            pt = ""

        oracle = (
            r["oracle_text"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", " \u00b7 ")
        )
        if len(oracle) > 200:
            oracle = oracle[:197] + "\u2026"

        link = (
            f'<a href="{r["scryfall_uri"]}" target="_blank">View ↗</a>'
            if r["scryfall_uri"]
            else ""
        )

        rows.append(
            "<tr>"
            f"<td>{img_html}</td>"
            f"<td style='white-space:nowrap'>{r['collector_number']}</td>"
            f"<td><b>{r['name']}</b></td>"
            f"<td style='white-space:nowrap'>{r['mana_cost']}</td>"
            f"<td>{r['cmc']}</td>"
            f"<td style='white-space:nowrap'>{r['type_line']}</td>"
            f"<td style='white-space:nowrap'>{r['rarity'].capitalize()}</td>"
            f"<td>{r['colors']}</td>"
            f"<td style='font-size:11px;max-width:280px'>{oracle}</td>"
            f"<td style='white-space:nowrap'>{pt}</td>"
            f"<td style='font-size:11px'>{r['keywords']}</td>"
            f"<td>{link}</td>"
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


st.html(f'<div style="height:750px;overflow:auto">{build_html_table(filtered)}</div>')
