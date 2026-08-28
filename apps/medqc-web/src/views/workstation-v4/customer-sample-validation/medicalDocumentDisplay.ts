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

const GENERIC_SECTION_LABELS = new Set(['正文', '记录内容', '文书内容', 'content', 'text'])

function normalizeSectionText(value: string): string {
  return value.normalize('NFKC').replace(/\s+/gu, '').trim()
}

function isGenericSectionLabel(value: string): boolean {
  return GENERIC_SECTION_LABELS.has(value.trim().toLowerCase())
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
