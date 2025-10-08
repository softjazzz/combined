/**
 * KAG质控服务
 * 替换原有的传统质控引擎，全面使用KAG进行质控分析
 */

import { supabase } from '@/lib/supabase'
import type { Database } from '@/types/supabase'

// KAG API配置
const KAG_API_CONFIG = {
  baseUrl: 'http://localhost:8001',  // KAG API Gateway地址
  timeout: 30000,
  retryAttempts: 3
}

// 类型定义
export interface KAGQCRequest {
  recordId: string
  content: string
  metadata?: Record<string, unknown>
  analysisMode?: 'comprehensive' | 'focused' | 'quick'
  selectedRules?: string[]
}

export interface KAGQCResponse {
  analysisId: string
  recordId: string
  status: string
  summary: {
    totalScore: number
    grade: '甲级' | '乙级' | '丙级'
    defectsCount: number
    rulesExecuted: number
    analysisTime: string
    processingDuration: number
  }
  defects: Array<{
    defectId: string
    ruleId: string
    ruleName: string
    defectType: string
    description: string
    evidenceText: string
    confidence: number
    deductionScore: number
    severity: 'critical' | 'major' | 'minor'
    location: string
    suggestion: string
    detectionTime: string
  }>
  recommendations: string[]
  processingTime: number
}

export interface KAGBatchRequest {
  records: Array<{
    recordId: string
    content: string
    metadata?: Record<string, unknown>
  }>
  batchId?: string
  analysisMode?: 'comprehensive' | 'focused' | 'quick'
}

export interface KAGBatchResponse {
  batchId: string
  status: string
  totalRecords: number
  completedRecords: number
  failedRecords: number
  results: KAGQCResponse[]
}

export interface KAGRule {
  ruleId: string
  ruleCode: string
  name: string
  description: string
  category: string
  ruleType: 'symbolic' | 'semantic' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  maxDeduction: number
  weight: number
  isActive: boolean
}

export class KAGQCService {
  private baseUrl: string
  private timeout: number
  private retryAttempts: number

  constructor() {
    this.baseUrl = KAG_API_CONFIG.baseUrl
    this.timeout = KAG_API_CONFIG.timeout
    this.retryAttempts = KAG_API_CONFIG.retryAttempts
  }

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.request('GET', '/health')
      return response.status === 'healthy'
    } catch (error) {
      console.error('KAG服务健康检查失败:', error)
      return false
    }
  }

  /**
   * 单个病历质控分析
   */
  async analyzeMedicalRecord(request: KAGQCRequest): Promise<KAGQCResponse> {
    try {
      console.log('开始KAG质控分析:', request.recordId)
      
      const response = await this.request('POST', '/api/qc/analyze', {
        record_id: request.recordId,
        content: request.content,
        metadata: request.metadata,
        analysis_mode: request.analysisMode || 'comprehensive',
        selected_rules: request.selectedRules
      })

      console.log('KAG质控分析完成:', response.analysisId)
      
      // 保存结果到Supabase
      await this.saveQCResultToSupabase(response)
      
      return response
    } catch (error) {
      console.error('KAG质控分析失败:', error)
      throw new Error(`质控分析失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  /**
   * 批量病历质控分析
   */
  async batchAnalyzeMedicalRecords(request: KAGBatchRequest): Promise<string> {
    try {
      console.log('开始批量KAG质控分析:', request.records.length, '份病历')
      
      const response = await this.request('POST', '/api/qc/batch-analyze', {
        records: request.records.map(r => ({
          record_id: r.recordId,
          content: r.content,
          metadata: r.metadata
        })),
        batch_id: request.batchId,
        analysis_mode: request.analysisMode || 'comprehensive'
      })

      console.log('批量分析任务已提交:', response.batchId)
      return response.batchId
    } catch (error) {
      console.error('批量质控分析失败:', error)
      throw new Error(`批量分析失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  /**
   * 获取批量处理状态
   */
  async getBatchStatus(batchId: string): Promise<{
    batchId: string
    status: string
    totalRecords: number
    completedRecords: number
    failedRecords: number
    startTime: string
    endTime?: string
  }> {
    try {
      return await this.request('GET', `/api/qc/batch-status/${batchId}`)
    } catch (error) {
      console.error('获取批量状态失败:', error)
      throw error
    }
  }

  /**
   * 获取批量处理结果
   */
  async getBatchResults(batchId: string): Promise<KAGBatchResponse> {
    try {
      const response = await this.request('GET', `/api/qc/batch-results/${batchId}`)
      
      // 保存批量结果到Supabase
      for (const result of response.results) {
        if (result.status === 'completed') {
          await this.saveQCResultToSupabase(result)
        }
      }
      
      return response
    } catch (error) {
      console.error('获取批量结果失败:', error)
      throw error
    }
  }

  /**
   * 获取质控规则列表
   */
  async getQCRules(): Promise<KAGRule[]> {
    try {
      const response = await this.request('GET', '/api/qc/rules')
      return response.rules
    } catch (error) {
      console.error('获取质控规则失败:', error)
      throw error
    }
  }

  /**
   * 获取质控统计信息
   */
  async getQCStatistics(): Promise<{
    totalAnalyses: number
    todayAnalyses: number
    averageScore: number
    gradeDistribution: Record<string, number>
    commonDefects: Array<{ defectType: string; count: number }>
  }> {
    try {
      return await this.request('GET', '/api/qc/statistics')
    } catch (error) {
      console.error('获取质控统计失败:', error)
      throw error
    }
  }

  /**
   * 保存质控结果到Supabase
   */
  private async saveQCResultToSupabase(result: KAGQCResponse): Promise<void> {
    try {
      // 保存主要质控结果
      const { data: qcResult, error: qcError } = await supabase
        .from('qc_results')
        .insert({
          record_id: result.recordId,
          score: result.summary.totalScore,
          grade: result.summary.grade,
          issues: result.defects.map(d => ({
            code: d.ruleId,
            description: d.description,
            severity: d.severity,
            deduction: d.deductionScore,
            location: d.location,
            suggestion: d.suggestion,
            source: 'kag'
          })),
          suggestions: result.recommendations.join('; '),
          analysis_time: new Date(result.summary.analysisTime),
          processing_duration: result.processingTime,
          analysis_method: 'kag',
          kag_analysis_id: result.analysisId
        })
        .select()
        .single()

      if (qcError) {
        console.error('保存质控结果失败:', qcError)
        return
      }

      // 保存详细的规则执行结果
      const ruleExecutions = result.defects.map(defect => ({
        record_id: result.recordId,
        rule_id: defect.ruleId,
        rule_name: defect.ruleName,
        passed: false,
        score: result.summary.totalScore,
        max_score: 100,
        deduction: defect.deductionScore,
        confidence: defect.confidence,
        execution_duration: Math.round(result.processingTime * 1000), // 转换为毫秒
        defect_details: {
          defectId: defect.defectId,
          defectType: defect.defectType,
          evidenceText: defect.evidenceText,
          location: defect.location,
          suggestion: defect.suggestion,
          detectionTime: defect.detectionTime
        }
      }))

      if (ruleExecutions.length > 0) {
        const { error: executionError } = await supabase
          .from('qc_rule_executions')
          .insert(ruleExecutions)

        if (executionError) {
          console.error('保存规则执行结果失败:', executionError)
        }
      }

      console.log('质控结果已保存到Supabase:', result.analysisId)
    } catch (error) {
      console.error('保存质控结果到Supabase失败:', error)
    }
  }

  /**
   * 通用HTTP请求方法
   */
  private async request(method: string, path: string, data?: unknown): Promise<unknown> {
    const url = `${this.baseUrl}${path}`
    
    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        const options: RequestInit = {
          method,
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          signal: AbortSignal.timeout(this.timeout)
        }

        if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
          options.body = JSON.stringify(data)
        }

        const response = await fetch(url, options)

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`HTTP ${response.status}: ${errorText}`)
        }

        const responseData = await response.json()
        return responseData
      } catch (error) {
        console.error(`请求失败 (尝试 ${attempt}/${this.retryAttempts}):`, error)
        
        if (attempt === this.retryAttempts) {
          throw error
        }
        
        // 等待后重试
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt))
      }
    }
  }

  /**
   * 将KAG结果转换为兼容原有系统的格式
   */
  convertToLegacyFormat(kagResult: KAGQCResponse): Record<string, unknown> {
    return {
      recordId: kagResult.recordId,
      summary: {
        totalScore: kagResult.summary.totalScore,
        grade: kagResult.summary.grade,
        overallAssessment: `基于KAG框架的智能质控分析，发现${kagResult.summary.defectsCount}个问题`,
        aiAnalysisScore: kagResult.summary.totalScore,
        combinedScore: kagResult.summary.totalScore
      },
      itemScores: this.generateItemScores(kagResult),
      issues: kagResult.defects.map(defect => ({
        code: defect.ruleId,
        description: defect.description,
        severity: defect.severity as any,
        itemId: defect.ruleId,
        deduction: defect.deductionScore,
        location: defect.location,
        suggestion: defect.suggestion,
        source: 'kag' as const
      })),
      strengths: this.extractStrengths(kagResult),
      recommendations: kagResult.recommendations,
      analysisTime: kagResult.summary.analysisTime,
      processingStats: {
        aiAnalysisTime: kagResult.processingTime,
        totalProcessingTime: kagResult.processingTime
      }
    }
  }

  /**
   * 生成项目评分（兼容原有格式）
   */
  private generateItemScores(kagResult: KAGQCResponse): unknown[] {
    const categories = {
      'completeness': '完整性',
      'consistency': '一致性', 
      'rationality': '合理性',
      'timeliness': '时效性'
    }

    const itemScores: unknown[] = []
    
    for (const [categoryKey, categoryName] of Object.entries(categories)) {
      const categoryDefects = kagResult.defects.filter(d => 
        d.ruleId.toLowerCase().includes(categoryKey)
      )
      
      const totalDeduction = categoryDefects.reduce((sum, d) => sum + d.deductionScore, 0)
      const baseScore = 25 // 每个维度基础分25分
      const actualScore = Math.max(0, baseScore - totalDeduction)
      
      itemScores.push({
        itemId: categoryKey,
        itemName: categoryName,
        totalScore: baseScore,
        actualScore,
        deduction: totalDeduction,
        assessment: actualScore >= 20 ? '良好' : actualScore >= 15 ? '一般' : '需改进'
      })
    }

    return itemScores
  }

  /**
   * 提取优势点（兼容原有格式）
   */
  private extractStrengths(kagResult: KAGQCResponse): string[] {
    const strengths: string[] = []
    
    if (kagResult.summary.totalScore >= 90) {
      strengths.push('整体质量优秀，达到甲级标准')
    }
    
    if (kagResult.summary.defectsCount === 0) {
      strengths.push('未发现质控缺陷，病历书写规范')
    } else if (kagResult.summary.defectsCount <= 2) {
      strengths.push('质控缺陷较少，整体规范性良好')
    }

    // 根据缺陷类型分析优势
    const severityCount = kagResult.defects.reduce((acc, d) => {
      acc[d.severity] = (acc[d.severity] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    if (!severityCount.critical) {
      strengths.push('无严重质控问题')
    }
    
    if (!severityCount.major) {
      strengths.push('无重要质控问题')
    }

    return strengths.length > 0 ? strengths : ['基于KAG框架进行了全面的质控分析']
  }
}

// 导出单例实例
export const kagQCService = new KAGQCService()
