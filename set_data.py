"""
Shared set configuration and card data loader.
Imported by both the Viewer and Ratings pages.

Set list is now driven by the `sets` table in Supabase (included_in_app = TRUE).
The SETS list below is kept as a fallback for local development without a live
database connection, and also seeds the initial state of the table.
"""

import os
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Fallback / seed list — mirrors the `sets` table seed in
# supabase/migrations/01_create_sets_table.sql.
# Tuple order: (set_code, csv_filename, display_name)
# ---------------------------------------------------------------------------
SETS = [
    ("blb", "Bloomburrow",                   "Bloomburrow"),
    ("dsk", "Duskmourn_House_of_Horror",     "Duskmourn: House of Horror"),
    ("fdn", "MTG_Foundations",               "MTG Foundations"),
    ("inr", "Innistrad_Remastered",          "Innistrad Remastered"),
    ("dft", "Aetherdrift",                   "Aetherdrift"),
    ("tdm", "Tarkir_Dragonstorm",            "Tarkir: Dragonstorm"),
    ("fin", "Final_Fantasy",                 "Final Fantasy"),
    ("eoe", "Edge_of_Eternities",            "Edge of Eternities"),
    ("om1", "Through_the_Omenpaths",         "Through the Omenpaths"),
    ("tla", "Avatar_TheLastAirbender",       "Avatar: The Last Airbender"),
    ("ecl", "Lorwyn_Eclipsed",               "Lorwyn Eclipsed"),
    ("tmt", "MTG_TeenageMutantNinjaTurtles", "Teenage Mutant Ninja Turtles"),
    ("sos", "Secrets_of_Strixhaven",         "Secrets of Strixhaven"),
]

# Module-level constants built from the fallback list.
# Pages that have a Supabase client available should call get_active_sets()
# instead to get the live, database-driven list.
SET_DISPLAY_NAMES = [display for _, _, display in SETS]
SET_LOOKUP = {display: (code, fname) for code, fname, display in SETS}


@st.cache_data(ttl=3600)  # Refresh at most once per hour
def get_active_sets(_client) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """Return (display_names, lookup) for sets where included_in_app is TRUE.

    Fetches from the `sets` Supabase table ordered by release date (newest
    first).  Falls back to the hardcoded SETS list on any error so the app
    continues to work during outages or local development without a live DB.

    The leading underscore on `_client` tells Streamlit's @st.cache_data
    decorator to exclude it from the cache key, which is intentional — the
    client is stateful and not hashable.

    Returns
    -------
    display_names : list[str]
        Ordered list of set names for the UI selectbox.
    lookup : dict[str, tuple[str, str]]
        Maps display_name → (set_code, csv_filename).
    """
    try:
        resp = (
            _client.table("sets")
            .select("set_code, csv_filename, display_name, set_name")
            .eq("included_in_app", True)
            .not_.is_("csv_filename", "null")
            .order("released_at", desc=True)
            .execute()
        )
        rows = resp.data
        if not rows:
            raise ValueError("No active sets returned from database.")

        active: list[tuple[str, str, str]] = [
            (
                row["set_code"],
                row["csv_filename"],
                row["display_name"] or row["set_name"],
            )
            for row in rows
        ]
    except Exception:
        # Graceful fallback so a DB hiccup never breaks the whole app.
        active = SETS

    display_names = [display for _, _, display in active]
    lookup = {display: (code, fname) for code, fname, display in active}
    return display_names, lookup

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

RARITY_ORDER  = ["common", "uncommon", "rare", "mythic"]
COLOR_OPTIONS = ["W", "U", "B", "R", "G"]
COLOR_LABELS  = {
    "W": "White (W)",
    "U": "Blue (U)",
    "B": "Black (B)",
    "R": "Red (R)",
    "G": "Green (G)",
}


@st.cache_data
def load_set(csv_filename: str, set_code: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{csv_filename}.csv")
    df = pd.read_csv(path, dtype=str).fillna("")
    df["image_small"] = df["collector_number"].apply(
        lambda n: f"https://api.scryfall.com/cards/{set_code}/{n}?format=image&version=small"
        if n else ""
    )
    df["image_normal"] = df["collector_number"].apply(
        lambda n: f"https://api.scryfall.com/cards/{set_code}/{n}?format=image&version=normal"
        if n else ""
    )
    return df
