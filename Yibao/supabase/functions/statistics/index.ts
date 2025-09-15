// Edge Function: statistics (Enhanced)
// @ts-nocheck
// Purpose: Comprehensive data analytics for medical insurance quality control
// Endpoints:
//   GET /statistics/dashboard - Dashboard KPIs
//   GET /statistics/trends?days=30&granularity=day - Trend data over time
//   GET /statistics/rules - Rule performance metrics
//   GET /statistics/departments - Department-level analytics
//   GET /statistics/doctors - Doctor-level analytics
//   GET /statistics/violations-analysis - Advanced violation analysis
//   GET /statistics/anomaly-detection - Anomaly detection results
//   GET /statistics/predictions - Predictive analytics

import { createClient } from 'npm:@supabase/supabase-js@2';

const ALLOWED_ORIGIN = Deno.env.get('ALLOWED_ORIGIN') || '*'
const corsHeaders = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
  'Access-Control-Max-Age': '86400'
};

// 数据分析工具函数
interface TimeSeriesPoint {
  date: string;
  value: number;
  metadata?: any;
}

interface TrendAnalysis {
  trend: 'increasing' | 'decreasing' | 'stable';
  slope: number;
  correlation: number;
  confidence: number;
}

// 计算趋势分析
function analyzeTrend(data: TimeSeriesPoint[]): TrendAnalysis {
  if (data.length < 3) {
    return { trend: 'stable', slope: 0, correlation: 0, confidence: 0 };
  }

  const n = data.length;
  const x = data.map((_, i) => i);
  const y = data.map(d => d.value);

  // 计算线性回归
  const sumX = x.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
  const sumXX = x.reduce((sum, xi) => sum + xi * xi, 0);

  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // 计算相关系数
  const meanX = sumX / n;
  const meanY = sumY / n;
  const numerator = x.reduce((sum, xi, i) => sum + (xi - meanX) * (y[i] - meanY), 0);
  const denomX = Math.sqrt(x.reduce((sum, xi) => sum + (xi - meanX) ** 2, 0));
  const denomY = Math.sqrt(y.reduce((sum, yi) => sum + (yi - meanY) ** 2, 0));
  const correlation = numerator / (denomX * denomY);

  // 确定趋势方向
  let trend: 'increasing' | 'decreasing' | 'stable' = 'stable';
  if (Math.abs(slope) > 0.1) {
    trend = slope > 0 ? 'increasing' : 'decreasing';
  }

  return {
    trend,
    slope,
    correlation,
    confidence: Math.abs(correlation)
  };
}

// 异常检测（基于Z-score）
function detectAnomalies(data: number[], threshold: number = 2): number[] {
  const mean = data.reduce((a, b) => a + b, 0) / data.length;
  const variance = data.reduce((sum, x) => sum + (x - mean) ** 2, 0) / data.length;
  const stdDev = Math.sqrt(variance);

  return data.map((value, index) => {
    const zScore = Math.abs((value - mean) / stdDev);
    return zScore > threshold ? index : -1;
  }).filter(index => index !== -1);
}

// 移动平均计算
function calculateMovingAverage(data: number[], window: number): number[] {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    const start = Math.max(0, i - window + 1);
    const slice = data.slice(start, i + 1);
    const avg = slice.reduce((a, b) => a + b, 0) / slice.length;
    result.push(Math.round(avg * 100) / 100);
  }
  return result;
}

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
        const days = Math.min(parseInt(url.searchParams.get('days') ?? '30'), 365);
        const granularity = url.searchParams.get('granularity') ?? 'day'; // day, week, month
        const includeAnalysis = url.searchParams.get('analysis') === 'true';
        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        const { data: trendData } = await supabase
          .from('yibao_violations')
          .select('created_at, severity, rule_id, visit_id')
          .gte('created_at', startDate)
          .order('created_at', { ascending: true });

        // 根据粒度分组数据
        const trends = new Map<string, {
          date: string;
          block: number;
          warn: number;
          info: number;
          total: number;
          unique_visits: Set<string>;
          unique_rules: Set<number>;
        }>();

        trendData?.forEach(v => {
          let dateKey: string;
          const date = new Date(v.created_at);

          switch (granularity) {
            case 'week':
              const weekStart = new Date(date);
              weekStart.setDate(date.getDate() - date.getDay());
              dateKey = weekStart.toISOString().split('T')[0];
              break;
            case 'month':
              dateKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`;
              break;
            default: // day
              dateKey = v.created_at.split('T')[0];
          }

          const existing = trends.get(dateKey) ?? {
            date: dateKey,
            block: 0,
            warn: 0,
            info: 0,
            total: 0,
            unique_visits: new Set(),
            unique_rules: new Set()
          };

          existing[v.severity as keyof typeof existing]++;
          existing.total++;
          existing.unique_visits.add(v.visit_id);
          existing.unique_rules.add(v.rule_id);
          trends.set(dateKey, existing);
        });

        // 转换为数组并计算额外指标
        const trendsArray = Array.from(trends.values())
          .map(t => ({
            date: t.date,
            block: t.block,
            warn: t.warn,
            info: t.info,
            total: t.total,
            unique_visits: t.unique_visits.size,
            unique_rules: t.unique_rules.size,
            severity_rate: {
              block_rate: t.total > 0 ? t.block / t.total : 0,
              warn_rate: t.total > 0 ? t.warn / t.total : 0,
              info_rate: t.total > 0 ? t.info / t.total : 0
            }
          }))
          .sort((a, b) => a.date.localeCompare(b.date));

        let analysis = null;
        if (includeAnalysis && trendsArray.length > 0) {
          const totalValues = trendsArray.map(t => t.total);
          const blockValues = trendsArray.map(t => t.block);
          const warnValues = trendsArray.map(t => t.warn);

          analysis = {
            total_trend: analyzeTrend(trendsArray.map((t, i) => ({ date: t.date, value: t.total }))),
            block_trend: analyzeTrend(trendsArray.map((t, i) => ({ date: t.date, value: t.block }))),
            warn_trend: analyzeTrend(trendsArray.map((t, i) => ({ date: t.date, value: t.warn }))),
            moving_averages: {
              total_7day: calculateMovingAverage(totalValues, 7),
              block_7day: calculateMovingAverage(blockValues, 7),
              warn_7day: calculateMovingAverage(warnValues, 7)
            },
            anomalies: {
              total_anomalies: detectAnomalies(totalValues),
              block_anomalies: detectAnomalies(blockValues),
              warn_anomalies: detectAnomalies(warnValues)
            },
            summary: {
              total_violations: totalValues.reduce((a, b) => a + b, 0),
              avg_daily_violations: totalValues.reduce((a, b) => a + b, 0) / totalValues.length,
              peak_day: trendsArray[totalValues.indexOf(Math.max(...totalValues))]?.date,
              peak_violations: Math.max(...totalValues)
            }
          };
        }

        return Response.json({
          trends: trendsArray,
          analysis,
          metadata: {
            granularity,
            days_analyzed: days,
            data_points: trendsArray.length,
            date_range: {
              start: trendsArray[0]?.date,
              end: trendsArray[trendsArray.length - 1]?.date
            }
          }
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

      case 'violations-analysis': {
        // 高级违规分析
        const timeRange = url.searchParams.get('range') ?? '30d';
        const groupBy = url.searchParams.get('group_by') ?? 'rule_type';

        let days = 30;
        if (timeRange.endsWith('d')) days = parseInt(timeRange);
        else if (timeRange.endsWith('w')) days = parseInt(timeRange) * 7;
        else if (timeRange.endsWith('m')) days = parseInt(timeRange) * 30;

        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

        // 获取违规数据及关联信息
        const { data: violationsData } = await supabase
          .from('yibao_violations')
          .select(`
            id, severity, created_at, visit_id, snapshot,
            yibao_rules!inner(code, name, rule_type, severity as rule_severity)
          `)
          .gte('created_at', startDate);

        if (!violationsData) {
          return Response.json({ error: 'No data found' }, { status: 404, headers: corsHeaders });
        }

        // 多维度分析
        const analysis: any = {
          overview: {
            total_violations: violationsData.length,
            unique_visits: new Set(violationsData.map(v => v.visit_id)).size,
            unique_rules: new Set(violationsData.map(v => v.yibao_rules.code)).size,
            time_range: { start: startDate, end: new Date().toISOString(), days }
          }
        };

        // 按规则类型分组
        if (groupBy === 'rule_type') {
          const byRuleType = violationsData.reduce((acc: any, v) => {
            const type = v.yibao_rules.rule_type;
            if (!acc[type]) {
              acc[type] = { total: 0, block: 0, warn: 0, info: 0, rules: new Set() };
            }
            acc[type].total++;
            acc[type][v.severity]++;
            acc[type].rules.add(v.yibao_rules.code);
            return acc;
          }, {});

          analysis.by_rule_type = Object.entries(byRuleType).map(([type, data]: [string, any]) => ({
            rule_type: type,
            total_violations: data.total,
            severity_breakdown: {
              block: data.block,
              warn: data.warn,
              info: data.info
            },
            unique_rules: data.rules.size,
            violation_rate: data.total / violationsData.length
          }));
        }

        // 按严重程度分析
        const bySeverity = violationsData.reduce((acc: any, v) => {
          acc[v.severity] = (acc[v.severity] || 0) + 1;
          return acc;
        }, {});

        analysis.severity_distribution = {
          block: { count: bySeverity.block || 0, rate: (bySeverity.block || 0) / violationsData.length },
          warn: { count: bySeverity.warn || 0, rate: (bySeverity.warn || 0) / violationsData.length },
          info: { count: bySeverity.info || 0, rate: (bySeverity.info || 0) / violationsData.length }
        };

        // 时间分布分析
        const hourlyDistribution = violationsData.reduce((acc: any, v) => {
          const hour = new Date(v.created_at).getHours();
          acc[hour] = (acc[hour] || 0) + 1;
          return acc;
        }, {});

        analysis.temporal_patterns = {
          hourly_distribution: Array.from({ length: 24 }, (_, i) => ({
            hour: i,
            count: hourlyDistribution[i] || 0
          })),
          peak_hour: Object.entries(hourlyDistribution).reduce((a: any, b: any) =>
            hourlyDistribution[a] > hourlyDistribution[b[0]] ? a : b[0], '0'
          )
        };

        // 规则效率分析
        const ruleEfficiency = violationsData.reduce((acc: any, v) => {
          const code = v.yibao_rules.code;
          if (!acc[code]) {
            acc[code] = {
              code,
              name: v.yibao_rules.name,
              rule_type: v.yibao_rules.rule_type,
              violations: 0,
              unique_visits: new Set()
            };
          }
          acc[code].violations++;
          acc[code].unique_visits.add(v.visit_id);
          return acc;
        }, {});

        analysis.rule_efficiency = Object.values(ruleEfficiency)
          .map((rule: any) => ({
            ...rule,
            unique_visits: rule.unique_visits.size,
            efficiency_score: rule.violations / rule.unique_visits.size // 每次就诊的平均违规数
          }))
          .sort((a: any, b: any) => b.violations - a.violations)
          .slice(0, 20); // 取前20个最活跃的规则

        return Response.json(analysis, { headers: corsHeaders });
      }

      case 'anomaly-detection': {
        // 异常检测分析
        const days = Math.min(parseInt(url.searchParams.get('days') ?? '30'), 90);
        const sensitivity = parseFloat(url.searchParams.get('sensitivity') ?? '2.0');
        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        const { data: dailyData } = await supabase
          .from('yibao_violations')
          .select('created_at, severity')
          .gte('created_at', startDate)
          .order('created_at', { ascending: true });

        // 按日期聚合
        const dailyViolations = dailyData?.reduce((acc: any, v) => {
          const date = v.created_at.split('T')[0];
          acc[date] = (acc[date] || 0) + 1;
          return acc;
        }, {}) || {};

        // 生成完整的日期序列
        const dateRange = [];
        for (let i = 0; i < days; i++) {
          const date = new Date(Date.now() - i * 24 * 60 * 60 * 1000);
          dateRange.unshift(date.toISOString().split('T')[0]);
        }

        const timeSeriesData = dateRange.map(date => ({
          date,
          violations: dailyViolations[date] || 0
        }));

        const violationCounts = timeSeriesData.map(d => d.violations);
        const anomalyIndices = detectAnomalies(violationCounts, sensitivity);

        const anomalies = anomalyIndices.map(index => ({
          date: timeSeriesData[index].date,
          violations: timeSeriesData[index].violations,
          z_score: Math.abs((timeSeriesData[index].violations -
            violationCounts.reduce((a, b) => a + b, 0) / violationCounts.length) /
            Math.sqrt(violationCounts.reduce((sum, x) => sum + (x - violationCounts.reduce((a, b) => a + b, 0) / violationCounts.length) ** 2, 0) / violationCounts.length)),
          severity: timeSeriesData[index].violations > violationCounts.reduce((a, b) => a + b, 0) / violationCounts.length ? 'high' : 'low'
        }));

        const analysis = {
          time_series: timeSeriesData,
          anomalies,
          statistics: {
            mean: violationCounts.reduce((a, b) => a + b, 0) / violationCounts.length,
            std_dev: Math.sqrt(violationCounts.reduce((sum, x) => sum + (x - violationCounts.reduce((a, b) => a + b, 0) / violationCounts.length) ** 2, 0) / violationCounts.length),
            min: Math.min(...violationCounts),
            max: Math.max(...violationCounts),
            total_anomalies: anomalies.length,
            anomaly_rate: anomalies.length / timeSeriesData.length
          },
          parameters: {
            sensitivity_threshold: sensitivity,
            days_analyzed: days,
            detection_method: 'z_score'
          }
        };

        return Response.json(analysis, { headers: corsHeaders });
      }

      case 'departments': {
        // 科室维度质控报告
        const timeRange = url.searchParams.get('range') ?? '30d';
        const includeComparison = url.searchParams.get('comparison') === 'true';

        let days = 30;
        if (timeRange.endsWith('d')) days = parseInt(timeRange);
        else if (timeRange.endsWith('w')) days = parseInt(timeRange) * 7;
        else if (timeRange.endsWith('m')) days = parseInt(timeRange) * 30;

        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

        // 获取科室违规数据（从snapshot中提取科室信息）
        const { data: violationsData } = await supabase
          .from('yibao_violations')
          .select(`
            id, severity, created_at, visit_id, snapshot,
            yibao_rules!inner(code, name, rule_type)
          `)
          .gte('created_at', startDate);

        if (!violationsData) {
          return Response.json({ departments: [], summary: {} }, { headers: corsHeaders });
        }

        // 从snapshot中提取科室信息并聚合
        const departmentStats = new Map<string, {
          department_code: string;
          department_name: string;
          total_violations: number;
          severity_breakdown: { block: number; warn: number; info: number };
          unique_visits: Set<string>;
          unique_rules: Set<string>;
          rule_types: Map<string, number>;
          daily_violations: Map<string, number>;
          top_rules: Map<string, { code: string; name: string; count: number }>;
        }>();

        violationsData.forEach(v => {
          // 从snapshot中提取科室信息
          const deptCode = v.snapshot?.visit?.department_code || v.snapshot?.department?.code || 'UNKNOWN';
          const deptName = v.snapshot?.visit?.department_name || v.snapshot?.department?.name || '未知科室';

          if (!departmentStats.has(deptCode)) {
            departmentStats.set(deptCode, {
              department_code: deptCode,
              department_name: deptName,
              total_violations: 0,
              severity_breakdown: { block: 0, warn: 0, info: 0 },
              unique_visits: new Set(),
              unique_rules: new Set(),
              rule_types: new Map(),
              daily_violations: new Map(),
              top_rules: new Map()
            });
          }

          const dept = departmentStats.get(deptCode)!;
          dept.total_violations++;
          dept.severity_breakdown[v.severity as keyof typeof dept.severity_breakdown]++;
          dept.unique_visits.add(v.visit_id);
          dept.unique_rules.add(v.yibao_rules.code);

          // 规则类型统计
          const ruleType = v.yibao_rules.rule_type;
          dept.rule_types.set(ruleType, (dept.rule_types.get(ruleType) || 0) + 1);

          // 日期统计
          const date = v.created_at.split('T')[0];
          dept.daily_violations.set(date, (dept.daily_violations.get(date) || 0) + 1);

          // 规则统计
          const ruleKey = v.yibao_rules.code;
          if (!dept.top_rules.has(ruleKey)) {
            dept.top_rules.set(ruleKey, {
              code: v.yibao_rules.code,
              name: v.yibao_rules.name,
              count: 0
            });
          }
          dept.top_rules.get(ruleKey)!.count++;
        });

        // 转换为数组并计算额外指标
        const departments = Array.from(departmentStats.values()).map(dept => {
          const violationRate = dept.total_violations / dept.unique_visits.size;
          const riskLevel = violationRate > 5 ? 'high' : violationRate > 2 ? 'medium' : 'low';

          // 计算趋势（简单的前后半期对比）
          const dailyViolationsArray = Array.from(dept.daily_violations.entries())
            .sort(([a], [b]) => a.localeCompare(b));
          const midPoint = Math.floor(dailyViolationsArray.length / 2);
          const firstHalf = dailyViolationsArray.slice(0, midPoint);
          const secondHalf = dailyViolationsArray.slice(midPoint);

          const firstHalfAvg = firstHalf.reduce((sum, [, count]) => sum + count, 0) / firstHalf.length || 0;
          const secondHalfAvg = secondHalf.reduce((sum, [, count]) => sum + count, 0) / secondHalf.length || 0;

          let trend = 'stable';
          if (secondHalfAvg > firstHalfAvg * 1.2) trend = 'increasing';
          else if (secondHalfAvg < firstHalfAvg * 0.8) trend = 'decreasing';

          return {
            department_code: dept.department_code,
            department_name: dept.department_name,
            total_violations: dept.total_violations,
            unique_visits: dept.unique_visits.size,
            unique_rules: dept.unique_rules.size,
            violation_rate: Math.round(violationRate * 100) / 100,
            risk_level: riskLevel,
            severity_breakdown: dept.severity_breakdown,
            rule_types: Object.fromEntries(dept.rule_types),
            trend,
            trend_change: Math.round((secondHalfAvg - firstHalfAvg) * 100) / 100,
            top_rules: Array.from(dept.top_rules.values())
              .sort((a, b) => b.count - a.count)
              .slice(0, 5),
            daily_pattern: Object.fromEntries(dept.daily_violations)
          };
        }).sort((a, b) => b.total_violations - a.total_violations);

        // 计算汇总统计
        const summary = {
          total_departments: departments.length,
          total_violations: departments.reduce((sum, d) => sum + d.total_violations, 0),
          avg_violation_rate: departments.reduce((sum, d) => sum + d.violation_rate, 0) / departments.length,
          high_risk_departments: departments.filter(d => d.risk_level === 'high').length,
          departments_with_increasing_trend: departments.filter(d => d.trend === 'increasing').length,
          top_department: departments[0]?.department_name || 'N/A',
          best_department: departments[departments.length - 1]?.department_name || 'N/A'
        };

        // 科室对比分析（如果请求）
        let comparison = null;
        if (includeComparison && departments.length > 1) {
          const avgViolationRate = summary.avg_violation_rate;
          comparison = {
            above_average: departments.filter(d => d.violation_rate > avgViolationRate),
            below_average: departments.filter(d => d.violation_rate <= avgViolationRate),
            performance_ranking: departments.map((d, index) => ({
              rank: index + 1,
              department_name: d.department_name,
              violation_rate: d.violation_rate,
              performance_score: Math.max(0, 100 - d.violation_rate * 10) // 简单评分算法
            }))
          };
        }

        return Response.json({
          departments,
          summary,
          comparison,
          metadata: {
            time_range: timeRange,
            days_analyzed: days,
            analysis_date: new Date().toISOString()
          }
        }, { headers: corsHeaders });
      }

      case 'doctors': {
        // 医生维度质控报告
        const timeRange = url.searchParams.get('range') ?? '30d';
        const departmentCode = url.searchParams.get('department');
        const includeProfile = url.searchParams.get('profile') === 'true';

        let days = 30;
        if (timeRange.endsWith('d')) days = parseInt(timeRange);
        else if (timeRange.endsWith('w')) days = parseInt(timeRange) * 7;
        else if (timeRange.endsWith('m')) days = parseInt(timeRange) * 30;

        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

        // 获取医生违规数据
        const { data: violationsData } = await supabase
          .from('yibao_violations')
          .select(`
            id, severity, created_at, visit_id, snapshot,
            yibao_rules!inner(code, name, rule_type)
          `)
          .gte('created_at', startDate);

        if (!violationsData) {
          return Response.json({ doctors: [], summary: {} }, { headers: corsHeaders });
        }

        // 从snapshot中提取医生信息并聚合
        const doctorStats = new Map<string, {
          doctor_code: string;
          doctor_name: string;
          department_code: string;
          department_name: string;
          total_violations: number;
          severity_breakdown: { block: number; warn: number; info: number };
          unique_visits: Set<string>;
          unique_rules: Set<string>;
          rule_types: Map<string, number>;
          violation_history: Array<{ date: string; count: number }>;
          improvement_trend: number;
        }>();

        violationsData.forEach(v => {
          // 从snapshot中提取医生信息
          const doctorCode = v.snapshot?.doctor?.code || v.snapshot?.visit?.doctor_code || 'UNKNOWN';
          const doctorName = v.snapshot?.doctor?.name || v.snapshot?.visit?.doctor_name || '未知医生';
          const deptCode = v.snapshot?.visit?.department_code || v.snapshot?.department?.code || 'UNKNOWN';
          const deptName = v.snapshot?.visit?.department_name || v.snapshot?.department?.name || '未知科室';

          // 如果指定了科室过滤
          if (departmentCode && deptCode !== departmentCode) {
            return;
          }

          if (!doctorStats.has(doctorCode)) {
            doctorStats.set(doctorCode, {
              doctor_code: doctorCode,
              doctor_name: doctorName,
              department_code: deptCode,
              department_name: deptName,
              total_violations: 0,
              severity_breakdown: { block: 0, warn: 0, info: 0 },
              unique_visits: new Set(),
              unique_rules: new Set(),
              rule_types: new Map(),
              violation_history: [],
              improvement_trend: 0
            });
          }

          const doctor = doctorStats.get(doctorCode)!;
          doctor.total_violations++;
          doctor.severity_breakdown[v.severity as keyof typeof doctor.severity_breakdown]++;
          doctor.unique_visits.add(v.visit_id);
          doctor.unique_rules.add(v.yibao_rules.code);

          // 规则类型统计
          const ruleType = v.yibao_rules.rule_type;
          doctor.rule_types.set(ruleType, (doctor.rule_types.get(ruleType) || 0) + 1);
        });

        // 转换为数组并计算医生质控档案
        const doctors = Array.from(doctorStats.values()).map(doctor => {
          const violationRate = doctor.total_violations / doctor.unique_visits.size;
          const qualityScore = Math.max(0, 100 - violationRate * 15); // 质控评分算法

          // 风险等级评估
          let riskLevel = 'low';
          if (violationRate > 3) riskLevel = 'high';
          else if (violationRate > 1.5) riskLevel = 'medium';

          // 改进建议
          const suggestions = [];
          const topRuleType = Array.from(doctor.rule_types.entries())
            .sort(([,a], [,b]) => b - a)[0];

          if (topRuleType) {
            suggestions.push(`重点关注${topRuleType[0]}类规则，占违规总数的${Math.round(topRuleType[1]/doctor.total_violations*100)}%`);
          }

          if (doctor.severity_breakdown.block > 0) {
            suggestions.push(`存在${doctor.severity_breakdown.block}次阻断级违规，需要立即整改`);
          }

          if (violationRate > 2) {
            suggestions.push('建议参加质控培训，提高规范意识');
          }

          return {
            doctor_code: doctor.doctor_code,
            doctor_name: doctor.doctor_name,
            department_code: doctor.department_code,
            department_name: doctor.department_name,
            total_violations: doctor.total_violations,
            unique_visits: doctor.unique_visits.size,
            unique_rules: doctor.unique_rules.size,
            violation_rate: Math.round(violationRate * 100) / 100,
            quality_score: Math.round(qualityScore * 100) / 100,
            risk_level: riskLevel,
            severity_breakdown: doctor.severity_breakdown,
            rule_types: Object.fromEntries(doctor.rule_types),
            improvement_suggestions: suggestions,
            performance_grade: qualityScore >= 90 ? 'A' : qualityScore >= 80 ? 'B' : qualityScore >= 70 ? 'C' : 'D'
          };
        }).sort((a, b) => b.total_violations - a.total_violations);

        // 计算汇总统计
        const summary = {
          total_doctors: doctors.length,
          total_violations: doctors.reduce((sum, d) => sum + d.total_violations, 0),
          avg_violation_rate: doctors.reduce((sum, d) => sum + d.violation_rate, 0) / doctors.length,
          avg_quality_score: doctors.reduce((sum, d) => sum + d.quality_score, 0) / doctors.length,
          high_risk_doctors: doctors.filter(d => d.risk_level === 'high').length,
          grade_distribution: {
            A: doctors.filter(d => d.performance_grade === 'A').length,
            B: doctors.filter(d => d.performance_grade === 'B').length,
            C: doctors.filter(d => d.performance_grade === 'C').length,
            D: doctors.filter(d => d.performance_grade === 'D').length
          },
          top_performer: doctors.find(d => d.performance_grade === 'A')?.doctor_name || 'N/A',
          needs_attention: doctors.filter(d => d.risk_level === 'high').map(d => d.doctor_name)
        };

        return Response.json({
          doctors,
          summary,
          metadata: {
            time_range: timeRange,
            department_filter: departmentCode,
            days_analyzed: days,
            analysis_date: new Date().toISOString()
          }
        }, { headers: corsHeaders });
      }

      case 'predictions': {
        // 预测分析 - 增强版
        const timeRange = url.searchParams.get('range') ?? '90d';
        const predictionDays = parseInt(url.searchParams.get('days') ?? '7');
        const modelType = url.searchParams.get('model') ?? 'linear'; // linear, moving_average, seasonal

        let days = 90;
        if (timeRange.endsWith('d')) days = parseInt(timeRange);
        else if (timeRange.endsWith('w')) days = parseInt(timeRange) * 7;
        else if (timeRange.endsWith('m')) days = parseInt(timeRange) * 30;

        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

        // 获取历史数据用于预测
        const { data: historicalData } = await supabase
          .from('yibao_violations')
          .select('created_at, severity, visit_id')
          .gte('created_at', startDate)
          .order('created_at');

        if (!historicalData || historicalData.length === 0) {
          return Response.json({ predictions: [], confidence: 0 }, { headers: corsHeaders });
        }

        // 按天聚合数据，包含更多维度
        const dailyData = new Map<string, {
          total: number;
          block: number;
          warn: number;
          info: number;
          unique_visits: Set<string>;
        }>();

        historicalData.forEach(v => {
          const date = v.created_at.split('T')[0];
          if (!dailyData.has(date)) {
            dailyData.set(date, {
              total: 0,
              block: 0,
              warn: 0,
              info: 0,
              unique_visits: new Set()
            });
          }
          const dayData = dailyData.get(date)!;
          dayData.total++;
          dayData[v.severity as keyof typeof dayData]++;
          dayData.unique_visits.add(v.visit_id);
        });

        const sortedDates = Array.from(dailyData.keys()).sort();
        const values = sortedDates.map(date => dailyData.get(date)!.total);
        const blockValues = sortedDates.map(date => dailyData.get(date)!.block);
        const warnValues = sortedDates.map(date => dailyData.get(date)!.warn);
        const infoValues = sortedDates.map(date => dailyData.get(date)!.info);

        const n = values.length;
        if (n < 7) {
          return Response.json({
            predictions: [],
            confidence: 0,
            message: '数据不足，无法进行预测'
          }, { headers: corsHeaders });
        }

        let predictions: any[] = [];
        let modelInfo: any = {};
        let confidence = 0;

        if (modelType === 'moving_average') {
          // 移动平均预测
          const windowSize = Math.min(7, Math.floor(n / 3));
          const recentValues = values.slice(-windowSize);
          const avgTotal = recentValues.reduce((a, b) => a + b, 0) / windowSize;

          const recentBlocks = blockValues.slice(-windowSize);
          const avgBlock = recentBlocks.reduce((a, b) => a + b, 0) / windowSize;

          const recentWarns = warnValues.slice(-windowSize);
          const avgWarn = recentWarns.reduce((a, b) => a + b, 0) / windowSize;

          const recentInfos = infoValues.slice(-windowSize);
          const avgInfo = recentInfos.reduce((a, b) => a + b, 0) / windowSize;

          // 计算移动平均的稳定性
          const variance = recentValues.reduce((sum, val) => sum + Math.pow(val - avgTotal, 2), 0) / windowSize;
          confidence = Math.max(0.1, Math.min(0.9, 1 - (Math.sqrt(variance) / avgTotal)));

          const lastDate = new Date(sortedDates[sortedDates.length - 1]);

          for (let i = 1; i <= predictionDays; i++) {
            const futureDate = new Date(lastDate);
            futureDate.setDate(futureDate.getDate() + i);

            predictions.push({
              date: futureDate.toISOString().split('T')[0],
              predicted_violations: Math.round(avgTotal),
              predicted_breakdown: {
                block: Math.round(avgBlock),
                warn: Math.round(avgWarn),
                info: Math.round(avgInfo)
              },
              confidence_level: confidence
            });
          }

          modelInfo = {
            type: 'moving_average',
            window_size: windowSize,
            average_violations: avgTotal,
            variance: variance,
            training_days: n
          };

        } else if (modelType === 'seasonal') {
          // 季节性预测（基于星期几的模式）
          const weeklyPattern = new Map<number, number[]>();

          sortedDates.forEach((date, index) => {
            const dayOfWeek = new Date(date).getDay();
            if (!weeklyPattern.has(dayOfWeek)) {
              weeklyPattern.set(dayOfWeek, []);
            }
            weeklyPattern.get(dayOfWeek)!.push(values[index]);
          });

          // 计算每个星期几的平均值
          const weeklyAverages = new Map<number, number>();
          weeklyPattern.forEach((values, dayOfWeek) => {
            const avg = values.reduce((a, b) => a + b, 0) / values.length;
            weeklyAverages.set(dayOfWeek, avg);
          });

          // 计算季节性模式的可靠性
          let totalVariance = 0;
          let totalCount = 0;
          weeklyPattern.forEach((values, dayOfWeek) => {
            const avg = weeklyAverages.get(dayOfWeek)!;
            const variance = values.reduce((sum, val) => sum + Math.pow(val - avg, 2), 0) / values.length;
            totalVariance += variance * values.length;
            totalCount += values.length;
          });
          const avgVariance = totalVariance / totalCount;
          const overallAvg = values.reduce((a, b) => a + b, 0) / values.length;
          confidence = Math.max(0.1, Math.min(0.9, 1 - (Math.sqrt(avgVariance) / overallAvg)));

          const lastDate = new Date(sortedDates[sortedDates.length - 1]);

          for (let i = 1; i <= predictionDays; i++) {
            const futureDate = new Date(lastDate);
            futureDate.setDate(futureDate.getDate() + i);
            const dayOfWeek = futureDate.getDay();

            const predicted = weeklyAverages.get(dayOfWeek) || overallAvg;

            predictions.push({
              date: futureDate.toISOString().split('T')[0],
              predicted_violations: Math.round(predicted),
              day_of_week: dayOfWeek,
              confidence_level: confidence
            });
          }

          modelInfo = {
            type: 'seasonal',
            weekly_pattern: Object.fromEntries(weeklyAverages),
            average_variance: avgVariance,
            training_days: n
          };

        } else {
          // 线性回归预测（默认）
          const x = Array.from({ length: n }, (_, i) => i);
          const sumX = x.reduce((a, b) => a + b, 0);
          const sumY = values.reduce((a, b) => a + b, 0);
          const sumXY = x.reduce((sum, xi, i) => sum + xi * values[i], 0);
          const sumXX = x.reduce((sum, xi) => sum + xi * xi, 0);

          const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
          const intercept = (sumY - slope * sumX) / n;

          // 计算R²
          const yMean = sumY / n;
          const ssRes = values.reduce((sum, yi, i) => {
            const predicted = slope * i + intercept;
            return sum + Math.pow(yi - predicted, 2);
          }, 0);
          const ssTot = values.reduce((sum, yi) => sum + Math.pow(yi - yMean, 2), 0);
          const rSquared = 1 - (ssRes / ssTot);
          confidence = Math.max(0.1, Math.min(0.9, rSquared));

          // 生成预测
          const lastDate = new Date(sortedDates[sortedDates.length - 1]);

          for (let i = 1; i <= predictionDays; i++) {
            const futureDate = new Date(lastDate);
            futureDate.setDate(futureDate.getDate() + i);

            const predicted = Math.max(0, Math.round(slope * (n + i - 1) + intercept));

            predictions.push({
              date: futureDate.toISOString().split('T')[0],
              predicted_violations: predicted,
              trend: slope > 0.1 ? 'increasing' : slope < -0.1 ? 'decreasing' : 'stable',
              confidence_level: confidence
            });
          }

          modelInfo = {
            type: 'linear_regression',
            r_squared: rSquared,
            slope,
            intercept,
            training_days: n
          };
        }

        return Response.json({
          predictions,
          model_info: modelInfo,
          confidence,
          historical_summary: {
            total_days: n,
            avg_daily_violations: values.reduce((a, b) => a + b, 0) / n,
            max_daily_violations: Math.max(...values),
            min_daily_violations: Math.min(...values)
          }
        }, { headers: corsHeaders });
      }

      default:
        return Response.json({ error: 'Unknown endpoint' }, { status: 404, headers: corsHeaders });
    }

  } catch (e) {
    console.error('Statistics error:', e);
    return Response.json({ error: String(e) }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);
