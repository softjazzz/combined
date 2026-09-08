import { buildDiagnosticSummary } from './qcDiagnosticSummary'
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
  options?: { diagnosticPackage?: boolean },
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
  if (!options?.diagnosticPackage) {
    return [...header, ...sections.map((section) => `\n${section}`)].join('\n').trim()
  }
  // 仅选择原调试文本已展示字段，不序列化 API 对象上的其他内部属性。
  const results = normalizedItems.map((item) => ({
    rule_id: item.rule_id,
    rule_name: item.rule_name,
    status: item.status,
    display_status: item.displayStatus || item.display_status,
    reason_code: item.reason_code,
    source_document: item.source_document,
    qc_point: item.qc_point,
    conclusion: item.conclusion,
    detail: item.detail,
    actual: item.actual,
    standard: item.standard,
    suggestion: item.suggestion,
    model_analysis: item.model_analysis,
    customer_display_facts: item.customer_display_facts,
    criterion_results: item.criterion_results,
    data_gap_details: item.data_gap_details,
    evidence: item.evidence?.map((evidence) => ({
      source_type: evidence.source_type,
      source_ref: evidence.source_ref,
      source_label: evidence.source_label,
      record_time: evidence.record_time,
      field_path: evidence.field_path,
      excerpt_kind: evidence.excerpt_kind,
      evidence_excerpt: evidence.evidence_excerpt,
    })),
  }))
  const summary = buildDiagnosticSummary(results, sanitizedContext)
  const payload = {
    schema_version: 'medqc-qc-diagnostic-v1',
    capture_completeness: 'partial',
    replay_capability: 'manual_review',
    missing_components: [
      'execution_inputs',
      'source_read_states',
      'model_requests_and_responses',
      'execution_build_version',
    ],
    context: sanitizedContext
      ? {
          instituteId: sanitizedContext.instituteId,
          patientId: sanitizedContext.patientId,
          visitId: sanitizedContext.visitId,
          recordId: sanitizedContext.recordId,
          recordRef: sanitizedContext.recordRef,
          jobId: sanitizedContext.jobId,
          ruleSetKey: sanitizedContext.ruleSetKey,
          ruleSetVersion: sanitizedContext.ruleSetVersion,
          resultSchemaVersion: sanitizedContext.resultSchemaVersion,
          expectedRuleCount: sanitizedContext.expectedRuleCount,
          resultRuleCount: sanitizedContext.resultRuleCount,
          isComplete: sanitizedContext.isComplete,
          missingRuleIds: sanitizedContext.missingRuleIds,
          conflictingRuleIds: sanitizedContext.conflictingRuleIds,
        }
      : undefined,
    summary,
    results,
  }
  header.push(
    '',
    '## 批量排查索引',
    `本包导出 ${summary.exported_result_count} 条结果，${summary.unique_rule_count} 个不同规则。`,
    summary.scope === 'full_loaded_result'
      ? '导出范围：已加载的完整结果。'
      : '导出范围：部分结果或完整性未知；不能用任务总数代替本包结果数。',
    '采集完整性：受限。未采集当次执行输入、源表读取状态、模型请求响应及执行构建版本，不支持自动回放。',
    '以下为状态与原因码分组，仅帮助定位，不重新判定业务结论。',
  )
  for (const group of summary.reason_groups) {
    header.push(`- ${group.status} / ${group.reason_code}：${group.rule_ids.join('、')}`)
  }
  header.push(
    '',
    '## 已导出证据来源',
    '以下仅统计结果附带的证据，不能据此认定源表已接入、为空或读取完整。',
  )
  for (const source of summary.evidence_sources) {
    header.push(
      `- ${source.source_type}：${source.evidence_count} 条证据，${source.unique_reference_count} 个不同引用；规则 ${source.rule_ids.join('、')}`,
    )
  }
  // JSON 与人工文本复用同一次脱敏，引用一致、日期只平移一次。
  const machine = JSON.stringify(payload, null, 2).replace(/`/g, '\\u0060')
  return [
    ...header,
    ...sections.map((section) => `\n${section}`),
    '',
    '## 机器可读诊断数据',
    '```json',
    machine,
    '```',
  ]
    .join('\n')
    .trim()
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
