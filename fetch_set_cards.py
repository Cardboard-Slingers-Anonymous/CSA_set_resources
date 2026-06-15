"""
Fetches card lists for the 10 most recent MTG Arena sets from Scryfall API
and saves each as a CSV file.
"""

import json
import csv
import time
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# 10 most recent main Arena sets as of April 2026, newest first
SETS = [
    ("msh", "Marvel_Super_Heroes"),
    ("sos", "Secrets_of_Strixhaven"),
    ("tmt", "MTG_TeenageMutantNinjaTurtles"),
    ("tla", "Avatar_TheLastAirbender"),
    ("om1", "Through_the_Omenpaths"),
    ("eoe", "Edge_of_Eternities"),
    ("fin", "Final_Fantasy"),
    ("ecl", "Lorwyn_Eclipsed"),
    ("tdm", "Tarkir_Dragonstorm"),
    ("dft", "Aetherdrift"),
    ("inr", "Innistrad_Remastered"),
    ("fdn", "MTG_Foundations"),
    ("dsk", "Duskmourn_House_of_Horror"),
    ("blb", "Bloomburrow"),
]

FIELDS = [
    "collector_number",
    "name",
    "mana_cost",
    "cmc",
    "type_line",
    "rarity",
    "colors",
    "color_identity",
    "oracle_text",
    "power",
    "toughness",
    "loyalty",
    "keywords",
    "set_name",
    "released_at",
    "scryfall_uri",
]


def fetch_cards_for_set(set_code):
    """Fetches all cards for a given set code via Scryfall search API."""
    cards = []
    import urllib.parse
    import urllib.request

    query = f"set:{set_code}"
    encoded_q = urllib.parse.quote(query)
    url = f"https://api.scryfall.com/cards/search?q={encoded_q}&order=set&unique=cards"
    while url:
        print(f"  Fetching: {url[:80]}...")
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ProjectDepot/1.0 (github.com/djsmith17)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:  # nosec B310 - URL is always HTTPS (api.scryfall.com)
            data = json.loads(resp.read().decode())
        cards.extend(data.get("data", []))
        url = data.get("next_page") if data.get("has_more") else None
        if url:
            time.sleep(0.12)  # Scryfall rate limit: max 10 req/s
    return cards


def flatten_card(card):
    """Extracts flat fields from a card object."""
    row = {}
    for field in FIELDS:
        val = card.get(field, "")
        if isinstance(val, list):
            val = ", ".join(val)
        row[field] = val if val is not None else ""
    return row


def save_csv(set_code, filename, cards):
    """Saves a list of card dicts to a CSV file."""
    path = os.path.join(OUTPUT_DIR, f"{filename}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for card in cards:
            writer.writerow(flatten_card(card))
    print(f"  Saved {len(cards)} cards -> {path}")
    return len(cards)


def main():
    total = 0
    for set_code, filename in SETS:
        print(f"\n=== Fetching set: {set_code} ({filename}) ===")
        try:
            cards = fetch_cards_for_set(set_code)
            count = save_csv(set_code, filename, cards)
            total += count
        except Exception as e:
            print(f"  ERROR fetching {set_code}: {e}")
        time.sleep(0.2)
    print(f"\nDone! Total cards written: {total}")


if __name__ == "__main__":
    main()
