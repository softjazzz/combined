import { config } from 'dotenv'
import { createClient } from '@supabase/supabase-js'

// 加载环境变量
config()

const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY
const deepseekApiKey = process.env.VITE_DEEPSEEK_API_KEY

console.log('🧪 测试当前AI分析功能...\n')

// 测试DeepSeek API连接
async function testDeepSeekAPI() {
  console.log('1️⃣ 测试DeepSeek API连接...')
  
  try {
    const response = await fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${deepseekApiKey}`
      },
      body: JSON.stringify({
        model: 'deepseek-v3',
        messages: [
          {
            role: 'user',
            content: '请简单介绍一下你的病案质控分析能力'
          }
        ],
        max_tokens: 500,
        temperature: 0.1
      })
    })

    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status}`)
    }

    const data = await response.json()
    console.log('✅ DeepSeek API连接成功')
    console.log('📝 AI响应:', data.choices[0].message.content.substring(0, 200) + '...')
    return true
  } catch (error) {
    console.error('❌ DeepSeek API连接失败:', error.message)
    return false
  }
}

// 测试数据库连接
async function testDatabase() {
  console.log('\n2️⃣ 测试数据库连接...')
  
  try {
    const supabase = createClient(supabaseUrl, supabaseKey)
    
    // 测试medical_records表
    const { data: records, error: recordsError } = await supabase
      .from('medical_records')
      .select('id, patient_name, status')
      .limit(3)
    
    if (recordsError) {
      throw recordsError
    }
    
    console.log('✅ 数据库连接成功')
    console.log(`📊 找到 ${records.length} 条医疗记录`)
    
    // 测试qc_results表
    const { data: qcResults, error: qcError } = await supabase
      .from('qc_results')
      .select('id, record_id, score')
      .limit(3)
    
    if (qcError) {
      throw qcError
    }
    
    console.log(`📊 找到 ${qcResults.length} 条质控结果`)
    return true
  } catch (error) {
    console.error('❌ 数据库连接失败:', error.message)
    return false
  }
}

// 测试Edge Function
async function testEdgeFunction() {
  console.log('\n3️⃣ 测试Edge Function...')
  
  try {
    const supabase = createClient(supabaseUrl, supabaseKey)
    
    // 调用Edge Function
    const { data, error } = await supabase.functions.invoke('qc-analysis', {
      body: {
        record_id: 'test-record-id',
        content: `
入院记录

患者：张三，男，45岁
主诉：胸闷气短3天
现病史：患者3天前无明显诱因出现胸闷气短，活动后加重，伴有轻微咳嗽，无发热、胸痛等症状。
既往史：高血压病史5年，规律服用降压药物。
体格检查：T 36.5℃，P 88次/分，R 20次/分，BP 140/90mmHg
心肺听诊：心率齐，无杂音，双肺呼吸音粗，无干湿啰音。
        `,
        analysis_mode: 'quick'
      }
    })
    
    if (error) {
      throw error
    }
    
    console.log('✅ Edge Function调用成功')
    console.log('📋 分析结果:', JSON.stringify(data, null, 2))
    return true
  } catch (error) {
    console.error('❌ Edge Function调用失败:', error.message)
    return false
  }
}

// 主测试函数
async function main() {
  console.log('配置信息:')
  console.log(`- Supabase URL: ${supabaseUrl}`)
  console.log(`- DeepSeek API Key: ${deepseekApiKey ? deepseekApiKey.substring(0, 12) + '...' : '未配置'}`)
  console.log()
  
  const apiTest = await testDeepSeekAPI()
  const dbTest = await testDatabase()
  
  if (apiTest && dbTest) {
    await testEdgeFunction()
  }
  
  console.log('\n🎯 测试完成！')
}

main().catch(console.error) 