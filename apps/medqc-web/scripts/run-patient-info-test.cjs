/**
 * 简化的患者信息提取测试脚本 (JavaScript版本)
 * 用于快速验证改进后的功能
 */

const fs = require('fs')
const path = require('path')

// 模拟测试数据
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
患者张伟，男，45岁，因"发热、咳嗽5天"入院。`,
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
患者李明，女，32岁，因"胸痛3天"入院。
入院科室：心内科`,
    expected: {
      patientName: '李明',
      patientGender: '女',
      patientAge: 32,
      department: '心内科'
    }
  }
]

// 模拟ResponseParser的增强提取方法
function extractPatientName(text) {
  const patterns = [
    /姓名[:：]\s*([^\s\n,，。]+)/,
    /患者\s*([^\s\n,，。]+)，/,
    /患者姓名[:：]\s*([^\s\n,，。]+)/,
    /病人\s*([^\s\n,，。]+)，/
  ]
  
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match && match[1] && match[1].trim().length >= 2) {
      const extractedName = match[1].trim()
      // 验证是否为有效姓名（中文姓名通常2-4个字符）
      if (/^[\u4e00-\u9fa5]{2,4}$/.test(extractedName)) {
        return extractedName
      }
    }
  }
  return null
}

function extractPatientAge(text) {
  const patterns = [
    /年龄[:：]\s*(\d+)[岁]?/,
    /(\d+)岁/,
    /，(\d+)岁，/,
    /患者[^，]*，[^，]*，(\d+)岁/
  ]
  
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match && match[1]) {
      const extractedAge = parseInt(match[1])
      if (extractedAge > 0 && extractedAge < 150) {
        return extractedAge
      }
    }
  }
  return null
}

function extractPatientGender(text) {
  const patterns = [
    /性别[:：]\s*([男女])/,
    /患者[^，]*，([男女])，/,
    /，([男女])性，/,
    /，([男女])，\d+岁/
  ]
  
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match && match[1]) {
      return match[1] === '男' ? '男' : '女'
    }
  }
  return null
}

function extractDepartment(text) {
  const patterns = [
    /科室[:：]\s*([^\s\n,，。]+)/,
    /入院科室[:：]\s*([^\s\n,，。]+)/,
    /([^\s]+科)\s*病程记录/,
    /([^\s]+科)\s*住院病历/
  ]
  
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match && match[1] && match[1].trim().length >= 2) {
      const extractedDept = match[1].trim()
      // 验证是否为有效科室名称
      if (/科$/.test(extractedDept) || /部$/.test(extractedDept)) {
        return extractedDept
      }
    }
  }
  return null
}

// 运行测试
function runTests() {
  console.log('🚀 开始患者信息提取功能测试')
  console.log('=' .repeat(60))

  const results = []

  testCases.forEach((testCase, index) => {
    console.log(`\n🧪 测试用例 ${index + 1}: ${testCase.name}`)
    console.log('-' .repeat(40))

    // 提取患者信息
    const extracted = {
      patientName: extractPatientName(testCase.content),
      patientGender: extractPatientGender(testCase.content),
      patientAge: extractPatientAge(testCase.content),
      department: extractDepartment(testCase.content)
    }

    // 验证结果
    const issues = []
    let success = true

    if (extracted.patientName !== testCase.expected.patientName) {
      issues.push(`姓名不匹配: 期望"${testCase.expected.patientName}", 实际"${extracted.patientName}"`)
      success = false
    }

    if (extracted.patientGender !== testCase.expected.patientGender) {
      issues.push(`性别不匹配: 期望"${testCase.expected.patientGender}", 实际"${extracted.patientGender}"`)
      success = false
    }

    if (extracted.patientAge !== testCase.expected.patientAge) {
      issues.push(`年龄不匹配: 期望${testCase.expected.patientAge}, 实际${extracted.patientAge}`)
      success = false
    }

    if (extracted.department !== testCase.expected.department) {
      issues.push(`科室不匹配: 期望"${testCase.expected.department}", 实际"${extracted.department}"`)
      success = false
    }

    // 输出结果
    console.log('📊 提取结果:')
    console.log(`  患者姓名: ${extracted.patientName || '未识别'} ${extracted.patientName === testCase.expected.patientName ? '✅' : '❌'}`)
    console.log(`  性别: ${extracted.patientGender || '未识别'} ${extracted.patientGender === testCase.expected.patientGender ? '✅' : '❌'}`)
    console.log(`  年龄: ${extracted.patientAge || '未识别'} ${extracted.patientAge === testCase.expected.patientAge ? '✅' : '❌'}`)
    console.log(`  科室: ${extracted.department || '未识别'} ${extracted.department === testCase.expected.department ? '✅' : '❌'}`)

    if (success) {
      console.log('🎉 测试通过!')
    } else {
      console.log('❌ 测试失败:')
      issues.forEach(issue => console.log(`  - ${issue}`))
    }

    results.push({
      testName: testCase.name,
      success,
      extracted,
      expected: testCase.expected,
      issues
    })
  })

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
    console.log('\n❌ 需要改进的地方:')
    failedTests.forEach(result => {
      console.log(`\n  ${result.testName}:`)
      result.issues.forEach(issue => console.log(`    - ${issue}`))
    })
  }

  // 保存报告
  const reportPath = path.join(__dirname, '../reports/patient-info-test-report.json')
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
    console.log('\n⚠️  部分测试用例失败，建议进一步优化提取逻辑。')
  }

  return results
}

// 运行测试
if (require.main === module) {
  runTests()
}

module.exports = { runTests, testCases }
