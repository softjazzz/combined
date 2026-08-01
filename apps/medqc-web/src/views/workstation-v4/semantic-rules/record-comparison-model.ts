import { normalizeCustomerQcResult } from '@/domain/customer-qc/result-normalizer'
import type { RawCustomerQcResult } from '@/domain/customer-qc/result-model'
import type {
  QCRecordCompareEvidence,
  QCRecordCompareIssue,
  SichuanBatchIssueItem,
  SichuanBatchJob,
  SichuanBatchSafeEvidenceRef,
} from '@/views/workstation-v4/semantic-rules/types'

export interface RecordComparisonScope {
  visitId?: string
  recordId?: string
  recordRef?: string
}

function normalizeStatus(value?: string): string {
  const status = String(value || '').trim().toLowerCase()
  if (status === 'technical_error_internal' || status === 'error') return 'technical_error'
  if (status === 'unsupported' || status === 'not_run') return 'not_executed'
  if (status === 'data_quality_gap') return 'data_gap'
  if (status === 'needs_manual_review') return 'ai_suggested_non_compliant'
  return status
}

function resolveStatus(item: SichuanBatchIssueItem): string {
  const isLuxian = String(item.rule_id || item.rule_code || '').toUpperCase().startsWith('LX0609-')
  return normalizeStatus(
    isLuxian
      ? item.status || item.canonical_status || item.result_status || item.display_status
      : item.result_status || item.status || item.canonical_status || item.display_status,
  )
}

function resolveStatusText(status: string): string {
  const labels: Record<string, string> = {
    non_compliant: '不合规',
    ai_suggested_non_compliant: 'AI判断：疑似问题',
    uncertain: 'AI判断',
    ai_suggested_compliant: 'AI判断：未见问题',
    not_applicable: '不适用',
    data_gap: '数据不足',
    not_executed: '未执行',
    technical_error: '技术异常',
    compliant: '合规',
  }
  return labels[status] || '结果项'
}

function resolveResultKindText(status: string): string {
  const labels: Record<string, string> = {
    non_compliant: '确定问题',
    ai_suggested_non_compliant: 'AI判断',
    ai_suggested_compliant: 'AI未见问题',
    technical_error: '技术异常',
    data_gap: '数据不足',
    uncertain: 'AI判断',
    not_executed: '未执行',
    not_applicable: '不适用',
    compliant: '合规',
  }
  return labels[status] || '结果项'
}

function isSafeEvidenceRef(value: unknown): value is SichuanBatchSafeEvidenceRef {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const evidence = value as Record<string, unknown>
  return (
    typeof evidence.source_type === 'string'
    && evidence.source_type.trim().length > 0
    && typeof evidence.source_ref === 'string'
    && /^[a-z0-9][a-z0-9:_-]{1,127}$/i.test(evidence.source_ref.trim())
  )
}

function resolveEvidenceSourceLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    admission_record: '入院记录',
    consultation_record: '会诊记录',
    daily_course_record: '日常病程记录',
    superior_round_record: '上级医师查房记录',
    surgery_record: '手术记录',
    presurg_summary: '术前小结',
    consent_form: '手术知情同意书',
    surgery_inform_consent: '手术知情同意书',
    inpat_order: '住院医嘱',
    medical_order: '医嘱',
    exam_report: '检查报告',
    lab_report: '检验报告',
  }
  return labels[sourceType.trim().toLowerCase()] || '相关文书'
}

function resolveControlledEvidenceFieldPath(
  ruleId: string,
  sourceType: string,
  normalizedFieldPath?: string,
) {
  if (normalizedFieldPath) return normalizedFieldPath
  // 018 的安全文书引用仅指向入院记录；主诉是该规则唯一允许展示的原文子段。
  // 这是前端授权态定位，不会把正文写回持久化质控结果。
  if (
    ruleId.trim().toUpperCase() === 'LX0609-018' &&
    sourceType.trim().toLowerCase() === 'admission_record'
  ) {
    return 'chief_complaint'
  }
  return undefined
}

function buildEvidence(item: SichuanBatchIssueItem, key: string): QCRecordCompareEvidence[] {
  const normalized = normalizeCustomerQcResult(item as unknown as RawCustomerQcResult)
  const ruleId = String(item.rule_id || item.rule_code || '')
  const seenRefs = new Set<string>()
  const refs = (Array.isArray(item.evidence) ? item.evidence.filter(isSafeEvidenceRef) : [])
    .filter((evidence) => {
      // 同一受控文书引用可能在聚合后重复出现；只合并完全相同的
      // “来源类型 + 安全引用”，不能按标题合并不同文书。
      const identity = `${evidence.source_type.trim().toLowerCase()}|${evidence.source_ref.trim()}`
      if (seenRefs.has(identity)) return false
      seenRefs.add(identity)
      return true
    })
  if (refs.length) {
    return refs.slice(0, 6).map((evidence, index) => ({
      key: `${key}-evidence-${index}`,
      // source_ref 是服务端授权文书的精确、安全引用；不能伪装成原文摘录。
      source_ref: evidence.source_ref.trim(),
      source_document_type: evidence.source_type,
      source_table: evidence.source_type,
      source_document_name: resolveEvidenceSourceLabel(evidence.source_type),
      section_field_path: resolveControlledEvidenceFieldPath(
        ruleId,
        evidence.source_type,
        normalized.display.evidenceSources.find(
          (source) => source.kind.trim().toLowerCase() === evidence.source_type.trim().toLowerCase(),
        )?.fieldPath,
      ),
      quote: '',
    }))
  }
  return normalized.display.evidenceSources.map((source, index) => ({
    key: `${key}-controlled-evidence-${index}`,
    source_document_type: source.kind,
    source_document_name: source.label,
    section_field_path: source.fieldPath,
    quote: '',
  }))
}

function matchesScope(item: SichuanBatchIssueItem, scope: RecordComparisonScope): boolean {
  const expected = new Set(
    [scope.visitId, scope.recordId, scope.recordRef]
      .map((value) => String(value || '').trim())
      .filter(Boolean),
  )
  if (!expected.size) return false
  return [item.visit_id, item.record_id, item.record_ref]
    .map((value) => String(value || '').trim())
    .some((value) => expected.has(value))
}

function collectJobItems(job: SichuanBatchJob): SichuanBatchIssueItem[] {
  if (Array.isArray(job.items) && job.items.length) return job.items
  const seen = new Set<string>()
  return (job.rule_results || [])
    .flatMap((ruleResult) => ruleResult.items || [])
    .filter((item) => {
      const key = [
        item.record_ref || item.record_id || item.visit_id || '',
        item.rule_id || item.rule_code || '',
        resolveStatus(item),
        item.reason_code || '',
      ].join('|')
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

/**
 * 单病历对照页的唯一结果视图模型。只接收任务内已保存结果，
 * 不做跨病历回退，不根据正文猜测来源。
 */
export function buildRecordComparisonIssues(
  job: SichuanBatchJob,
  scope: RecordComparisonScope,
): QCRecordCompareIssue[] {
  return collectJobItems(job)
    .filter((item) => matchesScope(item, scope))
    .map((item, index) => {
      const key = [
        item.rule_job_id || '',
        item.rule_id || item.rule_code || '',
        item.record_ref || item.record_id || item.visit_id || '',
        item.trace_id || index,
      ].join('|')
      const status = resolveStatus(item)
      const normalized = normalizeCustomerQcResult(item as unknown as RawCustomerQcResult)
      return {
        key,
        rule_code: String(item.rule_code || item.rule_id || '未知规则'),
        rule_name: String(item.rule_name || '未知质控点'),
        status,
        status_text: resolveStatusText(status),
        result_kind_text: resolveResultKindText(status),
        conclusion: item.findings || item.conclusion || '未返回结论',
        summary: normalized.display.summary,
        detail: normalized.display.detail,
        requirement: normalized.display.requirement,
        actual_value: normalized.display.actualValue,
        suggestion: normalized.display.suggestion,
        target_document_type: String(item.target_document_type || item.document_type || ''),
        evidences: buildEvidence(item, key),
      }
    })
}
