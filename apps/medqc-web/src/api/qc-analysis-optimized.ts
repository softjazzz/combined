/**
 * 优化版质控分析API
 * 集成性能优化、缓存、错误处理等功能
 */

import { optimizedQCAnalysisService, type OptimizedQCRequest, type OptimizedQCResult } from '../lib/qc-analysis-optimized'
import { databaseOptimizer } from '../lib/database-optimizer'
import { supabase } from '../lib/supabase'
import type { ApiResponse } from '../utils/api-wrapper'

// API请求接口
export interface QCAnalysisApiRequest {
  recordId: string
  content: string
  options?: {
    analysisMode?: 'comprehensive' | 'focused' | 'quick'
    enableRulesEngine?: boolean
    enableCache?: boolean
    priority?: 'high' | 'normal' | 'low'
    selectedCategories?: string[]
  }
}

// 批量分析请求
export interface BatchQCAnalysisRequest {
  records: Array<{
    recordId: string
    content: string
    priority?: 'high' | 'normal' | 'low'
  }>
  options?: {
    analysisMode?: 'comprehensive' | 'focused' | 'quick'
    enableRulesEngine?: boolean
    enableCache?: boolean
    maxConcurrency?: number
  }
}

/**
 * 执行单个病案质控分析
 */
export async function analyzeRecord(
  request: QCAnalysisApiRequest
): Promise<ApiResponse<OptimizedQCResult>> {
  try {
    // 验证输入
    if (!request.recordId || !request.content) {
      return {
        success: false,
        error: new Error('病案ID和内容不能为空')
      }
    }

    if (request.content.length > 50000) {
      return {
        success: false,
        error: new Error('病案内容过长，请确保小于50000字符')
      }
    }

    // 构建分析请求
    const analysisRequest: OptimizedQCRequest = {
      recordId: request.recordId,
      content: request.content,
      analysisMode: request.options?.analysisMode || 'comprehensive',
      enableRulesEngine: request.options?.enableRulesEngine !== false,
      enableCache: request.options?.enableCache !== false,
      priority: request.options?.priority || 'normal',
      selectedRuleCategories: request.options?.selectedCategories as any
    }

    // 执行分析
    const result = await optimizedQCAnalysisService.analyzeRecord(analysisRequest)

    // 保存分析结果到数据库
    await saveAnalysisResult(result)

    return {
      success: true,
      data: result
    }
  } catch (error) {
    console.error('质控分析API错误:', error)
    return {
      success: false,
      error: error as Error
    }
  }
}

/**
 * 批量质控分析
 */
export async function batchAnalyzeRecords(
  request: BatchQCAnalysisRequest
): Promise<ApiResponse<{
  results: Array<OptimizedQCResult | Error>
  summary: {
    total: number
    successful: number
    failed: number
    averageTime: number
  }
}>> {
  try {
    // 验证输入
    if (!request.records || request.records.length === 0) {
      return {
        success: false,
        error: new Error('批量分析记录不能为空')
      }
    }

    if (request.records.length > 50) {
      return {
        success: false,
        error: new Error('批量分析最多支持50条记录')
      }
    }

    // 构建分析请求
    const analysisRequests: OptimizedQCRequest[] = request.records.map(record => ({
      recordId: record.recordId,
      content: record.content,
      analysisMode: request.options?.analysisMode || 'comprehensive',
      enableRulesEngine: request.options?.enableRulesEngine !== false,
      enableCache: request.options?.enableCache !== false,
      priority: record.priority || 'normal'
    }))

    // 执行批量分析
    const batchResult = await optimizedQCAnalysisService.batchAnalyze(analysisRequests)

    // 保存成功的分析结果
    const successfulResults = batchResult.results.filter(
      (result): result is OptimizedQCResult => !(result instanceof Error)
    )

    await Promise.all(
      successfulResults.map(result => saveAnalysisResult(result))
    )

    return {
      success: true,
      data: batchResult
    }
  } catch (error) {
    console.error('批量质控分析API错误:', error)
    return {
      success: false,
      error: error as Error
    }
  }
}

/**
 * 获取分析历史
 */
export async function getAnalysisHistory(
  recordId: string,
  options: {
    limit?: number
    offset?: number
    orderBy?: 'analysis_time' | 'overall_score'
    order?: 'asc' | 'desc'
  } = {}
): Promise<ApiResponse<{
  data: OptimizedQCResult[]
  total: number
  hasMore: boolean
}>> {
  try {
    const {
      limit = 10,
      offset = 0,
      orderBy = 'analysis_time',
      order = 'desc'
    } = options

    // 使用优化的查询
    const result = await databaseOptimizer.executeOptimizedQuery(
      () => supabase
        .from('qc_results')
        .select('*')
        .eq('record_id', recordId)
        .order(orderBy, { ascending: order === 'asc' })
        .range(offset, offset + limit - 1),
      `analysis_history_${recordId}_${limit}_${offset}_${orderBy}_${order}`
    )

    // 获取总数
    const countResult = await databaseOptimizer.executeOptimizedQuery(
      () => supabase
        .from('qc_results')
        .select('*', { count: 'exact', head: true })
        .eq('record_id', recordId),
      `analysis_count_${recordId}`
    )

    const total = countResult.count || 0
    const hasMore = offset + limit < total

    return { success: true,
      data: {
        data: result || [],
        total,
        hasMore
      }
    }
  } catch (error) {
    console.error('获取分析历史错误:', error)
    return {
      success: false,
      error: error as Error
    }
  }
}

/**
 * 获取性能统计
 */
export async function getPerformanceStats(): Promise<ApiResponse<{
  analysis: Record<string, unknown>
  database: Record<string, unknown>
  cache: Record<string, unknown>
}>> {
  try {
    const analysisStats = optimizedQCAnalysisService.getPerformanceStats()
    const databaseStats = databaseOptimizer.getQueryStats()
    const cacheStats = databaseOptimizer.getCacheStats()

    return {
      success: true,
      data: {
        analysis: analysisStats,
        database: databaseStats,
        cache: cacheStats
      }
    }
  } catch (error) {
    console.error('获取性能统计错误:', error)
    return {
      success: false,
      error: error as Error
    }
  }
}

/**
 * 清空缓存
 */
export async function clearAllCaches(): Promise<ApiResponse<{ message: string }>> {
  try {
    optimizedQCAnalysisService.clearCache()
    databaseOptimizer.clearCache()

    return {
      success: true,
      data: { message: '所有缓存已清空' }
    }
  } catch (error) {
    console.error('清空缓存错误:', error)
    return {
      success: false,
      error: error as Error
    }
  }
}

/**
 * 保存分析结果到数据库
 */
async function saveAnalysisResult(result: OptimizedQCResult): Promise<void> {
  try {
    await databaseOptimizer.executeOptimizedQuery(
      () => supabase
        .from('qc_results')
        .upsert({
          record_id: result.recordId,
          overall_score: result.overallScore,
          grade: result.grade,
          completeness_score: result.completenessScore,
          consistency_score: result.consistencyScore,
          rationality_score: result.rationalityScore,
          timeliness_score: result.timelinessScore,
          issues: result.issues,
          suggestions: result.suggestions,
          analysis_time: result.analysisTime,
          processing_stats: result.processingStats,
          rules_engine_results: result.rulesEngineResults,
          raw_response: result.rawResponse,
          updated_at: new Date().toISOString()
        }),
      undefined,
      { enableCache: false } // 不缓存写操作
    )
  } catch (error) {
    console.error('保存分析结果失败:', error)
    // 不抛出错误，避免影响主流程
  }
}
