import type { SingleRecordQcResultItem } from './single-record-result-model'

const DEBUG_SCHEMA = 'medqc-qc-debug-v1'
type QcDebugResultItem = SingleRecordQcResultItem & { displayStatus?: string }

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
  appendJsonSection(lines, '受控判定事实 customer_display_facts', item.customer_display_facts)
  appendJsonSection(lines, '受控子结论 criterion_results', item.criterion_results)
  appendJsonSection(lines, '资料缺口 data_gap_details', item.data_gap_details)
  appendJsonSection(lines, '关键证据 evidence', item.evidence)
  return lines.join('\n')
}

export function buildQcResultDebugText(items: QcDebugResultItem[]): string {
  const normalizedItems = Array.isArray(items) ? items : []
  const header = [
    '# MedQC 质控调试信息',
    `格式版本：${DEBUG_SCHEMA}`,
    `结果数量：${normalizedItems.length}`,
    '说明：以下内容来自本次质控保存结果，仅用于核对规则状态、判定事实和证据链。',
  ]
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
