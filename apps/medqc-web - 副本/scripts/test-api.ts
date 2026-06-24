import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg'

const supabase = createClient(supabaseUrl, supabaseAnonKey)

// 模拟API调用
async function testGetMedicalRecords() {
  console.log('🧪 测试 getMedicalRecords API...\n')
  
  try {
    // 模拟前端API调用
    let query = supabase
      .from('medical_records')
      .select('*', { count: 'exact' })
      .order('created_at', { ascending: false })

    // 添加分页（模拟前端传递的参数）
    const limit = 50
    const offset = 0
    const start = offset
    const end = start + limit - 1
    query = query.range(start, end)

    const result = await query
    
    console.log('📊 API测试结果:')
    console.log(`- 成功: ${!result.error}`)
    console.log(`- 错误: ${result.error?.message || '无'}`)
    console.log(`- 返回记录数: ${result.data?.length || 0}`)
    console.log(`- 总记录数: ${result.count || 0}`)
    
    if (result.data && result.data.length > 0) {
      console.log('\n📋 前5个患者:')
      result.data.slice(0, 5).forEach((record, index) => {
        console.log(`${index + 1}. ${record.patient_name} (${record.patient_age}岁) - ${record.department}`)
      })
    }
    
    return result
    
  } catch (error) {
    console.error('❌ API测试失败:', error)
    return null
  }
}

// 运行测试
testGetMedicalRecords().catch(console.error)
