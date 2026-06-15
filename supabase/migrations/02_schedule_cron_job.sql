-- =============================================================================
-- STEP 3: Schedule the weekly Scryfall sync cron job
--
-- Run this AFTER:
--   1. Creating the `sets` table (01_create_sets_table.sql)
--   2. Deploying the Edge Function (supabase/functions/sync-scryfall-sets/)
--   3. Setting the CRON_SECRET Edge Function secret in the Supabase dashboard
--      (Dashboard → Edge Functions → sync-scryfall-sets → Secrets)
--
-- Replace the two placeholder values below before running:
--   YOUR_PROJECT_REF  → your Supabase project reference ID
--                       (found in Project Settings → General, e.g. "abcdefghijklmnop")
--   YOUR_CRON_SECRET  → the same value you set as the CRON_SECRET Edge Function secret
-- =============================================================================

-- pg_cron and pg_net are pre-installed in every Supabase project.
-- These CREATE EXTENSION statements are no-ops if they already exist.
CREATE EXTENSION IF NOT EXISTS pg_cron  WITH SCHEMA pg_catalog;
CREATE EXTENSION IF NOT EXISTS pg_net   WITH SCHEMA extensions;

-- Schedule: every Sunday at 03:00 UTC
-- Cron syntax: minute hour day-of-month month day-of-week
SELECT cron.schedule(
    'sync-scryfall-sets-weekly',      -- job name (must be unique)
    '0 3 * * 0',                      -- every Sunday at 03:00 UTC
    $$
    SELECT net.http_post(
        url     := 'https://YOUR_PROJECT_REF.supabase.co/functions/v1/sync-scryfall-sets',
        headers := jsonb_build_object(
            'Content-Type',  'application/json',
            'x-cron-secret', 'YOUR_CRON_SECRET'
        ),
        body    := '{}'::jsonb
    ) AS request_id;
    $$
);

-- Verify the job was created
SELECT jobid, jobname, schedule, command
FROM   cron.job
WHERE  jobname = 'sync-scryfall-sets-weekly';


-- =============================================================================
-- OPTIONAL: Run the sync immediately (for the initial data load)
--
-- You can also trigger it from the Supabase dashboard:
--   Edge Functions → sync-scryfall-sets → Test function
-- Just add the x-cron-secret header with your CRON_SECRET value.
-- =============================================================================

-- Uncomment to trigger an immediate sync:
-- SELECT net.http_post(
--     url     := 'https://YOUR_PROJECT_REF.supabase.co/functions/v1/sync-scryfall-sets',
--     headers := jsonb_build_object(
--         'Content-Type',  'application/json',
--         'x-cron-secret', 'YOUR_CRON_SECRET'
--     ),
--     body    := '{}'::jsonb
-- ) AS request_id;


-- =============================================================================
-- REFERENCE: Managing the cron job
-- =============================================================================

-- List all scheduled jobs:
-- SELECT * FROM cron.job;

-- View recent job run history:
-- SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;

-- Remove the job (if you need to recreate it with a different schedule):
-- SELECT cron.unschedule('sync-scryfall-sets-weekly');
