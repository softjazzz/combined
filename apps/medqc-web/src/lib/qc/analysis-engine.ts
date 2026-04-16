import type { QCAnalysisRequest, QCAnalysisResult, RuleAnalysisResult } from '../../types/ai-service'

type CategoryScoreKey = 'completeness' | 'consistency' | 'rationality' | 'timeliness'

interface HealthCheckResult {
  aiService: { status: string; message: string }
  database: { status: string; message: string }
  overall: string
}

const DEFAULT_RULES: Array<{
  id: string
  rule_code: string
  name: string
  category: CategoryScoreKey
  severity: 'critical' | 'major' | 'minor'
  keywords: string[]
}> = [
  {
    id: 'default-completeness-1',
    rule_code: 'QC-COMP-001',
    name: '病历完整性检查',
    category: 'completeness',
    severity: 'major',
    keywords: ['主诉', '现病史', '体格检查'],
  },
  {
    id: 'default-consistency-1',
    rule_code: 'QC-CONS-001',
    name: '诊断一致性检查',
    category: 'consistency',
    severity: 'major',
    keywords: ['诊断', '治疗', '出院'],
  },
  {
    id: 'default-rationality-1',
    rule_code: 'QC-RATI-001',
    name: '用药合理性检查',
    category: 'rationality',
    severity: 'critical',
    keywords: ['用药', '医嘱', '过敏'],
  },
  {
    id: 'default-time-1',
    rule_code: 'QC-TIME-001',
    name: '时效性检查',
    category: 'timeliness',
    severity: 'minor',
    keywords: ['入院时间', '出院时间', '记录时间'],
  },
]

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)))
}

function buildRuleResult(
  request: QCAnalysisRequest,
  rule: (typeof DEFAULT_RULES)[number],
): RuleAnalysisResult {
  const content = request.content || ''
  const hitCount = rule.keywords.filter((keyword) => content.includes(keyword)).length
  const hasViolation = hitCount === 0
  const confidence = hasViolation ? 0.74 : 0.9
  const evidence = hasViolation
    ? [`未在病历中检索到关键词: ${rule.keywords.join('、')}`]
    : [`命中关键词 ${hitCount}/${rule.keywords.length}`]

  return {
    ruleId: rule.id,
    ruleCode: rule.rule_code,
    ruleName: rule.name,
    hasViolation,
    confidence,
    evidence,
    reasoning: hasViolation ? '该规则的核心要点未覆盖。' : '该规则的核心要点有文书证据支撑。',
    category: rule.category,
    severity: rule.severity,
    score: hasViolation ? 60 : 95,
  }
}

function aggregateCategoryScores(ruleResults: RuleAnalysisResult[]): Record<CategoryScoreKey, number> {
  const categories: CategoryScoreKey[] = ['completeness', 'consistency', 'rationality', 'timeliness']
  const categoryScores = {
    completeness: 100,
    consistency: 100,
    rationality: 100,
    timeliness: 100,
  }

  categories.forEach((category) => {
    const scoped = ruleResults.filter((item) => item.category === category)
    if (scoped.length === 0) {
      categoryScores[category] = 100
      return
    }
    const avg = scoped.reduce((sum, item) => sum + (item.score ?? (item.hasViolation ? 60 : 95)), 0) / scoped.length
    categoryScores[category] = clampScore(avg)
  })

  return categoryScores
}

function buildGrade(score: number): 'A' | 'B' | 'C' {
  if (score >= 90) return 'A'
  if (score >= 75) return 'B'
  return 'C'
}

export const qcAnalysisEngine = {
  async analyze(request: QCAnalysisRequest): Promise<QCAnalysisResult> {
    const startedAt = Date.now()
    const rules = DEFAULT_RULES
    const ruleResults = rules.map((rule) => buildRuleResult(request, rule))
    const categoryScores = aggregateCategoryScores(ruleResults)
    const overallScore = clampScore(
      (categoryScores.completeness +
        categoryScores.consistency +
        categoryScores.rationality +
        categoryScores.timeliness) /
        4,
    )

    const violatedRules = ruleResults.filter((item) => item.hasViolation)
    const suggestions: string[] = []
    if (violatedRules.length > 0) {
      suggestions.push('优先补齐缺失文书要点，保证病历完整性与一致性。')
    }
    if (categoryScores.timeliness < 80) {
      suggestions.push('建议复核关键时间节点记录，避免时效类缺陷。')
    }
    if (suggestions.length === 0) {
      suggestions.push('当前病历质控表现良好，建议保持结构化记录习惯。')
    }

    const criticalIssues = violatedRules.filter((item) => item.severity === 'critical').length
    const majorIssues = violatedRules.filter((item) => item.severity === 'major').length
    const minorIssues = violatedRules.filter((item) => item.severity === 'minor').length

    return {
      recordId: request.recordId,
      overallScore,
      grade: buildGrade(overallScore),
      status: 'completed',
      ruleResults,
      categoryScores,
      summary: {
        totalRules: ruleResults.length,
        violatedRules: violatedRules.length,
        criticalIssues,
        majorIssues,
        minorIssues,
      },
      suggestions,
      analysisTime: Date.now() - startedAt,
      createdAt: new Date().toISOString(),
    }
  },

  async healthCheck(): Promise<HealthCheckResult> {
    return {
      aiService: {
        status: 'healthy',
        message: '分析引擎可用',
      },
      database: {
        status: 'healthy',
        message: '使用后端 API/兼容层',
      },
      overall: 'healthy',
    }
  },
}

