import type { EditableMedicalRecordDocument } from './types'

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  course_record: '病程记录',
  rescue_record: '抢救记录',
  consultation_record: '会诊记录',
  surgery_record: '手术记录',
  presurg_summary: '术前小结',
  anesthesia_record: '麻醉记录',
  surgery_inform_consent: '手术知情同意书',
  exam_report: '检查报告',
  lab_report: '检验报告',
  pathology_exam_report: '病理检查报告',
  pathology_exam_master: '病理检查申请单',
  medical_order: '医嘱',
  inpat_drug_order: '用药医嘱',
  inpat_nondrug_order: '非药物医嘱',
  discharge_record: '出院记录',
}

export type MedicalDocumentGroup = {
  key: string
  label: string
}

export function resolveMedicalDocumentTypeLabel(value?: string): string {
  const source = String(value || '').trim()
  const normalized = source.toLowerCase().replace(/^cdm[._]/u, '')
  if (!normalized) return ''
  if (DOCUMENT_TYPE_LABELS[normalized]) return DOCUMENT_TYPE_LABELS[normalized]
  const matchedKey = Object.keys(DOCUMENT_TYPE_LABELS)
    .sort((left, right) => right.length - left.length)
    .find((key) => normalized.includes(key))
  if (matchedKey) return DOCUMENT_TYPE_LABELS[matchedKey]
  return /[\u3400-\u9fff]/u.test(source) ? source : ''
}

export function resolveMedicalDocumentTitle(document: EditableMedicalRecordDocument): string {
  return (
    resolveMedicalDocumentTypeLabel(document.title) ||
    resolveMedicalDocumentTypeLabel(document.document_type) ||
    resolveMedicalDocumentTypeLabel(document.source_table) ||
    '未命名文书'
  )
}

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
  const value = `${document.source_table || ''} ${document.document_type || ''} ${
    document.title || ''
  }`.toLowerCase()
  return /(?:^|[\s._-])order|医嘱/u.test(value)
}

export function resolveMedicalDocumentGroup(
  document: EditableMedicalRecordDocument,
): MedicalDocumentGroup {
  const value = `${document.source_table || ''} ${document.document_type || ''} ${
    document.title || ''
  }`.toLowerCase()
  if (/admission|入院|首次病程/u.test(value)) {
    return { key: 'admission', label: '入院与首次病程' }
  }
  if (/daily|superior|senior|course|查房|病程/u.test(value)) {
    return { key: 'course', label: '病程记录' }
  }
  if (/consult|会诊/u.test(value)) return { key: 'consultation', label: '会诊记录' }
  if (/surgery|anesth|手术|麻醉/u.test(value)) {
    return { key: 'surgery', label: '手术麻醉' }
  }
  if (/exam|lab|pathology|检查|检验|病理/u.test(value)) {
    return { key: 'exam-lab', label: '检查检验' }
  }
  if (isMedicalOrderDocument(document)) return { key: 'order', label: '医嘱' }
  if (/discharge|出院/u.test(value)) return { key: 'discharge', label: '出院记录' }
  return { key: 'other', label: '其他文书' }
}
