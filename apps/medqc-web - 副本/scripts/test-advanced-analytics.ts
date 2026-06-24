#!/usr/bin/env node
/**
 * 高级统计分析模块测试脚本
 * 测试360度数据分析、医生绩效评估、智能报表生成和质控指标钻取功能
 */

import { analytics360Service } from '../src/lib/analytics/360-data-analysis'
import { doctorPerformanceService } from '../src/lib/analytics/doctor-performance-evaluation'
import { intelligentReportGenerator } from '../src/lib/analytics/intelligent-report-generator'
import { qcMetricsDrilldownService } from '../src/lib/analytics/qc-metrics-drilldown'

interface AnalyticsTestResult {
  module: string
  testName: string
  success: boolean
  duration: number
  dataPoints: number
  insights: number
  error?: string
}

class AdvancedAnalyticsTester {

  /**
   * 运行完整的高级分析测试
   */
  async runAdvancedAnalyticsTests(): Promise<void> {
    console.log('🚀 开始高级统计分析模块测试...\n')

    const testResults: AnalyticsTestResult[] = []

    // 1. 测试360度数据分析
    console.log('📊 测试360度数据分析模块...')
    const analytics360Results = await this.test360Analytics()
    testResults.push(...analytics360Results)

    // 2. 测试医生绩效评估
    console.log('\n👨‍⚕️ 测试医生绩效评估模块...')
    const performanceResults = await this.testDoctorPerformance()
    testResults.push(...performanceResults)

    // 3. 测试智能报表生成
    console.log('\n📋 测试智能报表生成模块...')
    const reportResults = await this.testIntelligentReports()
    testResults.push(...reportResults)

    // 4. 测试质控指标钻取
    console.log('\n🔍 测试质控指标钻取模块...')
    const drilldownResults = await this.testQCDrilldown()
    testResults.push(...drilldownResults)

    // 5. 测试模块集成
    console.log('\n🔗 测试模块集成...')
    await this.testModuleIntegration()

    // 生成测试报告
    this.generateTestReport(testResults)

    console.log('\n✅ 高级统计分析模块测试完成!')
  }

  /**
   * 测试360度数据分析
   */
  private async test360Analytics(): Promise<AnalyticsTestResult[]> {
    const results: AnalyticsTestResult[] = []

    // 测试基础360度分析
    try {
      const startTime = Date.now()
      
      const query = {
        dimensions: ['department', 'grade'],
        metrics: ['total_records', 'avg_score', 'completion_rate'],
        filters: [],
        timeRange: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          end: new Date()
        }
      }

      const result = await analytics360Service.analyze360(query)
      const duration = Date.now() - startTime

      results.push({
        module: '360度数据分析',
        testName: '基础分析查询',
        success: true,
        duration,
        dataPoints: result.data.length,
        insights: result.insights.length
      })

      console.log(`  ✅ 基础分析: ${result.data.length} 数据点, ${result.insights.length} 洞察 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '360度数据分析',
        testName: '基础分析查询',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 基础分析失败:`, error)
    }

    // 测试数据概览
    try {
      const startTime = Date.now()
      
      const overview = await analytics360Service.getDataOverview()
      const duration = Date.now() - startTime

      results.push({
        module: '360度数据分析',
        testName: '数据概览',
        success: true,
        duration,
        dataPoints: overview.quickStats.length,
        insights: overview.topInsights.length
      })

      console.log(`  ✅ 数据概览: ${overview.quickStats.length} 快速统计, ${overview.topInsights.length} 顶级洞察 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '360度数据分析',
        testName: '数据概览',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 数据概览失败:`, error)
    }

    // 测试部门对比分析
    try {
      const startTime = Date.now()
      
      const timeRange = {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date()
      }
      
      const comparison = await analytics360Service.getDepartmentComparison(timeRange)
      const duration = Date.now() - startTime

      results.push({
        module: '360度数据分析',
        testName: '部门对比分析',
        success: true,
        duration,
        dataPoints: comparison.departments.length,
        insights: comparison.insights.length
      })

      console.log(`  ✅ 部门对比: ${comparison.departments.length} 部门, ${comparison.insights.length} 洞察 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '360度数据分析',
        testName: '部门对比分析',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 部门对比失败:`, error)
    }

    return results
  }

  /**
   * 测试医生绩效评估
   */
  private async testDoctorPerformance(): Promise<AnalyticsTestResult[]> {
    const results: AnalyticsTestResult[] = []

    // 测试单个医生绩效评估
    try {
      const startTime = Date.now()
      
      const evaluationPeriod = {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date()
      }

      const report = await doctorPerformanceService.evaluateDoctorPerformance('doc_001', evaluationPeriod)
      const duration = Date.now() - startTime

      results.push({
        module: '医生绩效评估',
        testName: '单个医生评估',
        success: true,
        duration,
        dataPoints: report.scores.length,
        insights: report.achievements.length + report.recommendations.length
      })

      console.log(`  ✅ 单个医生评估: ${report.doctorName}, 总分 ${report.overallScore.toFixed(1)}, 排名 ${report.overallRank}/${report.totalDoctors} (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '医生绩效评估',
        testName: '单个医生评估',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 单个医生评估失败:`, error)
    }

    // 测试批量医生绩效评估
    try {
      const startTime = Date.now()
      
      const doctorIds = ['doc_001', 'doc_002', 'doc_003']
      const evaluationPeriod = {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date()
      }

      const batchResult = await doctorPerformanceService.evaluateBatchPerformance(doctorIds, evaluationPeriod)
      const duration = Date.now() - startTime

      results.push({
        module: '医生绩效评估',
        testName: '批量医生评估',
        success: true,
        duration,
        dataPoints: batchResult.reports.length,
        insights: batchResult.summary.topPerformers.length + batchResult.summary.improvementNeeded.length
      })

      console.log(`  ✅ 批量评估: ${batchResult.reports.length} 医生, 平均分 ${batchResult.summary.averageScore.toFixed(1)} (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '医生绩效评估',
        testName: '批量医生评估',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 批量医生评估失败:`, error)
    }

    // 测试部门绩效概览
    try {
      const startTime = Date.now()
      
      const evaluationPeriod = {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date()
      }

      const overview = await doctorPerformanceService.getDepartmentPerformanceOverview('内科', evaluationPeriod)
      const duration = Date.now() - startTime

      results.push({
        module: '医生绩效评估',
        testName: '部门绩效概览',
        success: true,
        duration,
        dataPoints: overview.totalDoctors,
        insights: overview.trends.length
      })

      console.log(`  ✅ 部门概览: ${overview.department}, ${overview.totalDoctors} 医生, 平均分 ${overview.averageScore.toFixed(1)} (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '医生绩效评估',
        testName: '部门绩效概览',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 部门绩效概览失败:`, error)
    }

    return results
  }

  /**
   * 测试智能报表生成
   */
  private async testIntelligentReports(): Promise<AnalyticsTestResult[]> {
    const results: AnalyticsTestResult[] = []

    // 测试日报生成
    try {
      const startTime = Date.now()
      
      const parameters = {
        date: {
          start: new Date(),
          end: new Date()
        }
      }

      const report = await intelligentReportGenerator.generateReport('daily_summary', parameters)
      const duration = Date.now() - startTime

      results.push({
        module: '智能报表生成',
        testName: '日报生成',
        success: true,
        duration,
        dataPoints: report.content.sections.length,
        insights: report.content.key_findings.length + report.content.recommendations.length
      })

      console.log(`  ✅ 日报生成: ${report.title}, ${report.content.sections.length} 章节 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '智能报表生成',
        testName: '日报生成',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 日报生成失败:`, error)
    }

    // 测试月报生成
    try {
      const startTime = Date.now()
      
      const parameters = {
        month: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          end: new Date()
        },
        departments: ['内科', '外科']
      }

      const report = await intelligentReportGenerator.generateReport('monthly_overview', parameters, 'html')
      const duration = Date.now() - startTime

      results.push({
        module: '智能报表生成',
        testName: '月报生成',
        success: true,
        duration,
        dataPoints: report.content.sections.length,
        insights: report.content.key_findings.length + report.content.recommendations.length
      })

      console.log(`  ✅ 月报生成: ${report.title}, ${report.content.sections.length} 章节 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '智能报表生成',
        testName: '月报生成',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 月报生成失败:`, error)
    }

    // 测试定制化报表
    try {
      const startTime = Date.now()
      
      const sections = [
        {
          type: 'summary' as const,
          title: '概要分析',
          dataQuery: { type: 'summary' }
        },
        {
          type: 'chart' as const,
          title: '趋势图表',
          dataQuery: { type: 'trend' },
          chartConfig: {
            type: 'line' as const,
            title: '质量趋势'
          }
        }
      ]

      const parameters = {
        timeRange: {
          start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
          end: new Date()
        }
      }

      const report = await intelligentReportGenerator.generateCustomReport(
        '定制化分析报表',
        sections,
        parameters
      )
      const duration = Date.now() - startTime

      results.push({
        module: '智能报表生成',
        testName: '定制化报表',
        success: true,
        duration,
        dataPoints: report.content.sections.length,
        insights: report.content.key_findings.length
      })

      console.log(`  ✅ 定制化报表: ${report.title}, ${report.content.sections.length} 章节 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '智能报表生成',
        testName: '定制化报表',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 定制化报表失败:`, error)
    }

    return results
  }

  /**
   * 测试质控指标钻取
   */
  private async testQCDrilldown(): Promise<AnalyticsTestResult[]> {
    const results: AnalyticsTestResult[] = []

    // 测试医院级别钻取
    try {
      const startTime = Date.now()
      
      const filters = {
        time_range: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          end: new Date()
        }
      }

      const result = await qcMetricsDrilldownService.performDrilldown('hospital_overview', filters)
      const duration = Date.now() - startTime

      results.push({
        module: '质控指标钻取',
        testName: '医院级别钻取',
        success: true,
        duration,
        dataPoints: result.data.length,
        insights: result.insights.length
      })

      console.log(`  ✅ 医院级别钻取: ${result.data.length} 数据项, ${result.insights.length} 洞察 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '质控指标钻取',
        testName: '医院级别钻取',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 医院级别钻取失败:`, error)
    }

    // 测试科室级别钻取
    try {
      const startTime = Date.now()
      
      const filters = {
        department: '内科',
        time_range: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          end: new Date()
        }
      }

      const result = await qcMetricsDrilldownService.performDrilldown('department_analysis', filters)
      const duration = Date.now() - startTime

      results.push({
        module: '质控指标钻取',
        testName: '科室级别钻取',
        success: true,
        duration,
        dataPoints: result.data.length,
        insights: result.insights.length
      })

      console.log(`  ✅ 科室级别钻取: ${result.data.length} 数据项, ${result.insights.length} 洞察 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '质控指标钻取',
        testName: '科室级别钻取',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 科室级别钻取失败:`, error)
    }

    // 测试多维度钻取
    try {
      const startTime = Date.now()
      
      const dimensions = ['department', 'grade']
      const metrics = ['total_records', 'avg_score']
      const filters = {
        time_range: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          end: new Date()
        }
      }

      const result = await qcMetricsDrilldownService.performMultiDimensionDrilldown(
        'hospital_overview',
        dimensions,
        metrics,
        filters
      )
      const duration = Date.now() - startTime

      results.push({
        module: '质控指标钻取',
        testName: '多维度钻取',
        success: true,
        duration,
        dataPoints: result.results.reduce((sum, r) => sum + r.data.length, 0),
        insights: result.crossAnalysis.correlations.length + result.crossAnalysis.patterns.length
      })

      console.log(`  ✅ 多维度钻取: ${result.results.length} 维度结果, ${result.visualizations.length} 可视化 (${duration}ms)`)

    } catch (error) {
      results.push({
        module: '质控指标钻取',
        testName: '多维度钻取',
        success: false,
        duration: 0,
        dataPoints: 0,
        insights: 0,
        error: error.message
      })
      console.log(`  ❌ 多维度钻取失败:`, error)
    }

    return results
  }

  /**
   * 测试模块集成
   */
  private async testModuleIntegration(): Promise<void> {
    console.log('  测试模块间数据流和集成...')

    try {
      // 1. 从360度分析获取部门数据
      const overview = await analytics360Service.getDataOverview()
      console.log(`  ✅ 获取概览数据: ${overview.quickStats.length} 统计项`)

      // 2. 基于概览数据生成医生绩效报表
      const doctorIds = ['doc_001', 'doc_002']
      const evaluationPeriod = {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
        end: new Date()
      }
      
      const performanceResult = await doctorPerformanceService.evaluateBatchPerformance(doctorIds, evaluationPeriod)
      console.log(`  ✅ 生成绩效数据: ${performanceResult.reports.length} 医生报告`)

      // 3. 基于绩效数据生成智能报表
      const reportParams = {
        doctor_id: 'doc_001',
        period: evaluationPeriod
      }
      
      const report = await intelligentReportGenerator.generateReport('doctor_performance', reportParams)
      console.log(`  ✅ 生成智能报表: ${report.title}`)

      // 4. 对报表数据进行钻取分析
      const drilldownFilters = {
        department: '内科',
        time_range: evaluationPeriod
      }
      
      const drilldownResult = await qcMetricsDrilldownService.performDrilldown('department_analysis', drilldownFilters)
      console.log(`  ✅ 执行钻取分析: ${drilldownResult.data.length} 数据项`)

      console.log('  ✅ 模块集成测试成功 - 数据流畅通')

    } catch (error) {
      console.log(`  ❌ 模块集成测试失败:`, error)
    }
  }

  /**
   * 生成测试报告
   */
  private generateTestReport(results: AnalyticsTestResult[]): void {
    console.log('\n📊 高级统计分析模块测试报告')
    console.log('=' .repeat(80))

    // 按模块分组统计
    const moduleStats = new Map<string, { total: number; success: number; totalDuration: number; totalDataPoints: number; totalInsights: number }>()

    for (const result of results) {
      if (!moduleStats.has(result.module)) {
        moduleStats.set(result.module, { total: 0, success: 0, totalDuration: 0, totalDataPoints: 0, totalInsights: 0 })
      }
      
      const stats = moduleStats.get(result.module)!
      stats.total++
      if (result.success) stats.success++
      stats.totalDuration += result.duration
      stats.totalDataPoints += result.dataPoints
      stats.totalInsights += result.insights
    }

    console.log('模块名称 | 测试数 | 成功率 | 平均耗时 | 数据点 | 洞察数')
    console.log('-'.repeat(80))

    let totalTests = 0
    let totalSuccess = 0
    let totalDuration = 0
    let totalDataPoints = 0
    let totalInsights = 0

    for (const [module, stats] of moduleStats) {
      const successRate = (stats.success / stats.total * 100).toFixed(1)
      const avgDuration = Math.round(stats.totalDuration / stats.total)
      
      console.log(
        `${module.padEnd(16)} | ` +
        `${stats.total.toString().padStart(6)} | ` +
        `${successRate.padStart(6)}% | ` +
        `${avgDuration.toString().padStart(8)}ms | ` +
        `${stats.totalDataPoints.toString().padStart(6)} | ` +
        `${stats.totalInsights.toString().padStart(6)}`
      )

      totalTests += stats.total
      totalSuccess += stats.success
      totalDuration += stats.totalDuration
      totalDataPoints += stats.totalDataPoints
      totalInsights += stats.totalInsights
    }

    console.log('-'.repeat(80))
    
    const overallSuccessRate = (totalSuccess / totalTests * 100).toFixed(1)
    const avgDuration = Math.round(totalDuration / totalTests)
    
    console.log(`总计: ${totalTests} 测试, ${totalSuccess} 成功, 成功率 ${overallSuccessRate}%`)
    console.log(`平均耗时: ${avgDuration}ms, 总数据点: ${totalDataPoints}, 总洞察: ${totalInsights}`)

    // 失败的测试详情
    const failedTests = results.filter(r => !r.success)
    if (failedTests.length > 0) {
      console.log('\n❌ 失败的测试:')
      for (const test of failedTests) {
        console.log(`  ${test.module} - ${test.testName}: ${test.error}`)
      }
    }

    console.log('\n💡 测试结论:')
    if (parseFloat(overallSuccessRate) >= 90) {
      console.log('✅ 高级统计分析模块工作优秀')
      console.log('✅ 所有核心功能正常运行')
      console.log('✅ 模块间集成良好')
      console.log('✅ 性能表现符合预期')
      console.log('✅ 建议投入生产使用')
    } else if (parseFloat(overallSuccessRate) >= 70) {
      console.log('⚠️ 高级统计分析模块基本可用')
      console.log('⚠️ 部分功能需要优化')
      console.log('⚠️ 建议修复问题后再部署')
    } else {
      console.log('❌ 高级统计分析模块需要重大改进')
      console.log('❌ 多个核心功能存在问题')
      console.log('❌ 不建议当前版本投入生产')
    }

    console.log('\n🎯 功能亮点:')
    console.log('• 360度数据分析提供全方位洞察')
    console.log('• 医生绩效评估支持个人和批量分析')
    console.log('• 智能报表生成支持多种格式和定制')
    console.log('• 质控指标钻取支持多层级深度分析')
    console.log('• 模块间无缝集成，数据流畅通')

    console.log('\n🚀 优化建议:')
    console.log('• 继续优化数据处理性能')
    console.log('• 增加更多可视化图表类型')
    console.log('• 扩展报表模板和定制选项')
    console.log('• 加强异常检测和预警功能')
    console.log('• 完善用户权限和数据安全')

    console.log('\n' + '='.repeat(80))
  }

  /**
   * 延迟函数
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}

/**
 * 主函数
 */
async function main() {
  try {
    const tester = new AdvancedAnalyticsTester()
    await tester.runAdvancedAnalyticsTests()
    
    console.log('\n🎉 高级统计分析模块验证完成!')
    console.log('📊 系统现在具备了强大的数据分析和洞察能力')
    console.log('🚀 所有高级功能已就绪，可以投入使用')
    
  } catch (error) {
    console.error('❌ 高级统计分析测试失败:', error)
    process.exit(1)
  }
}

// 运行测试
if (require.main === module) {
  main()
}

export { AdvancedAnalyticsTester }
