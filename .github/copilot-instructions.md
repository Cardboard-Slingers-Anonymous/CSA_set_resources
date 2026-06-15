# GitHub Copilot Instructions — CSA Set Resources

## Project Overview

A hosted Streamlit web app for community-driven **Magic: The Gathering Arena (MTGA) card ratings**, focused on the **Limited format** (draft/sealed). Users browse cards by set, rate them on a 0–5 scale (in 0.5 increments), and view aggregated community statistics.

**Live app:** https://csa-set-resources.streamlit.app/
**Repo:** Cardboard-Slingers-Anonymous/CSA_set_resources

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI framework | Streamlit (`streamlit>=1.56`) |
| Backend / DB | Supabase (Postgres) |
| Auth | Supabase Auth — Email OTP + OAuth (Google, GitHub) via PKCE |
| Data processing | pandas |
| Charts | Plotly (`plotly.graph_objects`) |
| Card images | Scryfall REST API (fetched at runtime by URL) |
| Deployment | Streamlit Cloud |
| Language | Python 3 |

---

## Repository Structure

```
app.py                  # Entry point: page navigation + persistent auth widget
auth.py                 # Supabase auth helpers (PKCE OAuth, OTP, require_auth)
supabase_client.py      # Supabase client factory (per-session in st.session_state)
ratings_db.py           # DB helpers: upsert/delete/fetch ratings
set_data.py             # Set registry, card CSV loader (@st.cache_data)
fetch_set_cards.py      # One-off script: pull card lists from Scryfall → CSV
requirements.txt        # Python dependencies
data/                   # CSV card data per set (fetched via fetch_set_cards.py)
pages/
    1_Viewer.py         # Public: browse and filter cards by set
    2_Ratings.py        # Auth-gated: rate cards; changes persisted to Supabase
    3_Dashboard.py      # Auth-gated: per-user histograms + community summary table
```

---

## Key Conventions

### Authentication
- **Always** use `require_auth(client)` at the top of any auth-gated page. It returns the Supabase `user` object or calls `st.stop()`.
- `handle_oauth_callback(client)` must be called in `app.py` before `pg.run()` so PKCE codes are exchanged on every page, including public ones.
- The authenticated user is stored in `st.session_state["user"]`.
- The Supabase client is stored in `st.session_state["supabase_client"]` (not `st.cache_resource`) to keep each user's PKCE state isolated.
- Auth is implemented with `flow_type="pkce"`. The PKCE `code_verifier` is embedded in the `redirect_to` URL as `?cv=` because session state is lost across browser redirects.

### Supabase Client
- Always obtain the client via `get_client()` from `supabase_client.py`. Never instantiate `create_client` directly in page code.
- Secrets are read from `st.secrets["supabase"]["url"]` and `st.secrets["supabase"]["key"]`. For local development, use `.streamlit/secrets.toml`. For Streamlit Cloud, configure secrets in the app dashboard.

### Database — `ratings` Table
- Schema: `(user_id UUID, set_code TEXT, collector_number TEXT, card_name TEXT, rating FLOAT, notes TEXT)`
- Unique constraint on `(user_id, set_code, collector_number)` — use `upsert` for insert-or-update.
- All DB operations go through `ratings_db.py` (`upsert_rating`, `delete_rating`, `get_user_ratings`, `get_community_ratings`, `get_all_ratings_for_set`).
- Aggregation is done **client-side in pandas**, not in SQL, to keep Supabase queries simple.
- Row Level Security (RLS) should be enabled on the `ratings` table. Users may only write rows where `user_id = auth.uid()`.

### Card Data
- Card lists are stored as CSVs in `data/` and loaded via `load_set(csv_filename, set_code)` in `set_data.py`.
- `load_set` is decorated with `@st.cache_data` — do not bypass this.
- Card images are **not** stored locally. They are fetched at runtime from the Scryfall API:
  - Thumbnail: `https://api.scryfall.com/cards/{set_code}/{collector_number}?format=image&version=small`
  - Full size: `https://api.scryfall.com/cards/{set_code}/{collector_number}?format=image&version=normal`
- To add a new set: add/generate the CSV via `fetch_set_cards.py`, then add (or seed) a row in the `public.sets` table with `included_in_app = TRUE` and the correct `csv_filename`/`display_name`.
### Rating Scale
- Ratings are floats from `0.0` to `5.0` in `0.5` increments.
- The canonical options list is `RATING_OPTIONS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]` (defined in `2_Ratings.py`).
- A `None` rating means unrated (the card has no DB row).

### State Management
- Pending rating edits are stored in **browser `localStorage`** (keyed by `rating_pending_{set_code}`) and read back via `streamlit_js_eval`. This avoids Streamlit reruns on every keystroke.
- Baseline ratings (last saved state) are stored in `st.session_state[f"baseline_{user_id}_{set_code}"]`.
- A `_save_counter` in `st.session_state` forces `streamlit_js_eval` to re-evaluate by changing its `key`.

### Pages
- **Viewer (`1_Viewer.py`)**: Public, no auth. Filters by name, rarity, color identity. Renders an HTML table with CSS hover-zoom for card images.
- **Ratings (`2_Ratings.py`)**: Auth-gated. Inline rating editing via an HTML/JS table; "Save Changes" persists via `upsert_rating` / `delete_rating`.
- **Dashboard (`3_Dashboard.py`)**: Auth-gated. Plotly bar charts per user, community summary table. Other users are anonymized as "User 1", "User 2", etc.; the current user is shown as "You".

---

## Development Patterns

- **Do not** use `st.cache_resource` for the Supabase client — always use `st.session_state`.
- **Do not** import Supabase or call auth functions from within `@st.cache_data` functions.
- When adding new DB columns, update both `ratings_db.py` helpers and the Supabase table schema.
- Card filtering uses pandas boolean masks; keep filter logic in the page file, not in `set_data.py`.
- Prefer `plotly.graph_objects` over `plotly.express` for chart customization consistency.
- `st.set_page_config` must be the first Streamlit call in each page file.
- Use `st.stop()` to halt page execution after `require_auth` fails or after an error that makes further rendering meaningless.

---

## Deployment (Streamlit Cloud)

- The app is deployed from the `main` branch at https://csa-set-resources.streamlit.app/.
- Secrets (`supabase.url`, `supabase.key`) are configured in the Streamlit Cloud dashboard, **not** committed to the repo.
- The Supabase anon key is used (not the service role key). RLS enforces per-user data isolation.
- `requirements.txt` is the sole dependency specification — keep it pinned and minimal.

---

## Domain Context (MTG / Limited)

- **Limited format**: Players build decks from a pool of opened booster packs (draft or sealed). Card ratings reflect how good a card is in this context, not in constructed formats.
- **Collector number**: The unique identifier for a card within a set (e.g., `"042"`). Used as the primary card key throughout the app.
- **Rarity order**: common → uncommon → rare → mythic (defined in `RARITY_ORDER` in `set_data.py`).
- **Color identity**: Uses the standard MTG color abbreviations: `W` (White), `U` (Blue), `B` (Black), `R` (Red), `G` (Green).
- **Scryfall**: The third-party API used to fetch card metadata and images. Rate-limit politely (50–100ms delay between requests) when running `fetch_set_cards.py`.
