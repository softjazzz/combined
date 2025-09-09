// Edge Function: violations
// @ts-nocheck
// Purpose: Query and manage violation records with filtering and pagination
// Endpoints:
//   GET /violations?page=1&limit=20&severity=warn&rule_code=DEMO_001
//   POST /violations (create new violation record)

import { createClient } from 'npm:@supabase/supabase-js@2';

const ALLOWED_ORIGIN = Deno.env.get('ALLOWED_ORIGIN') || '*'
const corsHeaders = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
  'Access-Control-Max-Age': '86400'
};

function getSupabase() {
  const url = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? Deno.env.get('SUPABASE_ANON_KEY');
  if (!url || !serviceKey) {
    throw new Error('Missing SUPABASE_URL or service key env');
  }
  return createClient(url, serviceKey, { auth: { persistSession: false } });
}

export async function handler(req: Request): Promise<Response> {
  try {
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const supabase = getSupabase();
    const url = new URL(req.url);

    if (req.method === 'GET') {
      // Query violations with filters
      const page = parseInt(url.searchParams.get('page') ?? '1');
      const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '20'), 100);
      const severity = url.searchParams.get('severity');
      const ruleCode = url.searchParams.get('rule_code');
      const visitId = url.searchParams.get('visit_id');

      // Optional: resolve rule_id by code to ensure filter works reliably
      let resolvedRuleId: number | null = null;
      if (ruleCode) {
        const { data: ruleByCode } = await supabase
          .from('yibao_rules')
          .select('id')
          .eq('code', ruleCode)
          .limit(1)
          .maybeSingle();
        resolvedRuleId = ruleByCode?.id ?? null;
      }

      let query = supabase
        .from('yibao_violations')
        .select(`
          id,
          visit_id,
          rule_id,
          severity,
          snapshot,
          created_at,
          yibao_rules!inner(code, name, rule_type)
        `, { count: 'exact' })
        .order('created_at', { ascending: false });

      if (severity) {
        query = query.eq('severity', severity);
      }
      if (visitId) {
        query = query.eq('visit_id', visitId);
      }
      if (resolvedRuleId) {
        query = query.eq('rule_id', resolvedRuleId);
      } else if (ruleCode) {
        // Fallback: try join filter if rule id not resolved
        query = query.eq('yibao_rules.code', ruleCode);
      }

      const offset = (page - 1) * limit;
      query = query.range(offset, offset + limit - 1);

      const { data, error, count } = await query;
      if (error) throw error;

      return Response.json({
        data: data ?? [],
        pagination: {
          page,
          limit,
          total: count ?? 0,
          totalPages: Math.ceil((count ?? 0) / limit)
        }
      }, { headers: corsHeaders });

    } else if (req.method === 'POST') {
      const url = new URL(req.url);
      const action = url.searchParams.get('action') || 'create';
      const body = await req.json();

      if (action === 'create') {
        const { visit_id, rule_id, severity, snapshot } = body;
        if (!visit_id || !rule_id || !severity) {
          return Response.json({ error: 'Missing required fields' }, { status: 400, headers: corsHeaders });
        }
        const { data, error } = await supabase
          .from('yibao_violations')
          .insert({ visit_id, rule_id, severity, snapshot: snapshot ?? {} })
          .select()
          .single();
        if (error) throw error;
        return Response.json({ data }, { status: 201, headers: corsHeaders });
      }

      if (action === 'ignore') {
        const { id, reason, note } = body;
        if (!id) return Response.json({ error: 'Missing violation id' }, { status: 400, headers: corsHeaders });
        const { data, error } = await supabase
          .from('yibao_violations')
          .update({ ignore_reason: reason ?? null, ignore_note: note ?? null })
          .eq('id', id)
          .select('id, ignore_reason, ignore_note')
          .single();
        if (error) throw error;
        return Response.json({ success: true, data }, { headers: corsHeaders });
      }

      return Response.json({ error: 'Unknown action' }, { status: 400, headers: corsHeaders });

    } else {
      return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
    }

  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);
