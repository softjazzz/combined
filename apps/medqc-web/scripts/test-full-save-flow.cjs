/**
 * 测试完整的保存和获取流程
 */

const fetch = require('node-fetch')

async function testFullFlow() {
  console.log('🧪 测试完整的保存和获取流程')
  console.log('=' .repeat(60))

  const testData = {
    record_number: 'LLM_FLOW_TEST',
    patient_name: '张伟',
    patient_age: 44,
    patient_gender: '男',
    department: '外二科',
    primary_diagnosis: '肛周脓肿',
    secondary_diagnosis: ['肛瘘'],
    major_surgery: '肛瘘根治术',
    documents: [
      {
        id: 'doc_1',
        type: 'first_progress_note',
        title: '首次病程记录',
        content: '患者张伟，性别男，年龄44岁...',
        confidence: 95
      }
    ],
    confidence: 95,
    content: '完整的病历内容...',
    method: 'LLM精准解析',
    parse_metadata: {
      provider: 'DeepSeek',
      model: 'deepseek-chat',
      tokens_used: 5524,
      processing_time: 7438,
      confidence: 95
    }
  }

  try {
    // 步骤1：保存记录
    console.log('📤 步骤1：保存LLM解析结果...')
    
    const saveResponse = await fetch('http://localhost:8001/api/medical-records', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(testData)
    })

    console.log(`📊 保存响应状态: ${saveResponse.status} ${saveResponse.statusText}`)

    if (!saveResponse.ok) {
      const errorText = await saveResponse.text()
      console.error('❌ 保存失败:', errorText)
      return false
    }

    const savedRecord = await saveResponse.json()
    console.log('✅ 保存成功!')
    console.log(`  记录ID: ${savedRecord.id}`)
    console.log(`  患者姓名: ${savedRecord.patient_name}`)
    console.log(`  状态: ${savedRecord.status}`)

    // 步骤2：获取记录详情
    console.log('\n📥 步骤2：获取记录详情...')
    
    const getResponse = await fetch(`http://localhost:8001/api/medical-records/${savedRecord.id}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    console.log(`📊 获取响应状态: ${getResponse.status} ${getResponse.statusText}`)

    if (!getResponse.ok) {
      const errorText = await getResponse.text()
      console.error('❌ 获取失败:', errorText)
      return false
    }

    const retrievedRecord = await getResponse.json()
    console.log('✅ 获取成功!')
    console.log(`  记录ID: ${retrievedRecord.id}`)
    console.log(`  患者姓名: ${retrievedRecord.patient_name}`)
    console.log(`  年龄: ${retrievedRecord.patient_age}`)
    console.log(`  性别: ${retrievedRecord.patient_gender}`)
    console.log(`  科室: ${retrievedRecord.department}`)
    console.log(`  状态: ${retrievedRecord.status}`)
    console.log(`  创建时间: ${retrievedRecord.created_at}`)

    // 步骤3：验证数据一致性
    console.log('\n🔍 步骤3：验证数据一致性...')
    
    const checks = [
      { field: 'id', expected: savedRecord.id, actual: retrievedRecord.id },
      { field: 'patient_name', expected: testData.patient_name, actual: retrievedRecord.patient_name },
      { field: 'patient_age', expected: testData.patient_age, actual: retrievedRecord.patient_age },
      { field: 'patient_gender', expected: testData.patient_gender, actual: retrievedRecord.patient_gender },
      { field: 'department', expected: testData.department, actual: retrievedRecord.department },
      { field: 'status', expected: 'completed', actual: retrievedRecord.status }
    ]

    let allValid = true
    checks.forEach(check => {
      const isValid = check.expected === check.actual
      console.log(`  ${check.field}: ${isValid ? '✅' : '❌'} (期望: ${check.expected}, 实际: ${check.actual})`)
      if (!isValid) allValid = false
    })

    if (allValid) {
      console.log('\n🎉 完整流程测试成功！')
      console.log('前端保存和详情页面功能应该可以正常工作了。')
      return true
    } else {
      console.log('\n⚠️  数据一致性检查失败，需要进一步调试。')
      return false
    }

  } catch (error) {
    console.error('❌ 测试过程中出现错误:', error.message)
    return false
  }
}

// 运行测试
if (require.main === module) {
  testFullFlow().then(success => {
    process.exit(success ? 0 : 1)
  }).catch(error => {
    console.error('测试执行失败:', error)
    process.exit(1)
  })
}

module.exports = { testFullFlow }
