// deno-lint-ignore-file no-explicit-any
// @ts-nocheck
// Edge Function: evaluate-rule (Enhanced)
// Purpose: High-performance rule evaluation with caching and batch processing
// Trigger: HTTP POST with JSON { event: string, context: { patient, visit, order, ... }, record?: boolean, batch?: boolean }
// Response: { decision: 'pass'|'warn'|'block', hits: [{ ruleCode, severity, message }], performance: {...} }

import { createClient } from 'npm:@supabase/supabase-js@2';

// CORS headers (dev uses *; change to your domains in production)
const ALLOWED_ORIGIN = Deno.env.get('ALLOWED_ORIGIN') || '*'
const corsHeaders = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
  'Access-Control-Max-Age': '86400'
};

// 性能配置
const PERFORMANCE_CONFIG = {
  BATCH_SIZE: parseInt(Deno.env.get('BATCH_SIZE') || '50'),
  MAX_CONCURRENT: parseInt(Deno.env.get('MAX_CONCURRENT') || '5'),
  CACHE_TTL_MS: parseInt(Deno.env.get('CACHE_TTL_MS') || '300000'), // 5分钟
  ENABLE_PARALLEL: Deno.env.get('ENABLE_PARALLEL') !== 'false'
};

// 内存缓存
const ruleCache = new Map();
const conditionCache = new Map();
const actionCache = new Map();
let cacheTimestamp = 0;

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

// 缓存管理函数
function isCacheValid(): boolean {
  return Date.now() - cacheTimestamp < PERFORMANCE_CONFIG.CACHE_TTL_MS;
}

function clearCache(): void {
  ruleCache.clear();
  conditionCache.clear();
  actionCache.clear();
  cacheTimestamp = 0;
}

// 批量加载规则数据到缓存
async function loadRulesToCache(supabase: any, ruleIds: number[]): Promise<void> {
  if (isCacheValid() && ruleCache.size > 0) {
    return; // 缓存仍然有效
  }

  try {
    // 并行加载所有数据
    const [rulesResult, condsResult, actsResult] = await Promise.all([
      supabase
        .from('yibao_rules')
        .select('id, code, name, rule_type, severity, enabled')
        .in('id', ruleIds)
        .eq('enabled', true),
      supabase
        .from('yibao_rule_conditions')
        .select('id, rule_id, priority, expression_json')
        .in('rule_id', ruleIds)
        .order('priority', { ascending: true }),
      supabase
        .from('yibao_rule_actions')
        .select('id, rule_id, action_type, message_template')
        .in('rule_id', ruleIds)
    ]);

    if (rulesResult.error) throw rulesResult.error;
    if (condsResult.error) throw condsResult.error;
    if (actsResult.error) throw actsResult.error;

    // 更新缓存
    ruleCache.clear();
    conditionCache.clear();
    actionCache.clear();

    (rulesResult.data || []).forEach(rule => ruleCache.set(rule.id, rule));

    (condsResult.data || []).forEach(cond => {
      if (!conditionCache.has(cond.rule_id)) {
        conditionCache.set(cond.rule_id, []);
      }
      conditionCache.get(cond.rule_id).push(cond);
    });

    (actsResult.data || []).forEach(act => {
      if (!actionCache.has(act.rule_id)) {
        actionCache.set(act.rule_id, []);
      }
      actionCache.get(act.rule_id).push(act);
    });

    cacheTimestamp = Date.now();
  } catch (error) {
    console.error('Failed to load rules to cache:', error);
    throw error;
  }
}

// 单个上下文评估（使用缓存）
function evaluateSingleContext(context: any): any[] {
  const hits: any[] = [];

  for (const [ruleId, rule] of ruleCache) {
    const rConds = conditionCache.get(ruleId) || [];
    const allTrue = rConds.every((c: any) => evalExpression(context, c.expression_json));

    if (allTrue) {
      const rActs = actionCache.get(ruleId) || [];
      const action = rActs[0] || {
        action_type: rule.severity === 'block' ? 'intercept' : 'warn',
        message_template: rule.name
      };
      const msg = renderMessage(action.message_template || rule.name, context);
      hits.push({
        ruleId: ruleId,
        ruleCode: rule.code,
        severity: rule.severity,
        action: action.action_type,
        message: msg
      });
    }
  }

  return hits;
}

// 批量评估（切片并行处理）
async function batchEvaluate(contexts: any[], recordViolations: boolean = false, supabase: any): Promise<any[]> {
  if (!PERFORMANCE_CONFIG.ENABLE_PARALLEL || contexts.length <= PERFORMANCE_CONFIG.BATCH_SIZE) {
    // 小批量或禁用并行时，直接处理
    return contexts.map(context => {
      const hits = evaluateSingleContext(context);
      return {
        context_id: context.id || 'unknown',
        decision: getDecision(hits),
        hits,
        execution_time_ms: 0 // 批量处理时不单独计时
      };
    });
  }

  // 大批量切片并行处理
  const chunks = [];
  for (let i = 0; i < contexts.length; i += PERFORMANCE_CONFIG.BATCH_SIZE) {
    chunks.push(contexts.slice(i, i + PERFORMANCE_CONFIG.BATCH_SIZE));
  }

  // 限制并发数
  const results: any[] = [];
  for (let i = 0; i < chunks.length; i += PERFORMANCE_CONFIG.MAX_CONCURRENT) {
    const concurrentChunks = chunks.slice(i, i + PERFORMANCE_CONFIG.MAX_CONCURRENT);

    const chunkPromises = concurrentChunks.map(async (chunk) => {
      return chunk.map(context => {
        const hits = evaluateSingleContext(context);
        return {
          context_id: context.id || 'unknown',
          decision: getDecision(hits),
          hits,
          execution_time_ms: 0
        };
      });
    });

    const chunkResults = await Promise.all(chunkPromises);
    results.push(...chunkResults.flat());
  }

  return results;
}

// 决策逻辑提取
function getDecision(hits: any[]): 'pass' | 'warn' | 'block' {
  let decision: 'pass' | 'warn' | 'block' = 'pass';
  for (const h of hits) {
    if (h.severity === 'block') {
      decision = 'block';
      break;
    }
    if (h.severity === 'warn') {
      decision = decision === 'pass' ? 'warn' : decision;
    }
  }
  return decision;
}

export async function handler(req: Request): Promise<Response> {
  const startTime = Date.now();
  let cacheHits = 0;
  let cacheMisses = 0;

  try {
    // CORS preflight
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (req.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
    }

    const requestBody = await req.json();
    const { event, context, contexts, record, batch } = requestBody;

    // 支持批量处理
    const isBatchRequest = batch === true || Array.isArray(contexts);

    if (isBatchRequest) {
      return await handleBatchRequest(requestBody, startTime);
    }

    // 单个请求处理
    const normalizedEvent = event || 'drug_order';
    if (!event || !context) {
      return Response.json({ error: 'Missing event or context' }, { status: 400, headers: corsHeaders });
    }

    const supabase = getSupabase();

    // 1) Find enabled rules that listen to this event
    const { data: triggerRules, error: trigErr } = await supabase
      .from('yibao_rule_triggers')
      .select('rule_id')
      .eq('event_type', normalizedEvent);
    if (trigErr) throw trigErr;

    const ruleIds = (triggerRules ?? []).map((r: any) => r.rule_id);
    if (ruleIds.length === 0) {
      return Response.json({
        decision: 'pass',
        hits: [],
        performance: {
          execution_time_ms: Date.now() - startTime,
          cache_hits: 0,
          cache_misses: 0,
          rules_evaluated: 0
        }
      }, { headers: corsHeaders });
    }

    // 使用缓存加载规则数据
    if (isCacheValid()) {
      cacheHits++;
    } else {
      cacheMisses++;
      await loadRulesToCache(supabase, ruleIds);
    }

    // 使用缓存进行评估
    const hits = evaluateSingleContext(context);
    const decision = getDecision(hits);

    // 记录违规（如果需要）
    if (record && hits.length > 0) {
      try {
        const violations = hits.map(hit => ({
          visit_id: context?.visit?.id ?? 'unknown',
          rule_id: hit.ruleId || 0,
          severity: hit.severity,
          snapshot: context,
        }));

        // 插入并返回ID，便于前端做“忽略”关联
        const { data: inserted, error: insErr } = await supabase
          .from('yibao_violations')
          .insert(violations)
          .select('id, rule_id')
          .order('id', { ascending: true });
        if (insErr) throw insErr;
        if (Array.isArray(inserted)) {
          for (let i = 0; i < hits.length && i < inserted.length; i++) {
            (hits[i] as any).violationId = inserted[i].id;
          }
        }
      } catch (violationError) {
        console.error('Failed to record violations:', violationError);
        // 不影响主流程，继续返回结果
      }
    }

    const executionTime = Date.now() - startTime;

    return Response.json({
      decision,
      hits,
      performance: {
        execution_time_ms: executionTime,
        cache_hits: cacheHits,
        cache_misses: cacheMisses,
        rules_evaluated: ruleCache.size,
        cache_hit_rate: cacheHits / (cacheHits + cacheMisses) || 0
      }
    }, { headers: corsHeaders });
  } catch (e) {
    console.error('Rule evaluation error:', e);
    return Response.json({
      error: String(e),
      timestamp: new Date().toISOString(),
      performance: {
        execution_time_ms: Date.now() - startTime,
        cache_hits: cacheHits,
        cache_misses: cacheMisses
      }
    }, { status: 500, headers: corsHeaders });
  }
}

// 批量请求处理函数
async function handleBatchRequest(requestBody: any, startTime: number): Promise<Response> {
  try {
    const { event, contexts, record } = requestBody;
    const normalizedEvent = event || 'drug_order';

    if (!contexts || !Array.isArray(contexts) || contexts.length === 0) {
      return Response.json({
        error: 'Missing or empty contexts array for batch request'
      }, { status: 400, headers: corsHeaders });
    }

    const supabase = getSupabase();

    // 获取触发规则
    const { data: triggerRules, error: trigErr } = await supabase
      .from('yibao_rule_triggers')
      .select('rule_id')
      .eq('event_type', normalizedEvent);
    if (trigErr) throw trigErr;

    const ruleIds = (triggerRules ?? []).map((r: any) => r.rule_id);
    if (ruleIds.length === 0) {
      return Response.json({
        results: contexts.map(ctx => ({
          context_id: ctx.id || 'unknown',
          decision: 'pass',
          hits: []
        })),
        performance: {
          execution_time_ms: Date.now() - startTime,
          total_contexts: contexts.length,
          rules_evaluated: 0,
          cache_hit_rate: 1.0
        }
      }, { headers: corsHeaders });
    }

    // 加载规则到缓存
    await loadRulesToCache(supabase, ruleIds);

    // 批量评估
    const results = await batchEvaluate(contexts, record, supabase);

    const executionTime = Date.now() - startTime;

    return Response.json({
      results,
      performance: {
        execution_time_ms: executionTime,
        total_contexts: contexts.length,
        rules_evaluated: ruleCache.size,
        avg_time_per_context: executionTime / contexts.length,
        cache_hit_rate: isCacheValid() ? 1.0 : 0.0,
        batch_size_used: PERFORMANCE_CONFIG.BATCH_SIZE,
        parallel_enabled: PERFORMANCE_CONFIG.ENABLE_PARALLEL
      }
    }, { headers: corsHeaders });

  } catch (error) {
    console.error('Batch evaluation error:', error);
    return Response.json({
      error: String(error),
      timestamp: new Date().toISOString(),
      performance: {
        execution_time_ms: Date.now() - startTime
      }
    }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);
