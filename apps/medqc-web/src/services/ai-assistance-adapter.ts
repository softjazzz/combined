// AI辅助服务适配器
// 适配Python FastAPI后端的AI辅助功能

import type {
  QCAuditTaskItem,
  AIDefectSuggestion,
  DefectAnalysisContext,
  QCDefect,
  BatchAuditRequest
} from '@/types/audit-module'

import { unifiedAPIClient } from './unified-api-client'

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export class AIAssistanceServiceAdapter {
  private useEnhancedAPI = true // 标志：是否使用增强版API

  /**
   * AI辅助缺陷识别（单个任务项）
   * 优先使用增强版Python FastAPI后端，降级到原始API
   */
  async suggestDefects(
    taskItem: QCAuditTaskItem,
    context: DefectAnalysisContext,
    options: {
      useCache?: boolean
      useEnhanced?: boolean
    } = {}
  ): Promise<AIDefectSuggestion[]> {
    const { useCache = true, useEnhanced = this.useEnhancedAPI } = options

    try {
      console.log(`AI辅助缺陷识别: 患者 ${taskItem.patient_name}`)

      let suggestions: AIDefectSuggestion[]

      if (useEnhanced) {
        // 使用增强版API
        try {
          suggestions = await this.callEnhancedDefectDetection(
            taskItem.id,
            context,
            useCache
          )
          console.log(`增强版AI识别到 ${suggestions.length} 个潜在缺陷`)
        } catch (enhancedError) {
          console.warn('增强版API调用失败，降级到原始API:', enhancedError)
          // 降级到原始API
          suggestions = await unifiedAPIClient.detectDefectsForTaskItem(
            taskItem.id,
            context
          )
          console.log(`原始API识别到 ${suggestions.length} 个潜在缺陷`)
        }
      } else {
        // 直接使用原始API
        suggestions = await unifiedAPIClient.detectDefectsForTaskItem(
          taskItem.id,
          context
        )
        console.log(`AI识别到 ${suggestions.length} 个潜在缺陷`)
      }

      return suggestions

    } catch (error) {
      console.error('AI缺陷识别失败:', error)

      // 返回空数组而不是抛出异常，保证用户体验
      return []
    }
  }

  /**
   * 调用增强版缺陷检测API
   */
  private async callEnhancedDefectDetection(
    taskItemId: string,
    context: DefectAnalysisContext,
    useCache: boolean
  ): Promise<AIDefectSuggestion[]> {
    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL}/api/enhanced-ai-assistance/defect-detection/${taskItemId}?use_cache=${useCache}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify(context)
      }
    )

    if (!response.ok) {
      throw new Error(`增强版API调用失败: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data.success ? data.data : data
  }

  private getAuthToken(): string {
    return localStorage.getItem('auth_token') || ''
  }

  /**
   * 批量AI缺陷识别
   * 优先使用增强版API，支持智能降级
   */
  async batchSuggestDefects(
    taskItems: QCAuditTaskItem[],
    context: DefectAnalysisContext,
    options: {
      useCache?: boolean
      useEnhanced?: boolean
    } = {}
  ): Promise<Record<string, AIDefectSuggestion[]>> {
    const { useCache = true, useEnhanced = this.useEnhancedAPI } = options

    try {
      console.log(`批量AI缺陷识别: ${taskItems.length} 个任务项`)

      let results: Record<string, AIDefectSuggestion[]>

      if (useEnhanced) {
        // 使用增强版API
        try {
          results = await this.callEnhancedBatchDefectDetection(
            taskItems,
            context,
            useCache
          )

          const totalSuggestions = Object.values(results).reduce(
            (sum, suggestions) => sum + suggestions.length, 0
          )
          console.log(`增强版批量AI识别完成，发现 ${totalSuggestions} 个潜在缺陷`)
        } catch (enhancedError) {
          console.warn('增强版批量API调用失败，降级到原始API:', enhancedError)
          // 降级到原始API
          results = await this.callOriginalBatchDefectDetection(taskItems, context)
        }
      } else {
        // 直接使用原始API
        results = await this.callOriginalBatchDefectDetection(taskItems, context)
      }

      return results

    } catch (error) {
      console.error('批量AI缺陷识别失败:', error)

      // 返回空结果而不是抛出异常
      const emptyResults: Record<string, AIDefectSuggestion[]> = {}
      taskItems.forEach(item => {
        emptyResults[item.id] = []
      })
      return emptyResults
    }
  }

  /**
   * 调用增强版批量缺陷检测API
   */
  private async callEnhancedBatchDefectDetection(
    taskItems: QCAuditTaskItem[],
    context: DefectAnalysisContext,
    useCache: boolean
  ): Promise<Record<string, AIDefectSuggestion[]>> {
    const request: BatchAuditRequest = {
      task_id: taskItems[0]?.task_id || '',
      task_item_ids: taskItems.map(item => item.id),
      batch_notes: '增强版AI批量缺陷识别'
    }

    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL}/api/enhanced-ai-assistance/batch-defect-detection?use_cache=${useCache}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify({
          ...request,
          analysis_context: context
        })
      }
    )

    if (!response.ok) {
      throw new Error(`增强版批量API调用失败: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data.success ? data.data : data
  }

  /**
   * 调用原始批量缺陷检测API
   */
  private async callOriginalBatchDefectDetection(
    taskItems: QCAuditTaskItem[],
    context: DefectAnalysisContext
  ): Promise<Record<string, AIDefectSuggestion[]>> {
    const request: BatchAuditRequest = {
      task_id: taskItems[0]?.task_id || '',
      task_item_ids: taskItems.map(item => item.id),
      batch_notes: 'AI批量缺陷识别'
    }

    const results = await unifiedAPIClient.batchDetectDefects(request, context)

    const totalSuggestions = Object.values(results).reduce(
      (sum, suggestions) => sum + suggestions.length, 0
    )

    console.log(`原始API批量识别完成，发现 ${totalSuggestions} 个潜在缺陷`)
    return results
  }

  /**
   * 生成整改计划
   */
  async generateRectificationPlan(
    defects: QCDefect[],
    medicalRecordId: string,
    context?: Record<string, unknown>
  ): Promise<unknown> {
    try {
      console.log(`生成整改计划: ${defects.length} 个缺陷`)
      
      const defectsData = defects.map(defect => ({
        id: defect.id,
        type: defect.defect_type,
        category: defect.defect_category,
        severity: defect.severity,
        title: defect.title,
        description: defect.description,
        location: defect.location,
        score_deduction: defect.score_deduction
      }))
      
      const plan = await unifiedAPIClient.generateRectificationPlan(
        defectsData,
        medicalRecordId,
        context
      )
      
      console.log('整改计划生成成功')
      return plan
      
    } catch (error: unknown) {
      console.error('生成整改计划失败:', error)
      throw new Error(`生成整改计划失败: ${getErrorMessage(error)}`)
    }
  }

  /**
   * 智能医疗记录分析
   */
  async smartAnalyzeMedicalRecord(
    medicalRecordId: string,
    analysisConfig: {
      focus_areas?: string[]
      analysis_depth?: 'basic' | 'comprehensive' | 'detailed'
      include_recommendations?: boolean
    } = {}
  ): Promise<unknown> {
    try {
      console.log(`智能分析医疗记录: ${medicalRecordId}`)
      
      const defaultConfig = {
        focus_areas: ['completeness', 'consistency', 'timeliness', 'accuracy'],
        analysis_depth: 'comprehensive' as const,
        include_recommendations: true,
        ...analysisConfig
      }
      
      const result = await unifiedAPIClient.smartMedicalRecordAnalysis(
        medicalRecordId,
        defaultConfig
      )
      
      console.log('智能分析完成')
      return result
      
    } catch (error: unknown) {
      console.error('智能分析失败:', error)
      throw new Error(`智能分析失败: ${getErrorMessage(error)}`)
    }
  }

  /**
   * AI质量评分预测
   */
  async predictQualityScore(
    medicalRecordId: string,
    predictionConfig: {
      model_type?: 'standard' | 'enhanced' | 'expert'
      include_confidence_interval?: boolean
      include_factor_analysis?: boolean
    } = {}
  ): Promise<{
    predicted_score: number
    confidence_interval?: [number, number]
    influencing_factors?: Array<{
      factor: string
      impact: number
      description: string
    }>
    model_info: {
      model_type: string
      version: string
      accuracy: number
    }
  }> {
    try {
      console.log(`AI质量评分预测: ${medicalRecordId}`)
      
      const defaultConfig = {
        model_type: 'enhanced' as const,
        include_confidence_interval: true,
        include_factor_analysis: true,
        ...predictionConfig
      }
      
      const result = await unifiedAPIClient.predictQualityScore(
        medicalRecordId,
        defaultConfig
      ) as {
        predicted_score: number
        confidence_interval?: [number, number]
        influencing_factors?: Array<{
          factor: string
          impact: number
          description: string
        }>
        model_info: {
          model_type: string
          version: string
          accuracy: number
        }
      }
      
      console.log(`预测评分: ${result.predicted_score}`)
      return result
      
    } catch (error: unknown) {
      console.error('质量评分预测失败:', error)
      throw new Error(`质量评分预测失败: ${getErrorMessage(error)}`)
    }
  }

  /**
   * 获取AI分析历史
   */
  async getAnalysisHistory(
    taskItemId: string,
    limit: number = 10
  ): Promise<Array<{
    id: string
    analysis_type: string
    timestamp: string
    results_summary: Record<string, unknown>
    confidence_score: number
    reviewer_feedback?: Record<string, unknown>
  }>> {
    try {
      return await unifiedAPIClient.getAIAnalysisHistory(taskItemId, limit)
    } catch (error: unknown) {
      console.error('获取分析历史失败:', error)
      return []
    }
  }

  /**
   * 提交AI分析反馈
   */
  async submitAnalysisFeedback(
    analysisId: string,
    feedback: {
      accuracy_rating: number // 1-5
      usefulness_rating: number // 1-5
      comments?: string
      suggested_improvements?: string[]
      would_recommend?: boolean
    }
  ): Promise<void> {
    try {
      console.log(`提交AI分析反馈: ${analysisId}`)
      
      const feedbackData = {
        analysis_id: analysisId,
        feedback_type: 'analysis_quality',
        ratings: {
          accuracy: feedback.accuracy_rating,
          usefulness: feedback.usefulness_rating
        },
        comments: feedback.comments,
        suggestions: feedback.suggested_improvements,
        recommendation: feedback.would_recommend,
        timestamp: new Date().toISOString()
      }
      
      await unifiedAPIClient.submitAIFeedback(feedbackData)
      
      console.log('反馈提交成功')
      
    } catch (error: unknown) {
      console.error('提交反馈失败:', error)
      throw new Error(`提交反馈失败: ${getErrorMessage(error)}`)
    }
  }

  /**
   * 获取AI服务状态
   */
  async getAIServiceStatus(): Promise<{
    qc_engine_status: string
    llm_service_status: string
    analysis_queue_size: number
    average_response_time: number
    success_rate: number
  }> {
    try {
      // 通过健康检查API获取状态
      const healthData = await unifiedAPIClient.getSystemHealth() as {
        services?: Record<string, unknown>
      }
      
      return {
        qc_engine_status: String(healthData.services?.qc_engine ?? 'unknown'),
        llm_service_status: String(healthData.services?.llm_service ?? 'unknown'),
        analysis_queue_size: Number(healthData.services?.queued_notifications ?? 0),
        average_response_time: 0, // 需要从实际监控数据获取
        success_rate: 0.95 // 需要从实际统计数据获取
      }
      
    } catch (error: unknown) {
      console.error('获取AI服务状态失败:', error)
      return {
        qc_engine_status: 'unknown',
        llm_service_status: 'unknown',
        analysis_queue_size: 0,
        average_response_time: 0,
        success_rate: 0
      }
    }
  }

  /**
   * 缓存AI分析结果（前端缓存）
   */
  private analysisCache = new Map<string, {
    data: unknown
    timestamp: number
    ttl: number
  }>()

  private getCacheKey(taskItemId: string, context: DefectAnalysisContext): string {
    return `${taskItemId}_${context.audit_level}_${JSON.stringify(context.reviewer_expertise)}`
  }

  private getCachedAnalysis(cacheKey: string): unknown | null {
    const cached = this.analysisCache.get(cacheKey)
    if (cached && Date.now() - cached.timestamp < cached.ttl) {
      return cached.data
    }
    
    if (cached) {
      this.analysisCache.delete(cacheKey)
    }
    
    return null
  }

  private setCachedAnalysis(cacheKey: string, data: unknown, ttlMinutes: number = 30): void {
    this.analysisCache.set(cacheKey, {
      data,
      timestamp: Date.now(),
      ttl: ttlMinutes * 60 * 1000
    })
  }

  /**
   * 带缓存的AI缺陷识别
   */
  async suggestDefectsWithCache(
    taskItem: QCAuditTaskItem,
    context: DefectAnalysisContext,
    useCache: boolean = true
  ): Promise<AIDefectSuggestion[]> {
    const cacheKey = this.getCacheKey(taskItem.id, context)
    
    if (useCache) {
      const cached = this.getCachedAnalysis(cacheKey)
      if (Array.isArray(cached)) {
        console.log('使用缓存的AI分析结果')
        return cached as AIDefectSuggestion[]
      }
    }
    
    const suggestions = await this.suggestDefects(taskItem, context)
    
    if (useCache && suggestions.length > 0) {
      this.setCachedAnalysis(cacheKey, suggestions)
    }
    
    return suggestions
  }

  /**
   * 获取AI服务性能统计
   */
  async getAIPerformanceStats(): Promise<{
    cache_hit_rate: number
    memory_cache_size: number
    performance_stats: Record<string, unknown>
    service_status: string
  }> {
    try {
      if (this.useEnhancedAPI) {
        const response = await fetch(
          `${import.meta.env.VITE_API_BASE_URL}/api/enhanced-ai-assistance/performance-stats`,
          {
            headers: {
              'Authorization': `Bearer ${this.getAuthToken()}`
            }
          }
        )

        if (response.ok) {
          const data = await response.json()
          return data.success ? data.data : data
        }
      }

      // 降级到本地统计
      return {
        cache_hit_rate: 0,
        memory_cache_size: this.analysisCache.size,
        performance_stats: {
          total_requests: 0,
          cache_hits: 0,
          error_count: 0
        },
        service_status: 'local'
      }
    } catch (error) {
      console.error('获取性能统计失败:', error)
      return {
        cache_hit_rate: 0,
        memory_cache_size: 0,
        performance_stats: {},
        service_status: 'error'
      }
    }
  }

  /**
   * 清理AI分析缓存
   */
  async clearAICache(): Promise<boolean> {
    try {
      if (this.useEnhancedAPI) {
        const response = await fetch(
          `${import.meta.env.VITE_API_BASE_URL}/api/enhanced-ai-assistance/clear-cache`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${this.getAuthToken()}`
            }
          }
        )

        if (response.ok) {
          console.log('后端AI分析缓存已清理')
        }
      }

      // 清理本地缓存
      this.clearAnalysisCache()
      return true
    } catch (error) {
      console.error('清理AI缓存失败:', error)
      return false
    }
  }

  /**
   * 获取增强版AI服务状态
   */
  async getEnhancedAIServiceStatus(): Promise<{
    service: string
    status: string
    version: string
    cache_stats: Record<string, unknown>
  }> {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/enhanced-ai-assistance/service-status`
      )

      if (response.ok) {
        const data = await response.json()
        return data.success ? data.data : data
      }

      throw new Error(`服务状态检查失败: ${response.status}`)
    } catch (error) {
      console.error('获取增强版AI服务状态失败:', error)
      return {
        service: 'enhanced_ai_defect_detection',
        status: 'unavailable',
        version: 'unknown',
        cache_stats: {}
      }
    }
  }

  /**
   * 切换API版本
   */
  switchToEnhancedAPI(enabled: boolean = true): void {
    this.useEnhancedAPI = enabled
    console.log(`AI服务已切换到${enabled ? '增强版' : '原始版'}API`)
  }

  /**
   * 检查增强版API可用性
   */
  async checkEnhancedAPIAvailability(): Promise<boolean> {
    try {
      const status = await this.getEnhancedAIServiceStatus()
      return status.status === 'healthy'
    } catch {
      return false
    }
  }

  /**
   * 清理分析缓存（本地）
   */
  clearAnalysisCache(): void {
    this.analysisCache.clear()
    console.log('本地AI分析缓存已清理')
  }

  /**
   * 获取本地缓存统计
   */
  getLocalCacheStats(): {
    size: number
    keys: string[]
    oldest_entry: string | null
    newest_entry: string | null
  } {
    const keys = Array.from(this.analysisCache.keys())
    let oldestEntry: string | null = null
    let newestEntry: string | null = null
    let oldestTime = Infinity
    let newestTime = 0

    for (const [key, value] of this.analysisCache.entries()) {
      if (value.timestamp < oldestTime) {
        oldestTime = value.timestamp
        oldestEntry = key
      }
      if (value.timestamp > newestTime) {
        newestTime = value.timestamp
        newestEntry = key
      }
    }

    return {
      size: this.analysisCache.size,
      keys,
      oldest_entry: oldestEntry,
      newest_entry: newestEntry
    }
  }
}

// 导出单例实例
export const aiAssistanceService = new AIAssistanceServiceAdapter()
