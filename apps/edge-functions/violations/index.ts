// Supabase Edge Function - violations writer
// POST /functions/v1/violations { visit_id, rule_id, severity, snapshot }

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

serve(async (req) => {
  try {
    if (req.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    const body = await req.json();

    const url = Deno.env.get('SUPABASE_URL');
    const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if (!url || !key) return new Response('Missing Supabase env', { status: 500 });

    const res = await fetch(`${url}/rest/v1/yibao_violations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', apikey: key, Authorization: `Bearer ${key}` },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) return new Response(JSON.stringify({ success: false, error: data }), { status: res.status });
    return new Response(JSON.stringify({ success: true, data }), { headers: { 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: String(e) }), { status: 500 });
  }
});


