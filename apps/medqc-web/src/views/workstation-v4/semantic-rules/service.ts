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

const DEFAULT_SEMANTIC_RULE_PAGE_SIZE = 10

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

function normalizeComplianceFlag(data: Record<string, any>): boolean {
  const raw = data.is_compliant
  if (raw === false) return false
  if (raw === 0) return false
  if (typeof raw === 'string') {
    const value = raw.trim().toLowerCase()
    if (['false', '0', 'no', 'non_compliant', '不合规', '不符合'].includes(value)) return false
  }

  const text = [data.findings, data.evidence, data.suggestion, data.llm_raw_output]
    .map((item) => String(item || ''))
    .join('\n')
  if (/"is_compliant"\s*:\s*false/i.test(text)) return false
  if (
    /不符合|不合规|不合规情形|缺陷|未[^。；，,]*(分析|记录|完成|签名|说明)|缺失|超时/.test(text)
  ) {
    return false
  }

  if (raw === true) return true
  if (typeof raw === 'number') return raw !== 0
  if (typeof raw === 'string') {
    const value = raw.trim().toLowerCase()
    if (['true', '1', 'yes', 'compliant', '合规', '符合'].includes(value)) return true
  }

  const status = String(data.status || '')
    .trim()
    .toLowerCase()
  if (['non_compliant', 'non-compliance', 'failed', 'error'].includes(status)) return false
  if (['compliant', 'not_applicable', 'not-applicable'].includes(status)) return true

  return true
}

const LUXIAN_0609_RULE_ID_PATTERN = /^LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}$/u
const LUXIAN_0609_PREFIX_PATTERN = /^LX0609-/iu

function normalizeRuleIdentity(value: unknown): string {
  const text = String(value || '').trim()
  const normalized = LUXIAN_0609_PREFIX_PATTERN.test(text) ? text.toUpperCase() : text
  if (!normalized) return ''
  if (LUXIAN_0609_PREFIX_PATTERN.test(normalized) && !LUXIAN_0609_RULE_ID_PATTERN.test(normalized)) {
    return ''
  }
  return normalized
}

function pickCanonicalRuleId(raw: Record<string, any>): string {
  const candidates = [raw.rule_id, raw.rule_code, raw.original_id, raw.id]
    .map((item) => String(item || '').trim())
    .filter(Boolean)
  if (candidates.some((value) => LUXIAN_0609_PREFIX_PATTERN.test(value))) {
    const identityFields = [raw.rule_id, raw.rule_code]
      .map((value) => String(value || '').trim().toUpperCase())
      .filter(Boolean)
    const identity = identityFields[0] || ''
    // 不利用别名修复旧编号或互相冲突的编号，以免反馈挂到其他规则。
    return LUXIAN_0609_RULE_ID_PATTERN.test(identity) && identityFields.every((value) => value === identity)
      ? identity
      : ''
  }
  const canonical = candidates.find((value) => /^(SC|LXE|LX|CL)-/i.test(value))
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
  const rawRuleCode = raw.rule_code ? String(raw.rule_code).trim() : ''
  const mappedRuleIds = Array.isArray(raw.mapped_rule_ids)
    ? raw.mapped_rule_ids.map(normalizeRuleIdentity).filter(Boolean)
    : []
  const dataDependencies = Array.isArray(raw.data_dependencies)
    ? raw.data_dependencies.map((item: unknown) => String(item)).filter(Boolean)
    : []
  const applicableDocumentLabels = Array.isArray(raw.applicable_document_labels)
    ? raw.applicable_document_labels.map((item: unknown) => String(item)).filter(Boolean)
    : []
  return {
    rule_id: canonicalRuleId,
    rule_code: canonicalRuleId.startsWith('LX0609-')
      ? canonicalRuleId
      : rawRuleCode && !LUXIAN_0609_PREFIX_PATTERN.test(rawRuleCode)
        ? rawRuleCode
        : undefined,
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
    executor_type: raw.executor_type ? String(raw.executor_type) : undefined,
    execution_domain: raw.execution_domain ? String(raw.execution_domain) : undefined,
    doc_scope: raw.doc_scope ? String(raw.doc_scope) : undefined,
    rule_version: raw.rule_version ? String(raw.rule_version) : undefined,
    prompt_version: raw.prompt_version ? String(raw.prompt_version) : undefined,
    custom_prompt: raw.custom_prompt ? String(raw.custom_prompt) : undefined,
    mapped_rule_ids: mappedRuleIds,
    primary_execution_rule_id: normalizeRuleIdentity(raw.primary_execution_rule_id) || undefined,
    release_scope: normalizeNonEmptyText(raw.release_scope),
    phase_status: normalizeNonEmptyText(raw.phase_status),
    pending_reason_code: normalizeNonEmptyText(raw.pending_reason_code),
    pending_definition_note: normalizeNonEmptyText(raw.pending_definition_note),
    implementation_status: raw.implementation_status
      ? String(raw.implementation_status)
      : undefined,
    dependency_type: raw.dependency_type ? String(raw.dependency_type) : undefined,
    data_status: raw.data_status ? String(raw.data_status) : undefined,
    trigger_condition: raw.trigger_condition ? String(raw.trigger_condition) : undefined,
    non_trigger_condition: raw.non_trigger_condition
      ? String(raw.non_trigger_condition)
      : undefined,
    rule_basis: raw.rule_basis ? String(raw.rule_basis) : undefined,
    customer_text: raw.customer_text ? String(raw.customer_text) : undefined,
    customer_policy: normalizeCustomerPolicy(raw.customer_policy),
    engine_judgment: normalizeEngineJudgment(raw.engine_judgment),
    standardized_rule: raw.standardized_rule ? String(raw.standardized_rule) : undefined,
    required_documents_label: raw.required_documents_label
      ? String(raw.required_documents_label)
      : undefined,
    data_dependencies: dataDependencies,
    coverage_level: raw.coverage_level ? String(raw.coverage_level) : undefined,
    included_in_v1: raw.included_in_v1 ? String(raw.included_in_v1) : undefined,
    example_source: raw.example_source ? String(raw.example_source) : undefined,
    positive_example: normalizeSemanticRuleExample(raw.positive_example, '正例'),
    negative_example: normalizeSemanticRuleExample(raw.negative_example, '反例'),
    applicable_document_labels: applicableDocumentLabels,
  }
}

function normalizeCustomerPolicy(value: unknown): SemanticRuleItem['customer_policy'] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined

  const raw = value as Record<string, unknown>
  const sourceDocument = normalizeNonEmptyText(raw.source_document)
  const qcPoint = normalizeNonEmptyText(raw.qc_point)
  const summary = normalizeNonEmptyText(raw.summary)
  if (!sourceDocument || !qcPoint || !summary || !Array.isArray(raw.sources)) return undefined

  const sources = raw.sources.map(normalizeNonEmptyText)
  if (sources.some((source) => !source)) return undefined

  return {
    source_document: sourceDocument,
    qc_point: qcPoint,
    summary,
    sources: sources as string[],
  }
}

const ENGINE_OUTCOME_KEYS = ['compliant', 'non_compliant', 'data_gap', 'not_applicable'] as const

function normalizeTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(normalizeNonEmptyText).filter((item): item is string => Boolean(item))
}

function normalizeEngineJudgment(value: unknown): SemanticRuleItem['engine_judgment'] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined

  const raw = value as Record<string, unknown>
  if (raw.withheld === true) {
    const reason = normalizeNonEmptyText(raw.withheld_reason)
    return reason ? { withheld: true, withheld_reason: reason } : undefined
  }
  const trigger = normalizeNonEmptyText(raw.trigger)
  const steps = normalizeTextList(raw.steps)
  if (raw.withheld !== false || !trigger || !steps.length) return undefined

  const rawOutcomes =
    raw.outcomes && typeof raw.outcomes === 'object' && !Array.isArray(raw.outcomes)
      ? (raw.outcomes as Record<string, unknown>)
      : {}
  const outcomes: Partial<Record<(typeof ENGINE_OUTCOME_KEYS)[number], string>> = {}
  for (const key of ENGINE_OUTCOME_KEYS) {
    const text = normalizeNonEmptyText(rawOutcomes[key])
    if (text) outcomes[key] = text
  }
  return {
    withheld: false,
    method: normalizeNonEmptyText(raw.method) || '',
    trigger,
    steps,
    outcomes,
    extra_notes: normalizeTextList(raw.extra_notes),
    data_gap_note: normalizeNonEmptyText(raw.data_gap_note) || '',
  }
}

function normalizeNonEmptyText(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const text = value.trim()
  return text || undefined
}

function normalizeSemanticRuleExample(
  value: unknown,
  fallbackTitle: string,
): SemanticRuleItem['positive_example'] {
  if (!value) return undefined
  if (typeof value === 'string') {
    const rawText = value.trim()
    if (!rawText) return undefined
    return {
      title: fallbackTitle,
      summary: '模拟病历文本',
      raw_text: rawText,
      sections: [{ heading: '模拟病历', content: rawText }],
      focusPoints: [],
    }
  }
  if (typeof value !== 'object') return undefined
  const record = value as Record<string, unknown>
  const rawText = typeof record.raw_text === 'string' ? record.raw_text.trim() : ''
  const sections = Array.isArray(record.sections)
    ? (record.sections as SemanticRuleItem['positive_example']['sections'])
    : rawText
      ? [{ heading: '模拟病历', content: rawText }]
      : []
  return {
    title: String(record.title || fallbackTitle),
    summary: String(record.summary || ''),
    raw_text: rawText || undefined,
    sections,
    focusPoints: Array.isArray(record.focusPoints)
      ? record.focusPoints.map((item) => String(item))
      : [],
  }
}

export type SemanticRuleRequestOptions = {
  signal?: AbortSignal
  skipErrorToast?: boolean
}

export function isRequestCanceledError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const candidate = error as { code?: unknown; name?: unknown }
  return candidate.code === 'ERR_CANCELED' || candidate.name === 'CanceledError' || candidate.name === 'AbortError'
}

export async function fetchSichuanRuleSetsFromBackend(
  options?: SemanticRuleRequestOptions,
): Promise<SichuanRuleSetOption[]> {
  const response = await ApiService.getRaw(
    '/api/v1/qc/sichuan/workspace/rule-sets',
    {
      _ts: Date.now(),
    },
    options ? { signal: options.signal, skipErrorToast: options.skipErrorToast } : undefined,
  )
  const payload = pickResponseData(response.data ?? response)
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
  > &
    Partial<Pick<SemanticRuleWorkspaceQueryState, 'releaseScope'>>,
): SemanticRuleItem[] {
  const keyword = query.keyword.trim().toLowerCase()

  return rules.filter((rule) => {
    if (query.complexity && rule.complexity !== query.complexity) return false
    if (query.defectLevel && rule.defect_level !== query.defectLevel) return false
    if (query.releaseScope && rule.release_scope !== query.releaseScope) return false

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
    const matchByMappedRule = (rule.mapped_rule_ids || []).some((ruleId) =>
      ruleId.toLowerCase().includes(keyword),
    )

    return (
      rule.rule_id.toLowerCase().includes(keyword) ||
      (rule.rule_code || '').toLowerCase().includes(keyword) ||
      rule.name.toLowerCase().includes(keyword) ||
      rule.description.toLowerCase().includes(keyword) ||
      rule.category.toLowerCase().includes(keyword) ||
      (rule.customer_text || '').toLowerCase().includes(keyword) ||
      (rule.standardized_rule || '').toLowerCase().includes(keyword) ||
      (rule.trigger_condition || '').toLowerCase().includes(keyword) ||
      (rule.non_trigger_condition || '').toLowerCase().includes(keyword) ||
      matchByMappedRule ||
      matchByDocType
    )
  })
}

export function toSemanticRulePage<T>(items: T[], page: number, pageSize: number): T[] {
  const safePage = Number.isFinite(page) && page > 0 ? Math.floor(page) : 1
  const safePageSize =
    Number.isFinite(pageSize) && pageSize > 0
      ? Math.floor(pageSize)
      : DEFAULT_SEMANTIC_RULE_PAGE_SIZE
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
    ruleSetKey: parseQueryStringValue(query.ruleSetKey),
    keyword: parseQueryStringValue(query.keyword),
    complexity: parseQueryStringValue(query.complexity),
    defectLevel: parseQueryStringValue(query.defectLevel),
    documentType: parseQueryStringValue(query.documentType),
    releaseScope: parseQueryStringValue(query.releaseScope),
    page: parsePositiveInt(query.page, 1),
    pageSize: parsePositiveInt(query.pageSize, DEFAULT_SEMANTIC_RULE_PAGE_SIZE),
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
  if (state.ruleSetKey) nextQuery.ruleSetKey = state.ruleSetKey
  if (state.complexity) nextQuery.complexity = state.complexity
  if (state.defectLevel) nextQuery.defectLevel = state.defectLevel
  if (state.documentType) nextQuery.documentType = state.documentType
  if (state.releaseScope) nextQuery.releaseScope = state.releaseScope
  if (state.page > 1) nextQuery.page = String(state.page)
  if (state.pageSize !== DEFAULT_SEMANTIC_RULE_PAGE_SIZE)
    nextQuery.pageSize = String(state.pageSize)

  return nextQuery
}

export async function fetchSemanticRulesFromBackend(
  ruleSetKey?: string,
  options?: SemanticRuleRequestOptions,
): Promise<{
  rules: SemanticRuleItem[]
  stats: SemanticRuleStats
}> {
  try {
    const params: Record<string, unknown> = {
      _ts: Date.now(),
    }
    if (ruleSetKey) {
      params.rule_set_key = ruleSetKey
    }
    const response = await ApiService.getRaw(
      '/api/v1/qc/sichuan/rules',
      {
        ...params,
      },
      options ? { signal: options.signal, skipErrorToast: options.skipErrorToast } : undefined,
    )
    const data = pickResponseData(response.data)
    const rules = Array.isArray(data.rules)
      ? data.rules.map((item: Record<string, any>) => normalizeSemanticRule(item))
      : []

    return {
      rules,
      stats: buildSemanticStatsFromRules(rules, data),
    }
  } catch (error) {
    if (isRequestCanceledError(error)) throw error
    throw new Error(parseRequestError(error, '加载规则库失败'))
  }
}

export async function fetchRulePrompt(
  ruleId: string,
  options?: SemanticRuleRequestOptions,
): Promise<{
  prompt: string
  isDefaultPrompt: boolean
}> {
  try {
    const response = await ApiService.getRaw(
      `/api/v1/qc/sichuan/rules/${encodeURIComponent(ruleId)}/prompt`,
      undefined,
      options ? { signal: options.signal, skipErrorToast: options.skipErrorToast } : undefined,
    )
    const data = pickResponseData(response.data)
    return {
      prompt: String(data.prompt || ''),
      isDefaultPrompt: Boolean(data.is_default ?? true),
    }
  } catch (error) {
    if (isRequestCanceledError(error)) throw error
    throw new Error(parseRequestError(error, '获取提示词失败'))
  }
}

export async function saveRulePrompt(
  ruleId: string,
  promptText: string,
  options?: SemanticRuleRequestOptions,
): Promise<void> {
  try {
    await ApiService.putRaw(
      `/api/v1/qc/sichuan/rules/${encodeURIComponent(ruleId)}/prompt`,
      {
        custom_prompt: promptText.trim() ? promptText.trim() : null,
      },
      options ? { signal: options.signal, skipErrorToast: options.skipErrorToast } : undefined,
    )
  } catch (error) {
    if (isRequestCanceledError(error)) throw error
    throw new Error(parseRequestError(error, '保存提示词失败'))
  }
}

export async function executeSemanticRuleTest(
  ruleId: string,
  medicalText: string,
  options?: SemanticRuleRequestOptions,
): Promise<SemanticRuleTestResult> {
  try {
    const response = await ApiService.postRaw(
      '/api/v1/qc/sichuan/test-rule',
      {
        rule_id: ruleId,
        medical_text: medicalText,
      },
      options ? { signal: options.signal, skipErrorToast: options.skipErrorToast } : undefined,
    )
    const data = pickResponseData(response.data)
    return {
      is_compliant: normalizeComplianceFlag(data),
      confidence: parseCount(data.confidence),
      findings: String(data.findings || ''),
      evidence: String(data.evidence || ''),
      suggestion: String(data.suggestion || ''),
      trace_id: String(data.trace_id || ''),
      status_code: Number(data.status_code || 0) || undefined,
      error_category: data.error_category ? String(data.error_category) : undefined,
    }
  } catch (error) {
    if (isRequestCanceledError(error)) throw error
    const parsed = parseSemanticRuleTestError(error, '规则测试失败')
    throw new SemanticRuleTestError(parsed.message, {
      statusCode: parsed.statusCode,
      traceId: parsed.traceId,
      detail: parsed.detail,
      errorCategory: parsed.errorCategory,
    })
  }
}
