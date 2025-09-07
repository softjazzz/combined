// 质控API测试工具
export async function testQCAPI() {
  const apiKey = 'sk-e2808814ae874c8f94e40f20c99bc3a3'
  const baseURL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
  
  const testContent = `
患者：李某，男，45岁
主诉：胸痛3小时
现病史：患者3小时前无明显诱因出现胸前区疼痛，呈压榨性，向左肩放射，伴出汗、恶心。
既往史：高血压病史10年，糖尿病5年。
体格检查：血压150/95mmHg，心率100次/分，心电图示ST段抬高。
入院诊断：急性心肌梗死
治疗：给予溶栓治疗，药物包括阿司匹林、氯吡格雷等。
出院情况：病情稳定出院。
  `

  const prompt = `
你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 评价标准
严格按照四川省住院病历质量评定标准，总分100分：
- 甲级病历：≥90分  
- 乙级病历：75-89分
- 丙级病历：<75分

## 评价项目（9项）
1. 病历基本要求(5分) - 真实性、规范性、完整性
2. 病案首页(20分) - 诊断准确性、信息完整性  
3. 入院记录(10分) - 病史采集、体检记录完整性
4. 病程记录(25分) - 诊疗过程、医师查房记录
5. 手术相关记录(10分) - 手术记录、麻醉记录完整性
6. 出院记录(10分) - 诊疗经过、出院医嘱
7. 知情同意书(10分) - 各种同意书完备性
8. 辅助检查(5分) - 检查结果记录完整性
9. 医嘱(5分) - 医嘱内容规范性

## 输出格式要求
请严格按照以下JSON格式输出：

\`\`\`json
{
  "summary": {
    "totalScore": 数字,
    "grade": "甲级/乙级/丙级",
    "overallAssessment": "总体评价文字"
  },
  "itemScores": [
    {
      "itemId": "项目ID",
      "itemName": "项目名称",
      "totalScore": 总分,
      "actualScore": 实际得分,
      "deduction": 扣分,
      "assessment": "评价说明"
    }
  ],
  "issues": [
    {
      "code": "缺陷代码",
      "description": "缺陷描述",
      "severity": "critical/major/minor",
      "itemId": "所属项目ID",
      "deduction": 扣分数值,
      "location": "在病历中的位置",
      "suggestion": "改进建议"
    }
  ],
  "strengths": ["优点列表"],
  "recommendations": ["改进建议列表"]
}
\`\`\`

## 病历内容
${testContent}

请对以上病历进行专业、客观、全面的质控分析。
`

  try {
    console.log('🔍 开始测试阿里云百炼API...')
    
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
            content: prompt
          }
        ],
        max_tokens: 4000,
        temperature: 0.1,
        stream: false
      })
    })

    if (!response.ok) {
      throw new Error(`API调用失败: ${response.status} ${response.statusText}`)
    }

    const data = await response.json() as any
    
    if (!data.choices || !data.choices[0] || !data.choices[0].message) {
      throw new Error('API响应格式异常')
    }

    const aiResponse = data.choices[0].message.content as string
    console.log('✅ API调用成功!')
    console.log('📄 AI响应内容:')
    console.log(aiResponse)

    // 尝试解析JSON
    try {
      const jsonMatch = aiResponse.match(/```json\s*([\s\S]*?)\s*```/)
      const jsonContent = jsonMatch ? jsonMatch[1] : aiResponse
      const parsed = JSON.parse(jsonContent.trim())
      
      console.log('✅ JSON解析成功!')
      console.log('📊 质控结果:', parsed)
      
      return {
        success: true,
        data: parsed,
        rawResponse: aiResponse
      }
    } catch (parseError) {
      console.warn('⚠️ JSON解析失败，但API调用成功')
      return {
        success: false,
        error: 'JSON解析失败',
        rawResponse: aiResponse
      }
    }

  } catch (error) {
    console.error('❌ API测试失败:', error)
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error)
    }
  }
}

// 在控制台中运行测试
// @ts-ignore
if (typeof window !== 'undefined') {
  // @ts-ignore
  window.testQCAPI = testQCAPI
  console.log('💡 在浏览器控制台中运行 testQCAPI() 来测试API')
} 