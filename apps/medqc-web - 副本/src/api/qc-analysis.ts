/**
 * 质控分析API接口
 * 提供RESTful服务供前端调用
 */
import { qcAnalysisEngine } from '../lib/qc/analysis-engine'
import type { QCAnalysisRequest, QCAnalysisResult } from '../types/ai-service'

export interface AnalysisAPIRequest {
  content: string
  recordId?: string
  options?: {
    includeCache?: boolean
    priority?: 'normal' | 'high'
    categories?: string[]
  }
}

export interface AnalysisAPIResponse {
  success: boolean
  data?: QCAnalysisResult
  error?: string
  message?: string
}

/**
 * 分析病历质控
 */
export async function analyzeRecord(request: AnalysisAPIRequest): Promise<AnalysisAPIResponse> {
  try {
    // 参数验证
    if (!request.content || request.content.trim().length === 0) {
      return {
        success: false,
        error: 'INVALID_INPUT',
        message: '病历内容不能为空',
      }
    }

    if (request.content.length > 50000) {
      return {
        success: false,
        error: 'CONTENT_TOO_LARGE',
        message: '病历内容过长，请确保内容小于50000字符',
      }
    }

    // 构建分析请求
    const analysisRequest: QCAnalysisRequest = {
      recordId: request.recordId || `record-${Date.now()}`,
      content: request.content,
      options: request.options || {},
    }

    // 执行分析
    const result = await qcAnalysisEngine.analyze(analysisRequest)

    return {
      success: true,
      data: result,
      message: '分析完成',
    }
  } catch (error) {
    console.error('API分析失败:', error)

    return {
      success: false,
      error: 'ANALYSIS_FAILED',
      message: error instanceof Error ? error.message : '分析过程中发生未知错误',
    }
  }
}

/**
 * 批量分析病历
 */
export async function batchAnalyzeRecords(requests: AnalysisAPIRequest[]): Promise<{
  success: boolean
  data?: QCAnalysisResult[]
  errors?: Array<{ index: number; error: string }>
  summary?: {
    total: number
    successful: number
    failed: number
    processingTime: number
  }
}> {
  const startTime = Date.now()
  const results: QCAnalysisResult[] = []
  const errors: Array<{ index: number; error: string }> = []

  try {
    // 参数验证
    if (!Array.isArray(requests) || requests.length === 0) {
      return {
        success: false,
        errors: [{ index: -1, error: '请求列表不能为空' }],
      }
    }

    if (requests.length > 10) {
      return {
        success: false,
        errors: [{ index: -1, error: '批量处理最多支持10个记录' }],
      }
    }

    // 逐个处理请求
    for (let i = 0; i < requests.length; i++) {
      try {
        const response = await analyzeRecord(requests[i])

        if (response.success && response.data) {
          results.push(response.data)
        } else {
          errors.push({
            index: i,
            error: response.message || '分析失败',
          })
        }
      } catch (error) {
        errors.push({
          index: i,
          error: error instanceof Error ? error.message : '处理失败',
        })
      }
    }

    const processingTime = Date.now() - startTime

    return {
      success: true,
      data: results,
      errors: errors.length > 0 ? errors : undefined,
      summary: {
        total: requests.length,
        successful: results.length,
        failed: errors.length,
        processingTime,
      },
    }
  } catch (error) {
    return {
      success: false,
      errors: [
        {
          index: -1,
          error: error instanceof Error ? error.message : '批量处理失败',
        },
      ],
    }
  }
}

/**
 * 获取分析历史
 */
export async function getAnalysisHistory(recordId: string): Promise<{
  success: boolean
  data?: unknown[]
  error?: string
}> {
  void recordId
  // 这里应该从数据库查询分析历史，暂时返回模拟数据
  return {
    success: true,
    data: [],
  }
}

/**
 * 获取系统健康状态
 */
export async function getSystemHealth(): Promise<{
  success: boolean
  data?: {
    aiService: { status: string; message: string }
    database: { status: string; message: string }
    overall: string
    timestamp: string
  }
  error?: string
}> {
  try {
    const health = await qcAnalysisEngine.healthCheck()

    return {
      success: true,
      data: {
        ...health,
        timestamp: new Date().toISOString(),
      },
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : '健康检查失败',
    }
  }
}

/**
 * 获取质控规则列表
 */
export async function getQCRules(category?: string): Promise<{
  success: boolean
  data?: unknown[]
  error?: string
}> {
  void category
  // 这里应该从数据库查询质控规则，暂时返回模拟数据
  return {
    success: true,
    data: [],
  }
}
