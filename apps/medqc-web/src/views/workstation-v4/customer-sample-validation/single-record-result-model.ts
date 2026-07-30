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
  rule_id: string
  rule_name: string
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
    displayStatus: text(item.display_status) || presentation.label,
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
    { key: 'all', label: '全部', count: items.length },
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
  ]
}
