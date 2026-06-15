-- =============================================================================
-- Add Marvel Super Heroes (msh) to the sets table
-- Run this in the Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql)
-- =============================================================================

INSERT INTO public.sets
    (set_code, set_name, display_name, csv_filename, included_in_app)
VALUES
    ('msh', 'Marvel Super Heroes', 'Marvel Super Heroes', 'Marvel_Super_Heroes', TRUE)
ON CONFLICT (set_code) DO UPDATE SET
    display_name    = EXCLUDED.display_name,
    csv_filename    = EXCLUDED.csv_filename,
    included_in_app = EXCLUDED.included_in_app;

-- Verify
SELECT set_code, display_name, csv_filename, included_in_app
FROM   public.sets
ORDER  BY released_at DESC NULLS LAST;
