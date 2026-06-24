/**
 * 患者信息提取功能测试脚本
 * 用于验证改进后的LLM解析功能是否能准确提取患者基本信息
 */

import { llmService } from '../src/services/llmService'
import { ResponseParser } from '../src/services/llm/responseParser'
import fs from 'fs'
import path from 'path'

// 测试用例数据
const testCases = [
  {
    name: '结构化格式病历',
    content: `患者基本信息：
姓名：张伟
性别：男
年龄：45岁
科室：内科
病历号：2024002

病程记录：
患者张伟，男，45岁，因"发热、咳嗽5天"入院。

现病史：
患者5天前出现发热，体温最高39.2℃，伴有咳嗽、咳痰，痰液为白色粘痰。

初步诊断：
1. 肺炎
2. 发热待查`,
    expected: {
      patientName: '张伟',
      patientGender: '男',
      patientAge: 45,
      department: '内科'
    }
  },
  {
    name: '病程记录格式',
    content: `首次病程记录
记录时间：2024-03-15 14:30

患者李明，女，32岁，因"胸痛3天"入院。
入院科室：心内科
住院号：2024003

现病史：
患者3天前无明显诱因出现胸痛，为持续性钝痛...

体格检查：
T：36.8℃，P：78次/分，R：18次/分，BP：110/70mmHg

初步诊断：
1. 冠心病？
2. 心绞痛？`,
    expected: {
      patientName: '李明',
      patientGender: '女',
      patientAge: 32,
      department: '心内科'
    }
  },
  {
    name: '混合格式病历',
    content: `泸县人民医院
病程记录

科室：外科    姓名：王小华    性别：女    年龄：28岁    床号：15    住院号：2024004

入院记录
患者王小华，女，28岁，已婚，因"右下腹痛12小时"入院。

现病史：
患者12小时前进食后出现右下腹痛，呈持续性胀痛...

初步诊断：
急性阑尾炎`,
    expected: {
      patientName: '王小华',
      patientGender: '女',
      patientAge: 28,
      department: '外科'
    }
  }
]

interface TestResult {
  testName: string
  success: boolean
  extractedData: any
  expectedData: any
  issues: string[]
}

/**
 * 运行单个测试用例
 */
async function runTestCase(testCase: any): Promise<TestResult> {
  const result: TestResult = {
    testName: testCase.name,
    success: false,
    extractedData: {},
    expectedData: testCase.expected,
    issues: []
  }

  try {
    console.log(`\n🧪 测试用例: ${testCase.name}`)
    console.log('=' .repeat(50))

    // 使用LLM服务解析文本
    const parseResult = await llmService.parseMedicalText(testCase.content, {
      extractPatientInfo: true,
      extractDiagnosis: true,
      classifyDocuments: false
    })

    if (!parseResult.success) {
      result.issues.push(`解析失败: ${parseResult.error}`)
      return result
    }

    const data = parseResult.data
    if (!data) {
      result.issues.push('解析结果为空')
      return result
    }

    result.extractedData = {
      patientName: data.patientName,
      patientGender: data.patientGender,
      patientAge: data.patientAge,
      department: data.department
    }

    // 验证提取结果
    let allCorrect = true

    // 检查患者姓名
    if (data.patientName !== testCase.expected.patientName) {
      result.issues.push(`姓名不匹配: 期望"${testCase.expected.patientName}", 实际"${data.patientName}"`)
      allCorrect = false
    }

    // 检查性别
    if (data.patientGender !== testCase.expected.patientGender) {
      result.issues.push(`性别不匹配: 期望"${testCase.expected.patientGender}", 实际"${data.patientGender}"`)
      allCorrect = false
    }

    // 检查年龄
    if (data.patientAge !== testCase.expected.patientAge) {
      result.issues.push(`年龄不匹配: 期望${testCase.expected.patientAge}, 实际${data.patientAge}`)
      allCorrect = false
    }

    // 检查科室
    if (data.department !== testCase.expected.department) {
      result.issues.push(`科室不匹配: 期望"${testCase.expected.department}", 实际"${data.department}"`)
      allCorrect = false
    }

    result.success = allCorrect

    // 输出结果
    console.log('📊 提取结果:')
    console.log(`  患者姓名: ${data.patientName} ${data.patientName === testCase.expected.patientName ? '✅' : '❌'}`)
    console.log(`  性别: ${data.patientGender} ${data.patientGender === testCase.expected.patientGender ? '✅' : '❌'}`)
    console.log(`  年龄: ${data.patientAge} ${data.patientAge === testCase.expected.patientAge ? '✅' : '❌'}`)
    console.log(`  科室: ${data.department} ${data.department === testCase.expected.department ? '✅' : '❌'}`)
    console.log(`  整体置信度: ${data.confidence}`)

    if (result.success) {
      console.log('🎉 测试通过!')
    } else {
      console.log('❌ 测试失败:')
      result.issues.forEach(issue => console.log(`  - ${issue}`))
    }

  } catch (error) {
    result.issues.push(`测试执行错误: ${error instanceof Error ? error.message : String(error)}`)
    console.log(`❌ 测试执行错误: ${error}`)
  }

  return result
}

/**
 * 运行所有测试用例
 */
async function runAllTests(): Promise<void> {
  console.log('🚀 开始患者信息提取功能测试')
  console.log('=' .repeat(60))

  // 初始化LLM服务
  try {
    await llmService.loadConfigFromDatabase('default')
    console.log('✅ LLM服务初始化成功')
  } catch (error) {
    console.error('❌ LLM服务初始化失败:', error)
    return
  }

  const results: TestResult[] = []

  // 运行所有测试用例
  for (const testCase of testCases) {
    const result = await runTestCase(testCase)
    results.push(result)
  }

  // 生成测试报告
  console.log('\n📋 测试报告')
  console.log('=' .repeat(60))

  const passedTests = results.filter(r => r.success)
  const failedTests = results.filter(r => !r.success)

  console.log(`总测试用例: ${results.length}`)
  console.log(`通过: ${passedTests.length} ✅`)
  console.log(`失败: ${failedTests.length} ❌`)
  console.log(`成功率: ${Math.round((passedTests.length / results.length) * 100)}%`)

  if (failedTests.length > 0) {
    console.log('\n❌ 失败的测试用例:')
    failedTests.forEach(result => {
      console.log(`\n  ${result.testName}:`)
      result.issues.forEach(issue => console.log(`    - ${issue}`))
    })
  }

  // 保存详细报告到文件
  const reportPath = path.join(__dirname, '../reports/patient-info-extraction-test-report.json')
  const reportDir = path.dirname(reportPath)
  
  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true })
  }

  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      total: results.length,
      passed: passedTests.length,
      failed: failedTests.length,
      successRate: Math.round((passedTests.length / results.length) * 100)
    },
    results: results
  }

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2))
  console.log(`\n📄 详细报告已保存到: ${reportPath}`)

  if (failedTests.length === 0) {
    console.log('\n🎉 所有测试用例都通过了！患者信息提取功能工作正常。')
  } else {
    console.log('\n⚠️  部分测试用例失败，需要进一步优化患者信息提取逻辑。')
  }
}

// 如果直接运行此脚本
if (require.main === module) {
  runAllTests().catch(console.error)
}

export { runAllTests, runTestCase, testCases }
