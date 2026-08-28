import type { EditableMedicalRecordDocument } from './types'
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
