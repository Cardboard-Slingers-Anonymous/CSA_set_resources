"""
Ratings Dashboard — auth-gated.
Per-user rating histograms and a sortable community summary table.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from auth import require_auth
from ratings_db import get_all_ratings_for_set
from set_data import SET_DISPLAY_NAMES, SET_LOOKUP, RARITY_ORDER, load_set
from supabase_client import get_client

RATING_BINS   = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
RARITY_COLORS = {
    "common":   "#c0c0c0",
    "uncommon": "#7fbfff",
    "rare":     "#e6c84a",
    "mythic":   "#e87c3e",
}

# ---------------------------------------------------------------------------
# Page setup & auth
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Ratings Dashboard", page_icon="📊", layout="wide")

client = get_client()
user   = require_auth(client)

# ---------------------------------------------------------------------------
# Set selector
# ---------------------------------------------------------------------------

st.title("📊 Ratings Dashboard")

selected_display = st.selectbox("Select a set", SET_DISPLAY_NAMES)
set_code, csv_filename = SET_LOOKUP[selected_display]

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

cards_df  = load_set(csv_filename, set_code)[["collector_number", "name", "rarity",
                                              "type_line", "colors", "image_small", "image_normal"]]  # Load set and keep only needed columns
ratings_df = get_all_ratings_for_set(client, set_code)                                                # Fetch all ratings for this set from the DB
if ratings_df.empty:
    st.info("No ratings yet for this set. Head to the Ratings page to get started.")
    st.stop()                                                                               # Halt execution if there's nothing to display
user_labels = {uid: f"User {i+1}" for i, uid in enumerate(ratings_df["user_id"].unique())}  # Assign anonymous labels to each user_id
user_labels[user.id] = "You"                                                                # Override current user's label with "You"
ratings_df["user_label"] = ratings_df["user_id"].map(user_labels)                           # Add display name column to dataframe

# ---------------------------------------------------------------------------
# Per-user rating histograms
# ---------------------------------------------------------------------------

st.subheader("Rating distributions by user")

users = ratings_df["user_label"].unique()          # All unique users in the dataset
#cols  = st.columns(len(users))                    # One column per user for side-by-side charts
cols = st.columns(2) # set a left and right column
user_data = ratings_df[ratings_df["user_label"] == user_labels[user.id]]["rating"].dropna()

def _draw_chart(user_name, data_to_draw, col_for_chart):
    """
    Draws a histogram figure on the dashboard
        user_name: name of the user being drawn (or the figure label)
        data_to_draw: dataframe containing the data to be plotted
        col_for_chart: column to draw chart on
    """
    # --- initialize bins to count each rating ---
    counts = {b: 0 for b in RATING_BINS}           # Initialize bin counts to 0

    # --- Round any ratings just in case they're magically not on the .5 scale  ---
    for val in data_to_draw:
        rounded = round(val * 2) / 2               # Snap value to nearest 0.5
        if rounded in counts:
            counts[rounded] += 1                   # Increment matching bin

    # --- Draw the figure ---
    fig = go.Figure(go.Bar(
        x=[str(k) for k in counts.keys()],         # Bin labels as strings
        y=list(counts.values()),                   # Counts as bar heights
        marker_color=dict(color="#5b8dee"),        # Blue bars cast as a plotly type to match stubs
    ))

    # --- Update the figure layout ---
    fig.update_layout(
        title=user_name,                          # Chart title = user label
        xaxis_title="Rating",
        yaxis_title="# Cards",
        margin=dict(l=20, r=20, t=40, b=40),       # Tight margins
        height=280,
        plot_bgcolor="#0e1117",                    # Dark plot background
        paper_bgcolor="#0e1117",                   # Dark paper background
        font_color="#e0e0e0",                      # Light text
    )

    col_for_chart.plotly_chart(fig, use_container_width=True)  # Render chart in its column

_draw_chart(user_labels[user.id],user_data,cols[1])
_draw_chart(user_labels[user.id],user_data,cols[2])

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

st.subheader("Card summary")

# Aggregate ratings per card
agg = (
    ratings_df.groupby("collector_number")["rating"]
    .agg(
        rating_count="count",
        avg_rating="mean",
        contentiousness="std",
    )
    .reset_index()
)
agg["avg_rating"]      = agg["avg_rating"].round(2)
agg["contentiousness"] = agg["contentiousness"].round(2).fillna(0.0)

# Add the current user's rating for context
my_ratings = (
    ratings_df[ratings_df["user_id"] == user.id][["collector_number", "rating"]]
    .rename(columns={"rating": "my_rating"})
)

summary = (
    cards_df
    .merge(agg, on="collector_number", how="left")
    .merge(my_ratings, on="collector_number", how="left")
)
summary["rating_count"]   = summary["rating_count"].fillna(0).astype(int)
summary["avg_rating"]     = pd.to_numeric(summary["avg_rating"],     errors="coerce")
summary["contentiousness"]= pd.to_numeric(summary["contentiousness"],errors="coerce")
summary["my_rating"]      = pd.to_numeric(summary["my_rating"],      errors="coerce")

# ---------------------------------------------------------------------------
# Summary table filters
# ---------------------------------------------------------------------------

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    selected_rarities = st.multiselect(
        "Rarity",
        options=[r for r in RARITY_ORDER if r in summary["rarity"].unique()],
        default=[r for r in RARITY_ORDER if r in summary["rarity"].unique()],
    )

with filter_col2:
    min_ratings = st.slider(
        "Minimum # of ratings",
        min_value=0,
        max_value=int(summary["rating_count"].max()) if summary["rating_count"].max() > 0 else 1,
        value=0,
    )

with filter_col3:
    show_contested = st.checkbox("Contested cards only (std dev ≥ 1.0)", value=False)

filtered_summary = summary.copy()

if selected_rarities:
    filtered_summary = filtered_summary[filtered_summary["rarity"].isin(selected_rarities)]

filtered_summary = filtered_summary[filtered_summary["rating_count"] >= min_ratings]

if show_contested:
    filtered_summary = filtered_summary[filtered_summary["contentiousness"] >= 1.0]

# ---------------------------------------------------------------------------
# Render summary table
# ---------------------------------------------------------------------------

st.caption(f"**{len(filtered_summary):,}** cards · {selected_display}")


def build_summary_html_table(df_rows):
    css = """
    <style>
    .sum-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }
    .sum-table th {
        background: #0e1117;
        color: #fafafa;
        padding: 8px 10px;
        text-align: left;
        border-bottom: 2px solid #444;
        white-space: nowrap;
        position: sticky;
        top: 0;
        z-index: 10;
        cursor: pointer;
        user-select: none;
    }
    .sum-table th:hover { background: #1a1f2e; }
    .sum-table th .sort-arrow { margin-left: 4px; opacity: 0.4; font-size: 10px; }
    .sum-table th.asc .sort-arrow::after  { content: "▲"; opacity: 1; }
    .sum-table th.desc .sort-arrow::after { content: "▼"; opacity: 1; }
    .sum-table th:not(.asc):not(.desc) .sort-arrow::after { content: "⇅"; }
    .sum-table td {
        padding: 6px 10px;
        border-bottom: 1px solid #2a2a2a;
        vertical-align: middle;
        color: #e0e0e0;
    }
    .sum-table tr:hover td { background: #1a1f2e; }
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
    </style>
    """

    js = """
    <script>
    (function() {
        function getVal(td, isNum) {
            var t = td.getAttribute('data-val') || td.innerText.trim();
            if (isNum) { var n = parseFloat(t); return isNaN(n) ? -Infinity : n; }
            return t.toLowerCase();
        }
        function sortTable(th) {
            var table = th.closest('table');
            var tbody = table.querySelector('tbody');
            var ths   = Array.from(table.querySelectorAll('thead th'));
            var col   = ths.indexOf(th);
            var isNum = th.getAttribute('data-type') === 'num';
            var asc   = !th.classList.contains('asc');
            ths.forEach(function(h) { h.classList.remove('asc', 'desc'); });
            th.classList.add(asc ? 'asc' : 'desc');
            var rows = Array.from(tbody.querySelectorAll('tr'));
            rows.sort(function(a, b) {
                var va = getVal(a.cells[col], isNum);
                var vb = getVal(b.cells[col], isNum);
                if (va < vb) return asc ? -1 : 1;
                if (va > vb) return asc ? 1 : -1;
                return 0;
            });
            rows.forEach(function(r) { tbody.appendChild(r); });
        }
        document.querySelectorAll('.sum-table thead th').forEach(function(th) {
            th.addEventListener('click', function() { sortTable(th); });
        });
    })();
    </script>
    """

    col_defs = [
        ("Card",           "",               False),
        ("#",              "collector_number", False),
        ("Name",           "name",            False),
        ("Rarity",         "rarity",          False),
        ("Type",           "type_line",       False),
        ("# Ratings",      "rating_count",    True),
        ("Avg Rating",     "avg_rating",      True),
        ("Contentiousness","contentiousness", True),
        ("My Rating",      "my_rating",       True),
    ]

    thead_cells = []
    for label, _, is_num in col_defs:
        dtype = 'num' if is_num else 'str'
        thead_cells.append(
            f'<th data-type="{dtype}">{label}<span class="sort-arrow"></span></th>'
        )
    thead = "<tr>" + "".join(thead_cells) + "</tr>"

    def fmt_num(val, decimals=2):
        try:
            f = float(val)
            if pd.isna(f):
                return '<td data-val="-1">—</td>'
            return f'<td data-val="{f}">{f:.{decimals}f}</td>'
        except (TypeError, ValueError):
            return '<td data-val="-1">—</td>'

    rows = []
    for _, r in df_rows.iterrows():
        thumb  = r.get("image_small", "")
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

        rows.append(
            "<tr>"
            f"<td>{img_html}</td>"
            f"<td style='white-space:nowrap'>{r['collector_number']}</td>"
            f"<td><b>{r['name']}</b></td>"
            f"<td style='white-space:nowrap'>{r['rarity'].capitalize()}</td>"
            f"<td style='white-space:nowrap'>{r['type_line']}</td>"
            f"<td>{int(r['rating_count'])}</td>"
            + fmt_num(r['avg_rating'], 2)
            + fmt_num(r['contentiousness'], 2)
            + fmt_num(r['my_rating'], 1)
            + "</tr>"
        )

    tbody = "\n".join(rows)
    return (
        f"{css}"
        "<div style='overflow-x:auto;'>"
        "<table class='sum-table'>"
        f"<thead>{thead}</thead>"
        f"<tbody>{tbody}</tbody>"
        "</table>"
        "</div>"
        f"{js}"
    )


components.html(build_summary_html_table(filtered_summary), height=750, scrolling=True)
