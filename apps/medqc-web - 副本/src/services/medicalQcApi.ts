/**
 * 统一的医疗质控系统API服务
 *
 * 架构说明：
 * - 前端：Vue3 + TypeScript
 * - 后端：Python FastAPI (统一后端)
 * - 核心技术：三层漏斗Token优化引擎
 * - AI服务：阿里云通义千问 (通过Python后端调用)
 *
 * 所有AI质控分析都通过Python后端处理，确保：
 * ✅ 技术栈统一
 * ✅ 性能优化 (三层漏斗)
 * ✅ 维护简单
 * ✅ 扩展性强
 */

import { resolveApiBaseUrl } from '@/utils/api-helpers'

// API配置
const API_BASE_URL = resolveApiBaseUrl()
const API_VERSION = import.meta.env.VITE_API_VERSION || 'v1'

// 接口类型定义
export interface QCAnalysisRequest {
  record_id: string
  record_text: string
  rule_ids?: string[]
  max_tokens?: number
  enable_optimization?: boolean
}

export interface RuleResult {
  rule_id: string
  rule_name: string
  result: '符合' | '不符合' | '待确认'
  confidence: number
  defect_level: '否决项' | 'A级缺陷' | 'B级缺陷' | 'C级缺陷' | null
  reasoning: string
  tokens_used: number
  processing_time: number
}

export interface OptimizationStats {
  original_tokens: number
  optimized_tokens: number
  compression_ratio: number
  token_savings: number
  cost_savings: number
  optimization_time: number
}

export interface QCAnalysisResponse {
  record_id: string
  rule_results: RuleResult[]
  optimization_stats: OptimizationStats
  total_processing_time: number
  total_tokens_used: number
  total_cost_estimate: number
  success: boolean
  error_message?: string
}

export interface SystemStatus {
  service: string
  version: string
  description: string
  features: string[]
  endpoints: Record<string, string>
  status: string
}

// API客户端类
export class MedicalQcApiClient {
  private baseUrl: string
  private apiVersion: string

  constructor() {
    this.baseUrl = API_BASE_URL
    this.apiVersion = API_VERSION
  }

  // 构建API URL
  private buildUrl(endpoint: string): string {
    return `${this.baseUrl}/api/${this.apiVersion}${endpoint}`
  }

  // 通用请求方法
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = endpoint.startsWith('http') ? endpoint : this.buildUrl(endpoint)

    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    }

    const response = await fetch(url, { ...defaultOptions, ...options })

    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status} ${response.statusText}`)
    }

    return response.json()
  }

  // 获取系统状态
  async getSystemStatus(): Promise<SystemStatus> {
    return this.request<SystemStatus>('/')
  }

  // 健康检查
  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.request('/medical-qc/health')
  }

  // 医疗记录质控分析（核心接口）
  async analyzeRecord(request: QCAnalysisRequest): Promise<QCAnalysisResponse> {
    return this.request<QCAnalysisResponse>('/medical-qc/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // 获取三层漏斗优化演示
  async getOptimizationDemo(): Promise<unknown> {
    return this.request('/medical-qc/demo')
  }

  // 批量分析（如果后端支持）
  async batchAnalyze(requests: QCAnalysisRequest[]): Promise<QCAnalysisResponse[]> {
    const results: QCAnalysisResponse[] = []

    // 并发处理，但限制并发数量
    const concurrency = 3
    for (let i = 0; i < requests.length; i += concurrency) {
      const batch = requests.slice(i, i + concurrency)
      const batchPromises = batch.map((request) => this.analyzeRecord(request))
      const batchResults = await Promise.all(batchPromises)
      results.push(...batchResults)
    }

    return results
  }
}

// 创建API客户端实例
export const medicalQcApi = new MedicalQcApiClient()

// 质控规则常量
export const QC_RULES = {
  SEMANTIC: {
    'S3.5.1': '主诉与主要诊断一致性',
    'S4.13.2b': '病史逻辑合理性',
    'S5.10.1': '治疗方案适宜性',
  },
  LOGICAL: {
    'L1.1': '时间完整性检查',
    'L2.1': '必填项检查',
    'L3.1': '格式规范检查',
  },
}

// 缺陷等级配置
export const DEFECT_LEVELS = {
  否决项: { color: 'red', priority: 1 },
  A级缺陷: { color: 'orange', priority: 2 },
  B级缺陷: { color: 'yellow', priority: 3 },
  C级缺陷: { color: 'blue', priority: 4 },
}

// 工具函数
export const formatCost = (cost: number): string => {
  return `$${cost.toFixed(3)}`
}

export const formatTokens = (tokens: number): string => {
  return tokens.toLocaleString()
}

export const formatCompressionRatio = (ratio: number): string => {
  return `${(ratio * 100).toFixed(1)}%`
}
