// Deno Deploy / Supabase Edge Function - rule-engine
// Endpoint: POST /functions/v1/rule-engine
// Body: { context: object, eventType?: string }
// Response: { success: boolean, hits: Array<{ ruleId:number; code:string; name:string; severity:string; messages:string[] }> }

// deno-lint-ignore-file no-explicit-any
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

type Hit = { ruleId: number; code: string; name: string; severity: string; messages: string[] };

function getByPath(obj: any, path: string): any {
  return String(path).split('.').reduce((acc: any, k: string) => acc == null ? undefined : acc[k], obj);
}

function evalClause(facts: any, clause: { fact: string; op: string; value: any }): boolean {
  const left = getByPath(facts, clause.fact);
  const op = clause.op;
  const val = clause.value;
  switch (op) {
    case '==': return left === val;
    case '!=': return left !== val;
    case '>': return typeof left === 'number' && left > val;
    case '>=': return typeof left === 'number' && left >= val;
    case '<': return typeof left === 'number' && left < val;
    case '<=': return typeof left === 'number' && left <= val;
    case 'in': return Array.isArray(val) && val.includes(left);
    case 'not_in': return Array.isArray(val) && !val.includes(left);
    default: return false;
  }
}

function evalExpression(facts: any, expr: any): boolean {
  if (!expr || typeof expr !== 'object') return false;
  if (Array.isArray(expr.all)) return expr.all.every((sub: any) => evalExpression(facts, sub));
  if (Array.isArray(expr.any)) return expr.any.some((sub: any) => evalExpression(facts, sub));
  return evalClause(facts, expr);
}

function renderMessage(template: string, facts: any): string {
  return template.replace(/\{([^}]+)\}/g, (_, p) => {
    const v = getByPath(facts, String(p).trim());
    return v == null ? '' : String(v);
  });
}

serve(async (req) => {
  try {
    if (req.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
    const { context, eventType } = await req.json().catch(() => ({ context: {}, eventType: 'order.drug.submit' }));

    const url = Deno.env.get('SUPABASE_URL');
    const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if (!url || !key) {
      return new Response(JSON.stringify({ success: false, error: 'Missing Supabase env' }), { status: 500 });
    }

    // fetch enabled rules with triggers
    const rulesRes = await fetch(`${url}/rest/v1/yibao_rules?enabled=eq.true&select=id,code,name,severity`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` }
    });
    const rules = await rulesRes.json();

    const hits: Hit[] = [];
    for (const rule of (Array.isArray(rules) ? rules : [])) {
      const condRes = await fetch(`${url}/rest/v1/yibao_rule_conditions?rule_id=eq.${rule.id}&select=priority,expression_json&order=priority.asc`, {
        headers: { apikey: key, Authorization: `Bearer ${key}` }
      });
      const conds = await condRes.json();
      const actRes = await fetch(`${url}/rest/v1/yibao_rule_actions?rule_id=eq.${rule.id}&select=action_type,message_template`, {
        headers: { apikey: key, Authorization: `Bearer ${key}` }
      });
      const actions = await actRes.json();

      const matched = Array.isArray(conds) && conds.every((c: any) => evalExpression(context, c.expression_json));
      if (matched) {
        const messages = (Array.isArray(actions) ? actions : []).map((a: any) => renderMessage(a.message_template || '', context)).filter(Boolean);
        hits.push({ ruleId: rule.id, code: rule.code, name: rule.name, severity: rule.severity || 'warn', messages });
      }
    }

    return new Response(JSON.stringify({ success: true, hits }, null, 2), { headers: { 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: String(e) }), { status: 500 });
  }
});


