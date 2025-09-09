// Supabase Edge Function - statistics
// GET /functions/v1/statistics -> aggregates for dashboard

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

serve(async (_req) => {
  try {
    const url = Deno.env.get('SUPABASE_URL');
    const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if (!url || !key) return new Response('Missing Supabase env', { status: 500 });

    const res = await fetch(`${url}/rest/v1/yibao_rule_statistics?select=*`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` }
    });
    const rows = await res.json();
    const byRuleType: Record<string, number> = {};
    let total = 0;
    if (Array.isArray(rows)) {
      for (const r of rows) { byRuleType[r.rule_type] = Number(r.hits || 0); total += Number(r.hits || 0); }
    }
    return new Response(JSON.stringify({ success: true, totalViolations: total, byRuleType }), { headers: { 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: String(e) }), { status: 500 });
  }
});


