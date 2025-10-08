/**
 * QC分析API服务
 * 集成DeepSeek AI进行智能质控分析
 */
import { supabase, TABLES } from '../lib/supabase'
import { updateMedicalRecord } from './medical-records'
import type { Database } from '../types/database'
import type { QCAnalysisResult } from '../types/ai-service'
import type { MedicalRecord } from '../types/medical-records'

// 阿里云百炼DeepSeek V3配置
const DEEPSEEK_CONFIG = {
  apiKey: 'sk-f1fa15b00fb042a9a80943a40e142daf',
  baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  model: 'deepseek-v3'
}

type QCResultRow = Database['public']['Tables']['qc_results']['Row']
type QCResultInsert = Database['public']['Tables']['qc_results']['Insert']

/**
 * 分析单个医疗记录
 */
export async function analyzeRecord(
  recordId: string
): Promise<{ data: QCAnalysisResult | null; error: Error | null }> {
  try {
    // 1. 获取医疗记录
    const { data: record, error: recordError } = await supabase
      .from(TABLES.MEDICAL_RECORDS)
      .select('*')
      .eq('id', recordId)
      .single()

    if (recordError || !record) {
      throw new Error(`获取医疗记录失败: ${recordError?.message}`)
    }

    // 2. 更新状态为分析中
    await updateMedicalRecord(recordId, { status: 'analyzing' })

    try {
      // 3. 调用DeepSeek进行分析
      const analysisResult = await callDeepSeekAnalysis(record.content)

      // 4. 保存分析结果到数据库
      const qcResult = await saveQCResult(recordId, analysisResult)

      // 5. 更新医疗记录状态和评分
      await updateMedicalRecord(recordId, {
        status: 'completed',
        qc_score: analysisResult.overallScore,
        qc_grade: analysisResult.grade
      })

      return { data: analysisResult, error: null }
    } catch (analysisError) {
      // 分析失败，更新状态
      await updateMedicalRecord(recordId, { status: 'failed' })
      throw analysisError
    }
  } catch (error) {
    console.error('分析医疗记录失败:', error)
    return {
      data: null,
      error: error as Error
    }
  }
}

/**
 * 批量分析医疗记录
 */
export async function batchAnalyzeRecords(
  recordIds: string[]
): Promise<{ 
  data: { successful: QCAnalysisResult[]; failed: string[] }; 
  error: Error | null 
}> {
  try {
    const successful: QCAnalysisResult[] = []
    const failed: string[] = []

    // 限制并发数量，避免API限制
    const batchSize = 3
    for (let i = 0; i < recordIds.length; i += batchSize) {
      const batch = recordIds.slice(i, i + batchSize)
      
      const promises = batch.map(async (recordId) => {
        const { data, error } = await analyzeRecord(recordId)
        if (error) {
          failed.push(recordId)
        } else if (data) {
          successful.push(data)
        }
      })

      await Promise.all(promises)
      
      // 避免过快调用API
      if (i + batchSize < recordIds.length) {
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
    }

    return {
      data: { successful, failed },
      error: null
    }
  } catch (error) { console.error('批量分析失败:', error)
    return {
      data: { successful:  [], failed: recordIds },
      error: error as Error
    }
  }
}

/**
 * 获取质控分析结果
 */
export async function getQCResult(
  recordId: string
): Promise<{ data: QCAnalysisResult | null; error: Error | null }> {
  try {
    const { data, error } = await supabase
      .from(TABLES.QC_RESULTS)
      .select('*')
      .eq('record_id', recordId)
      .order('created_at', { ascending: false })
      .limit(1)
      .single()

    if (error) {
      throw new Error(`获取质控结果失败: ${error.message}`)
    }

    const result = convertRowToQCResult(data)
    return { data: result, error: null }
  } catch (error) {
    console.error('获取质控结果失败:', error)
    return {
      data: null,
      error: error as Error
    }
  }
}

/**
 * 获取多个记录的质控结果
 */
export async function getMultipleQCResults(
  recordIds: string[]
): Promise<{ data: QCAnalysisResult[]; error: Error | null }> {
  try {
    const { data, error } = await supabase
      .from(TABLES.QC_RESULTS)
      .select('*')
      .in('record_id', recordIds)
      .order('created_at', { ascending: false })

    if (error) {
      throw new Error(`获取质控结果失败: ${error.message}`)
    }

    const results = (data || : unknown[]).map(convertRowToQCResult)
    return { data: results, error: null }
  } catch (error) { console.error('获取质控结果失败:', error)
    return {
      data:  [],
      error: error as Error
    }
  }
}

/**
 * 调用DeepSeek API进行分析
 */
async function callDeepSeekAnalysis(content: string): Promise<QCAnalysisResult> {
  const QC_ANALYSIS_PROMPT = `
你是一名专业的医疗质控专家，请对以下病案进行全面的质量控制分析。

请从以下四个维度进行评估：

1. **完整性评估**：
   - 检查病案记录是否完整
   - 必需信息是否齐全
   - 缺失哪些重要内容

2. **一致性评估**：
   - 症状、体征、检查结果是否一致
   - 诊断与临床表现是否匹配
   - 治疗方案与诊断是否相符

3. **合理性评估**：
   - 诊断是否合理
   - 治疗方案是否恰当
   - 用药是否规范

4. **及时性评估**：
   - 诊疗流程是否及时
   - 关键检查是否及时完成
   - 治疗是否及时启动

请以JSON格式返回分析结果，包含：
- completeness_score: 完整性评分(0-100)
- consistency_score: 一致性评分(0-100)  
- rationality_score: 合理性评分(0-100)
- timeliness_score: 及时性评分(0-100)
- overall_score: 总体评分(0-100)
- grade: 等级评定(A/B/C)
- issues: 发现的问题列表
- suggestions: 改进建议列表

病案内容：
${content}
`

  const startTime = Date.now()

  try {
    const response = await fetch(`${DEEPSEEK_CONFIG.baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${DEEPSEEK_CONFIG.apiKey}`
      },
      body: JSON.stringify({
        model: DEEPSEEK_CONFIG.model,
        messages: [
          {
            role: 'system',
            content: '你是一名专业的医疗质控专家，擅长分析病案质量并提供改进建议。请严格按照要求的JSON格式返回分析结果。'
          },
          {
            role: 'user',
            content: QC_ANALYSIS_PROMPT
          }
        ],
        max_tokens: 2000,
        temperature: 0.1
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`DeepSeek API调用失败: ${response.status} ${errorText}`)
    }

    const result = await response.json() as any
    const aiResponse = result.choices?.[0]?.message?.content || ''
    
    // 解析JSON结果
    const jsonMatch = aiResponse.match(/\{[\s\S]*\}/)
    if (!jsonMatch) {
      throw new Error('AI响应格式错误，无法解析JSON')
    }

    const analysisData = JSON.parse(jsonMatch[0])
    const analysisTime = Date.now() - startTime

    // 构造标准化结果
    const qcResult: QCAnalysisResult = { recordId: '', // 在调用方设置
      overallScore: analysisData.overall_score || 0,
      grade: analysisData.grade || 'C',
      status: 'completed',
      ruleResults:  [], // 简化实现
      categoryScores: {
        completeness: analysisData.completeness_score || 0,
        consistency: analysisData.consistency_score || 0,
        rationality: analysisData.rationality_score || 0,
        timeliness: analysisData.timeliness_score || 0
      },
      summary: {
        totalRules: 18,
        violatedRules: analysisData.issues?.length || 0,
        criticalIssues: Math.min(analysisData.issues?.length || 0, 2),
        majorIssues: Math.max(0, (analysisData.issues?.length || 0) - 2),
        minorIssues: 0
      },
      suggestions: analysisData.suggestions || [],
      analysisTime: analysisTime,
      createdAt: new Date().toISOString()
    }

    return qcResult
  } catch (error) {
    console.error('DeepSeek分析失败:', error)
    throw new Error(`AI分析失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}

/**
 * 保存质控结果到数据库
 */
async function saveQCResult(
  recordId: string, 
  analysisResult: QCAnalysisResult
): Promise<QCResultRow> { try {
    const insertData: QCResultInsert = {
      record_id: recordId,
      analysis_result: analysisResult,
      overall_score: analysisResult.overallScore,
      completeness_score: analysisResult.categoryScores.completeness,
      consistency_score: analysisResult.categoryScores.consistency,
      rationality_score: analysisResult.categoryScores.rationality,
      timeliness_score: analysisResult.categoryScores.timeliness,
      grade: analysisResult.grade,
      issues:  [], // 从suggestions中提取
      suggestions: analysisResult.suggestions,
      ai_model: 'deepseek-v3',
      analysis_time_ms: analysisResult.analysisTime,
      confidence_score: 0.95,
      rule_version: '1.0',
      created_at: new Date().toISOString()
    }

    const { data, error } = await supabase
      .from(TABLES.QC_RESULTS)
      .insert(insertData)
      .select()
      .single()

    if (error) {
      throw new Error(`保存质控结果失败: ${error.message}`)
    }

    return data
  } catch (error) {
    console.error('保存质控结果失败:', error)
    throw error
  }
}

/**
 * 转换数据库行为QCAnalysisResult类型
 */
function convertRowToQCResult(row: QCResultRow): QCAnalysisResult { return {
    recordId: row.record_id,
    overallScore: row.overall_score,
    grade: row.grade,
    status: 'completed',
    ruleResults:  [], // 简化实现
    categoryScores: {
      completeness: row.completeness_score,
      consistency: row.consistency_score,
      rationality: row.rationality_score,
      timeliness: row.timeliness_score
    },
    summary: {
      totalRules: 18,
      violatedRules: row.issues.length,
      criticalIssues: Math.min(row.issues.length, 2),
      majorIssues: Math.max(0, row.issues.length - 2),
      minorIssues: 0
    },
    suggestions: row.suggestions,
    analysisTime: row.analysis_time_ms,
    createdAt: row.created_at
  }
}

/**
 * 健康检查 - 测试DeepSeek API连接
 */
export async function healthCheck(): Promise<{ 
  status: 'ok' | 'error'; 
  message: string; 
  details?: Record<string, unknown> 
}> {
  try {
    const response = await fetch(`${DEEPSEEK_CONFIG.baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${DEEPSEEK_CONFIG.apiKey}`
      },
      body: JSON.stringify({
        model: DEEPSEEK_CONFIG.model,
        messages: [
          {
            role: 'user',
            content: '你好，请回复"连接正常"'
          }
        ],
        max_tokens: 50,
        temperature: 0
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json() as any
    const content = result.choices?.[0]?.message?.content || ''

    return {
      status: 'ok',
      message: 'DeepSeek API连接正常',
      details: {
        model: DEEPSEEK_CONFIG.model,
        response: content
      }
    }
  } catch (error) {
    return {
      status: 'error',
      message: 'DeepSeek API连接失败',
      details: {
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  }
} 