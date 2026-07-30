import {
  hasActionableCustomerExplanation,
  normalizeCustomerQcResult,
} from '@/domain/customer-qc/result-normalizer'
import type { RawCustomerQcResult } from '@/domain/customer-qc/result-model'

/** 兼容现有调用点；只声明统一解释器真正读取的边界字段。 */
export interface CustomerQcDisplaySource {
  rule_id?: unknown
  rule_code?: unknown
  qc_point_id?: unknown
  result_status?: unknown
  status?: unknown
  canonical_status?: unknown
  display_status?: unknown
  reason_code?: unknown
  criterion_results?: unknown
  evidence_problem_type?: unknown
  schema_version?: unknown
  explanation_contract_version?: unknown
  conclusion?: unknown
  findings?: unknown
  detail?: unknown
  requirement?: unknown
  suggestion?: unknown
  customer_display_facts?: unknown
  metadata?: unknown
  decision?: unknown
}

export interface CustomerQcDisplayModel {
  /** 仅当结果具备完整受控解释时，详情页才替换旧版通用卡片。 */
  isEnhanced: boolean
  conclusion: string
  detail: string
  requirement: string
  actualValue: string
  evidenceSource: string
  suggestion: string
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function cleanSafeText(value: unknown): string {
  const text = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : ''
  if (!text || /(?:prompt|raw_response|embedding|medical_text|evidence_payload)/i.test(text)) {
    return ''
  }
  return text
}

function normalizeSourceShape(source: CustomerQcDisplaySource): RawCustomerQcResult {
  const topLevelFacts = asRecord(source.customer_display_facts)
  let customerDisplayFacts: Record<string, unknown> | undefined = Object.keys(topLevelFacts).length
    ? topLevelFacts
    : undefined
  const metadata = asRecord(source.metadata)
  const decision = asRecord(source.decision)
  if (!customerDisplayFacts) {
    const legacyFacts = asRecord(
      metadata.customer_display_facts ||
        decision.customer_display_facts ||
        metadata.display_facts ||
        decision.display_facts,
    )
    const failureKind = cleanSafeText(legacyFacts.failure_kind)
    const diagnosticRelationState =
      failureKind === 'complaint_primary_diagnosis_mismatch'
        ? 'mismatch'
        : failureKind === 'complaint_lacks_diagnostic_clue'
          ? 'unsupported'
          : undefined
    customerDisplayFacts = Object.keys(legacyFacts).length
      ? {
          ...legacyFacts,
          ...(diagnosticRelationState
            ? { diagnostic_relation_state: diagnosticRelationState }
            : {}),
        }
      : undefined
  }
  return {
    rule_id: source.rule_id,
    rule_code: source.rule_code,
    qc_point_id: source.qc_point_id,
    result_status: source.result_status,
    status: source.status,
    canonical_status: source.canonical_status,
    display_status: source.display_status,
    reason_code: source.reason_code,
    criterion_results: source.criterion_results,
    evidence_problem_type: source.evidence_problem_type,
    schema_version: source.schema_version,
    explanation_contract_version: source.explanation_contract_version,
    conclusion: source.conclusion,
    findings: source.findings,
    detail: source.detail,
    requirement: source.requirement,
    suggestion: source.suggestion,
    customer_display_facts: customerDisplayFacts,
  }
}

/** 将运行结果适配为旧组件所需形状，不再维护第二套规则解释逻辑。 */
export function buildCustomerQcDisplayModel(
  source: CustomerQcDisplaySource,
): CustomerQcDisplayModel {
  const safeSource = normalizeSourceShape(source)
  const normalized = normalizeCustomerQcResult(safeSource)
  const isEnhanced = hasActionableCustomerExplanation(safeSource)
  if (!isEnhanced) {
    return {
      isEnhanced: false,
      conclusion: cleanSafeText(source.conclusion || source.findings) || normalized.display.summary,
      detail: '',
      requirement: '',
      actualValue: '',
      evidenceSource: '',
      suggestion: cleanSafeText(source.suggestion) || normalized.display.suggestion,
    }
  }
  return {
    isEnhanced: true,
    conclusion: normalized.display.summary,
    detail: normalized.display.detail || '',
    requirement: normalized.display.requirement || '',
    actualValue: normalized.display.actualValue || '',
    evidenceSource: normalized.display.evidenceSources.map((item) => item.label).join('、'),
    suggestion: normalized.display.suggestion,
  }
}
