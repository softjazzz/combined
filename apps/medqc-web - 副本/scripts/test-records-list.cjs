/**
 * 测试病历列表接口
 */

const fetch = require('node-fetch')

async function testRecordsList() {
  console.log('🧪 测试病历列表接口')
  console.log('=' .repeat(60))

  try {
    // 步骤1：登录获取token
    console.log('🔐 步骤1：用户登录...')
    
    const loginResponse = await fetch('http://localhost:8001/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: 'admin@medqc.com',
        password: 'admin123'
      })
    })

    console.log(`📊 登录响应状态: ${loginResponse.status} ${loginResponse.statusText}`)

    if (!loginResponse.ok) {
      const errorText = await loginResponse.text()
      console.error('❌ 登录失败:', errorText)
      return false
    }

    const loginData = await loginResponse.json()
    const token = loginData.access_token
    console.log('✅ 登录成功!')
    console.log(`  Token: ${token.substring(0, 20)}...`)

    // 步骤2：获取病历列表
    console.log('\n📋 步骤2：获取病历列表...')
    
    const recordsResponse = await fetch('http://localhost:8001/api/records', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      }
    })

    console.log(`📊 病历列表响应状态: ${recordsResponse.status} ${recordsResponse.statusText}`)

    if (!recordsResponse.ok) {
      const errorText = await recordsResponse.text()
      console.error('❌ 获取病历列表失败:', errorText)
      return false
    }

    const recordsData = await recordsResponse.json()
    console.log('✅ 获取病历列表成功!')
    console.log(`  总记录数: ${recordsData.total}`)
    console.log(`  当前页记录数: ${recordsData.data.length}`)
    
    if (recordsData.data.length > 0) {
      console.log('\n📄 记录详情:')
      recordsData.data.forEach((record, index) => {
        console.log(`  ${index + 1}. ${record.patient_name} (${record.id})`)
        console.log(`     科室: ${record.department || '未知'}`)
        console.log(`     状态: ${record.status}`)
        console.log(`     类型: ${record.record_type}`)
        console.log(`     创建时间: ${record.created_at}`)
        console.log('')
      })
      
      // 检查是否包含LLM解析的记录
      const llmRecords = recordsData.data.filter(r => r.record_type === 'LLM解析结果')
      if (llmRecords.length > 0) {
        console.log(`🎉 找到 ${llmRecords.length} 条LLM解析记录！`)
        console.log('✅ 数据源统一成功：病历列表可以显示LLM解析的记录')
      } else {
        console.log('⚠️  没有找到LLM解析记录，可能需要检查数据同步')
      }
    } else {
      console.log('📭 没有找到任何记录')
    }

    return true

  } catch (error) {
    console.error('❌ 测试过程中出现错误:', error.message)
    return false
  }
}

// 运行测试
if (require.main === module) {
  testRecordsList().then(success => {
    process.exit(success ? 0 : 1)
  }).catch(error => {
    console.error('测试执行失败:', error)
    process.exit(1)
  })
}

module.exports = { testRecordsList }
