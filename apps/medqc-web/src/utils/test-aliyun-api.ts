/**
 * 阿里云百炼API测试工具
 * 用于验证API配置是否正确
 */

interface AliyunAPIResponse {
  choices: Array<{
    message: {
      content: string
    }
  }>
}

export async function testAliyunAPI(): Promise<boolean> {
  const apiKey = 'sk-e2808814ae874c8f94e40f20c99bc3a3'
  const baseURL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
  
  try {
    console.log('🧪 开始测试阿里云百炼API连接...')
    
    const response = await fetch(`${baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'deepseek-v3',
        messages: [
          {
            role: 'user',
            content: '你好，请简单回复确认API连接正常。'
          }
        ],
        max_tokens: 100,
        temperature: 0.1,
        stream: false
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ API调用失败:', response.status, errorText)
      return false
    }

    const data: AliyunAPIResponse = await response.json()
    
    if (data.choices && data.choices[0] && data.choices[0].message) {
      console.log('✅ API连接成功!')
      console.log('📝 AI回复:', data.choices[0].message.content)
      return true
    } else {
      console.error('❌ API响应格式异常:', data)
      return false
    }
    
  } catch (error) {
    console.error('❌ 测试过程中发生错误:', error)
    return false
  }
}

export async function testQCAnalysis(): Promise<boolean> {
  const apiKey = 'sk-e2808814ae874c8f94e40f20c99bc3a3'
  const baseURL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
  
  const testPrompt = `
你是一位具有20年经验的资深病案质控专家，请对以下简单病历进行质控分析：

患者：张三，男，45岁
主诉：胸闷气短3天
现病史：患者3天前无明显诱因出现胸闷气短。
体格检查：心律齐，心率96次/分。
诊断：急性心肌梗死

请给出简单的质控评价（不超过100字）。
`

  try {
    console.log('🔍 开始测试质控分析功能...')
    
    const response = await fetch(`${baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'deepseek-v3',
        messages: [
          {
            role: 'user',
            content: testPrompt
          }
        ],
        max_tokens: 500,
        temperature: 0.1,
        stream: false
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ 质控分析调用失败:', response.status, errorText)
      return false
    }

    const data: AliyunAPIResponse = await response.json()
    
    if (data.choices && data.choices[0] && data.choices[0].message) {
      console.log('✅ 质控分析功能正常!')
      console.log('📋 质控分析结果:')
      console.log(data.choices[0].message.content)
      return true
    } else {
      console.error('❌ 质控分析响应格式异常:', data)
      return false
    }
    
  } catch (error) {
    console.error('❌ 质控分析测试过程中发生错误:', error)
    return false
  }
}

// 在浏览器控制台中运行测试
if (typeof globalThis !== 'undefined' && (globalThis as any).window) {
  (globalThis as any).testAliyunAPI = testAliyunAPI;
  (globalThis as any).testQCAnalysis = testQCAnalysis;
  
  console.log('🚀 阿里云百炼API测试工具已加载！')
  console.log('💡 使用方法：')
  console.log('   - 基础连接测试: testAliyunAPI()')
  console.log('   - 质控分析测试: testQCAnalysis()')
} 