"""
Ratings Dashboard — auth-gated.
Per-user rating histograms and a sortable community summary table.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
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

cards_df  = load_set(csv_filename, set_code)[["collector_number", "name", "rarity", "type_line", "colors"]]
ratings_df = get_all_ratings_for_set(client, set_code)

if ratings_df.empty:
    st.info("No ratings yet for this set. Head to the Ratings page to get started.")
    st.stop()

# Resolve display name for each user_id
user_labels = {uid: f"User {i+1}" for i, uid in enumerate(ratings_df["user_id"].unique())}
# Label the current user as "You"
user_labels[user.id] = "You"
ratings_df["user_label"] = ratings_df["user_id"].map(user_labels)

# ---------------------------------------------------------------------------
# Per-user rating histograms
# ---------------------------------------------------------------------------

st.subheader("Rating distributions by user")

users = ratings_df["user_label"].unique()
cols  = st.columns(len(users))

for col, user_label in zip(cols, users):
    user_data = ratings_df[ratings_df["user_label"] == user_label]["rating"].dropna()
    counts = {b: 0 for b in RATING_BINS}
    for val in user_data:
        rounded = round(val * 2) / 2
        if rounded in counts:
            counts[rounded] += 1

    fig = go.Figure(go.Bar(
        x=[str(k) for k in counts.keys()],
        y=list(counts.values()),
        marker_color="#5b8dee",
    ))
    fig.update_layout(
        title=user_label,
        xaxis_title="Rating",
        yaxis_title="# Cards",
        margin=dict(l=20, r=20, t=40, b=40),
        height=280,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font_color="#e0e0e0",
    )
    col.plotly_chart(fig, use_container_width=True)

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

st.dataframe(
    filtered_summary[[
        "collector_number", "name", "rarity", "type_line",
        "rating_count", "avg_rating", "contentiousness", "my_rating",
    ]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "collector_number": st.column_config.TextColumn("#", width="small"),
        "name":             st.column_config.TextColumn("Name"),
        "rarity":           st.column_config.TextColumn("Rarity", width="small"),
        "type_line":        st.column_config.TextColumn("Type"),
        "rating_count":     st.column_config.NumberColumn("# Ratings", width="small"),
        "avg_rating":       st.column_config.NumberColumn("Avg Rating", format="%.2f", width="small"),
        "contentiousness":  st.column_config.NumberColumn(
            "Contentiousness",
            help="Standard deviation of ratings — higher means more disagreement.",
            format="%.2f",
            width="small",
        ),
        "my_rating":        st.column_config.NumberColumn("My Rating", format="%.1f", width="small"),
    },
)
