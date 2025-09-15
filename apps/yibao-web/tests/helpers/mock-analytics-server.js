#!/usr/bin/env node

/**
 * 模拟数据分析API服务器
 * 用于测试数据分析模块功能
 */

import express from 'express'
import cors from 'cors'

const app = express()
const PORT = 54321

app.use(cors())
app.use(express.json())

// 生成模拟数据的工具函数
function generateMockTrendData(days, granularity) {
  const data = []
  const now = new Date()
  
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    
    const dateStr = date.toISOString().split('T')[0]
    const block = Math.floor(Math.random() * 20) + 5
    const warn = Math.floor(Math.random() * 30) + 10
    const info = Math.floor(Math.random() * 40) + 15
    
    data.push({
      date: dateStr,
      block,
      warn,
      info,
      total: block + warn + info,
      unique_visits: Math.floor(Math.random() * 50) + 20,
      unique_rules: Math.floor(Math.random() * 15) + 5,
      severity_rate: {
        block_rate: block / (block + warn + info),
        warn_rate: warn / (block + warn + info),
        info_rate: info / (block + warn + info)
      }
    })
  }
  
  return data
}

function generateTrendAnalysis(data) {
  const values = data.map(d => d.total)
  const slope = (values[values.length - 1] - values[0]) / values.length
  
  return {
    total_trend: {
      trend: slope > 1 ? 'increasing' : slope < -1 ? 'decreasing' : 'stable',
      slope,
      correlation: 0.7 + Math.random() * 0.3,
      confidence: 0.8 + Math.random() * 0.2
    },
    block_trend: {
      trend: 'stable',
      slope: 0.1,
      correlation: 0.6,
      confidence: 0.7
    },
    warn_trend: {
      trend: 'decreasing',
      slope: -0.2,
      correlation: 0.8,
      confidence: 0.9
    },
    moving_averages: {
      total_7day: values.map((_, i) => {
        const start = Math.max(0, i - 6)
        const slice = values.slice(start, i + 1)
        return slice.reduce((a, b) => a + b, 0) / slice.length
      }),
      block_7day: data.map(d => d.block),
      warn_7day: data.map(d => d.warn)
    },
    anomalies: {
      total_anomalies: [2, 5, 8],
      block_anomalies: [1, 3],
      warn_anomalies: [4, 7]
    },
    summary: {
      total_violations: values.reduce((a, b) => a + b, 0),
      avg_daily_violations: values.reduce((a, b) => a + b, 0) / values.length,
      peak_day: data[values.indexOf(Math.max(...values))].date,
      peak_violations: Math.max(...values)
    }
  }
}

// API 端点
app.get('/functions/v1/statistics/dashboard', (req, res) => {
  res.json({
    kpis: {
      todayViolations: Math.floor(Math.random() * 50) + 20,
      yesterdayViolations: Math.floor(Math.random() * 45) + 15,
      activeRules: 1173,
      severityBreakdown: {
        block: Math.floor(Math.random() * 10) + 5,
        warn: Math.floor(Math.random() * 15) + 8,
        info: Math.floor(Math.random() * 25) + 12
      }
    }
  })
})

app.get('/functions/v1/statistics/trends', (req, res) => {
  const days = parseInt(req.query.days) || 30
  const granularity = req.query.granularity || 'day'
  const includeAnalysis = req.query.analysis === 'true'
  
  const trends = generateMockTrendData(days, granularity)
  const analysis = includeAnalysis ? generateTrendAnalysis(trends) : null
  
  res.json({
    trends,
    analysis,
    metadata: {
      granularity,
      days_analyzed: days,
      data_points: trends.length,
      date_range: {
        start: trends[0]?.date,
        end: trends[trends.length - 1]?.date
      }
    }
  })
})

app.get('/functions/v1/statistics/violations-analysis', (req, res) => {
  const range = req.query.range || '30d'
  const groupBy = req.query.group_by || 'rule_type'
  
  const ruleTypes = ['药品使用', '诊疗规范', '费用控制', '医保政策', '临床路径']
  
  res.json({
    overview: {
      total_violations: Math.floor(Math.random() * 1000) + 500,
      unique_visits: Math.floor(Math.random() * 300) + 150,
      unique_rules: Math.floor(Math.random() * 50) + 25,
      time_range: {
        start: new Date(Date.now() - parseInt(range) * 24 * 60 * 60 * 1000).toISOString(),
        end: new Date().toISOString(),
        days: parseInt(range)
      }
    },
    by_rule_type: ruleTypes.map(type => ({
      rule_type: type,
      total_violations: Math.floor(Math.random() * 200) + 50,
      severity_breakdown: {
        block: Math.floor(Math.random() * 30) + 10,
        warn: Math.floor(Math.random() * 50) + 20,
        info: Math.floor(Math.random() * 80) + 30
      },
      unique_rules: Math.floor(Math.random() * 10) + 5,
      violation_rate: Math.random() * 0.3 + 0.1
    })),
    severity_distribution: {
      block: { count: 150, rate: 0.15 },
      warn: { count: 300, rate: 0.30 },
      info: { count: 550, rate: 0.55 }
    },
    temporal_patterns: {
      hourly_distribution: Array.from({ length: 24 }, (_, i) => ({
        hour: i,
        count: Math.floor(Math.random() * 50) + (i >= 8 && i <= 18 ? 20 : 5)
      })),
      peak_hour: '14'
    },
    rule_efficiency: Array.from({ length: 20 }, (_, i) => ({
      code: `RULE_${String(i + 1).padStart(3, '0')}`,
      name: `规则${i + 1}`,
      rule_type: ruleTypes[i % ruleTypes.length],
      violations: Math.floor(Math.random() * 100) + 20,
      unique_visits: Math.floor(Math.random() * 50) + 10,
      efficiency_score: Math.random() * 3 + 1
    })).sort((a, b) => b.violations - a.violations)
  })
})

app.get('/functions/v1/statistics/anomaly-detection', (req, res) => {
  const days = parseInt(req.query.days) || 30
  const sensitivity = parseFloat(req.query.sensitivity) || 2.0
  
  const timeSeries = Array.from({ length: days }, (_, i) => {
    const date = new Date()
    date.setDate(date.getDate() - (days - 1 - i))
    return {
      date: date.toISOString().split('T')[0],
      violations: Math.floor(Math.random() * 50) + 20 + (Math.random() > 0.9 ? 30 : 0)
    }
  })
  
  const anomalies = timeSeries
    .map((item, index) => ({ ...item, index }))
    .filter(() => Math.random() > 0.85)
    .map(item => ({
      date: item.date,
      violations: item.violations,
      z_score: Math.random() * 2 + sensitivity,
      severity: item.violations > 50 ? 'high' : 'low'
    }))
  
  const values = timeSeries.map(d => d.violations)
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const variance = values.reduce((sum, x) => sum + (x - mean) ** 2, 0) / values.length
  const stdDev = Math.sqrt(variance)
  
  res.json({
    time_series: timeSeries,
    anomalies,
    statistics: {
      mean,
      std_dev: stdDev,
      min: Math.min(...values),
      max: Math.max(...values),
      total_anomalies: anomalies.length,
      anomaly_rate: anomalies.length / timeSeries.length
    },
    parameters: {
      sensitivity_threshold: sensitivity,
      days_analyzed: days,
      detection_method: 'z_score'
    }
  })
})

app.get('/functions/v1/statistics/rules', (req, res) => {
  const rules = Array.from({ length: 50 }, (_, i) => ({
    ruleId: i + 1,
    code: `RULE_${String(i + 1).padStart(3, '0')}`,
    name: `医保规则${i + 1}`,
    ruleType: ['药品使用', '诊疗规范', '费用控制', '医保政策', '临床路径'][i % 5],
    totalViolations: Math.floor(Math.random() * 200) + 50,
    blockCount: Math.floor(Math.random() * 30) + 10,
    warnCount: Math.floor(Math.random() * 50) + 20,
    infoCount: Math.floor(Math.random() * 80) + 30
  })).sort((a, b) => b.totalViolations - a.totalViolations)
  
  res.json({ rules })
})

// 启动服务器
app.listen(PORT, () => {
  console.log(`🚀 模拟数据分析API服务器启动成功`)
  console.log(`📡 服务地址: http://localhost:${PORT}`)
  console.log(`📊 可用端点:`)
  console.log(`   GET /functions/v1/statistics/dashboard`)
  console.log(`   GET /functions/v1/statistics/trends`)
  console.log(`   GET /functions/v1/statistics/violations-analysis`)
  console.log(`   GET /functions/v1/statistics/anomaly-detection`)
  console.log(`   GET /functions/v1/statistics/rules`)
  console.log(`\n按 Ctrl+C 停止服务器`)
})

export default app
