import requests
import pandas as pd


# --- Basic building blocks for pulling data from 17 Lands from Claude ---
url = "https://www.17lands.com/card_ratings/data"
params = {
    "expansion": "TMT",
    "format": "PremierDraft",
    "start_date": "2026-03-03",
    "end_date": "2026-04-17",  # today or your desired end date
}

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, params=params, headers=headers)
data = response.json()

df = pd.DataFrame(data)
print(df.head())
df.to_csv("17lands_tmt.csv", index=False)