import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import { getAccessToken } from '@/utils/auth-token'
import type {
  SemanticKpiCard,
  SemanticRuleItem,
  SemanticRuleRowActionModel,
  SemanticRuleRowStatusModel,
  SemanticRuleStats,
  SemanticRuleTestResult,
  SemanticRuleWorkspaceQueryState,
} from './types'
import { SEMANTIC_RULE_QUERY_KEYS, getDocTypeZh } from './types'

const BASE_URL = import.meta.env.DEV
  ? ''
  : window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : 'http://124.220.6.136:8001'

function buildAuthHeaders(includeJson: boolean = false): Record<string, string> {
  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (includeJson) headers['Content-Type'] = 'application/json'
  return headers
}

function pickResponseData(payload: unknown): Record<string, any> {
  if (!payload || typeof payload !== 'object') return {}
  const maybeData = (payload as Record<string, any>).data
  if (maybeData && typeof maybeData === 'object') return maybeData as Record<string, any>
  return payload as Record<string, any>
}

function parseCount(value: unknown): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export function normalizeSemanticRule(raw: Record<string, any>): SemanticRuleItem {
  return {
    rule_id: String(raw.rule_id || raw.id || ''),
    rule_code: raw.rule_code ? String(raw.rule_code) : undefined,
    name: String(raw.name || raw.rule_name || '未命名规则'),
    description: String(raw.description || raw.desc || ''),
    category: String(raw.category || '未分类'),
    complexity: String(raw.complexity || '中复杂度'),
    defect_level: String(raw.defect_level || '一般缺陷'),
    score_deduction: parseCount(raw.score_deduction),
    applicable_documents: Array.isArray(raw.applicable_documents)
      ? raw.applicable_documents.map((item: unknown) => String(item))
      : [],
    medical_domain: String(raw.medical_domain || '通用'),
    requires_rag: Boolean(raw.requires_rag),
    requires_cot: Boolean(raw.requires_cot),
  }
}

export function buildSemanticStatsFromRules(
  rules: SemanticRuleItem[],
  rawData?: Record<string, any>,
): SemanticRuleStats {
  const fallbackComplexity: Record<string, number> = {}
  const fallbackDefect: Record<string, number> = {}

  rules.forEach((rule) => {
    fallbackComplexity[rule.complexity] = (fallbackComplexity[rule.complexity] || 0) + 1
    fallbackDefect[rule.defect_level] = (fallbackDefect[rule.defect_level] || 0) + 1
  })

  const apiComplexity =
    rawData &&
    rawData.complexity_distribution &&
    typeof rawData.complexity_distribution === 'object'
      ? (rawData.complexity_distribution as Record<string, number>)
      : {}
  const apiDefect =
    rawData &&
    rawData.defect_level_distribution &&
    typeof rawData.defect_level_distribution === 'object'
      ? (rawData.defect_level_distribution as Record<string, number>)
      : {}

  return {
    total_rules: parseCount(rawData?.total_rules) || rules.length,
    rule_categories: Array.isArray(rawData?.rule_categories)
      ? rawData?.rule_categories.map((item: unknown) => String(item))
      : [...new Set(rules.map((item) => item.category))],
    complexity_distribution:
      Object.keys(apiComplexity).length > 0 ? apiComplexity : fallbackComplexity,
    defect_level_distribution: Object.keys(apiDefect).length > 0 ? apiDefect : fallbackDefect,
  }
}

export function filterSemanticRules(
  rules: SemanticRuleItem[],
  query: Pick<
    SemanticRuleWorkspaceQueryState,
    'keyword' | 'complexity' | 'defectLevel' | 'documentType'
  >,
): SemanticRuleItem[] {
  const keyword = query.keyword.trim().toLowerCase()

  return rules.filter((rule) => {
    if (query.complexity && rule.complexity !== query.complexity) return false
    if (query.defectLevel && rule.defect_level !== query.defectLevel) return false

    if (query.documentType) {
      const hasDocType = (rule.applicable_documents || []).some((docType) => {
        const zhDocType = getDocTypeZh(docType)
        return docType === query.documentType || zhDocType === query.documentType
      })
      if (!hasDocType) return false
    }

    if (!keyword) return true
    const matchByDocType = (rule.applicable_documents || []).some((docType) => {
      const zhDocType = getDocTypeZh(docType)
      return docType.toLowerCase().includes(keyword) || zhDocType.toLowerCase().includes(keyword)
    })

    return (
      rule.rule_id.toLowerCase().includes(keyword) ||
      (rule.rule_code || '').toLowerCase().includes(keyword) ||
      rule.name.toLowerCase().includes(keyword) ||
      rule.description.toLowerCase().includes(keyword) ||
      rule.category.toLowerCase().includes(keyword) ||
      matchByDocType
    )
  })
}

export function toSemanticRulePage<T>(items: T[], page: number, pageSize: number): T[] {
  const safePage = Number.isFinite(page) && page > 0 ? Math.floor(page) : 1
  const safePageSize = Number.isFinite(pageSize) && pageSize > 0 ? Math.floor(pageSize) : 20
  const start = (safePage - 1) * safePageSize
  return items.slice(start, start + safePageSize)
}

export function buildSemanticKpiCards(args: {
  stats: SemanticRuleStats
  criticalDefectCount: number
  riskDensity: string
  lastRefreshedLabel: string
}): SemanticKpiCard[] {
  return [
    {
      key: 'total',
      label: '总规则',
      value: String(args.stats.total_rules || 0),
      desc: '规则总量',
      tone: 'brand',
    },
    {
      key: 'critical',
      label: '严重缺陷',
      value: String(args.criticalDefectCount || 0),
      desc: '高风险规则',
      tone: 'danger',
    },
    {
      key: 'density',
      label: '风险密度',
      value: args.riskDensity || '0%',
      desc: '严重缺陷占比',
      tone: 'warning',
    },
    {
      key: 'sync',
      label: '最近同步',
      value: args.lastRefreshedLabel || '未同步',
      desc: '数据更新时间',
      tone: 'safe',
    },
  ]
}

export function buildSemanticRuleRowStatusModel(
  rule: SemanticRuleItem,
): SemanticRuleRowStatusModel {
  const defectLevel = String(rule.defect_level || '')
  let primaryTone: SemanticRuleRowStatusModel['primaryTone'] = 'neutral'
  if (defectLevel.includes('严重') || defectLevel === 'critical') primaryTone = 'danger'
  else if (defectLevel.includes('一般') || defectLevel === 'major') primaryTone = 'warning'
  else if (defectLevel.includes('轻微') || defectLevel === 'minor') primaryTone = 'safe'

  let secondaryTone: SemanticRuleRowStatusModel['secondaryTone'] = 'neutral'
  if (rule.complexity === '高复杂度') secondaryTone = 'danger'
  else if (rule.complexity === '中复杂度') secondaryTone = 'warning'
  else if (rule.complexity === '低复杂度') secondaryTone = 'neutral'

  return {
    primaryLabel: defectLevel || '未标记',
    primaryTone,
    secondaryLabel: rule.complexity || '复杂度未知',
    secondaryTone,
  }
}

export function buildSemanticRuleRowActionModel(): SemanticRuleRowActionModel {
  return {
    primaryLabel: '查看结果',
    secondaryLabel: '评估',
  }
}

function parseQueryStringValue(value: unknown): string {
  if (Array.isArray(value)) return value.length > 0 ? String(value[0]) : ''
  if (value === null || value === undefined) return ''
  return String(value)
}

function parsePositiveInt(value: unknown, fallback: number): number {
  const parsed = Number.parseInt(parseQueryStringValue(value), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export function parseSemanticWorkspaceQuery(query: LocationQuery): SemanticRuleWorkspaceQueryState {
  return {
    keyword: parseQueryStringValue(query.keyword),
    complexity: parseQueryStringValue(query.complexity),
    defectLevel: parseQueryStringValue(query.defectLevel),
    documentType: parseQueryStringValue(query.documentType),
    page: parsePositiveInt(query.page, 1),
    pageSize: parsePositiveInt(query.pageSize, 20),
  }
}

export function buildSemanticWorkspaceQuery(
  baseQuery: LocationQuery,
  state: SemanticRuleWorkspaceQueryState,
): LocationQueryRaw {
  const nextQuery: LocationQueryRaw = { ...baseQuery }

  SEMANTIC_RULE_QUERY_KEYS.forEach((key) => {
    delete nextQuery[key]
  })

  if (state.keyword.trim()) nextQuery.keyword = state.keyword.trim()
  if (state.complexity) nextQuery.complexity = state.complexity
  if (state.defectLevel) nextQuery.defectLevel = state.defectLevel
  if (state.documentType) nextQuery.documentType = state.documentType
  if (state.page > 1) nextQuery.page = String(state.page)
  if (state.pageSize !== 20) nextQuery.pageSize = String(state.pageSize)

  return nextQuery
}

export async function fetchSemanticRulesFromBackend(): Promise<{
  rules: SemanticRuleItem[]
  stats: SemanticRuleStats
}> {
  const response = await fetch(`${BASE_URL}/api/v1/qc/sichuan/rules?_ts=${Date.now()}`, {
    headers: buildAuthHeaders(),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || '加载规则库失败')
  }

  const payload = await response.json()
  const data = pickResponseData(payload)
  const rules = Array.isArray(data.rules)
    ? data.rules.map((item: Record<string, any>) => normalizeSemanticRule(item))
    : []

  return {
    rules,
    stats: buildSemanticStatsFromRules(rules, data),
  }
}

export async function fetchRulePrompt(ruleId: string): Promise<{
  prompt: string
  isDefaultPrompt: boolean
}> {
  const response = await fetch(
    `${BASE_URL}/api/v1/qc/sichuan/rules/${encodeURIComponent(ruleId)}/prompt`,
    {
      headers: buildAuthHeaders(),
    },
  )

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || '获取提示词失败')
  }

  const payload = await response.json()
  const data = pickResponseData(payload)
  return {
    prompt: String(data.prompt || ''),
    isDefaultPrompt: Boolean(data.is_default ?? true),
  }
}

export async function saveRulePrompt(ruleId: string, promptText: string): Promise<void> {
  const response = await fetch(
    `${BASE_URL}/api/v1/qc/sichuan/rules/${encodeURIComponent(ruleId)}/prompt`,
    {
      method: 'PUT',
      headers: buildAuthHeaders(true),
      body: JSON.stringify({
        custom_prompt: promptText.trim() ? promptText.trim() : null,
      }),
    },
  )

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || '保存提示词失败')
  }
}

export async function executeSemanticRuleTest(
  ruleId: string,
  medicalText: string,
): Promise<SemanticRuleTestResult> {
  const response = await fetch(`${BASE_URL}/api/v1/qc/sichuan/test-rule`, {
    method: 'POST',
    headers: buildAuthHeaders(true),
    body: JSON.stringify({
      rule_id: ruleId,
      medical_text: medicalText,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || '规则测试失败')
  }

  const payload = await response.json()
  const data = pickResponseData(payload)
  return {
    is_compliant: Boolean(data.is_compliant ?? true),
    confidence: parseCount(data.confidence),
    findings: String(data.findings || ''),
    evidence: String(data.evidence || ''),
    suggestion: String(data.suggestion || ''),
  }
}
