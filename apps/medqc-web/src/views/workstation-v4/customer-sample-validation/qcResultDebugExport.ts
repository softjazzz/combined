import type { SingleRecordQcEvidence, SingleRecordQcResultItem } from './single-record-result-model'
import { sanitizeQcDebugPayload } from './qcDebugSanitizer'

const DEBUG_SCHEMA = 'medqc-qc-debug-v4-redacted-minimal'
type QcDebugResultItem = SingleRecordQcResultItem & { displayStatus?: string }

export interface QcResultDebugContext {
  instituteId?: string
  patientId?: string
  visitId?: string
  recordId?: string
  recordRef?: string
  jobId?: string
  ruleSetKey?: string
  ruleSetVersion?: string
  resultSchemaVersion?: string
  expectedRuleCount?: number
  resultRuleCount?: number
  isComplete?: boolean
  missingRuleIds?: string[]
  conflictingRuleIds?: string[]
  patientName?: string
}

function text(value: unknown): string {
  return String(value ?? '').trim()
}

function appendTextSection(lines: string[], label: string, value: unknown) {
  const normalized = text(value)
  if (!normalized) return
  lines.push(`${label}：${normalized}`)
}

function appendJsonSection(lines: string[], label: string, value: unknown) {
  if (value === undefined || value === null) return
  if (Array.isArray(value) && value.length === 0) return
  if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0) return
  lines.push('', `${label}：`, JSON.stringify(value, null, 2))
}

function appendEvidenceField(lines: string[], label: string, value: unknown) {
  const normalized = text(value)
  if (normalized) lines.push(`- ${label}：${normalized}`)
}

function appendEvidenceSections(lines: string[], evidence: SingleRecordQcEvidence[] | undefined) {
  if (!Array.isArray(evidence) || evidence.length === 0) return
  lines.push('', `关键证据 evidence（${evidence.length} 条）：`)
  evidence.forEach((item, index) => {
    lines.push(`### 证据 ${index + 1}`)
    appendEvidenceField(lines, '来源文书', item.source_label)
    appendEvidenceField(lines, '来源类型', item.source_type)
    appendEvidenceField(lines, '安全引用', item.source_ref)
    appendEvidenceField(lines, '记录时间', item.record_time)
    appendEvidenceField(lines, '字段路径', item.field_path)
    appendEvidenceField(lines, '摘要类型', item.excerpt_kind)
    appendEvidenceField(lines, '关键原文摘要', item.evidence_excerpt)
  })
}

function appendContext(lines: string[], context: QcResultDebugContext | undefined) {
  if (!context) return
  lines.push('', '## 任务与病历上下文')
  appendTextSection(lines, '机构ID', context.instituteId)
  appendTextSection(lines, '患者ID', context.patientId)
  appendTextSection(lines, '就诊ID', context.visitId)
  appendTextSection(lines, '病历ID', context.recordId)
  appendTextSection(lines, '病历安全引用', context.recordRef)
  appendTextSection(lines, '质控任务ID', context.jobId)
  appendTextSection(lines, '规则集', context.ruleSetKey)
  appendTextSection(lines, '规则集版本', context.ruleSetVersion)
  appendTextSection(lines, '结果结构版本', context.resultSchemaVersion)
  if (typeof context.expectedRuleCount === 'number') {
    lines.push(`预期规则数：${context.expectedRuleCount}`)
  }
  if (typeof context.resultRuleCount === 'number') {
    lines.push(`实际结果数：${context.resultRuleCount}`)
  }
  if (typeof context.isComplete === 'boolean') {
    lines.push(`结果完整性：${context.isComplete ? '完整' : '不完整'}`)
  }
  appendJsonSection(lines, '缺失规则', context.missingRuleIds)
  appendJsonSection(lines, '冲突规则', context.conflictingRuleIds)
}

function appendStatusSummary(lines: string[], items: QcDebugResultItem[]) {
  const counts = new Map<string, number>()
  items.forEach((item) => {
    const status = text(item.status) || 'unknown'
    counts.set(status, (counts.get(status) || 0) + 1)
  })
  if (!counts.size) return
  lines.push('', '状态分布：')
  Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .forEach(([status, count]) => lines.push(`- ${status}：${count}`))
}

function buildRuleDebugSection(item: QcDebugResultItem, index: number): string {
  const lines = [`## ${index + 1}. ${text(item.rule_id) || '未知规则'} ${text(item.rule_name)}`]
  appendTextSection(lines, '适用文书', item.source_document)
  appendTextSection(lines, '质控点说明', item.qc_point)
  appendTextSection(lines, '客户展示状态', item.displayStatus || item.display_status)
  appendTextSection(lines, '原始状态', item.status)
  appendTextSection(lines, '原因码', item.reason_code)
  appendTextSection(lines, '质控结论', item.conclusion)
  appendTextSection(lines, '完整判定说明', item.detail)
  appendTextSection(lines, '实际情况', item.actual)
  appendTextSection(lines, '核对标准', item.standard)
  appendTextSection(lines, '处理建议', item.suggestion)
  appendTextSection(lines, '模型分析', item.model_analysis)
  if (
    item.rule_id === 'LX0609-061' &&
    item.customer_display_facts &&
    typeof item.customer_display_facts === 'object'
  ) {
    appendTextSection(
      lines,
      '出院时间来源',
      (item.customer_display_facts as Record<string, unknown>).discharge_time_source,
    )
  }
  appendJsonSection(lines, '受控判定事实 customer_display_facts', item.customer_display_facts)
  appendJsonSection(lines, '受控子结论 criterion_results', item.criterion_results)
  appendJsonSection(lines, '资料缺口 data_gap_details', item.data_gap_details)
  appendEvidenceSections(lines, item.evidence)
  return lines.join('\n')
}

export function buildQcResultDebugText(
  items: QcDebugResultItem[],
  context?: QcResultDebugContext,
): string {
  const sanitized = sanitizeQcDebugPayload(
    { items: Array.isArray(items) ? items : [], context },
    { patientName: context?.patientName },
  )
  const normalizedItems = sanitized.items
  const sanitizedContext = sanitized.context
  const header = [
    '# MedQC 质控调试信息',
    `格式版本：${DEBUG_SCHEMA}`,
    `结果数量：${normalizedItems.length}`,
    '说明：以下内容已脱敏，并按最小必要原则仅保留核对规则状态、判定事实和证据链所需信息。受控事实中的完整原始正文字段和访问凭证不会导出；身份标识已使用临时别名，日期已整体平移但时间间隔保持不变。内容仍包含脱敏后的医疗判定语义，仅限授权调试使用，发送前仍请人工复核。',
  ]
  appendContext(header, sanitizedContext)
  appendStatusSummary(header, normalizedItems)
  const sections = normalizedItems.map(buildRuleDebugSection)
  return [...header, ...sections.map((section) => `\n${section}`)].join('\n').trim()
}

export async function copyQcResultDebugText(value: string): Promise<boolean> {
  if (!value.trim()) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    // Clipboard API 受浏览器权限限制时继续使用兼容回退。
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)
    return copied
  } catch {
    return false
  }
}
