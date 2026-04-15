"""
Shared set configuration and card data loader.
Imported by both the Viewer and Ratings pages.
"""

import os
import pandas as pd
import streamlit as st

SETS = [
    ("sos", "Secrets_of_Strixhaven",        "Secrets of Strixhaven"),
    ("tmt", "MTG_TeenageMutantNinjaTurtles", "Teenage Mutant Ninja Turtles"),
    ("ecl", "Lorwyn_Eclipsed",               "Lorwyn Eclipsed"),
    ("tla", "Avatar_TheLastAirbender",       "Avatar: The Last Airbender"),
    ("om1", "Through_the_Omenpaths",         "Through the Omenpaths"),
    ("eoe", "Edge_of_Eternities",            "Edge of Eternities"),
    ("fin", "Final_Fantasy",                 "Final Fantasy"),
    ("tdm", "Tarkir_Dragonstorm",            "Tarkir: Dragonstorm"),
    ("dft", "Aetherdrift",                   "Aetherdrift"),
    ("inr", "Innistrad_Remastered",          "Innistrad Remastered"),
    ("fdn", "MTG_Foundations",               "MTG Foundations"),
    ("dsk", "Duskmourn_House_of_Horror",     "Duskmourn: House of Horror"),
    ("blb", "Bloomburrow",                   "Bloomburrow"),
]

SET_DISPLAY_NAMES = [display for _, _, display in SETS]
SET_LOOKUP = {display: (code, fname) for code, fname, display in SETS}

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
