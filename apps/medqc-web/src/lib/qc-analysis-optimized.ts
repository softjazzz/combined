import { qcAnalysisEngine } from './qc/analysis-engine'
import type { QCAnalysisRequest, QCAnalysisResult, RuleAnalysisResult } from '../types/ai-service'

export type OptimizedQCAnalysisMode = 'comprehensive' | 'focused' | 'quick'
export type OptimizedQCAnalysisPriority = 'high' | 'normal' | 'low'

export interface OptimizedQCRequest {
  recordId: string
  content: string
  analysisMode: OptimizedQCAnalysisMode
  enableRulesEngine: boolean
  enableCache: boolean
  priority: OptimizedQCAnalysisPriority
  selectedRuleCategories?: string[]
}

export interface OptimizedQCIssue {
  code: string
  description: string
  severity: 'critical' | 'major' | 'minor'
  deduction: number
  location?: string
  suggestion: string
  source: 'optimized'
  ruleId: string
  ruleName: string
  category: string
  confidence: number
}

export interface OptimizedQCResult {
  recordId: string
  overallScore: number
  grade: 'A' | 'B' | 'C'
  status: 'completed' | 'failed' | 'analyzing'
  completenessScore: number
  consistencyScore: number
  rationalityScore: number
  timelinessScore: number
  issues: OptimizedQCIssue[]
  suggestions: string[]
  analysisTime: number
  createdAt: string
  analysisMode: OptimizedQCAnalysisMode
  priority: OptimizedQCAnalysisPriority
  processingStats: {
    cacheHit: boolean
    rulesExecuted: number
    analyzedCategories: string[]
    analysisMode: OptimizedQCAnalysisMode
    priority: OptimizedQCAnalysisPriority
    cacheKey: string
  }
  rulesEngineResults: {
    ruleResults: RuleAnalysisResult[]
    categoryScores: QCAnalysisResult['categoryScores']
    summary: QCAnalysisResult['summary']
  }
  rawResponse: Record<string, unknown>
}

export interface OptimizedPerformanceStats {
  optimizer: {
    totalRequests: number
    cacheHits: number
    cacheMisses: number
    cacheHitRate: number
    averageResponseTime: number
    cacheSize: number
    lastUpdated: string | null
  }
}

interface CacheEntry {
  value: OptimizedQCResult
  expiresAt: number
}

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)))
}

function buildGrade(score: number): 'A' | 'B' | 'C' {
  if (score >= 90) return 'A'
  if (score >= 75) return 'B'
  return 'C'
}

function toRiskLevel(score: number): 'low' | 'medium' | 'high' | 'critical' {
  if (score >= 90) return 'low'
  if (score >= 75) return 'medium'
  if (score >= 60) return 'high'
  return 'critical'
}

function hashString(source: string): string {
  let hash = 2166136261
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16)
}

function buildCacheKey(request: OptimizedQCRequest): string {
  const categories = request.selectedRuleCategories?.slice().sort().join(',') ?? ''
  return [
    request.recordId,
    request.analysisMode,
    request.priority,
    request.enableRulesEngine ? 'rules:on' : 'rules:off',
    request.enableCache ? 'cache:on' : 'cache:off',
    categories,
    hashString(request.content),
  ].join('|')
}

function normalizeCategories(categories?: string[]): string[] {
  const normalized = (categories ?? [])
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
  return Array.from(new Set(normalized))
}

function filterRuleResults(
  ruleResults: RuleAnalysisResult[],
  selectedCategories: string[],
): RuleAnalysisResult[] {
  if (selectedCategories.length === 0) {
    return ruleResults
  }
  return ruleResults.filter((item) => selectedCategories.includes(item.category))
}

function aggregateCategoryScores(ruleResults: RuleAnalysisResult[]): QCAnalysisResult['categoryScores'] {
  const categories: Array<keyof QCAnalysisResult['categoryScores']> = [
    'completeness',
    'consistency',
    'rationality',
    'timeliness',
  ]
  return categories.reduce((accumulator, category) => {
    const scoped = ruleResults.filter((item) => item.category === category)
    if (scoped.length === 0) {
      accumulator[category] = 100
      return accumulator
    }

    const average =
      scoped.reduce((sum, item) => sum + (item.score ?? (item.hasViolation ? 60 : 95)), 0) / scoped.length
    accumulator[category] = clampScore(average)
    return accumulator
  }, {
    completeness: 100,
    consistency: 100,
    rationality: 100,
    timeliness: 100,
  })
}

function buildIssues(ruleResults: RuleAnalysisResult[]): OptimizedQCIssue[] {
  return ruleResults
    .filter((item) => item.hasViolation)
    .map((item) => ({
      code: item.ruleCode,
      description: item.reasoning,
      severity:
        item.severity === 'critical'
          ? 'critical'
          : item.severity === 'major'
            ? 'major'
            : 'minor',
      deduction: Math.max(0, 100 - (item.score ?? 60)),
      location: item.location,
      suggestion: item.evidence[0] || item.reasoning,
      source: 'optimized' as const,
      ruleId: item.ruleId,
      ruleName: item.ruleName,
      category: item.category,
      confidence: item.confidence,
    }))
}

class OptimizedQCAnalysisService {
  private readonly cache = new Map<string, CacheEntry>()

  private totalRequests = 0

  private cacheHits = 0

  private cacheMisses = 0

  private totalResponseTime = 0

  private lastUpdated: string | null = null

  async analyzeRecord(request: OptimizedQCRequest): Promise<OptimizedQCResult> {
    const cacheKey = buildCacheKey(request)
    const startedAt = Date.now()
    this.totalRequests += 1

    if (request.enableCache) {
      const cached = this.cache.get(cacheKey)
      if (cached && cached.expiresAt > Date.now()) {
        this.cacheHits += 1
        this.totalResponseTime += Date.now() - startedAt
        this.lastUpdated = new Date().toISOString()
        return {
          ...cached.value,
          analysisTime: Date.now() - startedAt,
          processingStats: {
            ...cached.value.processingStats,
            cacheHit: true,
            cacheKey,
          },
        }
      }
      this.cacheMisses += 1
    }

    const qcRequest: QCAnalysisRequest = {
      recordId: request.recordId,
      content: request.content,
      options: {
        priority: request.priority === 'low' ? 'normal' : request.priority,
        categories: normalizeCategories(request.selectedRuleCategories),
        includeCache: request.enableCache,
      },
    }

    const baseResult = await qcAnalysisEngine.analyze(qcRequest)
    const selectedCategories = normalizeCategories(request.selectedRuleCategories)
    const ruleResults = filterRuleResults(baseResult.ruleResults, selectedCategories)
    const categoryScores = aggregateCategoryScores(ruleResults)
    const overallScore = clampScore(
      (categoryScores.completeness + categoryScores.consistency + categoryScores.rationality + categoryScores.timeliness) /
        4,
    )
    const violatedRules = ruleResults.filter((item) => item.hasViolation)
    const issues = buildIssues(ruleResults)
    const suggestions = baseResult.suggestions.length > 0
      ? [...baseResult.suggestions]
      : ['当前病历质控表现稳定，建议继续保持结构化记录习惯。']

    const result: OptimizedQCResult = {
      recordId: request.recordId,
      overallScore,
      grade: buildGrade(overallScore),
      status: 'completed',
      completenessScore: categoryScores.completeness,
      consistencyScore: categoryScores.consistency,
      rationalityScore: categoryScores.rationality,
      timelinessScore: categoryScores.timeliness,
      issues,
      suggestions: violatedRules.length > 0 ? suggestions : ['当前病历无明显缺陷，建议保持现有执行标准。'],
      analysisTime: Date.now() - startedAt,
      createdAt: new Date().toISOString(),
      analysisMode: request.analysisMode,
      priority: request.priority,
      processingStats: {
        cacheHit: false,
        rulesExecuted: ruleResults.length,
        analyzedCategories: selectedCategories.length > 0 ? selectedCategories : ['all'],
        analysisMode: request.analysisMode,
        priority: request.priority,
        cacheKey,
      },
      rulesEngineResults: {
        ruleResults,
        categoryScores,
        summary: {
          totalRules: ruleResults.length,
          violatedRules: violatedRules.length,
          criticalIssues: violatedRules.filter((item) => item.severity === 'critical').length,
          majorIssues: violatedRules.filter((item) => item.severity === 'major').length,
          minorIssues: violatedRules.filter((item) => item.severity === 'minor').length,
        },
      },
      rawResponse: {
        baseResult,
        riskLevel: toRiskLevel(overallScore),
      },
    }

    this.totalResponseTime += result.analysisTime
    this.lastUpdated = result.createdAt

    if (request.enableCache) {
      this.cache.set(cacheKey, {
        value: result,
        expiresAt: Date.now() + 30_000,
      })
    }

    return result
  }

  async batchAnalyze(requests: OptimizedQCRequest[]): Promise<{
    results: Array<OptimizedQCResult | Error>
    summary: { total: number; successful: number; failed: number; averageTime: number }
  }> {
    const results: Array<OptimizedQCResult | Error> = []
    let successful = 0
    let failed = 0
    let totalAnalysisTime = 0

    for (const request of requests) {
      try {
        const result = await this.analyzeRecord(request)
        results.push(result)
        successful += 1
        totalAnalysisTime += result.analysisTime
      } catch (error) {
        failed += 1
        results.push(error instanceof Error ? error : new Error('质控分析失败'))
      }
    }

    return {
      results,
      summary: {
        total: requests.length,
        successful,
        failed,
        averageTime: successful > 0 ? Math.round(totalAnalysisTime / successful) : 0,
      },
    }
  }

  getPerformanceStats(): OptimizedPerformanceStats {
    return {
      optimizer: {
        totalRequests: this.totalRequests,
        cacheHits: this.cacheHits,
        cacheMisses: this.cacheMisses,
        cacheHitRate: this.totalRequests > 0 ? this.cacheHits / this.totalRequests : 0,
        averageResponseTime: this.totalRequests > 0 ? this.totalResponseTime / this.totalRequests : 0,
        cacheSize: this.cache.size,
        lastUpdated: this.lastUpdated,
      },
    }
  }

  clearCache(): void {
    this.cache.clear()
    this.totalRequests = 0
    this.cacheHits = 0
    this.cacheMisses = 0
    this.totalResponseTime = 0
    this.lastUpdated = null
  }
}

export const optimizedQCAnalysisService = new OptimizedQCAnalysisService()
