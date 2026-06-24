/**
 * 调试Supabase保存问题
 */

const fetch = require('node-fetch')

async function debugSupabaseSave() {
  console.log('🔧 调试Supabase保存问题')
  console.log('=' .repeat(60))

  try {
    // 步骤1：创建LLM解析记录
    console.log('📤 步骤1：创建LLM解析记录...')
    
    const testData = {
      patient_name: '测试患者',
      patient_age: 30,
      patient_gender: '男',
      department: '测试科室',
      primary_diagnosis: '测试诊断',
      content: '这是一个测试记录，用于调试Supabase保存问题...',
      method: 'LLM精准解析'
    }

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
    console.log(`  科室: ${savedRecord.department}`)
    console.log(`  状态: ${savedRecord.status}`)
    console.log(`  类型: ${savedRecord.record_type}`)

    const recordId = savedRecord.id

    // 步骤2：直接通过无认证接口获取记录
    console.log('\n📥 步骤2：通过无认证接口获取记录...')
    
    const getResponse = await fetch(`http://localhost:8001/api/medical-records/${recordId}`)
    console.log(`📊 获取响应状态: ${getResponse.status} ${getResponse.statusText}`)

    if (getResponse.ok) {
      const retrievedRecord = await getResponse.json()
      console.log('✅ 无认证接口获取成功!')
      console.log(`  记录ID: ${retrievedRecord.id}`)
      console.log(`  患者姓名: ${retrievedRecord.patient_name}`)
      console.log(`  科室: ${retrievedRecord.department}`)
    } else {
      const errorText = await getResponse.text()
      console.log('❌ 无认证接口获取失败:', errorText)
    }

    // 步骤3：通过认证接口获取病历列表
    console.log('\n🔐 步骤3：登录并获取病历列表...')
    
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

    if (!loginResponse.ok) {
      console.error('❌ 登录失败')
      return false
    }

    const loginData = await loginResponse.json()
    const token = loginData.access_token

    const recordsResponse = await fetch('http://localhost:8001/api/records', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      }
    })

    console.log(`📊 病历列表响应状态: ${recordsResponse.status} ${recordsResponse.statusText}`)

    if (recordsResponse.ok) {
      const recordsData = await recordsResponse.json()
      console.log('✅ 病历列表获取成功!')
      console.log(`  总记录数: ${recordsData.total}`)
      
      // 查找我们刚创建的记录
      const ourRecord = recordsData.data.find(r => r.id === recordId)
      if (ourRecord) {
        console.log('🎉 在病历列表中找到了我们的记录!')
        console.log(`  记录ID: ${ourRecord.id}`)
        console.log(`  患者姓名: ${ourRecord.patient_name}`)
        console.log(`  科室: ${ourRecord.department || '未知'}`)
        console.log(`  类型: ${ourRecord.record_type}`)
      } else {
        console.log('⚠️  在病历列表中没有找到我们的记录')
        console.log('📋 当前列表中的记录:')
        recordsData.data.forEach((record, index) => {
          console.log(`  ${index + 1}. ${record.patient_name} (${record.id})`)
          console.log(`     类型: ${record.record_type}`)
          console.log(`     科室: ${record.department || '未知'}`)
        })
      }

      // 检查是否有LLM解析记录
      const llmRecords = recordsData.data.filter(r => r.record_type === 'LLM解析结果')
      console.log(`\n🔍 LLM解析记录统计: ${llmRecords.length} 条`)
      
    } else {
      const errorText = await recordsResponse.text()
      console.error('❌ 获取病历列表失败:', errorText)
    }

    return true

  } catch (error) {
    console.error('❌ 调试过程中出现错误:', error.message)
    return false
  }
}

// 运行调试
if (require.main === module) {
  debugSupabaseSave().then(success => {
    console.log('\n' + '='.repeat(60))
    if (success) {
      console.log('🔧 调试完成，请检查上述输出来定位问题')
    } else {
      console.log('❌ 调试过程中出现错误')
    }
    process.exit(success ? 0 : 1)
  }).catch(error => {
    console.error('调试执行失败:', error)
    process.exit(1)
  })
}

module.exports = { debugSupabaseSave }
