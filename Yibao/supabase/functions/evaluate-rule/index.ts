// deno-lint-ignore-file no-explicit-any
// Edge Function: evaluate-rule
// Purpose: Evaluate enabled rules for a given event and clinical context
// Trigger: HTTP POST with JSON { event: string, context: { patient, visit, order, ... }, record?: boolean }
// Response: { decision: 'pass'|'warn'|'block', hits: [{ ruleCode, severity, message }] }

import { createClient } from 'npm:@supabase/supabase-js@2';

// Create Supabase client with service role if available (functions run server-side)
function getSupabase() {
  const url = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? Deno.env.get('SUPABASE_ANON_KEY');
  if (!url || !serviceKey) {
    throw new Error('Missing SUPABASE_URL or service key env');
  }
  return createClient(url, serviceKey, { auth: { persistSession: false } });
}

// Utility: get value from dotted path (e.g., 'patient.age')
function getByPath(obj: any, path: string): any {
  return path.split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

// Evaluate a single atomic clause
function evalClause(facts: any, clause: any): boolean {
  const left = getByPath(facts, clause.fact);
  const op = clause.op;
  const val = clause.value;

  switch (op) {
    case '==':
      return left === val;
    case '!=':
      return left !== val;
    case '>':
      return typeof left === 'number' && left > val;
    case '>=':
      return typeof left === 'number' && left >= val;
    case '<':
      return typeof left === 'number' && left < val;
    case '<=':
      return typeof left === 'number' && left <= val;
    case 'in':
      return Array.isArray(val) && val.includes(left);
    case 'not_in':
      return Array.isArray(val) && !val.includes(left);
    default:
      return false;
  }
}

// Evaluate expression tree { all: [...]} or { any: [...] } or atomic clause
function evalExpression(facts: any, expr: any): boolean {
  if (!expr || typeof expr !== 'object') return false;
  if (Array.isArray(expr.all)) {
    return expr.all.every((sub) => evalExpression(facts, sub));
  }
  if (Array.isArray(expr.any)) {
    return expr.any.some((sub) => evalExpression(facts, sub));
  }
  return evalClause(facts, expr);
}

// Compose message with simple template replacement {a.b}
function renderMessage(tpl: string, facts: any): string {
  return tpl.replace(/\{([^}]+)\}/g, (_, p) => {
    const v = getByPath(facts, p.trim());
    return v == null ? '' : String(v);
  });
}

export async function handler(req: Request): Promise<Response> {
  try {
    if (req.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    const { event, context, record } = await req.json();
    if (!event || !context) {
      return Response.json({ error: 'Missing event or context' }, { status: 400 });
    }

    const supabase = getSupabase();

    // 1) Find enabled rules that listen to this event
    const { data: triggerRules, error: trigErr } = await supabase
      .from('yibao_rule_triggers')
      .select('rule_id')
      .eq('event_type', event);
    if (trigErr) throw trigErr;

    const ruleIds = (triggerRules ?? []).map((r: any) => r.rule_id);
    if (ruleIds.length === 0) {
      return Response.json({ decision: 'pass', hits: [] });
    }

    const { data: rules, error: rulesErr } = await supabase
      .from('yibao_rules')
      .select('id, code, name, rule_type, severity, enabled')
      .in('id', ruleIds)
      .eq('enabled', true);
    if (rulesErr) throw rulesErr;

    // Preload conditions and actions for these rules
    const { data: conds, error: condErr } = await supabase
      .from('yibao_rule_conditions')
      .select('id, rule_id, priority, expression_json')
      .in('rule_id', ruleIds)
      .order('priority', { ascending: true });
    if (condErr) throw condErr;

    const { data: acts, error: actErr } = await supabase
      .from('yibao_rule_actions')
      .select('id, rule_id, action_type, message_template')
      .in('rule_id', ruleIds);
    if (actErr) throw actErr;

    const byRuleConds = new Map<number, any[]>();
    (conds ?? []).forEach((c) => {
      const arr = byRuleConds.get(c.rule_id) ?? [];
      arr.push(c);
      byRuleConds.set(c.rule_id, arr);
    });

    const byRuleActs = new Map<number, any[]>();
    (acts ?? []).forEach((a) => {
      const arr = byRuleActs.get(a.rule_id) ?? [];
      arr.push(a);
      byRuleActs.set(a.rule_id, arr);
    });

    const hits: any[] = [];

    for (const r of rules ?? []) {
      const rConds = byRuleConds.get(r.id) ?? [];
      const allTrue = rConds.every((c) => evalExpression(context, c.expression_json));
      if (allTrue) {
        const rActs = byRuleActs.get(r.id) ?? [];
        // pick first action or default to warn
        const action = rActs[0] ?? { action_type: r.severity === 'block' ? 'intercept' : 'warn', message_template: r.name };
        const msg = renderMessage(action.message_template ?? r.name, context);
        hits.push({ ruleCode: r.code, severity: r.severity, action: action.action_type, message: msg });

        // Optionally record violation
        if (record) {
          await supabase.from('yibao_violations').insert({
            visit_id: context?.visit?.id ?? 'unknown',
            rule_id: r.id,
            severity: r.severity,
            snapshot: context,
          });
        }
      }
    }

    // Final decision: highest severity among hits
    let decision: 'pass' | 'warn' | 'block' = 'pass';
    for (const h of hits) {
      if (h.severity === 'block') { decision = 'block'; break; }
      if (h.severity === 'warn') { decision = decision === 'pass' ? 'warn' : decision; }
    }

    return Response.json({ decision, hits });
  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500 });
  }
}

Deno.serve(handler);
