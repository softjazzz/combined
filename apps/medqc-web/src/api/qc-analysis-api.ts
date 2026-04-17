/**
 * QC分析API服务
 * 通过后端代理进行智能质控分析
 */
import { supabase, TABLES } from '../lib/backend-store'
import { updateMedicalRecord } from './medical-records'
import { ApiService } from '@/services/apiService'
import type { Database } from '../types/database'
import type { QCAnalysisResult } from '../types/ai-service'

type QCResultRow = Database['public']['Tables']['qc_results']['Row']
type QCResultInsert = Database['public']['Tables']['qc_results']['Insert']
type LLMProxyResponse = {
  choices?: Array<{
    message?: {
      content?: string
    }
  }>
}

type UnknownRecord = Record<string, unknown>

function isRecordLike(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeQCResultRow(value: unknown): QCResultRow | null {
  return isRecordLike(value) ? (value as QCResultRow) : null
}

function normalizeQCResultRows(value: unknown): QCResultRow[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.map(normalizeQCResultRow).filter((row): row is QCResultRow => row !== null)
}

function readJsonLike<T>(value: unknown): T | undefined {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value) as T
    } catch {
      return undefined
    }
  }

  if (Array.isArray(value) || isRecordLike(value)) {
    return value as T
  }

  return undefined
}

function normalizeRecordList(value: unknown): UnknownRecord[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.filter(isRecordLike)
}

function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.map((item) => (typeof item === 'string' ? item : String(item))).filter(Boolean)
}

function getIssueList(value: unknown): UnknownRecord[] {
  if (Array.isArray(value)) {
    return normalizeRecordList(value)
  }

  if (isRecordLike(value)) {
    return normalizeRecordList(value.items)
  }

  return []
}

function getSuggestionList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return normalizeStringList(value)
  }

  if (isRecordLike(value)) {
    return normalizeStringList(value.list)
  }

  return []
}

/**
 * 分析单个医疗记录
 */
export async function analyzeRecord(
  recordId: string,
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
    const recordRow = isRecordLike(record) ? record : null
    const medicalContent =
      typeof recordRow?.content === 'string' ? recordRow.content : String(recordRow?.content || '')

    // 2. 更新状态为分析中
    await updateMedicalRecord(recordId, { status: 'analyzing' })

    try {
      // 3. 调用DeepSeek进行分析
      const analysisResult = await callDeepSeekAnalysis(medicalContent)
      analysisResult.recordId = recordId

      // 4. 保存分析结果到数据库
      await saveQCResult(recordId, analysisResult)

      // 5. 更新医疗记录状态和评分
      await updateMedicalRecord(recordId, {
        status: 'completed',
        qc_score: analysisResult.overallScore,
        qc_grade: analysisResult.grade,
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
      error: error as Error,
    }
  }
}

/**
 * 批量分析医疗记录
 */
export async function batchAnalyzeRecords(recordIds: string[]): Promise<{
  data: { successful: QCAnalysisResult[]; failed: string[] }
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
        await new Promise((resolve) => setTimeout(resolve, 1000))
      }
    }

    return {
      data: { successful, failed },
      error: null,
    }
  } catch (error) {
    console.error('批量分析失败:', error)
    return {
      data: { successful: [], failed: recordIds },
      error: error as Error,
    }
  }
}

/**
 * 获取质控分析结果
 */
export async function getQCResult(
  recordId: string,
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

    const result = normalizeQCResultRow(data)
    return { data: result ? convertRowToQCResult(result) : null, error: null }
  } catch (error) {
    console.error('获取质控结果失败:', error)
    return {
      data: null,
      error: error as Error,
    }
  }
}

/**
 * 获取多个记录的质控结果
 */
export async function getMultipleQCResults(
  recordIds: string[],
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

    const results = normalizeQCResultRows(data).map((row) => convertRowToQCResult(row))
    return { data: results, error: null }
  } catch (error) {
    console.error('获取质控结果失败:', error)
    return {
      data: [],
      error: error as Error,
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
    const result = await callLLMProxy({
      model: 'deepseek-v3',
      messages: [
        {
          role: 'system',
          content:
            '你是一名专业的医疗质控专家，擅长分析病案质量并提供改进建议。请严格按照要求的JSON格式返回分析结果。',
        },
        {
          role: 'user',
          content: QC_ANALYSIS_PROMPT,
        },
      ],
      max_tokens: 2000,
      temperature: 0.1,
    })

    const aiResponse = result.choices?.[0]?.message?.content || ''

    // 解析JSON结果
    const jsonMatch = aiResponse.match(/\{[\s\S]*\}/)
    if (!jsonMatch) {
      throw new Error('AI响应格式错误，无法解析JSON')
    }

    const analysisData = JSON.parse(jsonMatch[0]) as {
      overall_score?: number
      grade?: 'A' | 'B' | 'C'
      completeness_score?: number
      consistency_score?: number
      rationality_score?: number
      timeliness_score?: number
      issues?: unknown[]
      suggestions?: unknown[]
    }
    const analysisTime = Date.now() - startTime
    const issueList = Array.isArray(analysisData.issues) ? analysisData.issues : []
    const suggestions = Array.isArray(analysisData.suggestions) ? analysisData.suggestions : []

    // 构造标准化结果
    const qcResult: QCAnalysisResult = {
      recordId: '', // 在调用方设置
      overallScore: analysisData.overall_score || 0,
      grade: analysisData.grade || 'C',
      status: 'completed',
      ruleResults: [], // 简化实现
      categoryScores: {
        completeness: analysisData.completeness_score || 0,
        consistency: analysisData.consistency_score || 0,
        rationality: analysisData.rationality_score || 0,
        timeliness: analysisData.timeliness_score || 0,
      },
      summary: {
        totalRules: 18,
        violatedRules: issueList.length,
        criticalIssues: Math.min(issueList.length, 2),
        majorIssues: Math.max(0, issueList.length - 2),
        minorIssues: 0,
      },
      suggestions: suggestions.map(String),
      analysisTime: analysisTime,
      createdAt: new Date().toISOString(),
    }

    return qcResult
  } catch (error) {
    console.error('质控分析失败:', error)
    throw new Error(`AI分析失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}

async function callLLMProxy(requestBody: Record<string, unknown>): Promise<LLMProxyResponse> {
  try {
    const response = await ApiService.postRaw<LLMProxyResponse>('/api/v1/llm/parse-text', {
      requestBody,
    })

    return response.data
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    throw new Error(`代理分析调用失败: ${message}`)
  }
}

/**
 * 保存质控结果到数据库
 */
async function saveQCResult(
  recordId: string,
  analysisResult: QCAnalysisResult,
): Promise<QCResultRow> {
  try {
    const issuesPayload: Record<string, unknown> = {
      items: analysisResult.ruleResults,
    }

    const suggestionsPayload: Record<string, unknown> = {
      list: analysisResult.suggestions,
    }

    const insertData: QCResultInsert = {
      record_id: recordId,
      score: analysisResult.overallScore,
      ai_score: analysisResult.categoryScores.completeness,
      rule_score: analysisResult.categoryScores.consistency,
      grade: analysisResult.grade,
      issues: issuesPayload,
      suggestions: suggestionsPayload,
      category_scores: analysisResult.categoryScores as Record<string, unknown>,
      confidence_score: 0.95,
      rule_version: '1.0',
      analysis_time: String(analysisResult.analysisTime),
      raw_analysis: JSON.stringify(analysisResult),
      summary: JSON.stringify(analysisResult.summary),
      is_reviewed: false,
      reviewer_id: null,
      review_notes: null,
    }

    const { data, error } = await supabase
      .from(TABLES.QC_RESULTS)
      .upsert(insertData, { onConflict: 'record_id' })
      .select()
      .single()

    if (error) {
      throw new Error(`保存质控结果失败: ${error.message}`)
    }

    const saved = normalizeQCResultRow(data)
    if (!saved) {
      throw new Error('保存质控结果失败: 返回数据格式异常')
    }

    return saved
  } catch (error) {
    console.error('保存质控结果失败:', error)
    throw error
  }
}

/**
 * 转换数据库行为QCAnalysisResult类型
 */
function convertRowToQCResult(row: QCResultRow): QCAnalysisResult {
  const categoryScoresRecord = isRecordLike(row.category_scores) ? row.category_scores : {}
  const parseCategoryScore = (key: string): number => {
    const value = categoryScoresRecord[key]
    return typeof value === 'number' ? value : 0
  }

  const issueList = getIssueList(row.issues)
  const suggestionList = getSuggestionList(row.suggestions)
  const summary = readJsonLike<QCAnalysisResult['summary']>(row.summary)
  const rawAnalysis = readJsonLike<Partial<QCAnalysisResult>>(row.raw_analysis)

  const rawRuleResults = Array.isArray(rawAnalysis?.ruleResults) ? rawAnalysis.ruleResults : []

  return {
    recordId: row.record_id,
    overallScore: typeof row.score === 'number' ? row.score : rawAnalysis?.overallScore || 0,
    grade: row.grade || rawAnalysis?.grade || 'C',
    status: 'completed',
    ruleResults: rawRuleResults,
    categoryScores: {
      completeness: parseCategoryScore('completeness'),
      consistency: parseCategoryScore('consistency'),
      rationality: parseCategoryScore('rationality'),
      timeliness: parseCategoryScore('timeliness'),
    },
    summary: summary || {
      totalRules: 18,
      violatedRules: issueList.length,
      criticalIssues: issueList.filter(
        (item) => typeof item.severity === 'string' && item.severity === 'critical',
      ).length,
      majorIssues: issueList.filter(
        (item) => typeof item.severity === 'string' && item.severity === 'major',
      ).length,
      minorIssues: issueList.filter(
        (item) => typeof item.severity === 'string' && item.severity === 'minor',
      ).length,
    },
    suggestions: suggestionList.map(String),
    analysisTime: Number(row.analysis_time ?? rawAnalysis?.analysisTime ?? 0) || 0,
    createdAt: row.analysis_time ?? rawAnalysis?.createdAt ?? new Date().toISOString(),
  }
}

/**
 * 健康检查 - 测试DeepSeek API连接
 */
export async function healthCheck(): Promise<{
  status: 'ok' | 'error'
  message: string
  details?: Record<string, unknown>
}> {
  try {
    const result = await callLLMProxy({
      model: 'deepseek-v3',
      messages: [
        {
          role: 'user',
          content: '你好，请回复"连接正常"',
        },
      ],
      max_tokens: 50,
      temperature: 0,
    })
    const content = result.choices?.[0]?.message?.content || ''

    return {
      status: 'ok',
      message: 'AI分析连接正常',
      details: {
        model: 'deepseek-v3',
        response: content,
      },
    }
  } catch (error) {
    return {
      status: 'error',
      message: 'AI分析连接失败',
      details: {
        error: error instanceof Error ? error.message : '未知错误',
      },
    }
  }
}
