/**
 * Supabase Edge Function: sync-scryfall-sets
 *
 * Fetches the full set list from the Scryfall API and upserts metadata into
 * the `sets` table. Only Scryfall-sourced fields are updated on conflict;
 * user-managed fields (display_name, csv_filename, included_in_app) are
 * never overwritten.
 *
 * Invoked weekly by a pg_cron job. Protected by an optional CRON_SECRET
 * environment variable checked against the `x-cron-secret` request header.
 *
 * Required Edge Function secrets (set in Supabase dashboard):
 *   CRON_SECRET  – shared secret that the pg_cron job must send in the
 *                  `x-cron-secret` header. Leave unset to disable auth
 *                  (not recommended for production).
 *
 * SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are injected automatically
 * by the Supabase Edge Function runtime.
 */

import { createClient } from "jsr:@supabase/supabase-js@2";

const SCRYFALL_SETS_URL = "https://api.scryfall.com/sets";

interface ScryfallSet {
  code: string;
  name: string;
  set_type: string;
  released_at: string | null;
  card_count: number;
  scryfall_uri: string;
  icon_svg_uri: string;
  arena_code?: string;
  digital: boolean;
}

interface ScryfallResponse {
  object: string;
  has_more: boolean;
  data: ScryfallSet[];
}

Deno.serve(async (req: Request) => {
  // ── Auth: verify the cron secret if one is configured ──────────────────
  const cronSecret = Deno.env.get("CRON_SECRET");
  if (cronSecret) {
    const provided = req.headers.get("x-cron-secret");
    if (provided !== cronSecret) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  // ── Only allow POST ─────────────────────────────────────────────────────
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    // ── 1. Fetch all sets from Scryfall ──────────────────────────────────
    const scryfallRes = await fetch(SCRYFALL_SETS_URL, {
      headers: {
        "User-Agent": "CSA-Set-Resources/1.0 (https://csa-set-resources.streamlit.app/)",
        "Accept": "application/json",
      },
    });

    if (!scryfallRes.ok) {
      throw new Error(
        `Scryfall API returned ${scryfallRes.status}: ${scryfallRes.statusText}`
      );
    }

    const scryfallData: ScryfallResponse = await scryfallRes.json();
    const allSets: ScryfallSet[] = scryfallData.data;

    // ── 2. Build upsert payload ──────────────────────────────────────────
    // Only include Scryfall-sourced columns; user-managed columns
    // (display_name, csv_filename, included_in_app) are intentionally omitted
    // so they are NOT overwritten on conflict.
    const upsertRows = allSets.map((s) => ({
      set_code: s.code,
      set_name: s.name,
      set_type: s.set_type,
      released_at: s.released_at ?? null,
      card_count: s.card_count,
      scryfall_uri: s.scryfall_uri,
      icon_svg_uri: s.icon_svg_uri,
      arena_code: s.arena_code ?? null,
      is_digital: s.digital,
      last_synced_at: new Date().toISOString(),
    }));

    // ── 3. Upsert into Supabase ──────────────────────────────────────────
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    // Process in batches of 200 to stay under payload limits
    const BATCH_SIZE = 200;
    let totalUpserted = 0;

    for (let i = 0; i < upsertRows.length; i += BATCH_SIZE) {
      const batch = upsertRows.slice(i, i + BATCH_SIZE);
      const { error } = await supabase
        .from("sets")
        .upsert(batch, { onConflict: "set_code" });

      if (error) throw error;
      totalUpserted += batch.length;
    }

    console.log(`Synced ${totalUpserted} sets from Scryfall.`);

    return new Response(
      JSON.stringify({
        success: true,
        sets_synced: totalUpserted,
        synced_at: new Date().toISOString(),
      }),
      { headers: { "Content-Type": "application/json" } }
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("sync-scryfall-sets error:", message);
    return new Response(
      JSON.stringify({ success: false, error: message }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});
