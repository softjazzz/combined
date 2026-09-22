export type SingleRecordQcStatus =
  | 'non_compliant'
  | 'ai_suggested_non_compliant'
  | 'technical_error'
  | 'evaluation_unknown'
  | 'uncertain'
  | 'data_gap'
  | 'not_applicable'
  | 'compliant'
  | 'ai_suggested_compliant'
  | 'not_executed'
  | string

export interface SingleRecordQcEvidence {
  source_ref: string
  source_type?: string
  source_label?: string
  field_path?: string
  record_time?: string
  /** 单病历已授权读取时才会返回；由后端按 source_ref 精确解析。 */
  evidence_excerpt?: string
  excerpt_kind?: '字段级依据' | '文书级依据' | string
  recommendation_index?: number
  evidence_role?: 'opinion' | 'execution'
}

function isSafeRecommendationEvidenceRef(
  value: unknown,
): value is { source_type: string; source_ref: string } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const ref = value as Record<string, unknown>
  return (
    typeof ref.source_type === 'string' &&
    ref.source_type.trim().length > 0 &&
    typeof ref.source_ref === 'string' &&
    /^src_[0-9a-f]{24}$/i.test(ref.source_ref.trim()) &&
    !Object.prototype.hasOwnProperty.call(ref, 'source_document_id')
  )
}

function isLegacySafeEvidenceRef(
  value: unknown,
): value is { source_type?: string; source_ref: string } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const evidence = value as Record<string, unknown>
  return (
    typeof evidence.source_ref === 'string' &&
    /^[a-z0-9][a-z0-9:_-]{1,127}$/i.test(evidence.source_ref.trim()) &&
    !Object.prototype.hasOwnProperty.call(evidence, 'source_document_id')
  )
}

export function recommendationEvidenceForSingleRecord(
  item: Pick<SingleRecordQcResultItem, 'rule_id' | 'customer_display_facts' | 'evidence'>,
): SingleRecordQcEvidence[] {
  if (
    !['LX0609-03-01-01', 'LX0609-03-01-04'].includes(
      String(item.rule_id || '')
        .trim()
        .toUpperCase(),
    )
  ) {
    return Array.isArray(item.evidence) ? item.evidence.slice(0, 8) : []
  }
  const facts = item.customer_display_facts
  const entries =
    facts && typeof facts === 'object' && !Array.isArray(facts)
      ? (facts as Record<string, unknown>).recommendation_evidence
      : undefined
  const rows: SingleRecordQcEvidence[] = []
  const seen = new Set<string>()
  if (Array.isArray(entries)) {
    for (const entry of entries) {
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue
      const record = entry as Record<string, unknown>
      const recommendationIndex = record.recommendation_index
      if (
        typeof recommendationIndex !== 'number' ||
        !Number.isInteger(recommendationIndex) ||
        recommendationIndex < 1
      )
        continue
      for (const [evidenceRole, field] of [
        ['opinion', 'opinion_evidence'],
        ['execution', 'execution_evidence'],
      ] as const) {
        const refs = record[field]
        if (!Array.isArray(refs)) continue
        for (const ref of refs) {
          if (!isSafeRecommendationEvidenceRef(ref)) continue
          const sourceType = ref.source_type.trim()
          const sourceRef = ref.source_ref.trim()
          const identity = `${sourceType.toLowerCase()}|${sourceRef}|${recommendationIndex}|${evidenceRole}`
          if (seen.has(identity)) continue
          seen.add(identity)
          rows.push({
            source_ref: sourceRef,
            source_type: sourceType,
            recommendation_index: recommendationIndex,
            evidence_role: evidenceRole,
          })
        }
      }
    }
  }
  for (const evidence of Array.isArray(item.evidence) ? item.evidence : []) {
    if (!isLegacySafeEvidenceRef(evidence)) continue
    const sourceRef = evidence.source_ref.trim()
    if (rows.some((row) => row.source_ref === sourceRef)) continue
    const sourceType = String(evidence.source_type || '').trim()
    const identity = `${sourceType.toLowerCase()}|${sourceRef}`
    if (seen.has(identity)) continue
    seen.add(identity)
    rows.push({ ...evidence, source_ref: sourceRef })
  }
  return rows.slice(0, 8)
}

/** 规则执行器已保存的受控子结论；用于解释多条件规则，不在浏览器重算质控结论。 */
export interface SingleRecordQcCriterionResult {
  criterion_id: string
  kind: 'text_length' | 'semantic_relation' | string
  status: 'passed' | 'failed' | 'unknown' | string
  reason_code: string
  actual_value?: number | string | boolean | null
  expected_value?: number | string | boolean | null
  operator?: string
  unit?: string
  rationale_code?: string
  dimensions?: string[]
  medical_analysis?: string
}

/** 数据不足结果保存的来源/字段缺口；仅用于展示后端已判定的受控事实。 */
export interface SingleRecordQcDataGapDetails {
  reason_code?: string
  missing_sources?: string[]
  missing_fields?: string[]
  required_sources?: string[]
  unavailable_sources?: string[]
  availability?: Record<string, string | boolean | null | undefined>
}

/**
 * 单病历最新结果接口的前端固定读模型。
 * 不承载任务树、前端去重或跨病历选择职责。
 */
export interface SingleRecordQcResultItem {
  /** 后端保存的规则和条目结构版本，不是临床日期。 */
  rule_version?: string
  schema_version?: string
  /** 保存结果的资料缺口描述，不代表当次源表读取快照。 */
  source_status?: string
  missing_fields?: string[]
  missing_sources?: string[]
  rule_id: string
  rule_name: string
  /** 规则总表提供的客户展示分组，不参与结果判定。 */
  source_document?: string
  /** 规则总表提供的客户质控点说明，不参与结果判定。 */
  qc_point?: string
  status: SingleRecordQcStatus
  display_status?: string
  reason_code?: string
  conclusion?: string
  detail?: string
  actual?: string
  standard?: string
  suggestion?: string
  model_analysis?: string
  evidence?: SingleRecordQcEvidence[]
  criterion_results?: SingleRecordQcCriterionResult[]
  customer_display_facts?: Record<string, unknown>
  data_gap_details?: SingleRecordQcDataGapDetails
}

/**
 * 单病历最新已保存结果接口的固定返回结构。
 * 前端不再承担任务挑选、合并或去重职责。
 */
export interface SingleRecordQcResultPayload {
  schema_version: 'lx0609-single-record-result-v1'
  state: 'ready' | 'not_found' | 'technical_error'
  reason_code: string
  record_ref: string
  job_id: string
  rule_set_key?: string
  rule_set_version?: string
  items: SingleRecordQcResultItem[]
  expected_rule_count: number
  result_rule_count: number
  is_complete: boolean
  missing_rule_ids?: string[]
  conflicting_rule_ids?: string[]
}

export type SingleRecordQcResultTone = 'danger' | 'warning' | 'success' | 'neutral'

export interface SingleRecordQcResultViewItem extends SingleRecordQcResultItem {
  key: string
  displayStatus: string
  tone: SingleRecordQcResultTone
  sortOrder: number
  conclusionText: string
}

export interface SingleRecordQcStatusSummary {
  key: string
  label: string
  count: number
  tone: SingleRecordQcResultTone
}

/**
 * 单病历结果面板的唯一状态分组。它只负责展示归类，不能改变服务端 RuleDecision。
 * “待处理”统一承接需要人工关注、资料补充或技术排查的保守状态。
 */
export type SingleRecordQcResultTabKey =
  | 'all'
  | 'non_compliant'
  | 'pending'
  | 'not_applicable'
  | 'compliant'

export interface SingleRecordQcStatusTab {
  key: SingleRecordQcResultTabKey
  label: string
  count: number
}

export type SingleRecordQcResultReportTab =
  | 'non_compliant'
  | 'data_gap'
  | 'uncertain'
  | 'compliant'
  | 'not_applicable'
  | 'all'

export interface SingleRecordQcResultDocumentGroup {
  key: string
  sourceDocument: string
  items: SingleRecordQcResultViewItem[]
}

export interface SingleRecordQcResultPresentation {
  counts: {
    nonCompliant: number
    dataGap: number
    uncertain: number
    notApplicable: number
    compliant: number
    technicalError: number
    other: number
  }
  sectionsByTab: Record<SingleRecordQcResultReportTab, SingleRecordQcResultDocumentGroup[]>
}

const STATUS_PRESENTATION: Record<
  string,
  { label: string; tone: SingleRecordQcResultTone; sortOrder: number }
> = {
  non_compliant: { label: '确定问题', tone: 'danger', sortOrder: 10 },
  ai_suggested_non_compliant: { label: '建议复核', tone: 'warning', sortOrder: 20 },
  technical_error: { label: '技术异常', tone: 'warning', sortOrder: 30 },
  evaluation_unknown: { label: '待确认', tone: 'warning', sortOrder: 40 },
  uncertain: { label: '待确认', tone: 'warning', sortOrder: 40 },
  data_gap: { label: '数据不足', tone: 'warning', sortOrder: 50 },
  not_executed: { label: '未执行', tone: 'warning', sortOrder: 60 },
  not_applicable: { label: '不适用', tone: 'neutral', sortOrder: 70 },
  compliant: { label: '合规', tone: 'success', sortOrder: 80 },
  ai_suggested_compliant: { label: '建议复核', tone: 'warning', sortOrder: 90 },
}

function text(value: unknown): string {
  return String(value || '').trim()
}

export function toSingleRecordQcResultViewItem(
  item: SingleRecordQcResultItem,
  index: number,
): SingleRecordQcResultViewItem {
  const presentation = STATUS_PRESENTATION[item.status] || {
    label: '待确认',
    tone: 'warning' as const,
    sortOrder: 45,
  }
  return {
    ...item,
    evidence: Array.isArray(item.evidence) ? item.evidence : [],
    key: `${text(item.rule_id) || 'unknown-rule'}-${index}`,
    // 最终状态来自后端保存的 RuleDecision；展示解释缺失不应篡改该状态。
    // 否则会把真实的不合规错误地从“确定问题”汇总中隐藏。
    // 接口可能将内部枚举放入展示字段；仅保留中文标签，不向客户暴露英文状态。
    displayStatus: /\p{Script=Han}/u.test(text(item.display_status))
      ? text(item.display_status)
      : presentation.label,
    tone: presentation.tone,
    sortOrder: presentation.sortOrder,
    conclusionText: text(item.conclusion),
  }
}

export function buildSingleRecordQcResultItems(
  items: SingleRecordQcResultItem[] | undefined | null,
): SingleRecordQcResultViewItem[] {
  return (items || []).map(toSingleRecordQcResultViewItem)
}

const REPORT_UNCERTAIN_STATUSES = new Set<SingleRecordQcStatus>([
  'uncertain',
  'evaluation_unknown',
  'ai_suggested_non_compliant',
])

function resolveSingleRecordQcReportTab(
  item: Pick<SingleRecordQcResultItem, 'status'>,
): Exclude<SingleRecordQcResultReportTab, 'all'> | null {
  if (item.status === 'non_compliant') return 'non_compliant'
  if (item.status === 'data_gap') return 'data_gap'
  if (REPORT_UNCERTAIN_STATUSES.has(item.status)) return 'uncertain'
  if (item.status === 'compliant') return 'compliant'
  if (item.status === 'not_applicable') return 'not_applicable'
  return null
}

function groupSingleRecordQcResultItems(
  items: SingleRecordQcResultViewItem[],
): SingleRecordQcResultDocumentGroup[] {
  const groups = new Map<string, SingleRecordQcResultDocumentGroup>()
  items.forEach((item) => {
    const sourceDocument = text(item.source_document) || '其他质控点'
    const existing = groups.get(sourceDocument)
    if (existing) {
      existing.items.push(item)
      return
    }
    groups.set(sourceDocument, {
      key: sourceDocument,
      sourceDocument,
      items: [item],
    })
  })
  return Array.from(groups.values())
}

/**
 * 只把 Canonical 条目组织成客户可扫描的报告结构，不修改状态、顺序或结论。
 */
export function buildSingleRecordQcPresentation(
  items: SingleRecordQcResultItem[] | undefined | null,
): SingleRecordQcResultPresentation {
  const sourceItems = items || []
  const ruleIds = new Set<string>()
  sourceItems.forEach((item) => {
    const ruleId = text(item.rule_id).toUpperCase()
    if (!ruleId) {
      throw new Error('单病历质控结果缺少规则身份')
    }
    if (ruleIds.has(ruleId)) {
      throw new Error(`单病历质控结果存在重复规则：${ruleId}`)
    }
    ruleIds.add(ruleId)
  })

  const viewItems = buildSingleRecordQcResultItems(sourceItems)
  const nonCompliantItems = viewItems.filter(
    (item) => resolveSingleRecordQcReportTab(item) === 'non_compliant',
  )
  const dataGapItems = viewItems.filter(
    (item) => resolveSingleRecordQcReportTab(item) === 'data_gap',
  )
  const uncertainItems = viewItems.filter(
    (item) => resolveSingleRecordQcReportTab(item) === 'uncertain',
  )
  const compliantItems = viewItems.filter(
    (item) => resolveSingleRecordQcReportTab(item) === 'compliant',
  )
  const notApplicableItems = viewItems.filter(
    (item) => resolveSingleRecordQcReportTab(item) === 'not_applicable',
  )
  const technicalErrorCount = viewItems.filter((item) => item.status === 'technical_error').length

  return {
    counts: {
      nonCompliant: nonCompliantItems.length,
      dataGap: dataGapItems.length,
      uncertain: uncertainItems.length,
      notApplicable: notApplicableItems.length,
      compliant: compliantItems.length,
      technicalError: technicalErrorCount,
      other:
        viewItems.length -
        nonCompliantItems.length -
        dataGapItems.length -
        uncertainItems.length -
        compliantItems.length -
        notApplicableItems.length -
        technicalErrorCount,
    },
    sectionsByTab: {
      non_compliant: groupSingleRecordQcResultItems(nonCompliantItems),
      data_gap: groupSingleRecordQcResultItems(dataGapItems),
      uncertain: groupSingleRecordQcResultItems(uncertainItems),
      compliant: groupSingleRecordQcResultItems(compliantItems),
      not_applicable: groupSingleRecordQcResultItems(notApplicableItems),
      all: groupSingleRecordQcResultItems(viewItems),
    },
  }
}

export function buildSingleRecordQcStatusSummary(
  items: SingleRecordQcResultViewItem[],
): SingleRecordQcStatusSummary[] {
  const order: Array<{ key: string; label: string; tone: SingleRecordQcResultTone }> = [
    { key: 'danger', label: '确定问题', tone: 'danger' },
    { key: 'warning', label: '待处理', tone: 'warning' },
    { key: 'neutral', label: '不适用', tone: 'neutral' },
    { key: 'success', label: '合规', tone: 'success' },
  ]
  return order
    .map((item) => ({
      ...item,
      count: items.filter((result) => result.tone === item.tone).length,
    }))
    .filter((item) => item.count > 0)
}

export function resolveSingleRecordQcResultTab(
  item: Pick<SingleRecordQcResultViewItem, 'status'>,
): Exclude<SingleRecordQcResultTabKey, 'all'> {
  if (item.status === 'non_compliant') return 'non_compliant'
  if (item.status === 'not_applicable') return 'not_applicable'
  if (item.status === 'compliant') return 'compliant'
  return 'pending'
}

export function buildSingleRecordQcStatusTabs(
  items: SingleRecordQcResultViewItem[],
): SingleRecordQcStatusTab[] {
  return [
    {
      key: 'non_compliant',
      label: '确定问题',
      count: items.filter((item) => resolveSingleRecordQcResultTab(item) === 'non_compliant')
        .length,
    },
    {
      key: 'pending',
      label: '待处理',
      count: items.filter((item) => resolveSingleRecordQcResultTab(item) === 'pending').length,
    },
    {
      key: 'not_applicable',
      label: '不适用',
      count: items.filter((item) => resolveSingleRecordQcResultTab(item) === 'not_applicable')
        .length,
    },
    {
      key: 'compliant',
      label: '合规',
      count: items.filter((item) => resolveSingleRecordQcResultTab(item) === 'compliant').length,
    },
    { key: 'all', label: '全部', count: items.length },
  ]
}
