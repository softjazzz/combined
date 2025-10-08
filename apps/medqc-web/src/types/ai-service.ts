/**
 * AI服务相关类型定义
 */

// AI服务配置
export interface AIServiceConfig {
  apiKey: string
  baseURL: string
  model: string
  maxRetries: number
  timeout: number
}

// 质控分析请求
export interface QCAnalysisRequest {
  content: string
  recordId: string
  rules?: QCRule[]
  options?: {
    includeCache?: boolean
    priority?: 'normal' | 'high'
    categories?: string[]
  }
}

// 质控规则定义
export interface QCRule {
  id: string
  rule_code: string
  name: string
  description: string
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  prompt_template: string
  check_logic: Record<string, unknown>
  is_active: boolean
  version: string
}

// 单个规则分析结果
export interface RuleAnalysisResult {
  ruleId: string
  ruleCode: string
  ruleName: string
  hasViolation: boolean
  confidence: number
  evidence: string[]
  reasoning: string
  location?: string
  score?: number
  category: string
  severity: string
}

// 完整质控分析结果
export interface QCAnalysisResult {
  recordId: string
  overallScore: number
  grade: 'A' | 'B' | 'C'
  status: 'completed' | 'failed' | 'analyzing'
  ruleResults: RuleAnalysisResult[]
  categoryScores: {
    completeness: number
    consistency: number
    rationality: number
    timeliness: number
  }
  summary: {
    totalRules: number
    violatedRules: number
    criticalIssues: number
    majorIssues: number
    minorIssues: number
  }
  suggestions: string[]
  analysisTime: number // 分析耗时（毫秒）
  createdAt: string
}

// 分析缓存
export interface AnalysisCache {
  contentHash: string
  segmentType: string
  analysisResult: QCAnalysisResult
  ruleVersion: string
  confidenceScore: number
  createdAt: string
  expiresAt: string
  accessCount: number
}

// AI响应格式
export interface AIAnalysisResponse {
  hasViolation: boolean
  confidence: number
  evidence: string[]
  reasoning: string
  location?: string
  score?: number
}

// 批量分析请求
export interface BatchAnalysisRequest {
  records: Array<{
    id: string
    content: string
  }>
  rules?: QCRule[]
  options?: {
    parallel?: boolean
    maxConcurrency?: number
  }
}

// 批量分析结果
export interface BatchAnalysisResult {
  results: QCAnalysisResult[]
  summary: {
    total: number
    completed: number
    failed: number
    averageScore: number
    processingTime: number
  }
} 