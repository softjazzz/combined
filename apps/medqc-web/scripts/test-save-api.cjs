/**
 * 测试前端保存API功能
 */

const fetch = require('node-fetch')

async function testSaveAPI() {
  console.log('🧪 测试LLM解析结果保存API')
  console.log('=' .repeat(50))

  const testData = {
    record_number: 'LLM_TEST_001',
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
    console.log('📤 发送保存请求...')
    
    const response = await fetch('http://localhost:8001/api/medical-records', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(testData)
    })

    console.log(`📊 响应状态: ${response.status} ${response.statusText}`)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ 保存失败:', errorText)
      return false
    }

    const result = await response.json()
    console.log('✅ 保存成功!')
    console.log('📋 返回结果:')
    console.log(`  记录ID: ${result.id}`)
    console.log(`  患者姓名: ${result.patient_name}`)
    console.log(`  年龄: ${result.patient_age}`)
    console.log(`  性别: ${result.patient_gender}`)
    console.log(`  科室: ${result.department}`)
    console.log(`  状态: ${result.status}`)
    console.log(`  创建时间: ${result.created_at}`)
    console.log(`  创建者: ${result.created_by}`)

    return true

  } catch (error) {
    console.error('❌ 测试失败:', error.message)
    return false
  }
}

// 运行测试
if (require.main === module) {
  testSaveAPI().then(success => {
    if (success) {
      console.log('\n🎉 API测试通过！前端保存功能应该可以正常工作了。')
    } else {
      console.log('\n⚠️  API测试失败，需要检查后端配置。')
    }
  }).catch(console.error)
}

module.exports = { testSaveAPI }
