import type { EditableMedicalRecordDocument, EditableMedicalRecordSection } from './types'
import {
  resolveMedicalDocumentGroup,
  resolveMedicalDocumentTitle,
  resolveMedicalDocumentTypeLabel,
  type MedicalDocumentGroup,
} from '../utils/medicalDocumentTaxonomy'

export { resolveMedicalDocumentGroup, resolveMedicalDocumentTitle, resolveMedicalDocumentTypeLabel }
export type { MedicalDocumentGroup }

export function resolveMedicalDocumentTime(document: EditableMedicalRecordDocument): string {
  return String(document.record_time || document.submit_time || '').trim()
}

export function resolveMedicalDocumentTimeLabel(document: EditableMedicalRecordDocument): string {
  return document.record_time_source === 'source_submit_time' ||
    (!String(document.record_time || '').trim() && Boolean(document.submit_time?.trim()))
    ? '提交时间'
    : '记录时间'
}

export function formatMedicalDocumentTime(value?: string): string {
  const normalized = String(value || '').trim()
  if (!normalized) return '未返回时间'
  return normalized
    .replace('T', ' ')
    .replace(/(?:Z|[+-]\d{2}:?\d{2})$/u, '')
    .slice(0, 19)
}

export function medicalDocumentHasContent(document: EditableMedicalRecordDocument): boolean {
  if (document.has_content === true) return true
  if (String(document.content || '').trim()) return true
  return Boolean(document.sections?.some((section) => String(section.text || '').trim()))
}

export function isMedicalOrderDocument(document: EditableMedicalRecordDocument): boolean {
  return resolveMedicalDocumentGroup(document).key === 'orders'
}

const GENERIC_SECTION_LABELS = new Set([
  '正文',
  '记录内容',
  '文书内容',
  '基础信息',
  'content',
  'text',
  'recordcontent',
])

function normalizeSectionText(value: string): string {
  return value.normalize('NFKC').replace(/\s+/gu, '').trim()
}

function isGenericSectionLabel(value: string): boolean {
  const normalized = value
    .normalize('NFKC')
    .replace(/[\s_-]+/gu, '')
    .trim()
    .toLowerCase()
  return GENERIC_SECTION_LABELS.has(normalized)
}

/** 去掉源系统在章节正文首行重复输出的章节标题。 */
export function displayMedicalDocumentSectionText(section: EditableMedicalRecordSection): string {
  const text = String(section.text || '').trim()
  if (!text) return '未记录'
  const lines = text.split(/\r?\n/u)
  const normalizeLine = (value: string) => value.replace(/\s+/gu, '').replace(/[：:]+$/u, '')
  if (
    lines.length > 1 &&
    normalizeLine(lines[0] || '') === normalizeLine(String(section.label || ''))
  ) {
    return lines.slice(1).join('\n').trim() || '未记录'
  }
  return text
}

/** 只整理诊断章节的显式字段及编号，不推断主次诊断或改动原始数据。 */
export function formatDiagnosisSection(label: string, text: string): string {
  if (!label.includes('诊断') || !/诊断类型\s*[:：]/u.test(text)) return text
  return text
    .replace(/\s*(诊断类型|第一诊断|主要诊断|主诊断|其他诊断|诊断时间)\s*[:：]\s*/gu, '\n$1：')
    .split('\n')
    .map((line) => {
      if (!/^(第一诊断|主要诊断|主诊断|其他诊断)：/u.test(line)) return line
      // 仅拆分明确的连续编号；不把 L1、L3、L4 或小数当作列表编号。
      const items = line.match(/(?:^|[：\s；;])\d+[.、．](?!\d)/gu)
      if (!items || items.length < 2) return line
      return line.replace(/([：\s；;])(?=\d+[.、．](?!\d))/gu, (separator) =>
        separator === '：' ? '：\n' : '\n',
      )
    })
    .join('\n')
    .trim()
}

/**
 * 源系统可能同时返回结构化章节和“正文”投影；正文相同则属于同一份文书内容。
 * 这里只做展示层去重，不改变文书正文、字段或质控输入。
 */
export function deduplicateMedicalDocumentSections(
  sections: EditableMedicalRecordSection[],
): EditableMedicalRecordSection[] {
  const result: EditableMedicalRecordSection[] = []
  const indexByText = new Map<string, number>()

  sections.forEach((section) => {
    const text = String(section.text || '').trim()
    const signature = normalizeSectionText(text)
    if (!signature) {
      result.push(section)
      return
    }

    const existingIndex = indexByText.get(signature)
    if (existingIndex === undefined) {
      indexByText.set(signature, result.length)
      result.push(section)
      return
    }

    const existing = result[existingIndex]
    if (
      existing &&
      isGenericSectionLabel(String(existing.label || '')) &&
      !isGenericSectionLabel(String(section.label || ''))
    ) {
      result[existingIndex] = section
    }
  })

  return result
}
