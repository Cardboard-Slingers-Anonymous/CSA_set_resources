-- =============================================================================
-- STEP 1: Create the `sets` table
-- Run this in the Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.sets (
    -- Primary key: Scryfall set code (e.g. 'tdm', 'blb')
    set_code        TEXT PRIMARY KEY,

    -- Fields synced weekly from Scryfall
    set_name        TEXT        NOT NULL,
    set_type        TEXT,                          -- e.g. 'expansion', 'masters', 'commander'
    released_at     DATE,
    card_count      INTEGER,
    scryfall_uri    TEXT,
    icon_svg_uri    TEXT,
    arena_code      TEXT,                          -- non-NULL means set is available on MTG Arena
    is_digital      BOOLEAN     DEFAULT FALSE,
    last_synced_at  TIMESTAMPTZ,

    -- Fields managed manually by the CSA team
    display_name    TEXT,                          -- Override the Scryfall name for the UI dropdown
    csv_filename    TEXT,                          -- data/<csv_filename>.csv — set when CSV exists
    included_in_app BOOLEAN     NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── RLS ────────────────────────────────────────────────────────────────────
-- The sets table is public-read (no user data) but only the sync function
-- (which uses the service role key) may write.

ALTER TABLE public.sets ENABLE ROW LEVEL SECURITY;

-- Anyone (including anonymous visitors) may read the sets list
CREATE POLICY "sets_public_select"
    ON public.sets
    FOR SELECT
    USING (true);

-- No INSERT / UPDATE / DELETE via the anon or authenticated roles.
-- Writes are performed exclusively by the Edge Function (service role).


-- =============================================================================
-- STEP 2: Seed existing sets
-- These are the sets already tracked in the app. They are inserted with
-- included_in_app = TRUE so the app continues to work immediately.
-- =============================================================================

INSERT INTO public.sets
    (set_code, set_name, display_name, csv_filename, included_in_app)
VALUES
    ('blb',  'Bloomburrow',                    'Bloomburrow',                    'Bloomburrow',                   TRUE),
    ('dsk',  'Duskmourn: House of Horror',     'Duskmourn: House of Horror',     'Duskmourn_House_of_Horror',     TRUE),
    ('fdn',  'MTG Foundations',                'MTG Foundations',                'MTG_Foundations',               TRUE),
    ('inr',  'Innistrad Remastered',           'Innistrad Remastered',           'Innistrad_Remastered',          TRUE),
    ('dft',  'Aetherdrift',                    'Aetherdrift',                    'Aetherdrift',                   TRUE),
    ('tdm',  'Tarkir: Dragonstorm',            'Tarkir: Dragonstorm',            'Tarkir_Dragonstorm',            TRUE),
    ('fin',  'Final Fantasy',                  'Final Fantasy',                  'Final_Fantasy',                 TRUE),
    ('eoe',  'Edge of Eternities',             'Edge of Eternities',             'Edge_of_Eternities',            TRUE),
    ('om1',  'Through the Omenpaths',          'Through the Omenpaths',          'Through_the_Omenpaths',         TRUE),
    ('tla',  'Avatar: The Last Airbender',     'Avatar: The Last Airbender',     'Avatar_TheLastAirbender',       TRUE),
    ('ecl',  'Lorwyn Eclipsed',                'Lorwyn Eclipsed',                'Lorwyn_Eclipsed',               TRUE),
    ('tmt',  'Teenage Mutant Ninja Turtles',   'Teenage Mutant Ninja Turtles',   'MTG_TeenageMutantNinjaTurtles', TRUE),
    ('sos',  'Secrets of Strixhaven',          'Secrets of Strixhaven',          'Secrets_of_Strixhaven',         TRUE)
ON CONFLICT (set_code) DO UPDATE SET
    display_name    = EXCLUDED.display_name,
    csv_filename    = EXCLUDED.csv_filename,
    included_in_app = EXCLUDED.included_in_app;

-- Verify the seed worked
SELECT set_code, display_name, csv_filename, included_in_app
FROM   public.sets
ORDER  BY released_at DESC NULLS LAST;
