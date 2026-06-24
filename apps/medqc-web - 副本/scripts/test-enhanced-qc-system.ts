/**
 * 增强质控系统测试脚本
 * 验证AI分析和规则引擎的整合效果
 */

import { qcAnalysisService } from '../src/lib/qc-analysis'
import { QCRulesEngine } from '../src/lib/qc-rules-engine'
import type { QCRequest } from '../src/lib/qc-analysis'

// 测试用病历数据
const testMedicalRecords = [
  {
    id: 'test-001',
    title: '完整病历测试',
    content: `
患者信息：
姓名：张三
年龄：45岁
性别：男
过敏史：青霉素过敏

入院记录：
入院时间：2024-01-15
主诉：胸痛3天
现病史：患者3天前无明显诱因出现胸痛，呈压榨性，持续性，伴有气短、出汗。
既往史：高血压病史5年，规律服用降压药物。
体格检查：血压150/90mmHg，心率85次/分，心律齐，心音清晰。

入院诊断：
1. 急性心肌梗死
2. 高血压病

治疗经过：
给予阿司匹林、氯吡格雷双联抗血小板治疗，阿托伐他汀调脂治疗，美托洛尔控制心率。
行冠脉造影检查，发现左前降支90%狭窄，行PCI术。

出院记录：
出院时间：2024-01-22
出院诊断：
1. 急性心肌梗死（已行PCI术）
2. 高血压病
出院医嘱：继续双联抗血小板治疗12个月，他汀类药物长期服用。
    `,
    expected: {
      grade: '甲级',
      score: 90,
      issues: 0
    }
  },
  {
    id: 'test-002',
    title: '缺陷病历测试',
    content: `
患者信息：
姓名：李四
年龄：38岁
性别：女
过敏史：无记录

入院记录：
入院时间：2024-01-10
主诉：腹痛
现病史：患者腹痛，具体情况不详。
既往史：无特殊。

入院诊断：
腹痛待查

治疗经过：
给予对症治疗。

出院记录：
出院时间：2024-01-15
出院诊断：
急性胃炎
    `,
    expected: {
      grade: '丙级',
      score: 60,
      issues: 5
    }
  },
  {
    id: 'test-003',
    title: '一致性问题测试',
    content: `
患者信息：
姓名：王五
年龄：52岁
性别：男
过敏史：无

入院记录：
入院时间：2024-01-08
主诉：发热、咳嗽3天
现病史：患者3天前出现发热，体温最高39.2℃，伴有咳嗽、咳痰。
既往史：糖尿病病史10年。

入院诊断：
1. 社区获得性肺炎
2. 2型糖尿病

治疗经过：
给予头孢曲松抗感染治疗，胰岛素控制血糖。
胸部CT显示双肺炎症。

出院记录：
出院时间：2024-01-15
出院诊断：
1. 急性支气管炎
2. 2型糖尿病
    `,
    expected: {
      grade: '乙级',
      score: 75,
      issues: 2
    }
  }
]

// 测试配置
const testConfig = {
  enableRulesEngine: true,
  selectedRuleCategories: ['completeness', 'consistency', 'rationality', 'timeliness'] as const,
  analysisMode: 'comprehensive' as const
}

// 测试结果统计
interface TestResults {
  totalTests: number
  passedTests: number
  failedTests: number
  averageScore: number
  averageProcessingTime: number
  ruleEngineStats: {
    totalRules: number
    passedRules: number
    failedRules: number
    averageConfidence: number
  }
  detailedResults: Array<{
    recordId: string
    title: string
    actualScore: number
    expectedScore: number
    actualGrade: string
    expectedGrade: string
    actualIssues: number
    expectedIssues: number
    processingTime: number
    passed: boolean
    issues: string[]
  }>
}

/**
 * 执行质控系统测试
 */
async function runEnhancedQCTests(): Promise<TestResults> {
  console.log('🚀 开始测试增强质控系统...\n')
  
  const results: TestResults = {
    totalTests: 0,
    passedTests: 0,
    failedTests: 0,
    averageScore: 0,
    averageProcessingTime: 0,
    ruleEngineStats: {
      totalRules: 0,
      passedRules: 0,
      failedRules: 0,
      averageConfidence: 0
    },
    detailedResults: []
  }

  let totalScore = 0
  let totalProcessingTime = 0
  let totalRules = 0
  let totalPassedRules = 0
  let totalConfidence = 0

  for (const record of testMedicalRecords) {
    console.log(`📋 测试病历: ${record.title}`)
    console.log(`📝 病历ID: ${record.id}`)
    
    const startTime = Date.now()
    
    try {
      // 构建质控请求
      const request: QCRequest = {
        recordId: record.id,
        content: record.content,
        enableRulesEngine: testConfig.enableRulesEngine,
        selectedRuleCategories: testConfig.selectedRuleCategories,
        analysisMode: testConfig.analysisMode
      }

      // 执行质控分析
      const analysisResult = await qcAnalysisService.analyzeRecord(request)
      
      const processingTime = Date.now() - startTime
      totalProcessingTime += processingTime

      // 分析结果
      const actualScore = analysisResult.summary.combinedScore || analysisResult.summary.totalScore
      const actualGrade = analysisResult.summary.grade
      const actualIssues = analysisResult.issues.length
      
      // 统计规则引擎结果
      if (analysisResult.rulesEngineResults) {
        totalRules += analysisResult.rulesEngineResults.length
        totalPassedRules += analysisResult.rulesEngineResults.filter(r => r.passed).length
        totalConfidence += analysisResult.rulesEngineResults.reduce((sum, r) => sum + r.confidence, 0)
      }

      // 判断测试是否通过
      const scoreMatch = Math.abs(actualScore - record.expected.score) <= 10
      const gradeMatch = actualGrade === record.expected.grade
      const issuesMatch = Math.abs(actualIssues - record.expected.issues) <= 2
      
      const testPassed = scoreMatch && (gradeMatch || issuesMatch)
      
      if (testPassed) {
        results.passedTests++
        console.log(`✅ 测试通过`)
      } else {
        results.failedTests++
        console.log(`❌ 测试失败`)
      }

      // 详细结果
      const detailedResult = {
        recordId: record.id,
        title: record.title,
        actualScore,
        expectedScore: record.expected.score,
        actualGrade,
        expectedGrade: record.expected.grade,
        actualIssues,
        expectedIssues: record.expected.issues,
        processingTime,
        passed: testPassed,
        issues: testPassed ? [] : [
          !scoreMatch ? `评分不匹配: 期望${record.expected.score}, 实际${actualScore}` : '',
          !gradeMatch ? `等级不匹配: 期望${record.expected.grade}, 实际${actualGrade}` : '',
          !issuesMatch ? `问题数不匹配: 期望${record.expected.issues}, 实际${actualIssues}` : ''
        ].filter(Boolean)
      }
      
      results.detailedResults.push(detailedResult)
      totalScore += actualScore

      // 输出详细信息
      console.log(`📊 综合评分: ${actualScore}分 (期望: ${record.expected.score}分)`)
      console.log(`🏆 质控等级: ${actualGrade} (期望: ${record.expected.grade})`)
      console.log(`⚠️  发现问题: ${actualIssues}个 (期望: ${record.expected.issues}个)`)
      console.log(`⏱️  处理时间: ${processingTime}ms`)
      
      if (analysisResult.summary.aiAnalysisScore && analysisResult.summary.rulesEngineScore) {
        console.log(`🤖 AI分析得分: ${analysisResult.summary.aiAnalysisScore}分`)
        console.log(`📋 规则引擎得分: ${analysisResult.summary.rulesEngineScore}分`)
      }
      
      if (analysisResult.processingStats) {
        console.log(`📈 处理统计:`)
        console.log(`   - AI分析时间: ${Math.round(analysisResult.processingStats.aiAnalysisTime / 1000)}秒`)
        console.log(`   - 规则引擎时间: ${Math.round(analysisResult.processingStats.rulesEngineTime / 1000)}秒`)
        console.log(`   - 总处理时间: ${Math.round(analysisResult.processingStats.totalProcessingTime / 1000)}秒`)
      }
      
      console.log(`---`)
      
    } catch (error) {
      console.error(`❌ 测试失败: ${error instanceof Error ? error.message : '未知错误'}`)
      results.failedTests++
      
      results.detailedResults.push({
        recordId: record.id,
        title: record.title,
        actualScore: 0,
        expectedScore: record.expected.score,
        actualGrade: '丙级',
        expectedGrade: record.expected.grade,
        actualIssues: 0,
        expectedIssues: record.expected.issues,
        processingTime: Date.now() - startTime,
        passed: false,
        issues: [`执行异常: ${error instanceof Error ? error.message : '未知错误'}`]
      })
    }
    
    results.totalTests++
  }

  // 计算统计数据
  results.averageScore = totalScore / results.totalTests
  results.averageProcessingTime = totalProcessingTime / results.totalTests
  
  if (totalRules > 0) {
    results.ruleEngineStats = {
      totalRules,
      passedRules: totalPassedRules,
      failedRules: totalRules - totalPassedRules,
      averageConfidence: totalConfidence / totalRules
    }
  }

  return results
}

/**
 * 测试规则引擎独立功能
 */
async function testRulesEngineStandalone(): Promise<void> {
  console.log('\n🔧 测试规则引擎独立功能...\n')
  
  const rulesEngine = new QCRulesEngine()
  
  // 测试规则统计
  const stats = rulesEngine.getRuleStatistics()
  console.log(`📊 规则引擎统计:`)
  console.log(`   - 总规则数: ${stats.total}`)
  console.log(`   - 活跃规则数: ${stats.active}`)
  console.log(`   - 按类别分布:`, stats.byCategory)
  console.log(`   - 按类型分布:`, stats.byType)
  
  // 测试单个规则执行
  const testContext = {
    recordId: 'test-rules-001',
    content: testMedicalRecords[1].content, // 使用缺陷病历
    metadata: {
      patientId: 'patient-001',
      department: '内科',
      admissionDate: '2024-01-10',
      recordType: 'inpatient' as const
    }
  }
  
  console.log(`\n🧪 测试完整性规则执行:`)
  const completenessResults = await rulesEngine.executeRulesByCategory('completeness', testContext)
  
  completenessResults.forEach((result, index) => {
    console.log(`   ${index + 1}. ${result.ruleName}`)
    console.log(`      - 通过: ${result.passed ? '✅' : '❌'}`)
    console.log(`      - 得分: ${result.score}/${result.maxScore}`)
    console.log(`      - 置信度: ${Math.round(result.confidence * 100)}%`)
    console.log(`      - 问题数: ${result.issues.length}`)
  })
}

/**
 * 输出测试报告
 */
function printTestReport(results: TestResults): void {
  console.log('\n📊 测试报告')
  console.log('=' .repeat(50))
  
  // 总体统计
  console.log(`\n📈 总体统计:`)
  console.log(`   - 总测试数: ${results.totalTests}`)
  console.log(`   - 通过测试: ${results.passedTests}`)
  console.log(`   - 失败测试: ${results.failedTests}`)
  console.log(`   - 通过率: ${Math.round((results.passedTests / results.totalTests) * 100)}%`)
  console.log(`   - 平均评分: ${Math.round(results.averageScore)}分`)
  console.log(`   - 平均处理时间: ${Math.round(results.averageProcessingTime)}ms`)
  
  // 规则引擎统计
  if (results.ruleEngineStats.totalRules > 0) {
    console.log(`\n🔧 规则引擎统计:`)
    console.log(`   - 总规则数: ${results.ruleEngineStats.totalRules}`)
    console.log(`   - 通过规则: ${results.ruleEngineStats.passedRules}`)
    console.log(`   - 失败规则: ${results.ruleEngineStats.failedRules}`)
    console.log(`   - 规则通过率: ${Math.round((results.ruleEngineStats.passedRules / results.ruleEngineStats.totalRules) * 100)}%`)
    console.log(`   - 平均置信度: ${Math.round(results.ruleEngineStats.averageConfidence * 100)}%`)
  }
  
  // 详细结果
  console.log(`\n📋 详细测试结果:`)
  results.detailedResults.forEach((result, index) => {
    console.log(`\n${index + 1}. ${result.title}`)
    console.log(`   - 状态: ${result.passed ? '✅ 通过' : '❌ 失败'}`)
    console.log(`   - 评分: ${result.actualScore}/${result.expectedScore}`)
    console.log(`   - 等级: ${result.actualGrade} (期望: ${result.expectedGrade})`)
    console.log(`   - 问题: ${result.actualIssues}个 (期望: ${result.expectedIssues}个)`)
    console.log(`   - 处理时间: ${result.processingTime}ms`)
    
    if (result.issues.length > 0) {
      console.log(`   - 失败原因:`)
      result.issues.forEach(issue => {
        console.log(`     • ${issue}`)
      })
    }
  })
  
  // 性能分析
  console.log(`\n⚡ 性能分析:`)
  const fastestTest = Math.min(...results.detailedResults.map(r => r.processingTime))
  const slowestTest = Math.max(...results.detailedResults.map(r => r.processingTime))
  
  console.log(`   - 最快处理时间: ${fastestTest}ms`)
  console.log(`   - 最慢处理时间: ${slowestTest}ms`)
  console.log(`   - 性能稳定性: ${slowestTest / fastestTest <= 3 ? '✅ 良好' : '⚠️ 需要优化'}`)
  
  // 建议
  console.log(`\n💡 优化建议:`)
  if (results.passedTests / results.totalTests < 0.8) {
    console.log(`   - 测试通过率较低，建议检查规则配置和阈值设置`)
  }
  if (results.averageProcessingTime > 5000) {
    console.log(`   - 平均处理时间较长，建议优化算法或增加缓存`)
  }
  if (results.ruleEngineStats.averageConfidence < 0.7) {
    console.log(`   - 规则置信度较低，建议完善规则逻辑或增加训练数据`)
  }
  
  console.log(`\n🎉 测试完成！`)
}

/**
 * 主测试函数
 */
async function main(): Promise<void> {
  try {
    console.log('🏥 病案质控系统增强测试')
    console.log('=' .repeat(50))
    
    // 测试规则引擎独立功能
    await testRulesEngineStandalone()
    
    // 测试整合系统
    const results = await runEnhancedQCTests()
    
    // 输出测试报告
    printTestReport(results)
    
  } catch (error) {
    console.error('❌ 测试执行失败:', error)
    process.exit(1)
  }
}

// 执行测试
if (require.main === module) {
  main()
}

export { runEnhancedQCTests, testRulesEngineStandalone } 