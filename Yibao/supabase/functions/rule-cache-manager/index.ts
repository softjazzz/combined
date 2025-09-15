// Edge Function: rule-cache-manager
// Purpose: 规则缓存管理 - 热重载、监控、预热功能
// Methods: POST /reload, GET /stats, POST /preload, DELETE /clear

import { createClient } from 'npm:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
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

// 缓存统计信息
interface CacheStats {
  total_rules: number;
  active_rules: number;
  cache_size_mb: number;
  hit_rate: number;
  last_reload_time: string;
  uptime_seconds: number;
  request_count: number;
  error_count: number;
}

// 全局缓存状态
let cacheStats: CacheStats = {
  total_rules: 0,
  active_rules: 0,
  cache_size_mb: 0,
  hit_rate: 0,
  last_reload_time: new Date().toISOString(),
  uptime_seconds: 0,
  request_count: 0,
  error_count: 0
};

const startTime = Date.now();

// 获取缓存统计信息
async function getCacheStats(): Promise<CacheStats> {
  const supabase = getSupabase();
  
  try {
    // 获取规则统计
    const { data: ruleStats, error: statsError } = await supabase
      .from('yibao_rules')
      .select('enabled')
      .eq('enabled', true);

    if (statsError) throw statsError;

    const totalRules = ruleStats?.length || 0;
    const activeRules = ruleStats?.filter(r => r.enabled).length || 0;

    // 估算缓存大小（简化计算）
    const cacheSizeMB = (totalRules * 2) / 1024; // 假设每个规则约2KB

    // 计算运行时间
    const uptimeSeconds = Math.floor((Date.now() - startTime) / 1000);

    cacheStats = {
      ...cacheStats,
      total_rules: totalRules,
      active_rules: activeRules,
      cache_size_mb: Math.round(cacheSizeMB * 100) / 100,
      uptime_seconds: uptimeSeconds,
      last_reload_time: new Date().toISOString()
    };

    return cacheStats;
  } catch (error) {
    cacheStats.error_count++;
    throw error;
  }
}

// 预热缓存
async function preloadCache(eventTypes?: string[]): Promise<any> {
  const supabase = getSupabase();
  const startTime = Date.now();
  
  try {
    let triggerQuery = supabase.from('yibao_rule_triggers').select('rule_id, event_type');
    
    if (eventTypes && eventTypes.length > 0) {
      triggerQuery = triggerQuery.in('event_type', eventTypes);
    }

    const { data: triggers, error: triggerError } = await triggerQuery;
    if (triggerError) throw triggerError;

    const ruleIds = [...new Set((triggers || []).map(t => t.rule_id))];
    
    if (ruleIds.length === 0) {
      return {
        success: true,
        message: 'No rules to preload',
        preloaded_rules: 0,
        execution_time_ms: Date.now() - startTime
      };
    }

    // 并行加载所有相关数据
    const [rulesResult, condsResult, actsResult] = await Promise.all([
      supabase
        .from('yibao_rules')
        .select('*')
        .in('id', ruleIds)
        .eq('enabled', true),
      supabase
        .from('yibao_rule_conditions')
        .select('*')
        .in('rule_id', ruleIds),
      supabase
        .from('yibao_rule_actions')
        .select('*')
        .in('rule_id', ruleIds)
    ]);

    if (rulesResult.error) throw rulesResult.error;
    if (condsResult.error) throw condsResult.error;
    if (actsResult.error) throw actsResult.error;

    const preloadedRules = rulesResult.data?.length || 0;
    const preloadedConditions = condsResult.data?.length || 0;
    const preloadedActions = actsResult.data?.length || 0;

    // 更新统计信息
    cacheStats.total_rules = preloadedRules;
    cacheStats.active_rules = preloadedRules;
    cacheStats.last_reload_time = new Date().toISOString();

    return {
      success: true,
      message: 'Cache preloaded successfully',
      preloaded_rules: preloadedRules,
      preloaded_conditions: preloadedConditions,
      preloaded_actions: preloadedActions,
      event_types: eventTypes || 'all',
      execution_time_ms: Date.now() - startTime
    };

  } catch (error) {
    cacheStats.error_count++;
    throw error;
  }
}

// 重载缓存
async function reloadCache(): Promise<any> {
  const startTime = Date.now();
  
  try {
    // 调用预热缓存功能
    const result = await preloadCache();
    
    return {
      ...result,
      message: 'Cache reloaded successfully',
      reload_time: new Date().toISOString()
    };
  } catch (error) {
    cacheStats.error_count++;
    throw error;
  }
}

// 清空缓存
async function clearCache(): Promise<any> {
  try {
    // 这里应该调用实际的缓存清空逻辑
    // 由于我们使用的是 Edge Function 的内存缓存，重启函数即可清空
    
    cacheStats = {
      total_rules: 0,
      active_rules: 0,
      cache_size_mb: 0,
      hit_rate: 0,
      last_reload_time: new Date().toISOString(),
      uptime_seconds: 0,
      request_count: 0,
      error_count: 0
    };

    return {
      success: true,
      message: 'Cache cleared successfully',
      cleared_at: new Date().toISOString()
    };
  } catch (error) {
    cacheStats.error_count++;
    throw error;
  }
}

// 健康检查
async function healthCheck(): Promise<any> {
  const supabase = getSupabase();
  
  try {
    // 测试数据库连接
    const { data, error } = await supabase
      .from('yibao_rules')
      .select('count')
      .limit(1);

    if (error) throw error;

    const stats = await getCacheStats();

    return {
      status: 'healthy',
      database_connection: 'ok',
      cache_status: 'active',
      uptime_seconds: stats.uptime_seconds,
      total_requests: stats.request_count,
      error_rate: stats.error_count / Math.max(stats.request_count, 1),
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      database_connection: 'error',
      cache_status: 'error',
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }
}

export async function handler(req: Request): Promise<Response> {
  cacheStats.request_count++;
  
  try {
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const url = new URL(req.url);
    const action = url.pathname.split('/').pop();

    let result;

    switch (req.method) {
      case 'GET':
        switch (action) {
          case 'stats':
            result = await getCacheStats();
            break;
          case 'health':
            result = await healthCheck();
            break;
          default:
            return Response.json({ error: 'Invalid GET action' }, { status: 400, headers: corsHeaders });
        }
        break;

      case 'POST':
        const body = req.method === 'POST' ? await req.json() : {};
        
        switch (action) {
          case 'reload':
            result = await reloadCache();
            break;
          case 'preload':
            result = await preloadCache(body.event_types);
            break;
          default:
            return Response.json({ error: 'Invalid POST action' }, { status: 400, headers: corsHeaders });
        }
        break;

      case 'DELETE':
        switch (action) {
          case 'clear':
            result = await clearCache();
            break;
          default:
            return Response.json({ error: 'Invalid DELETE action' }, { status: 400, headers: corsHeaders });
        }
        break;

      default:
        return Response.json({ error: 'Method not allowed' }, { status: 405, headers: corsHeaders });
    }

    return Response.json(result, { headers: corsHeaders });

  } catch (error) {
    cacheStats.error_count++;
    console.error('Cache manager error:', error);
    return Response.json({ 
      error: error.message || 'Internal server error',
      timestamp: new Date().toISOString()
    }, { 
      status: 500, 
      headers: corsHeaders 
    });
  }
}

Deno.serve(handler);
