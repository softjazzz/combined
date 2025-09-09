// Edge Function: statistics
// @ts-nocheck
// Purpose: Generate aggregated statistics for dashboard and reporting
// Endpoints:
//   GET /statistics/dashboard - Dashboard KPIs
//   GET /statistics/trends?days=30 - Trend data over time
//   GET /statistics/rules - Rule performance metrics

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
    const path = url.pathname.split('/').pop();

    if (req.method !== 'GET') {
      return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
    }

    switch (path) {
      case 'dashboard': {
        // Dashboard KPIs
        const today = new Date().toISOString().split('T')[0];
        const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        // Total violations today
        const { count: todayViolations } = await supabase
          .from('yibao_violations')
          .select('*', { count: 'exact', head: true })
          .gte('created_at', today);

        // Total violations yesterday
        const { count: yesterdayViolations } = await supabase
          .from('yibao_violations')
          .select('*', { count: 'exact', head: true })
          .gte('created_at', yesterday)
          .lt('created_at', today);

        // Active rules count
        const { count: activeRules } = await supabase
          .from('yibao_rules')
          .select('*', { count: 'exact', head: true })
          .eq('enabled', true);

        // Severity breakdown today
        const { data: severityData } = await supabase
          .from('yibao_violations')
          .select('severity')
          .gte('created_at', today);

        const severityBreakdown = {
          block: severityData?.filter(v => v.severity === 'block').length ?? 0,
          warn: severityData?.filter(v => v.severity === 'warn').length ?? 0,
          info: severityData?.filter(v => v.severity === 'info').length ?? 0
        };

        return Response.json({
          kpis: {
            todayViolations: todayViolations ?? 0,
            yesterdayViolations: yesterdayViolations ?? 0,
            activeRules: activeRules ?? 0,
            severityBreakdown
          }
        }, { headers: corsHeaders });
      }

      case 'trends': {
        const days = Math.min(parseInt(url.searchParams.get('days') ?? '30'), 90);
        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        const { data: trendData } = await supabase
          .from('yibao_violations')
          .select('created_at, severity')
          .gte('created_at', startDate)
          .order('created_at', { ascending: true });

        // Group by date
        const trends = new Map<string, { date: string; block: number; warn: number; info: number }>();
        
        trendData?.forEach(v => {
          const date = v.created_at.split('T')[0];
          const existing = trends.get(date) ?? { date, block: 0, warn: 0, info: 0 };
          existing[v.severity as keyof typeof existing]++;
          trends.set(date, existing);
        });

        return Response.json({
          trends: Array.from(trends.values()).sort((a, b) => a.date.localeCompare(b.date))
        }, { headers: corsHeaders });
      }

      case 'rules': {
        // Rule performance metrics
        const { data: ruleStats } = await supabase
          .from('yibao_violations')
          .select(`
            rule_id,
            severity,
            yibao_rules!inner(code, name, rule_type)
          `);

        const ruleMetrics = new Map<number, {
          ruleId: number;
          code: string;
          name: string;
          ruleType: string;
          totalViolations: number;
          blockCount: number;
          warnCount: number;
          infoCount: number;
        }>();

        ruleStats?.forEach(v => {
          const existing = ruleMetrics.get(v.rule_id) ?? {
            ruleId: v.rule_id,
            code: v.yibao_rules.code,
            name: v.yibao_rules.name,
            ruleType: v.yibao_rules.rule_type,
            totalViolations: 0,
            blockCount: 0,
            warnCount: 0,
            infoCount: 0
          };
          
          existing.totalViolations++;
          if (v.severity === 'block') existing.blockCount++;
          else if (v.severity === 'warn') existing.warnCount++;
          else if (v.severity === 'info') existing.infoCount++;
          
          ruleMetrics.set(v.rule_id, existing);
        });

        return Response.json({
          rules: Array.from(ruleMetrics.values())
            .sort((a, b) => b.totalViolations - a.totalViolations)
        }, { headers: corsHeaders });
      }

      default:
        return Response.json({ error: 'Unknown endpoint' }, { status: 404, headers: corsHeaders });
    }

  } catch (e) {
    return Response.json({ error: String(e) }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);
