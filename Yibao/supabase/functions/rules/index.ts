// Edge Function: rules
// @ts-nocheck
// Purpose: Manage rules (toggle enable, future: CRUD)
// Endpoints:
//   POST /rules?action=toggle  body: { id:number, enabled:boolean }

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
    const action = url.searchParams.get('action') || '';

    if (req.method === 'POST' && action === 'toggle') {
      const body = await req.json();
      const id = Number(body?.id);
      const enabled = Boolean(body?.enabled);
      if (!id || Number.isNaN(id)) {
        return Response.json({ error: 'Invalid id' }, { status: 400, headers: corsHeaders });
      }

      const { data, error } = await supabase
        .from('yibao_rules')
        .update({ enabled })
        .eq('id', id)
        .select('*')
        .maybeSingle();
      if (error) throw error;

      return Response.json({ success: true, data }, { headers: corsHeaders });
    }

    if (req.method === 'POST' && action === 'save') {
      const body = await req.json();
      const rule = body?.rule || {};
      const conditions = Array.isArray(body?.conditions) ? body.conditions : [];
      const actions = Array.isArray(body?.actions) ? body.actions : [];
      const triggers = Array.isArray(body?.triggers) ? body.triggers : [];

      if (!rule?.code || !rule?.name) {
        return Response.json({ error: 'Missing required rule fields (code, name)' }, { status: 400, headers: corsHeaders });
      }

      // Upsert rule
      let ruleId = Number(rule?.id || 0);
      if (ruleId > 0) {
        const { error: upErr } = await supabase
          .from('yibao_rules')
          .update({
            code: rule.code,
            name: rule.name,
            rule_type: rule.rule_type ?? null,
            severity: rule.severity ?? 'warn',
            enabled: rule.enabled ?? true,
            category_id: rule.category_id ?? null,
            version: rule.version ?? 1,
            metadata: rule.metadata ?? {}
          })
          .eq('id', ruleId);
        if (upErr) throw upErr;
      } else {
        const { data: inserted, error: insErr } = await supabase
          .from('yibao_rules')
          .insert({
            code: rule.code,
            name: rule.name,
            rule_type: rule.rule_type ?? null,
            severity: rule.severity ?? 'warn',
            enabled: rule.enabled ?? true,
            category_id: rule.category_id ?? null,
            version: rule.version ?? 1,
            metadata: rule.metadata ?? {}
          })
          .select('id')
          .single();
        if (insErr) throw insErr;
        ruleId = inserted?.id;
      }

      // Replace conditions/actions for this rule
      // Delete old
      await supabase.from('yibao_rule_conditions').delete().eq('rule_id', ruleId);
      await supabase.from('yibao_rule_actions').delete().eq('rule_id', ruleId);
      await supabase.from('yibao_rule_triggers').delete().eq('rule_id', ruleId);

      // Insert new
      if (conditions.length) {
        const condRows = conditions.map((c: any, idx: number) => ({
          rule_id: ruleId,
          priority: c?.priority ?? idx + 1,
          expression_json: c?.expression_json ?? c?.expression ?? {}
        }));
        const { error: condErr } = await supabase.from('yibao_rule_conditions').insert(condRows);
        if (condErr) throw condErr;
      }

      if (actions.length) {
        const actRows = actions.map((a: any) => ({
          rule_id: ruleId,
          action_type: a?.action_type ?? 'warn',
          message_template: a?.message_template ?? a?.message ?? ''
        }));
        const { error: actErr } = await supabase.from('yibao_rule_actions').insert(actRows);
        if (actErr) throw actErr;
      }

      if (triggers.length) {
        const trigRows = triggers.map((t: any, idx: number) => ({
          rule_id: ruleId,
          event_type: t?.event_type ?? 'order.drug.submit',
          priority: t?.priority ?? idx + 1
        }));
        // 若表未有 priority 字段，可忽略该列
        const { error: trigErr } = await supabase.from('yibao_rule_triggers').insert(trigRows);
        if (trigErr) throw trigErr;
      }

      // Return merged result
      const { data: updated } = await supabase
        .from('yibao_rules')
        .select('*')
        .eq('id', ruleId)
        .single();

      return Response.json({ success: true, data: { rule: updated, ruleId } }, { headers: corsHeaders });
    }

    return Response.json({ error: 'Not Found' }, { status: 404, headers: corsHeaders });
  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);


