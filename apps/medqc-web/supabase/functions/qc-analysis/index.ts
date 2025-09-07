import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

// 质控分析请求接口
interface QCAnalysisRequest {
  record_id: string
  content: string
  focus_items?: string[]
  analysis_mode?: 'comprehensive' | 'focused' | 'quick'
}

// 质控分析结果接口
interface QCAnalysisResult {
  record_id: string
  summary: {
    total_score: number
    grade: '甲级' | '乙级' | '丙级'
    overall_assessment: string
  }
  item_scores: Array<{
    item_id: string
    item_name: string
    total_score: number
    actual_score: number
    deduction: number
    assessment: string
  }>
  issues: Array<{
    code: string
    description: string
    severity: 'critical' | 'major' | 'minor'
    item_id: string
    deduction: number | string
    location: string
    suggestion: string
  }>
  strengths: string[]
  recommendations: string[]
  analysis_time: string
}

// 质控项目配置
const QC_ITEMS = [
  { id: 'basic', name: '病历基本要求', totalScore: 5 },
  { id: 'homepage', name: '病案首页', totalScore: 20 },
  { id: 'admission', name: '入院记录', totalScore: 10 },
  { id: 'progress', name: '病程记录', totalScore: 25 },
  { id: 'surgery', name: '手术相关记录', totalScore: 10 },
  { id: 'discharge', name: '出院记录', totalScore: 10 },
  { id: 'consent', name: '知情同意书', totalScore: 10 },
  { id: 'auxiliary', name: '辅助检查', totalScore: 5 },
  { id: 'orders', name: '医嘱', totalScore: 5 }
]

// 构建质控分析Prompt
function buildQCPrompt(content: string, focusItems?: string[]): string {
  let prompt = `
你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 你的专业背景
- 医学博士，主任医师职称
- 专业从事病案质控工作20年
- 熟悉国家卫健委病历书写规范
- 精通ICD-10疾病编码和手术操作编码
- 对各科室诊疗规范和临床路径非常熟悉

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

## 特殊评价规则
- 单项否决丙级：共23项严重缺陷，一旦发现直接判为丙级
- 乙级扣分：某些重要缺陷直接扣11分
- 各项目扣分不超过该项目总分

## 输出格式要求
请严格按照以下JSON格式输出：

\`\`\`json
{
  "summary": {
    "total_score": 数字,
    "grade": "甲级/乙级/丙级",
    "overall_assessment": "总体评价文字"
  },
  "item_scores": [
    {
      "item_id": "项目ID",
      "item_name": "项目名称", 
      "total_score": 总分,
      "actual_score": 实际得分,
      "deduction": 扣分,
      "assessment": "评价说明"
    }
  ],
  "issues": [
    {
      "code": "缺陷代码如1.1.1",
      "description": "缺陷描述",
      "severity": "critical/major/minor",
      "item_id": "所属项目ID",
      "deduction": 扣分数值或等级,
      "location": "在病历中的位置",
      "suggestion": "改进建议"
    }
  ],
  "strengths": ["优点列表"],
  "recommendations": ["改进建议列表"]
}
\`\`\`

## 病历内容
${content}

请对以上病历进行专业、客观、全面的质控分析。
`

  return prompt
}

// 调用阿里云百炼API
async function callAliyunAPI(prompt: string): Promise<string> {
  const apiKey = Deno.env.get('ALIYUN_API_KEY') || 'sk-e2808814ae874c8f94e40f20c99bc3a3'
  if (!apiKey) {
    throw new Error('ALIYUN_API_KEY环境变量未设置')
  }

  const response = await fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', {
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
    const errorText = await response.text()
    throw new Error(`阿里云百炼API调用失败: ${response.status} ${errorText}`)
  }

  const data = await response.json()
  
  if (!data.choices || !data.choices[0] || !data.choices[0].message) {
    throw new Error('DeepSeek API返回格式异常')
  }

  return data.choices[0].message.content
}

// 解析AI响应
function parseAIResponse(response: string): Partial<QCAnalysisResult> {
  try {
    // 提取JSON内容
    const jsonMatch = response.match(/```json\s*([\s\S]*?)\s*```/)
    let jsonContent = jsonMatch ? jsonMatch[1] : response
    
    jsonContent = jsonContent.trim()
    const parsed = JSON.parse(jsonContent)
    
    return parsed
  } catch (error) {
    console.error('解析AI响应失败:', error)
    
    // 降级处理
    const scoreMatch = response.match(/总分[：:]\s*(\d+)/i)
    const gradeMatch = response.match(/(甲级|乙级|丙级)/i)
    
    const total_score = scoreMatch ? parseInt(scoreMatch[1]) : 0
    const grade = gradeMatch ? gradeMatch[1] : '丙级'
    
    return {
      summary: {
        total_score,
        grade: grade as '甲级' | '乙级' | '丙级',
        overall_assessment: '解析异常，需要人工审核'
      },
      item_scores: QC_ITEMS.map(item => ({
        item_id: item.id,
        item_name: item.name,
        total_score: item.totalScore,
        actual_score: Math.floor(item.totalScore * 0.8),
        deduction: Math.floor(item.totalScore * 0.2),
        assessment: '解析异常'
      })),
      issues: [],
      strengths: [],
      recommendations: ['建议人工复核此病历质控结果']
    }
  }
}

serve(async (req) => {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  }

  // 处理CORS预检请求
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // 验证请求方法
    if (req.method !== 'POST') {
      return new Response(
        JSON.stringify({ error: '仅支持POST请求' }), 
        { 
          status: 405, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      )
    }

    // 解析请求体
    const { record_id, content, focus_items, analysis_mode }: QCAnalysisRequest = await req.json()
    
    // 参数验证
    if (!record_id || !content) {
      return new Response(
        JSON.stringify({ error: '缺少必要参数: record_id, content' }), 
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      )
    }

    console.log(`开始分析病历: ${record_id}`)

    // 构建分析Prompt
    const prompt = buildQCPrompt(content, focus_items)
    
    // 调用阿里云百炼API
    const rawResponse = await callAliyunAPI(prompt)
    
    // 解析AI响应
    const analysisResult = parseAIResponse(rawResponse)
    
    // 构建最终结果
    const finalResult: QCAnalysisResult = {
      record_id,
      summary: analysisResult.summary || {
        total_score: 0,
        grade: '丙级',
        overall_assessment: '分析失败'
      },
      item_scores: analysisResult.item_scores || [],
      issues: analysisResult.issues || [],
      strengths: analysisResult.strengths || [],
      recommendations: analysisResult.recommendations || [],
      analysis_time: new Date().toISOString()
    }

    console.log(`分析完成: ${record_id}, 评分: ${finalResult.summary.total_score}`)

    // 初始化Supabase客户端
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // 保存质控结果到数据库
    const { error: dbError } = await supabase
      .from('qc_results')
      .insert({
        record_id,
        score: finalResult.summary.total_score,
        issues: finalResult.issues,
        suggestions: finalResult.recommendations,
        summary: finalResult.summary.overall_assessment,
        raw_analysis: JSON.stringify(finalResult),
        analysis_time: finalResult.analysis_time
      })

    if (dbError) {
      console.error('保存质控结果失败:', dbError)
    }

    // 更新病历状态
    const { error: updateError } = await supabase
      .from('medical_records')
      .update({ 
        status: 'completed',
        qc_score: finalResult.summary.total_score,
        updated_at: new Date().toISOString()
      })
      .eq('id', record_id)

    if (updateError) {
      console.error('更新病历状态失败:', updateError)
    }

    return new Response(
      JSON.stringify({ 
        success: true, 
        data: finalResult 
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    )

  } catch (error) {
    console.error('质控分析失败:', error)
    
    return new Response(
      JSON.stringify({ 
        error: `质控分析失败: ${error instanceof Error ? error.message : '未知错误'}` 
      }),
      { 
        status: 500, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    )
  }
}) 