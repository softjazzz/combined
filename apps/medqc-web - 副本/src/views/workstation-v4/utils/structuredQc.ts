import type {
  StructuredQCFilterState,
  StructuredQCDisplayStatus,
  StructuredQCGroup,
  StructuredQCIssue,
  StructuredQCOverview,
  StructuredQCResult,
  StructuredQCStatus,
  StructuredQCSubitemAnchor,
} from '@/views/workstation-v4/types'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from '@/views/workstation-v4/semantic-rules/types'

const STATUS_LABEL_MAP: Record<StructuredQCStatus, string> = {
  non_compliant: '不合规',
  uncertain: '待复核',
  compliant: '合规',
  not_applicable: '不适用',
  failed: '失败',
  error: '错误',
}

const DISPLAY_STATUS_SET = new Set<StructuredQCDisplayStatus>([
  'confirmed_defect',
  'qc_review_candidate',
  'needs_review',
  'data_quality_gap',
  'rejected_by_system',
  'technical_error_internal',
  'compliant',
  'not_applicable',
  '',
])

const DEFAULT_FILTER: StructuredQCFilterState = {
  keyword: '',
  statusList: ['non_compliant', 'uncertain'],
  documentType: '',
  executionDomain: '',
  defectLevel: '',
}

function toText(value: unknown): string {
  return String(value ?? '').trim()
}

function toNumber(value: unknown, fallback = 0): number {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function toBoolean(value: unknown): boolean | null {
  if (value === true) return true
  if (value === false) return false
  if (String(value).trim().toLowerCase() === 'true') return true
  if (String(value).trim().toLowerCase() === 'false') return false
  return null
}

function normalizeStatus(status: unknown, isCompliant: unknown): StructuredQCStatus {
  const normalized = toText(status).toLowerCase()
  if (
    normalized === 'non_compliant' ||
    normalized === 'uncertain' ||
    normalized === 'compliant' ||
    normalized === 'not_applicable' ||
    normalized === 'failed' ||
    normalized === 'error'
  ) {
    return normalized
  }
  if (isCompliant === false) return 'non_compliant'
  return 'compliant'
}

function normalizeDisplayStatus(
  value: unknown,
  fallbackStatus: StructuredQCStatus,
): StructuredQCDisplayStatus {
  const normalized = toText(value).toLowerCase() as StructuredQCDisplayStatus
  if (DISPLAY_STATUS_SET.has(normalized)) return normalized
  if (fallbackStatus === 'non_compliant') return ''
  if (fallbackStatus === 'uncertain') return ''
  if (fallbackStatus === 'compliant' || fallbackStatus === 'not_applicable') return fallbackStatus
  return ''
}

function isNoChangeSuggestion(text: string): boolean {
  const normalized = toText(text).replace(/\s+/g, '')
  if (!normalized) return false
  const patterns = [
    /(无需|无须).{0,4}(修改|调整|处理|整改|更改|改动|补充)/,
    /无需整改/,
    /无需处理/,
    /无需完善/,
    /符合规则要求/,
    /符合要求/,
    /无明显问题/,
  ]
  return patterns.some((pattern) => pattern.test(normalized))
}

function normalizeSuggestion(
  status: StructuredQCStatus,
  suggestion: string,
  ruleName: string,
): string {
  const suggestionText = toText(suggestion)
  if (status === 'non_compliant') {
    if (!suggestionText || isNoChangeSuggestion(suggestionText)) {
      return ruleName
        ? `请按“${ruleName}”规则补充或修正相关记录。`
        : '请根据规则要求补充或修正相关记录。'
    }
  }
  if (status === 'uncertain' && isNoChangeSuggestion(suggestionText)) {
    return '证据不足，建议人工复核相关文书并补充佐证。'
  }
  return suggestionText
}

function buildIssueKey(input: {
  ruleId: string
  recordId: string
  visitId: string
  findings: string
  traceId: string
}) {
  return [
    input.ruleId,
    input.recordId,
    input.visitId,
    input.traceId,
    input.findings.slice(0, 48),
  ].join('|')
}

function normalizeSubitemAnchor(
  raw: Record<string, unknown>,
  fallback: Partial<StructuredQCSubitemAnchor> = {},
): StructuredQCSubitemAnchor | null {
  const anchorId = toText(raw.anchor_id) || toText(raw.anchorId) || fallback.anchorId || ''
  const subitemId = toText(raw.subitem_id) || toText(raw.subitemId) || anchorId
  const parentRuleId =
    toText(raw.parent_rule_id) ||
    toText(raw.parentRuleId) ||
    toText(raw.rule_id) ||
    fallback.parentRuleId ||
    ''
  if (!anchorId && !subitemId) return null
  const displayStatus =
    toText(raw.display_status) ||
    toText(raw.displayStatus) ||
    fallback.displayStatus ||
    'needs_review'
  const displayBucket =
    toText(raw.display_bucket) ||
    toText(raw.displayBucket) ||
    fallback.displayBucket ||
    (displayStatus === 'data_quality_gap' ? '数据缺口' : '待复核')
  return {
    parentRuleId,
    anchorId: anchorId || subitemId,
    subitemId: subitemId || anchorId,
    subitemName:
      toText(raw.subitem_name) || toText(raw.subitemName) || fallback.subitemName || '专项检查项',
    anchorEvidenceStatus:
      toText(raw.anchor_evidence_status) ||
      toText(raw.anchorEvidenceStatus) ||
      fallback.anchorEvidenceStatus ||
      '',
    anchorEvidence:
      toText(raw.anchor_evidence) ||
      toText(raw.anchorEvidence) ||
      toText(raw.evidence) ||
      fallback.anchorEvidence ||
      '',
    anchorDecisionReason:
      toText(raw.anchor_decision_reason) ||
      toText(raw.anchorDecisionReason) ||
      toText(raw.findings) ||
      fallback.anchorDecisionReason ||
      '',
    displayStatus,
    displayBucket,
    canShowAsDefect: toBoolean(raw.can_show_as_defect) ?? toBoolean(raw.canShowAsDefect) ?? false,
    internalOnly: toBoolean(raw.internal_only) ?? toBoolean(raw.internalOnly) ?? false,
  }
}

function normalizeSubitemAnchorList(value: unknown): StructuredQCSubitemAnchor[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item) => normalizeSubitemAnchor(item))
    .filter((item): item is StructuredQCSubitemAnchor => Boolean(item))
}

function toStructuredIssue(
  raw: Record<string, unknown>,
  fallback: Partial<StructuredQCIssue> = {},
): StructuredQCIssue {
  const status = normalizeStatus(raw.status, raw.is_compliant)
  const resolvedRuleName =
    toText(raw.rule_name) || toText(raw.ruleName) || fallback.ruleName || '未知规则'
  const metadataSource = (
    raw.metadata && typeof raw.metadata === 'object'
      ? (raw.metadata as Record<string, unknown>)
      : {}
  ) as Record<string, unknown>

  const issue: StructuredQCIssue = {
    id: '',
    status,
    statusLabel: STATUS_LABEL_MAP[status],
    displayStatus: normalizeDisplayStatus(raw.display_status ?? raw.displayStatus, status),
    displayBucket: toText(raw.display_bucket) || toText(raw.displayBucket),
    postprocessLabel: toText(raw.postprocess_label) || toText(raw.postprocessLabel),
    postprocessReason: toText(raw.postprocess_reason) || toText(raw.postprocessReason),
    evidenceProblemType: toText(raw.evidence_problem_type) || toText(raw.evidenceProblemType),
    canShowAsDefect: toBoolean(raw.can_show_as_defect) ?? toBoolean(raw.canShowAsDefect) ?? false,
    canShowToDoctor: toBoolean(raw.can_show_to_doctor) ?? toBoolean(raw.canShowToDoctor) ?? true,
    internalOnly: toBoolean(raw.internal_only) ?? toBoolean(raw.internalOnly) ?? false,
    postprocessMode: toText(raw.postprocess_mode) || toText(raw.postprocessMode),
    firstPassStatus: toText(raw.first_pass_status) || toText(raw.firstPassStatus),
    firstPassDisplayStatus:
      toText(raw.first_pass_display_status) || toText(raw.firstPassDisplayStatus),
    adjudicatedDisplayStatus:
      toText(raw.adjudicated_display_status) || toText(raw.adjudicatedDisplayStatus),
    adjudicatorReason: toText(raw.adjudicator_reason) || toText(raw.adjudicatorReason),
    adjudicatorSupportingQuote:
      toText(raw.adjudicator_supporting_quote) || toText(raw.adjudicatorSupportingQuote),
    adjudicatorConfidence: toNumber(raw.adjudicator_confidence ?? raw.adjudicatorConfidence, 0),
    ruleRequirementMatch: toText(raw.rule_requirement_match) || toText(raw.ruleRequirementMatch),
    ruleJobId: toText(raw.rule_job_id) || toText(raw.ruleJobId),
    ruleId: toText(raw.rule_id) || toText(raw.ruleId) || fallback.ruleId || '',
    ruleCode: toText(raw.rule_code) || toText(raw.ruleCode) || fallback.ruleCode || '',
    ruleName: resolvedRuleName,
    findings: toText(raw.findings) || toText(raw.description),
    evidence: toText(raw.evidence),
    suggestion: normalizeSuggestion(status, toText(raw.suggestion), resolvedRuleName),
    confidence: toNumber(raw.confidence, 0),
    documentType:
      toText(raw.document_type) || toText(raw.documentType) || fallback.documentType || '',
    executionDomain:
      toText(raw.execution_domain) || toText(raw.executionDomain) || fallback.executionDomain || '',
    ruleFamily: toText(raw.rule_family) || toText(raw.ruleFamily) || fallback.ruleFamily || '',
    defectLevel: toText(raw.defect_level) || toText(raw.defectLevel) || fallback.defectLevel || '',
    executorType:
      toText(raw.executor_type) || toText(raw.executorType) || fallback.executorType || '',
    recordId: toText(raw.record_id) || toText(raw.recordId) || fallback.recordId || '',
    visitId: toText(raw.visit_id) || toText(raw.visitId) || fallback.visitId || '',
    patientName: toText(raw.patient_name) || toText(raw.patientName) || fallback.patientName || '',
    department: toText(raw.department) || fallback.department || '',
    metadata: {
      traceId: toText(raw.trace_id) || toText(metadataSource.trace_id),
      cacheHit: toBoolean(raw.cache_hit) ?? toBoolean(metadataSource.cache_hit),
      promptVersion: toText(raw.prompt_version) || toText(metadataSource.prompt_version),
      modelVersion: toText(raw.model_version) || toText(metadataSource.model_version),
      ruleVersion: toText(raw.rule_version) || toText(metadataSource.rule_version),
      evidenceSource: toText(raw.evidence_source) || toText(metadataSource.evidence_source),
      cacheKey: toText(raw.cache_key) || toText(metadataSource.cache_key),
      docScope: toText(raw.doc_scope) || toText(metadataSource.doc_scope),
      costClass: toText(raw.cost_class) || toText(metadataSource.cost_class),
      llmFallback: toBoolean(raw.llm_fallback) ?? toBoolean(metadataSource.llm_fallback),
      refined: toBoolean(raw.refined) ?? toBoolean(metadataSource.refined),
      refineReason: toText(raw.refine_reason) || toText(metadataSource.refine_reason),
      screeningStatus: toText(raw.screening_status) || toText(metadataSource.screening_status),
      finalDecisionSource:
        toText(raw.final_decision_source) || toText(metadataSource.final_decision_source),
      subitemAnchors: normalizeSubitemAnchorList(metadataSource.subitem_anchors),
    },
  }

  issue.id = buildIssueKey({
    ruleId: issue.ruleId || issue.ruleCode,
    recordId: issue.recordId,
    visitId: issue.visitId,
    findings: issue.findings,
    traceId: issue.metadata.traceId,
  })
  return issue
}

function collectTopLevelSubitemAnchors(
  payload: Record<string, unknown>,
): StructuredQCSubitemAnchor[] {
  return normalizeSubitemAnchorList(payload.subitem_anchor_results)
}

export function getSubitemAnchorDisplayLabel(anchor: StructuredQCSubitemAnchor): string {
  if (anchor.displayStatus === 'data_quality_gap') return '数据缺口'
  return '专项检查项（待复核）'
}

export function shouldCountSubitemAnchorAsDefect(_anchor: StructuredQCSubitemAnchor): boolean {
  return false
}

function buildOverview(
  issues: StructuredQCIssue[],
  summary: Record<string, unknown>,
  options: {
    docCount?: number
    processingTimeSeconds?: number
  } = {},
): StructuredQCOverview {
  const counter = issues.reduce(
    (acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1
      return acc
    },
    {} as Record<StructuredQCStatus, number>,
  )
  const totalRules = Math.max(
    toNumber(summary.total_rules),
    toNumber(summary.rule_count),
    issues.length,
  )
  const compliantCount = toNumber(summary.compliant_rules, counter.compliant || 0)
  const notApplicableCount = toNumber(summary.not_applicable, counter.not_applicable || 0)
  const uncertainCount = toNumber(
    summary.qc_review_candidate_count ??
      summary.needs_review_count ??
      summary.uncertain_count ??
      summary.uncertain_records,
    counter.uncertain || 0,
  )
  const failedCount = toNumber(summary.failed_count, counter.failed || 0)
  const issueCount = toNumber(
    summary.confirmed_defect_count ?? summary.issues_found ?? summary.issue_records,
    (counter.non_compliant || 0) + (counter.uncertain || 0),
  )
  const complianceRateRaw = summary.compliance_rate
  const complianceRate =
    complianceRateRaw !== undefined && complianceRateRaw !== null
      ? toNumber(complianceRateRaw)
      : totalRules > 0
        ? Math.round(((compliantCount + notApplicableCount) / totalRules) * 10000) / 100
        : 0

  return {
    totalRules,
    complianceRate,
    issueCount,
    uncertainCount,
    compliantCount,
    notApplicableCount,
    failedCount,
    docCount: Math.max(0, Number(options.docCount || 0)),
    processingTimeSeconds: Math.max(0, Number(options.processingTimeSeconds || 0)),
  }
}

function topGroups(
  issues: StructuredQCIssue[],
  kind: StructuredQCGroup['kind'],
  labelResolver: (issue: StructuredQCIssue) => string,
  prefix: string,
  top = 6,
): StructuredQCGroup[] {
  const counter = new Map<string, number>()
  issues.forEach((issue) => {
    const label = toText(labelResolver(issue)) || '未命名'
    counter.set(label, (counter.get(label) || 0) + 1)
  })
  return Array.from(counter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, top)
    .map(([label, count]) => ({
      key: `${prefix}:${label}`,
      label,
      count,
      kind,
    }))
}

function buildGroups(issues: StructuredQCIssue[]): StructuredQCGroup[] {
  const statusGroups = topGroups(issues, 'status', (issue) => issue.statusLabel, 'status', 8)
  const docGroups = topGroups(issues, 'document', (issue) => issue.documentType, 'document')
  const domainGroups = topGroups(issues, 'domain', (issue) => issue.executionDomain, 'domain')
  const defectGroups = topGroups(issues, 'defect', (issue) => issue.defectLevel, 'defect')
  const ruleGroups = topGroups(issues, 'rule', (issue) => issue.ruleCode || issue.ruleName, 'rule')
  return [...statusGroups, ...docGroups, ...domainGroups, ...defectGroups, ...ruleGroups]
}

export function createDefaultStructuredQCFilter(): StructuredQCFilterState {
  return {
    ...DEFAULT_FILTER,
  }
}

export function isProblemStatus(status: StructuredQCStatus): boolean {
  return status === 'non_compliant' || status === 'uncertain'
}

export function filterStructuredQCIssues(
  issues: StructuredQCIssue[],
  filter: StructuredQCFilterState,
): StructuredQCIssue[] {
  const keyword = toText(filter.keyword).toLowerCase()
  const statusSet = new Set(filter.statusList || [])
  return issues.filter((issue) => {
    if (statusSet.size > 0 && !statusSet.has(issue.status)) return false
    if (filter.documentType && issue.documentType !== filter.documentType) return false
    if (filter.executionDomain && issue.executionDomain !== filter.executionDomain) return false
    if (filter.defectLevel && issue.defectLevel !== filter.defectLevel) return false
    if (!keyword) return true
    const haystack = [
      issue.ruleCode,
      issue.ruleName,
      issue.findings,
      issue.evidence,
      issue.suggestion,
      issue.documentType,
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(keyword)
  })
}

export function mapSichuanEvaluationToStructuredQC(
  payload: Record<string, unknown>,
  options: {
    docCount?: number
  } = {},
): StructuredQCResult {
  const summary =
    (payload.evaluation_summary && typeof payload.evaluation_summary === 'object'
      ? (payload.evaluation_summary as Record<string, unknown>)
      : {}) || {}
  const performance =
    (payload.performance_metrics && typeof payload.performance_metrics === 'object'
      ? (payload.performance_metrics as Record<string, unknown>)
      : {}) || {}
  const results = Array.isArray(payload.evaluation_results) ? payload.evaluation_results : []
  const issues = results
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item) => toStructuredIssue(item, { recordId: toText(payload.document_id) }))
  const subitemAnchors = collectTopLevelSubitemAnchors(payload)

  return {
    overview: buildOverview(issues, summary, {
      docCount: options.docCount,
      processingTimeSeconds: toNumber(performance.processing_time, toNumber(payload.api_time, 0)),
    }),
    issues,
    groups: buildGroups(issues),
    subitemAnchors,
  }
}

function collectBatchIssueSource(
  job: SichuanBatchJob | null | undefined,
  debug: SichuanBatchJobDebugSnapshot | null | undefined,
): Array<Record<string, unknown>> {
  const rows: Array<Record<string, unknown>> = []
  const fromRuleResults = (job?.rule_results || []).flatMap((ruleResult) => {
    return (ruleResult.items || []).map(
      (item) =>
        ({
          ...item,
          rule_code: item.rule_code || ruleResult.rule_code,
          rule_name: item.rule_name || ruleResult.rule_name,
        }) as Record<string, unknown>,
    )
  })
  if (fromRuleResults.length > 0) {
    rows.push(...fromRuleResults)
  } else if (Array.isArray(debug?.recent_items) && debug?.recent_items.length > 0) {
    rows.push(...debug.recent_items.map((item) => ({ ...item }) as Record<string, unknown>))
  }
  return rows
}

export function mapBatchJobToStructuredQC(
  job: SichuanBatchJob | null | undefined,
  debug: SichuanBatchJobDebugSnapshot | null | undefined,
): StructuredQCResult {
  const rows = collectBatchIssueSource(job, debug)
  const issues = rows.map((item) => toStructuredIssue(item))
  const summary =
    (job?.summary && typeof job.summary === 'object'
      ? (job.summary as unknown as Record<string, unknown>)
      : {}) || {}
  const overview = buildOverview(issues, summary, {
    docCount: toNumber(summary.total_records, toNumber(job?.total_records, 0)),
    processingTimeSeconds: toNumber(
      summary.total_processing_time,
      toNumber(job?.total_processing_time, 0),
    ),
  })
  return {
    overview,
    issues,
    groups: buildGroups(issues),
    subitemAnchors: [],
  }
}

export const __structuredQcTestUtils = {
  normalizeSubitemAnchor,
  normalizeSubitemAnchorList,
}
