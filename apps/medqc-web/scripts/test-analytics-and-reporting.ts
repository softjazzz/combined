#!/usr/bin/env tsx

/**
 * 360度数据分析和智能报表功能测试脚本
 * 运行命令: npx tsx scripts/test-analytics-and-reporting.ts
 */

import { createClient } from '@supabase/supabase-js'
import { analyticsEngine } from '../src/lib/analytics-engine'
import { reportEngine } from '../src/lib/report-engine'

// 配置
const SUPABASE_URL = process.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co'
const SUPABASE_ANON_KEY = process.env.VITE_SUPABASE_ANON_KEY || 'your-anon-key'

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  console.error('❌ 请设置环境变量 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY')
  process.exit(1)
}

// 创建Supabase客户端
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

interface TestResult {
  name: string
  success: boolean
  duration: number
  error?: string
  data?: any
}

const testResults: TestResult[] = []

async function runTest(testName: string, testFn: () => Promise<any>): Promise<void> {
  console.log(`🧪 测试: ${testName}`)
  const startTime = Date.now()
  
  try {
    const result = await testFn()
    const duration = Date.now() - startTime
    
    testResults.push({
      name: testName,
      success: true,
      duration,
      data: result
    })
    
    console.log(`✅ ${testName} - 通过 (${duration}ms)`)
  } catch (error) {
    const duration = Date.now() - startTime
    const errorMessage = error instanceof Error ? error.message : String(error)
    
    testResults.push({
      name: testName,
      success: false,
      duration,
      error: errorMessage
    })
    
    console.log(`❌ ${testName} - 失败 (${duration}ms)`)
    console.log(`   错误: ${errorMessage}`)
  }
}

async function testAnalyticsEngine() {
  console.log('\n📊 测试360度数据分析引擎...\n')

  // 测试获取分析指标
  await runTest('获取分析指标', async () => {
    const metrics = await analyticsEngine.getAnalyticsMetrics()
    if (!Array.isArray(metrics)) {
      throw new Error('返回的指标不是数组')
    }
    if (metrics.length === 0) {
      throw new Error('没有找到分析指标')
    }
    console.log(`   找到 ${metrics.length} 个分析指标`)
    return metrics
  })

  // 测试科室对比分析
  await runTest('科室对比分析', async () => {
    const timeRange = {
      start: '2024-01-01',
      end: '2024-12-31',
      granularity: 'day' as const
    }
    
    const comparison = await analyticsEngine.analyzeDepartmentComparison(timeRange)
    if (!Array.isArray(comparison)) {
      throw new Error('返回的对比数据不是数组')
    }
    
    console.log(`   分析了 ${comparison.length} 个科室`)
    return comparison
  })

  // 测试医生绩效分析
  await runTest('医生绩效分析', async () => {
    const timeRange = {
      start: '2024-01-01',
      end: '2024-12-31',
      granularity: 'day' as const
    }
    
    const performance = await analyticsEngine.analyzeDoctorPerformance(timeRange)
    if (!Array.isArray(performance)) {
      throw new Error('返回的绩效数据不是数组')
    }
    
    console.log(`   分析了 ${performance.length} 位医生`)
    return performance
  })

  // 测试趋势分析
  await runTest('趋势分析', async () => {
    const timeRange = {
      start: '2024-01-01',
      end: '2024-12-31',
      granularity: 'day' as const
    }
    
    const trends = await analyticsEngine.analyzeTrends('avg_qc_score', timeRange)
    if (!Array.isArray(trends)) {
      throw new Error('返回的趋势数据不是数组')
    }
    
    console.log(`   分析了 ${trends.length} 个时间点`)
    return trends
  })

  // 测试智能洞察生成
  await runTest('智能洞察生成', async () => {
    const timeRange = {
      start: '2024-01-01',
      end: '2024-12-31',
      granularity: 'day' as const
    }
    
    const insights = await analyticsEngine.generateInsights(timeRange)
    if (!Array.isArray(insights)) {
      throw new Error('返回的洞察数据不是数组')
    }
    
    console.log(`   生成了 ${insights.length} 个洞察`)
    return insights
  })

  // 测试多维度分析
  await runTest('多维度分析', async () => {
    const config = {
      dimensions: ['department', 'quality'] as const,
      metrics: ['avg_qc_score', 'grade_a_rate'],
      timeRange: {
        start: '2024-01-01',
        end: '2024-12-31',
        granularity: 'day' as const
      }
    }
    
    const results = await analyticsEngine.executeAnalysis(config)
    if (!Array.isArray(results)) {
      throw new Error('返回的分析结果不是数组')
    }
    
    console.log(`   执行了 ${results.length} 个分析`)
    return results
  })
}

async function testReportEngine() {
  console.log('\n📋 测试智能报表引擎...\n')

  // 测试获取报表模板
  await runTest('获取报表模板', async () => {
    const templates = await reportEngine.getReportTemplates()
    if (!Array.isArray(templates)) {
      throw new Error('返回的模板不是数组')
    }
    if (templates.length === 0) {
      throw new Error('没有找到报表模板')
    }
    console.log(`   找到 ${templates.length} 个报表模板`)
    return templates
  })

  // 测试生成报表
  await runTest('生成报表', async () => {
    const templates = await reportEngine.getReportTemplates()
    if (templates.length === 0) {
      throw new Error('没有可用的报表模板')
    }
    
    const template = templates[0]
    const parameters = {
      period_start: '2024-01-01',
      period_end: '2024-01-31',
      output_format: 'pdf'
    }
    
    const reportInstance = await reportEngine.generateReport(template.id, parameters)
    if (!reportInstance.id) {
      throw new Error('报表实例创建失败')
    }
    
    console.log(`   创建报表实例: ${reportInstance.id}`)
    return reportInstance
  })

  // 测试获取报表列表
  await runTest('获取报表列表', async () => {
    const reports = await reportEngine.getReportInstances({ limit: 10 })
    if (!Array.isArray(reports)) {
      throw new Error('返回的报表列表不是数组')
    }
    
    console.log(`   找到 ${reports.length} 个报表实例`)
    return reports
  })

  // 测试创建自定义报表模板
  await runTest('创建自定义报表模板', async () => {
    const template = {
      template_code: 'test_template',
      template_name: '测试报表模板',
      template_type: 'qc_summary' as const,
      description: '这是一个测试报表模板',
      layout_config: {
        sections: ['overview', 'analysis'],
        page_size: 'A4' as const,
        orientation: 'portrait' as const
      },
      chart_configs: [
        {
          id: 'test_chart',
          type: 'line' as const,
          title: '测试图表',
          data_source: 'analytics_results',
          metrics: ['avg_qc_score'],
          dimensions: ['time']
        }
      ],
      output_formats: ['pdf', 'excel'],
      is_active: true,
      is_system_template: false
    }
    
    const createdTemplate = await reportEngine.createReportTemplate(template)
    if (!createdTemplate.id) {
      throw new Error('报表模板创建失败')
    }
    
    console.log(`   创建模板: ${createdTemplate.id}`)
    return createdTemplate
  })
}

async function testDatabaseIntegration() {
  console.log('\n🗄️  测试数据库集成...\n')

  // 测试分析指标表
  await runTest('分析指标表查询', async () => {
    const { data, error } = await supabase
      .from('analytics_metrics')
      .select('*')
      .limit(5)
    
    if (error) {
      throw new Error(`查询失败: ${error.message}`)
    }
    
    if (!Array.isArray(data)) {
      throw new Error('返回数据格式错误')
    }
    
    console.log(`   查询到 ${data.length} 条记录`)
    return data
  })

  // 测试报表模板表
  await runTest('报表模板表查询', async () => {
    const { data, error } = await supabase
      .from('report_templates')
      .select('*')
      .limit(5)
    
    if (error) {
      throw new Error(`查询失败: ${error.message}`)
    }
    
    if (!Array.isArray(data)) {
      throw new Error('返回数据格式错误')
    }
    
    console.log(`   查询到 ${data.length} 条记录`)
    return data
  })

  // 测试数据立方体表
  await runTest('数据立方体表查询', async () => {
    const { data, error } = await supabase
      .from('data_cubes')
      .select('*')
      .limit(5)
    
    if (error) {
      throw new Error(`查询失败: ${error.message}`)
    }
    
    if (!Array.isArray(data)) {
      throw new Error('返回数据格式错误')
    }
    
    console.log(`   查询到 ${data.length} 条记录`)
    return data
  })

  // 测试科室分析视图
  await runTest('科室分析视图查询', async () => {
    const { data, error } = await supabase
      .from('v_department_analytics')
      .select('*')
      .limit(5)
    
    if (error) {
      throw new Error(`查询失败: ${error.message}`)
    }
    
    if (!Array.isArray(data)) {
      throw new Error('返回数据格式错误')
    }
    
    console.log(`   查询到 ${data.length} 条记录`)
    return data
  })

  // 测试数据库函数
  await runTest('科室排名函数测试', async () => {
    const { data, error } = await supabase
      .rpc('calculate_department_ranking', {
        p_period_start: '2024-01-01',
        p_period_end: '2024-12-31'
      })
    
    if (error) {
      throw new Error(`函数调用失败: ${error.message}`)
    }
    
    if (!Array.isArray(data)) {
      throw new Error('返回数据格式错误')
    }
    
    console.log(`   计算了 ${data.length} 个科室排名`)
    return data
  })

  // 测试质量洞察函数
  await runTest('质量洞察函数测试', async () => {
    const { data, error } = await supabase
      .rpc('generate_quality_insight', {
        p_department: null,
        p_period_days: 30
      })
    
    if (error) {
      throw new Error(`函数调用失败: ${error.message}`)
    }
    
    if (!data) {
      throw new Error('没有返回洞察数据')
    }
    
    console.log(`   生成洞察: ${JSON.stringify(data)}`)
    return data
  })
}

async function testPerformance() {
  console.log('\n⚡ 测试性能...\n')

  // 测试分析引擎性能
  await runTest('分析引擎性能测试', async () => {
    const startTime = Date.now()
    
    const timeRange = {
      start: '2024-01-01',
      end: '2024-12-31',
      granularity: 'day' as const
    }
    
    const [comparison, performance, trends, insights] = await Promise.all([
      analyticsEngine.analyzeDepartmentComparison(timeRange),
      analyticsEngine.analyzeDoctorPerformance(timeRange),
      analyticsEngine.analyzeTrends('avg_qc_score', timeRange),
      analyticsEngine.generateInsights(timeRange)
    ])
    
    const duration = Date.now() - startTime
    
    if (duration > 10000) {
      throw new Error(`性能测试超时: ${duration}ms`)
    }
    
    console.log(`   并行执行4个分析任务耗时: ${duration}ms`)
    return {
      duration,
      comparison: comparison.length,
      performance: performance.length,
      trends: trends.length,
      insights: insights.length
    }
  })

  // 测试报表生成性能
  await runTest('报表生成性能测试', async () => {
    const startTime = Date.now()
    
    const templates = await reportEngine.getReportTemplates()
    if (templates.length === 0) {
      throw new Error('没有可用的报表模板')
    }
    
    const template = templates[0]
    const parameters = {
      period_start: '2024-01-01',
      period_end: '2024-01-31',
      output_format: 'pdf'
    }
    
    const reportInstance = await reportEngine.generateReport(template.id, parameters)
    const duration = Date.now() - startTime
    
    if (duration > 5000) {
      throw new Error(`报表生成超时: ${duration}ms`)
    }
    
    console.log(`   报表生成任务提交耗时: ${duration}ms`)
    return { duration, reportId: reportInstance.id }
  })
}

async function generateTestReport() {
  console.log('\n📊 生成测试报告...\n')

  const totalTests = testResults.length
  const passedTests = testResults.filter(r => r.success).length
  const failedTests = testResults.filter(r => r.success === false).length
  const totalDuration = testResults.reduce((sum, r) => sum + r.duration, 0)
  const averageDuration = totalDuration / totalTests

  console.log('📋 测试总结:')
  console.log(`  总测试数: ${totalTests}`)
  console.log(`  通过: ${passedTests}`)
  console.log(`  失败: ${failedTests}`)
  console.log(`  成功率: ${((passedTests / totalTests) * 100).toFixed(1)}%`)
  console.log(`  总耗时: ${totalDuration}ms`)
  console.log(`  平均耗时: ${averageDuration.toFixed(0)}ms`)

  if (failedTests > 0) {
    console.log('\n❌ 失败的测试:')
    testResults
      .filter(r => !r.success)
      .forEach(r => {
        console.log(`  • ${r.name}: ${r.error}`)
      })
  }

  console.log('\n⏱️  性能统计:')
  testResults
    .sort((a, b) => b.duration - a.duration)
    .slice(0, 5)
    .forEach(r => {
      console.log(`  • ${r.name}: ${r.duration}ms`)
    })

  // 保存详细报告
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      total: totalTests,
      passed: passedTests,
      failed: failedTests,
      success_rate: (passedTests / totalTests) * 100,
      total_duration: totalDuration,
      average_duration: averageDuration
    },
    results: testResults
  }

  console.log('\n💾 测试报告已生成')
  console.log('📄 详细报告:')
  console.log(JSON.stringify(report, null, 2))
}

async function runAllTests() {
  console.log('🚀 开始360度数据分析和智能报表功能测试...\n')

  try {
    await testDatabaseIntegration()
    await testAnalyticsEngine()
    await testReportEngine()
    await testPerformance()
    await generateTestReport()

    const passedTests = testResults.filter(r => r.success).length
    const totalTests = testResults.length

    if (passedTests === totalTests) {
      console.log('\n🎉 所有测试通过! 360度数据分析和智能报表系统运行正常')
      process.exit(0)
    } else {
      console.log('\n⚠️  部分测试失败，请检查系统配置')
      process.exit(1)
    }
  } catch (error) {
    console.error('\n❌ 测试执行失败:', error)
    process.exit(1)
  }
}

// 运行所有测试
runAllTests().catch(console.error) 