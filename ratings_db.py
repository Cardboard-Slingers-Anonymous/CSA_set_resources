"""
Database helpers for the ratings table.
All aggregation is done client-side in pandas.
"""

import pandas as pd
from supabase import Client


def get_user_ratings(client: Client, user_id: str, set_code: str) -> dict:
    """
    Returns the logged-in user's ratings for a set.
    Shape: {collector_number: {"rating": float, "notes": str}}
    """
    response = (
        client.table("ratings")
        .select("collector_number, rating, notes")
        .eq("user_id", user_id)
        .eq("set_code", set_code)
        .execute()
    )
    return {
        row["collector_number"]: {"rating": row["rating"], "notes": row["notes"]}
        for row in response.data
    }


def get_community_ratings(client: Client, set_code: str) -> dict:
    """
    Returns aggregated community ratings for a set.
    Shape: {collector_number: {"avg_rating": float, "count": int}}
    """
    response = (
        client.table("ratings")
        .select("collector_number, rating")
        .eq("set_code", set_code)
        .execute()
    )
    if not response.data:
        return {}

    df = pd.DataFrame(response.data)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    agg = df.groupby("collector_number")["rating"].agg(["mean", "count"])
    return {
        cn: {"avg_rating": round(row["mean"], 2), "count": int(row["count"])}
        for cn, row in agg.iterrows()
    }


def get_all_ratings_for_set(client: Client, set_code: str) -> pd.DataFrame:
    """
    Returns all ratings rows for a set as a DataFrame.
    Used by the Dashboard page for per-user histograms and summary tables.
    Columns: user_id, collector_number, card_name, rating, notes
    """
    response = (
        client.table("ratings")
        .select("user_id, collector_number, card_name, rating, notes")
        .eq("set_code", set_code)
        .execute()
    )
    if not response.data:
        return pd.DataFrame(columns=["user_id", "collector_number", "card_name", "rating", "notes"])

    df = pd.DataFrame(response.data)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    return df


def upsert_rating(
    client: Client,
    user_id: str,
    set_code: str,
    collector_number: str,
    card_name: str,
    rating: float,
    notes: str,
) -> None:
    """
    Insert or update a single card rating for the logged-in user.
    The unique constraint on (user_id, set_code, collector_number) handles deduplication.
    """
    client.table("ratings").upsert(
        {
            "user_id": user_id,
            "set_code": set_code,
            "collector_number": collector_number,
            "card_name": card_name,
            "rating": rating,
            "notes": notes,
        },
        on_conflict="user_id,set_code,collector_number",
    ).execute()
