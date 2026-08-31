import type { CustomerQcDecisionStatus, CustomerQcEvidenceAvailability } from './result-model'

export interface CustomerQcStatusPresentation {
  label: string
  tone: 'success' | 'danger' | 'warning' | 'muted' | 'info'
}

export interface CustomerQcNotExecutedPresentation {
  status: 'not_executed'
  summary: string
  detail: string
  suggestion: string
}

const STATUS_MAP: Record<string, CustomerQcDecisionStatus> = {
  compliant: 'compliant',
  pass: 'compliant',
  合规: 'compliant',
  non_compliant: 'non_compliant',
  noncompliant: 'non_compliant',
  fail: 'non_compliant',
  defect: 'non_compliant',
  不合规: 'non_compliant',
  not_applicable: 'not_applicable',
  notapplicable: 'not_applicable',
  na: 'not_applicable',
  不适用: 'not_applicable',
  data_gap: 'data_gap',
  data_insufficient: 'data_gap',
  insufficient_data: 'data_gap',
  数据不足: 'data_gap',
  technical_error: 'technical_error',
  error: 'technical_error',
  evaluation_unknown: 'evaluation_unknown',
  uncertain: 'evaluation_unknown',
  unknown: 'evaluation_unknown',
  needs_review: 'evaluation_unknown',
  ai_suggested_non_compliant: 'evaluation_unknown',
}

const UNAVAILABLE_EVIDENCE_CODES = new Set([
  'source_unavailable',
  'source_error',
  'source_partial_unproven',
  'unavailable',
  'error',
])

const MISSING_EVIDENCE_CODES = new Set([
  'source_empty',
  'missing_required_document',
  'missing_required_field',
  'empty',
])

const NOT_EXECUTED_STATUS_KEYS = new Set(['not_executed', 'not_run', 'unsupported', '未执行'])

function normalizedKey(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

/** 读取阶段性执行状态；不把未执行结果塞进客户侧临床六态。 */
export function resolveCustomerQcNotExecutedPresentation(
  source: unknown,
): CustomerQcNotExecutedPresentation | undefined {
  const candidates =
    source && typeof source === 'object' && !Array.isArray(source)
      ? (['result_status', 'status', 'canonical_status', 'display_status'] as const).map(
          (field) => (source as Record<string, unknown>)[field],
        )
      : [source]
  const firstStatus = candidates.find((value) => normalizedKey(value))
  if (!NOT_EXECUTED_STATUS_KEYS.has(normalizedKey(firstStatus))) return undefined
  return {
    status: 'not_executed',
    summary: '当前阶段未执行，不纳入正式结论。',
    detail: '该质控点尚未纳入当前执行范围，本次不形成合规、不合规或资料充分性判断。',
    suggestion: '当前无需按缺陷处理；待该质控点纳入执行范围后再进行核对。',
  }
}

/** 将所有候选状态映射到客户侧五态/技术错误，AI 建议态绝不等同于不合规。 */
export function resolveCustomerQcStatus(value: unknown): CustomerQcDecisionStatus {
  return STATUS_MAP[normalizedKey(value)] ?? 'evaluation_unknown'
}

/** 证据可用性与临床结论分离，避免把来源异常错误解释成临床缺陷。 */
export function resolveEvidenceAvailability(
  decisionStatus: CustomerQcDecisionStatus,
  evidenceProblemType: unknown,
): CustomerQcEvidenceAvailability {
  const key = normalizedKey(evidenceProblemType)
  if (UNAVAILABLE_EVIDENCE_CODES.has(key) || decisionStatus === 'technical_error') {
    return 'unavailable'
  }
  if (MISSING_EVIDENCE_CODES.has(key)) {
    return 'missing'
  }
  if (decisionStatus === 'data_gap') {
    return 'unknown'
  }
  return 'available'
}

/** 客户侧状态文案的唯一来源，组件不得自行翻译内部状态枚举。 */
export function resolveCustomerQcStatusPresentation(
  status: CustomerQcDecisionStatus,
): CustomerQcStatusPresentation {
  const presentations: Record<CustomerQcDecisionStatus, CustomerQcStatusPresentation> = {
    compliant: { label: '合规', tone: 'success' },
    non_compliant: { label: '不合规', tone: 'danger' },
    not_applicable: { label: '不适用', tone: 'muted' },
    data_gap: { label: '数据不足', tone: 'warning' },
    evaluation_unknown: { label: '建议确认', tone: 'info' },
    technical_error: { label: '执行异常', tone: 'warning' },
  }
  return presentations[status]
}
