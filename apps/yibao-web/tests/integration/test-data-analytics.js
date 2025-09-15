#!/usr/bin/env node

/**
 * 数据分析模块测试脚本
 * 测试新增的统计分析功能、违规趋势分析、异常检测等功能
 */

const BASE_URL = 'http://localhost:54321/functions/v1'

// 测试配置
const TEST_CONFIG = {
  timeRanges: ['7d', '30d', '90d'],
  granularities: ['day', 'week', 'month'],
  anomalySensitivities: [1.5, 2.0, 2.5],
  groupByOptions: ['rule_type', 'severity']
}

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
}

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`)
}

// HTTP 请求工具
async function makeRequest(endpoint, params = {}) {
  const url = new URL(`${BASE_URL}/statistics/${endpoint}`)
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, value.toString())
    }
  })

  try {
    const response = await fetch(url.toString())
    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${data.error || 'Unknown error'}`)
    }
    
    return { success: true, data, status: response.status }
  } catch (error) {
    return { success: false, error: error.message, status: 0 }
  }
}

// 测试函数
async function testDashboardKPIs() {
  log('\n📊 测试仪表盘KPI指标...', 'blue')
  
  const result = await makeRequest('dashboard')
  
  if (result.success) {
    const { kpis } = result.data
    log('✅ 仪表盘KPI获取成功', 'green')
    log(`   今日违规: ${kpis.todayViolations}`, 'cyan')
    log(`   昨日违规: ${kpis.yesterdayViolations}`, 'cyan')
    log(`   活跃规则: ${kpis.activeRules}`, 'cyan')
    log(`   严重程度分布: 阻断${kpis.severityBreakdown.block}, 警告${kpis.severityBreakdown.warn}, 提醒${kpis.severityBreakdown.info}`, 'cyan')
    return true
  } else {
    log(`❌ 仪表盘KPI获取失败: ${result.error}`, 'red')
    return false
  }
}

async function testEnhancedTrends() {
  log('\n📈 测试增强趋势分析...', 'blue')
  
  let passCount = 0
  let totalTests = 0
  
  for (const days of TEST_CONFIG.timeRanges) {
    for (const granularity of TEST_CONFIG.granularities) {
      totalTests++
      
      log(`  测试 ${days} ${granularity} 粒度...`, 'yellow')
      
      const result = await makeRequest('trends', {
        days: parseInt(days),
        granularity,
        analysis: 'true'
      })
      
      if (result.success) {
        const { trends, analysis, metadata } = result.data
        
        if (trends && Array.isArray(trends) && analysis && metadata) {
          log(`    ✅ 成功获取 ${trends.length} 个数据点`, 'green')
          log(`    📊 趋势分析: ${analysis.total_trend?.trend || 'N/A'}`, 'cyan')
          log(`    📈 移动平均: ${analysis.moving_averages ? '已计算' : '未计算'}`, 'cyan')
          log(`    🚨 异常点: ${analysis.anomalies?.total_anomalies?.length || 0} 个`, 'cyan')
          passCount++
        } else {
          log(`    ❌ 数据结构不完整`, 'red')
        }
      } else {
        log(`    ❌ 请求失败: ${result.error}`, 'red')
      }
    }
  }
  
  log(`\n📈 趋势分析测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow')
  return passCount === totalTests
}

async function testViolationAnalysis() {
  log('\n🔍 测试违规分析功能...', 'blue')
  
  let passCount = 0
  let totalTests = 0
  
  for (const range of TEST_CONFIG.timeRanges) {
    for (const groupBy of TEST_CONFIG.groupByOptions) {
      totalTests++
      
      log(`  测试 ${range} ${groupBy} 分组...`, 'yellow')
      
      const result = await makeRequest('violations-analysis', {
        range,
        group_by: groupBy
      })
      
      if (result.success) {
        const data = result.data
        
        if (data.overview && data.severity_distribution && data.temporal_patterns) {
          log(`    ✅ 分析完成`, 'green')
          log(`    📊 总违规数: ${data.overview.total_violations}`, 'cyan')
          log(`    👥 涉及就诊: ${data.overview.unique_visits}`, 'cyan')
          log(`    📋 触发规则: ${data.overview.unique_rules}`, 'cyan')
          log(`    ⏰ 高峰时段: ${data.temporal_patterns.peak_hour}:00`, 'cyan')
          
          if (groupBy === 'rule_type' && data.by_rule_type) {
            log(`    📝 规则类型: ${data.by_rule_type.length} 种`, 'cyan')
          }
          
          if (data.rule_efficiency) {
            log(`    🎯 规则效率: 前${Math.min(data.rule_efficiency.length, 5)}个规则分析`, 'cyan')
          }
          
          passCount++
        } else {
          log(`    ❌ 分析数据不完整`, 'red')
        }
      } else {
        log(`    ❌ 请求失败: ${result.error}`, 'red')
      }
    }
  }
  
  log(`\n🔍 违规分析测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow')
  return passCount === totalTests
}

async function testAnomalyDetection() {
  log('\n🚨 测试异常检测功能...', 'blue')
  
  let passCount = 0
  let totalTests = 0
  
  for (const days of ['30', '60', '90']) {
    for (const sensitivity of TEST_CONFIG.anomalySensitivities) {
      totalTests++
      
      log(`  测试 ${days}天 敏感度${sensitivity}...`, 'yellow')
      
      const result = await makeRequest('anomaly-detection', {
        days,
        sensitivity
      })
      
      if (result.success) {
        const { time_series, anomalies, statistics, parameters } = result.data
        
        if (time_series && anomalies && statistics && parameters) {
          log(`    ✅ 异常检测完成`, 'green')
          log(`    📊 时间序列: ${time_series.length} 个数据点`, 'cyan')
          log(`    🚨 异常点: ${anomalies.length} 个`, 'cyan')
          log(`    📈 平均值: ${statistics.mean.toFixed(2)}`, 'cyan')
          log(`    📊 标准差: ${statistics.std_dev.toFixed(2)}`, 'cyan')
          log(`    📉 异常率: ${(statistics.anomaly_rate * 100).toFixed(1)}%`, 'cyan')
          
          if (anomalies.length > 0) {
            const highAnomalies = anomalies.filter(a => a.severity === 'high').length
            const lowAnomalies = anomalies.filter(a => a.severity === 'low').length
            log(`    ⬆️ 高异常: ${highAnomalies} 个`, 'cyan')
            log(`    ⬇️ 低异常: ${lowAnomalies} 个`, 'cyan')
          }
          
          passCount++
        } else {
          log(`    ❌ 检测数据不完整`, 'red')
        }
      } else {
        log(`    ❌ 请求失败: ${result.error}`, 'red')
      }
    }
  }
  
  log(`\n🚨 异常检测测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow')
  return passCount === totalTests
}

async function testRulePerformance() {
  log('\n⚡ 测试规则性能分析...', 'blue')
  
  const result = await makeRequest('rules')
  
  if (result.success) {
    const { rules } = result.data
    
    if (rules && Array.isArray(rules)) {
      log('✅ 规则性能分析成功', 'green')
      log(`   分析规则数: ${rules.length}`, 'cyan')
      
      if (rules.length > 0) {
        const topRule = rules[0]
        log(`   最活跃规则: ${topRule.code} (${topRule.totalViolations} 次违规)`, 'cyan')
        
        const totalViolations = rules.reduce((sum, rule) => sum + rule.totalViolations, 0)
        log(`   总违规次数: ${totalViolations}`, 'cyan')
        
        const ruleTypes = [...new Set(rules.map(rule => rule.ruleType))]
        log(`   规则类型数: ${ruleTypes.length}`, 'cyan')
      }
      
      return true
    } else {
      log(`❌ 规则数据格式错误`, 'red')
      return false
    }
  } else {
    log(`❌ 规则性能分析失败: ${result.error}`, 'red')
    return false
  }
}

async function testDataIntegrity() {
  log('\n🔍 测试数据完整性...', 'blue')
  
  // 测试数据一致性
  const dashboardResult = await makeRequest('dashboard')
  const trendsResult = await makeRequest('trends', { days: 1, analysis: 'true' })
  
  if (dashboardResult.success && trendsResult.success) {
    const dashboardToday = dashboardResult.data.kpis.todayViolations
    const trendsToday = trendsResult.data.trends[trendsResult.data.trends.length - 1]?.total || 0
    
    if (Math.abs(dashboardToday - trendsToday) <= 1) { // 允许1的误差（时间差）
      log('✅ 数据一致性检查通过', 'green')
      log(`   仪表盘今日违规: ${dashboardToday}`, 'cyan')
      log(`   趋势分析今日违规: ${trendsToday}`, 'cyan')
      return true
    } else {
      log('❌ 数据一致性检查失败', 'red')
      log(`   仪表盘今日违规: ${dashboardToday}`, 'red')
      log(`   趋势分析今日违规: ${trendsToday}`, 'red')
      return false
    }
  } else {
    log('❌ 无法获取数据进行一致性检查', 'red')
    return false
  }
}

async function performanceTest() {
  log('\n⚡ 性能测试...', 'blue')
  
  const tests = [
    { name: '仪表盘KPI', endpoint: 'dashboard' },
    { name: '30天趋势', endpoint: 'trends', params: { days: 30, analysis: 'true' } },
    { name: '违规分析', endpoint: 'violations-analysis', params: { range: '30d' } },
    { name: '异常检测', endpoint: 'anomaly-detection', params: { days: 30 } },
    { name: '规则性能', endpoint: 'rules' }
  ]
  
  for (const test of tests) {
    const startTime = Date.now()
    const result = await makeRequest(test.endpoint, test.params || {})
    const endTime = Date.now()
    const duration = endTime - startTime
    
    if (result.success) {
      const status = duration < 1000 ? 'green' : duration < 3000 ? 'yellow' : 'red'
      log(`  ✅ ${test.name}: ${duration}ms`, status)
    } else {
      log(`  ❌ ${test.name}: 失败 (${result.error})`, 'red')
    }
  }
}

// 主测试函数
async function runAllTests() {
  log('🚀 开始数据分析模块测试', 'magenta')
  log('=' * 50, 'magenta')
  
  const results = []
  
  // 基础功能测试
  results.push(await testDashboardKPIs())
  results.push(await testEnhancedTrends())
  results.push(await testViolationAnalysis())
  results.push(await testAnomalyDetection())
  results.push(await testRulePerformance())
  
  // 数据完整性测试
  results.push(await testDataIntegrity())
  
  // 性能测试
  await performanceTest()
  
  // 测试总结
  const passedTests = results.filter(Boolean).length
  const totalTests = results.length
  
  log('\n' + '=' * 50, 'magenta')
  log('📋 测试总结', 'magenta')
  log(`总测试数: ${totalTests}`, 'cyan')
  log(`通过测试: ${passedTests}`, 'green')
  log(`失败测试: ${totalTests - passedTests}`, 'red')
  log(`成功率: ${((passedTests / totalTests) * 100).toFixed(1)}%`, passedTests === totalTests ? 'green' : 'yellow')
  
  if (passedTests === totalTests) {
    log('\n🎉 所有测试通过！数据分析模块功能正常', 'green')
  } else {
    log('\n⚠️ 部分测试失败，请检查相关功能', 'yellow')
  }
  
  return passedTests === totalTests
}

// 运行测试
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests().catch(error => {
    log(`💥 测试执行出错: ${error.message}`, 'red')
    process.exit(1)
  })
}
