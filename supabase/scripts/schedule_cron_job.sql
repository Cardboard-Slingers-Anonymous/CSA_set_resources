-- =============================================================================
-- Manual script: Schedule the weekly Scryfall sync cron job
--
-- ⚠ DO NOT move this file into supabase/migrations/.
--   It is intentionally kept here as a one-time manual step because it reads
--   project-specific configuration that cannot safely live in a migration.
--
-- Prerequisites (complete these before running):
--
--   1. Run the migration:  supabase/migrations/01_create_sets_table.sql
--   2. Deploy the Edge Function:
--        supabase functions deploy sync-scryfall-sets
--   3. Add CRON_SECRET to the Edge Function's secrets:
--        supabase secrets set CRON_SECRET=<your-secret>
--      OR: Dashboard → Edge Functions → sync-scryfall-sets → Secrets
--   4. Store the same secret in Supabase Vault (so this script can read it):
--        Run in the SQL Editor:
--          SELECT vault.create_secret('<your-secret>', 'cron_secret');
--   5. Store the Edge Function base URL as a Postgres setting (no trailing slash):
--        Run in the SQL Editor:
--          ALTER DATABASE postgres
--            SET "app.edge_function_base_url" =
--              'https://<YOUR_PROJECT_REF>.supabase.co/functions/v1';
--      Then reconnect (or run `SELECT pg_reload_conf();`) for the setting to take effect.
--
-- After completing the prerequisites, run this script once in the SQL Editor.
-- =============================================================================

DO $$
DECLARE
    v_base_url TEXT;
    v_secret   TEXT;
    v_url      TEXT;
    v_command  TEXT;
BEGIN
    -- ── Read config ────────────────────────────────────────────────────────
    v_base_url := current_setting('app.edge_function_base_url', true);
    IF v_base_url IS NULL OR v_base_url = '' THEN
        RAISE EXCEPTION
            'app.edge_function_base_url is not set. '
            'Run: ALTER DATABASE postgres SET "app.edge_function_base_url" = ''https://<ref>.supabase.co/functions/v1'';';
    END IF;

    SELECT decrypted_secret
      INTO v_secret
      FROM vault.decrypted_secrets
     WHERE name = 'cron_secret';

    IF v_secret IS NULL THEN
        RAISE EXCEPTION
            'Vault secret "cron_secret" not found. '
            'Run: SELECT vault.create_secret(''<value>'', ''cron_secret'');';
    END IF;

    v_url := v_base_url || '/sync-scryfall-sets';

    -- ── Idempotent scheduling ──────────────────────────────────────────────
    -- Unschedule the old job if it already exists so we can safely re-run
    -- this script (e.g. after changing the schedule or URL).
    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'sync-scryfall-sets-weekly') THEN
        PERFORM cron.unschedule('sync-scryfall-sets-weekly');
        RAISE NOTICE 'Removed existing cron job; rescheduling.';
    END IF;

    v_command := format(
        $cmd$
        SELECT net.http_post(
            url     := %L,
            headers := jsonb_build_object(
                'Content-Type',  'application/json',
                'x-cron-secret', %L
            ),
            body    := '{}'::jsonb
        ) AS request_id;
        $cmd$,
        v_url, v_secret
    );

    -- Schedule: every Sunday at 03:00 UTC
    PERFORM cron.schedule(
        'sync-scryfall-sets-weekly',  -- unique job name
        '0 3 * * 0',                  -- cron: minute hour dom month dow
        v_command
    );

    RAISE NOTICE 'Cron job scheduled → % (every Sunday 03:00 UTC)', v_url;
END;
$$;

-- Verify
SELECT jobid, jobname, schedule
FROM   cron.job
WHERE  jobname = 'sync-scryfall-sets-weekly';


-- =============================================================================
-- Reference: Managing the job
-- =============================================================================

-- List all scheduled jobs:
-- SELECT * FROM cron.job;

-- View recent run history:
-- SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;

-- Remove the job (to reschedule with a different config, just re-run this script):
-- SELECT cron.unschedule('sync-scryfall-sets-weekly');

-- Trigger an immediate sync (add x-cron-secret header in the dashboard):
-- Dashboard → Edge Functions → sync-scryfall-sets → Test function
