import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import { ApiService } from '@/services/apiService'
import type {
  SemanticKpiCard,
  SemanticRuleItem,
  SemanticRuleRowActionModel,
  SemanticRuleRowStatusModel,
  SemanticRuleStats,
  SemanticRuleTestResult,
  SichuanRuleSetOption,
  SemanticRuleWorkspaceQueryState,
} from './types'
import { SEMANTIC_RULE_QUERY_KEYS, getDocTypeZh } from './types'

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

function pickCanonicalRuleId(raw: Record<string, any>): string {
  const candidates = [raw.rule_id, raw.rule_code, raw.original_id, raw.id]
    .map((item) => String(item || '').trim())
    .filter(Boolean)
  const canonical = candidates.find((value) => /^(SC|LX|LXE)-/i.test(value))
  return canonical || candidates[0] || ''
}

function readErrorMessageFromRaw(raw: string, fallback: string): string {
  if (!raw) return fallback
  try {
    const parsed = JSON.parse(raw) as Record<string, any>
    return (
      String(parsed?.detail || '') ||
      String(parsed?.message || '') ||
      String(parsed?.error || '') ||
      String(parsed?.data?.message || '') ||
      raw
    )
  } catch {
    return raw
  }
}

function parseRequestError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object') {
    const maybeResponse = (error as any).response
    if (maybeResponse && typeof maybeResponse === 'object') {
      const payload = maybeResponse.data
      if (typeof payload === 'string') {
        return readErrorMessageFromRaw(payload, fallback)
      }
      if (payload && typeof payload === 'object') {
        return (
          String(payload.detail || '') ||
          String(payload.message || '') ||
          String(payload.error || '') ||
          String(payload.data?.message || '') ||
          fallback
        )
      }
    }
    const maybeMessage = String((error as any).message || '').trim()
    if (maybeMessage) return maybeMessage
  }
  return fallback
}

type SemanticRuleTestErrorMeta = {
  statusCode?: number
  traceId?: string
  detail?: string
  errorCategory?: string
}

export class SemanticRuleTestError extends Error {
  statusCode?: number
  traceId?: string
  detail?: string
  errorCategory?: string

  constructor(message: string, meta?: SemanticRuleTestErrorMeta) {
    super(message)
    this.name = 'SemanticRuleTestError'
    this.statusCode = meta?.statusCode
    this.traceId = meta?.traceId
    this.detail = meta?.detail
    this.errorCategory = meta?.errorCategory
  }
}

function toErrorCategory(statusCode?: number): string {
  if (statusCode === 401) return 'unauthorized'
  if (statusCode === 403) return 'permission_denied'
  if (statusCode === 404) return 'not_found'
  if (statusCode === 422) return 'validation_error'
  if (typeof statusCode === 'number' && statusCode >= 500) return 'server_error'
  return 'unknown'
}

function parseSemanticRuleTestError(
  error: unknown,
  fallback: string,
): {
  message: string
  statusCode?: number
  traceId?: string
  detail?: string
  errorCategory: string
} {
  const messageText = parseRequestError(error, fallback)
  let statusCode: number | undefined
  let traceId = ''
  let detail = ''

  if (error && typeof error === 'object') {
    const maybeResponse = (error as any).response
    if (maybeResponse && typeof maybeResponse === 'object') {
      const parsedStatus = Number(maybeResponse.status)
      if (Number.isFinite(parsedStatus)) {
        statusCode = parsedStatus
      }

      const payload = maybeResponse.data
      if (payload && typeof payload === 'object') {
        traceId = String(
          payload.trace_id || payload.traceId || payload?.data?.trace_id || '',
        ).trim()
        detail = String(
          payload.detail || payload.message || payload.error || payload?.data?.message || '',
        ).trim()
      } else if (typeof payload === 'string') {
        try {
          const parsed = JSON.parse(payload) as Record<string, any>
          traceId = String(parsed.trace_id || parsed.traceId || parsed?.data?.trace_id || '').trim()
          detail = String(
            parsed.detail || parsed.message || parsed.error || parsed?.data?.message || '',
          ).trim()
        } catch {
          detail = payload.trim()
        }
      }
    }
  }

  return {
    message: messageText,
    statusCode,
    traceId: traceId || undefined,
    detail: detail || undefined,
    errorCategory: toErrorCategory(statusCode),
  }
}

export function normalizeSemanticRule(raw: Record<string, any>): SemanticRuleItem {
  const canonicalRuleId = pickCanonicalRuleId(raw)
  return {
    rule_id: canonicalRuleId,
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
    launch_tier: String(raw.launch_tier || 'UNKNOWN'),
    launch_tier_label: String(raw.launch_tier_label || ''),
  }
}

export async function fetchSichuanRuleSetsFromBackend(): Promise<SichuanRuleSetOption[]> {
  const response = await ApiService.getRaw('/api/v1/qc/sichuan/workspace/rule-sets', {
    _ts: Date.now(),
  })
  const payload = pickResponseData(response)
  const items = Array.isArray(payload.items) ? payload.items : []
  return items.map((item) => ({
    rule_set_key: String(item.rule_set_key || ''),
    rule_set_name: String(item.rule_set_name || item.rule_set_key || ''),
    rule_set_version: String(item.rule_set_version || 'v1'),
    scope: String(item.scope || 'unknown'),
    rule_ids: Array.isArray(item.rule_ids)
      ? item.rule_ids.map((ruleId: unknown) => String(ruleId))
      : [],
    rule_count: parseCount(item.rule_count ?? item.rule_ids?.length),
    execution_strategy: item.execution_strategy ? String(item.execution_strategy) : undefined,
    quality_profile: item.quality_profile ? String(item.quality_profile) : undefined,
    bucket_strategy: item.bucket_strategy ? String(item.bucket_strategy) : undefined,
    enable_selective_refine:
      typeof item.enable_selective_refine === 'boolean' ? item.enable_selective_refine : undefined,
    refine_confidence_threshold:
      item.refine_confidence_threshold === undefined
        ? undefined
        : Number(item.refine_confidence_threshold),
    batch_output_mode: item.batch_output_mode ? String(item.batch_output_mode) : undefined,
    max_refine_candidates:
      item.max_refine_candidates === undefined ? undefined : Number(item.max_refine_candidates),
    description: item.description ? String(item.description) : undefined,
  }))
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
  try {
    const response = await ApiService.getRaw('/api/v1/qc/sichuan/rules', {
      _ts: Date.now(),
    })
    const data = pickResponseData(response.data)
    const rules = Array.isArray(data.rules)
      ? data.rules.map((item: Record<string, any>) => normalizeSemanticRule(item))
      : []

    return {
      rules,
      stats: buildSemanticStatsFromRules(rules, data),
    }
  } catch (error) {
    throw new Error(parseRequestError(error, '加载规则库失败'))
  }
}

export async function fetchRulePrompt(ruleId: string): Promise<{
  prompt: string
  isDefaultPrompt: boolean
}> {
  try {
    const response = await ApiService.getRaw(
      `/api/v1/qc/sichuan/rules/${encodeURIComponent(ruleId)}/prompt`,
    )
    const data = pickResponseData(response.data)
    return {
      prompt: String(data.prompt || ''),
      isDefaultPrompt: Boolean(data.is_default ?? true),
    }
  } catch (error) {
    throw new Error(parseRequestError(error, '获取提示词失败'))
  }
}

export async function saveRulePrompt(ruleId: string, promptText: string): Promise<void> {
  try {
    await ApiService.putRaw(`/api/v1/qc/sichuan/rules/${encodeURIComponent(ruleId)}/prompt`, {
      custom_prompt: promptText.trim() ? promptText.trim() : null,
    })
  } catch (error) {
    throw new Error(parseRequestError(error, '保存提示词失败'))
  }
}

export async function executeSemanticRuleTest(
  ruleId: string,
  medicalText: string,
): Promise<SemanticRuleTestResult> {
  try {
    const response = await ApiService.postRaw('/api/v1/qc/sichuan/test-rule', {
      rule_id: ruleId,
      medical_text: medicalText,
    })
    const data = pickResponseData(response.data)
    return {
      is_compliant: Boolean(data.is_compliant ?? true),
      confidence: parseCount(data.confidence),
      findings: String(data.findings || ''),
      evidence: String(data.evidence || ''),
      suggestion: String(data.suggestion || ''),
      trace_id: String(data.trace_id || ''),
      status_code: Number(data.status_code || 0) || undefined,
      error_category: data.error_category ? String(data.error_category) : undefined,
    }
  } catch (error) {
    const parsed = parseSemanticRuleTestError(error, '规则测试失败')
    throw new SemanticRuleTestError(parsed.message, {
      statusCode: parsed.statusCode,
      traceId: parsed.traceId,
      detail: parsed.detail,
      errorCategory: parsed.errorCategory,
    })
  }
}
