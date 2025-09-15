// Edge Function: rule-performance-monitor
// Purpose: 质控引擎性能监控和统计分析
// Methods: GET /stats, GET /metrics, POST /benchmark, GET /health

import { createClient } from 'npm:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
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

// 性能统计接口
interface PerformanceStats {
  total_evaluations: number;
  avg_execution_time_ms: number;
  p95_execution_time_ms: number;
  cache_hit_rate: number;
  error_rate: number;
  rules_per_evaluation: number;
  violations_detected: number;
}

// 获取性能统计
async function getPerformanceStats(supabase: any, timeRange: string = '24h'): Promise<PerformanceStats> {
  const now = new Date();
  let startTime: Date;
  
  switch (timeRange) {
    case '1h':
      startTime = new Date(now.getTime() - 60 * 60 * 1000);
      break;
    case '24h':
      startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      break;
    case '7d':
      startTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      break;
    default:
      startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  }

  try {
    // 获取违规统计
    const { data: violations, error: violationsError } = await supabase
      .from('yibao_violations')
      .select('id, created_at, severity')
      .gte('created_at', startTime.toISOString());

    if (violationsError) throw violationsError;

    // 模拟性能数据（实际应该从日志或监控系统获取）
    const totalEvaluations = Math.floor(Math.random() * 10000) + 1000;
    const avgExecutionTime = Math.random() * 50 + 10; // 10-60ms
    const p95ExecutionTime = avgExecutionTime * 2.5;
    const cacheHitRate = 0.85 + Math.random() * 0.1; // 85-95%
    const errorRate = Math.random() * 0.02; // 0-2%
    const rulesPerEvaluation = 15 + Math.random() * 10; // 15-25 rules

    return {
      total_evaluations: totalEvaluations,
      avg_execution_time_ms: Math.round(avgExecutionTime * 100) / 100,
      p95_execution_time_ms: Math.round(p95ExecutionTime * 100) / 100,
      cache_hit_rate: Math.round(cacheHitRate * 1000) / 1000,
      error_rate: Math.round(errorRate * 1000) / 1000,
      rules_per_evaluation: Math.round(rulesPerEvaluation * 10) / 10,
      violations_detected: violations?.length || 0
    };
  } catch (error) {
    throw new Error(`Failed to get performance stats: ${error.message}`);
  }
}

// 获取详细指标
async function getDetailedMetrics(supabase: any): Promise<any> {
  try {
    // 获取规则统计
    const { data: ruleStats, error: ruleError } = await supabase
      .from('yibao_rules')
      .select('enabled, severity, rule_type')
      .eq('enabled', true);

    if (ruleError) throw ruleError;

    // 获取最近的违规趋势
    const { data: recentViolations, error: violationError } = await supabase
      .from('yibao_violations')
      .select('severity, created_at')
      .gte('created_at', new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString())
      .order('created_at', { ascending: false });

    if (violationError) throw violationError;

    // 按严重程度分组规则
    const rulesBySeverity = (ruleStats || []).reduce((acc: any, rule: any) => {
      acc[rule.severity] = (acc[rule.severity] || 0) + 1;
      return acc;
    }, {});

    // 按类型分组规则
    const rulesByType = (ruleStats || []).reduce((acc: any, rule: any) => {
      acc[rule.rule_type] = (acc[rule.rule_type] || 0) + 1;
      return acc;
    }, {});

    // 违规趋势（按天）
    const violationTrend = (recentViolations || []).reduce((acc: any, violation: any) => {
      const date = violation.created_at.split('T')[0];
      if (!acc[date]) {
        acc[date] = { total: 0, warn: 0, block: 0 };
      }
      acc[date].total++;
      acc[date][violation.severity]++;
      return acc;
    }, {});

    return {
      rule_distribution: {
        by_severity: rulesBySeverity,
        by_type: rulesByType,
        total_active: ruleStats?.length || 0
      },
      violation_trend: violationTrend,
      recent_violations: {
        total: recentViolations?.length || 0,
        last_24h: (recentViolations || []).filter(v => 
          new Date(v.created_at) > new Date(Date.now() - 24 * 60 * 60 * 1000)
        ).length
      }
    };
  } catch (error) {
    throw new Error(`Failed to get detailed metrics: ${error.message}`);
  }
}

// 执行性能基准测试
async function runBenchmark(supabase: any, params: any): Promise<any> {
  const { test_contexts = 100, concurrent_requests = 5 } = params;
  
  try {
    const startTime = Date.now();
    const results = [];

    // 生成测试上下文
    const testContexts = Array.from({ length: test_contexts }, (_, i) => ({
      id: `test_${i}`,
      patient: {
        id: `patient_${i}`,
        age: 30 + Math.floor(Math.random() * 50),
        gender: Math.random() > 0.5 ? 'M' : 'F'
      },
      visit: {
        id: `visit_${i}`,
        department: 'internal_medicine'
      },
      order: {
        drug_code: `drug_${Math.floor(Math.random() * 100)}`,
        dosage: Math.random() * 100
      }
    }));

    // 分批并发测试
    const batchSize = Math.ceil(test_contexts / concurrent_requests);
    for (let i = 0; i < concurrent_requests; i++) {
      const batch = testContexts.slice(i * batchSize, (i + 1) * batchSize);
      
      const batchStartTime = Date.now();
      
      // 调用评估API（这里模拟）
      const batchResult = {
        batch_id: i,
        contexts_count: batch.length,
        execution_time_ms: Math.random() * 100 + 20, // 20-120ms
        cache_hit_rate: 0.8 + Math.random() * 0.2,
        violations_found: Math.floor(Math.random() * batch.length * 0.1)
      };
      
      results.push(batchResult);
    }

    const totalTime = Date.now() - startTime;
    const avgExecutionTime = results.reduce((sum, r) => sum + r.execution_time_ms, 0) / results.length;
    const totalViolations = results.reduce((sum, r) => sum + r.violations_found, 0);

    return {
      benchmark_id: `bench_${Date.now()}`,
      test_parameters: {
        test_contexts,
        concurrent_requests,
        batch_size: batchSize
      },
      results: {
        total_execution_time_ms: totalTime,
        avg_batch_time_ms: Math.round(avgExecutionTime * 100) / 100,
        throughput_contexts_per_second: Math.round((test_contexts / totalTime) * 1000),
        total_violations_found: totalViolations,
        violation_rate: Math.round((totalViolations / test_contexts) * 1000) / 1000
      },
      batch_results: results,
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    throw new Error(`Benchmark failed: ${error.message}`);
  }
}

// 健康检查
async function healthCheck(supabase: any): Promise<any> {
  try {
    const startTime = Date.now();
    
    // 测试数据库连接
    const { data: dbTest, error: dbError } = await supabase
      .from('yibao_rules')
      .select('count')
      .limit(1);

    const dbLatency = Date.now() - startTime;

    if (dbError) {
      return {
        status: 'unhealthy',
        database: {
          status: 'error',
          error: dbError.message,
          latency_ms: dbLatency
        },
        timestamp: new Date().toISOString()
      };
    }

    // 检查关键表
    const tableChecks = await Promise.all([
      supabase.from('yibao_rules').select('count').limit(1),
      supabase.from('yibao_rule_conditions').select('count').limit(1),
      supabase.from('yibao_rule_actions').select('count').limit(1),
      supabase.from('yibao_violations').select('count').limit(1)
    ]);

    const allTablesHealthy = tableChecks.every(check => !check.error);

    return {
      status: allTablesHealthy ? 'healthy' : 'degraded',
      database: {
        status: 'ok',
        latency_ms: dbLatency
      },
      tables: {
        yibao_rules: !tableChecks[0].error,
        yibao_rule_conditions: !tableChecks[1].error,
        yibao_rule_actions: !tableChecks[2].error,
        yibao_violations: !tableChecks[3].error
      },
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }
}

export async function handler(req: Request): Promise<Response> {
  try {
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const url = new URL(req.url);
    const action = url.pathname.split('/').pop();
    const supabase = getSupabase();

    let result;

    switch (req.method) {
      case 'GET':
        const params = Object.fromEntries(url.searchParams);
        
        switch (action) {
          case 'stats':
            result = await getPerformanceStats(supabase, params.time_range);
            break;
          case 'metrics':
            result = await getDetailedMetrics(supabase);
            break;
          case 'health':
            result = await healthCheck(supabase);
            break;
          default:
            return Response.json({ error: 'Invalid GET action' }, { status: 400, headers: corsHeaders });
        }
        break;

      case 'POST':
        const body = await req.json();
        
        switch (action) {
          case 'benchmark':
            result = await runBenchmark(supabase, body);
            break;
          default:
            return Response.json({ error: 'Invalid POST action' }, { status: 400, headers: corsHeaders });
        }
        break;

      default:
        return Response.json({ error: 'Method not allowed' }, { status: 405, headers: corsHeaders });
    }

    return Response.json(result, { headers: corsHeaders });

  } catch (error) {
    console.error('Performance monitor error:', error);
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
