import type { EditableMedicalRecordDocument } from './types'
import { testRecordDocumentTypeOptions } from './syntheticCaseBuilder'
import { parseBackendDateTime } from './recordPresentation'
import { formatPlannedOrderEndTime } from './medicalOrderDisplay'

export type EditableCopyOrderTypeFilter = 'long' | 'temporary'

export type EditableCopyOrderRow = {
  document: EditableMedicalRecordDocument
  orderId: string
  startTime: string
  plannedEndTime: string
  stopTime: string
  orderType: string
  item: string
  status: string
  orderTypeKey: EditableCopyOrderTypeFilter
}

export function isEditableOrderDocument(
  document?: Partial<EditableMedicalRecordDocument> | null,
): boolean {
  const probe = [document?.document_type, document?.title, document?.source_table, document?.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  return (
    probe.includes('order') ||
    probe.includes('医嘱') ||
    probe.includes('长期') ||
    probe.includes('临时')
  )
}

function editableOrderContentLines(document: EditableMedicalRecordDocument): string[] {
  return String(document.content || '')
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean)
}

function resolveEditableOrderKindFromContent(
  document: EditableMedicalRecordDocument,
): EditableCopyOrderTypeFilter | null {
  const firstLine = editableOrderContentLines(document)[0] || ''
  const normalized = firstLine.replace(/\s+/gu, '')
  if (/^长期(医嘱)?[:：]?$/u.test(normalized) || /^长期医嘱[:：]/u.test(normalized)) return 'long'
  if (/^临时(医嘱)?[:：]?$/u.test(normalized) || /^临时医嘱[:：]/u.test(normalized))
    return 'temporary'
  return null
}

export function resolveEditableOrderTypeLabel(document: EditableMedicalRecordDocument): string {
  const kindFromContent = resolveEditableOrderKindFromContent(document)
  if (kindFromContent === 'long') return '长期医嘱'
  if (kindFromContent === 'temporary') return '临时医嘱'
  const probe = [document.document_type, document.title, document.source_table, document.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (probe.includes('临时') || probe.includes('temp')) return '临时医嘱'
  if (probe.includes('长期') || probe.includes('long')) return '长期医嘱'
  if (probe.includes('出院')) return '出院医嘱'
  if (probe.includes('drug') || probe.includes('药')) return '药品医嘱'
  return '医嘱'
}

export function resolveEditableOrderTypeKey(
  document: EditableMedicalRecordDocument,
): EditableCopyOrderTypeFilter {
  const kindFromContent = resolveEditableOrderKindFromContent(document)
  if (kindFromContent) return kindFromContent
  const label = resolveEditableOrderTypeLabel(document)
  if (label.includes('长期')) return 'long'
  if (label.includes('临时')) return 'temporary'
  const probe = [document.document_type, document.title, document.source_table, document.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (probe.includes('long') || probe.includes('长期')) return 'long'
  return 'temporary'
}

function normalizeEditableOrderTimeText(value?: string, fallback = '-'): string {
  const raw = String(value || '').trim()
  if (!raw) return fallback
  const parsed = parseBackendDateTime(raw)
  if (Number.isNaN(parsed.getTime())) return raw.replace('T', ' ').slice(0, 19)
  return parsed.toISOString().slice(0, 19).replace('T', ' ')
}

function resolveEditableOrderStartTimeValue(document: EditableMedicalRecordDocument): string {
  return document.order_start_time || document.record_time || document.submit_time || ''
}

function resolveEditableOrderStopTimeValue(document: EditableMedicalRecordDocument): string {
  return document.order_stop_time || ''
}

function editableOrderTimeValue(document: EditableMedicalRecordDocument): number {
  const parsed = parseBackendDateTime(resolveEditableOrderStartTimeValue(document))
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime()
}

export function compareEditableOrderDocumentByTimeDesc(
  left: EditableMedicalRecordDocument,
  right: EditableMedicalRecordDocument,
): number {
  return editableOrderTimeValue(right) - editableOrderTimeValue(left)
}

function stripEditableOrderPrefix(value: string): string {
  return value
    .replace(/^(长期医嘱|临时医嘱|医嘱记录|医嘱)[:：]\s*/u, '')
    .replace(/^(长期|临时)(医嘱)?[:：]?\s*/u, '')
    .trim()
}

function isEditableOrderKindLine(value: string): boolean {
  return /^(长期|临时)(医嘱)?[:：]?$/u.test(value.replace(/\s+/gu, ''))
}

function isEditableOrderStatusLine(value: string): boolean {
  return /^(新开|开立|停止|停用|作废|撤销|执行中|已执行|未执行)$/u.test(value.trim())
}

function isEditableOrderCategoryLine(value: string): boolean {
  return /^(用药|药品|护理|治疗|处置|检查|检验|手术|麻醉|输血|会诊|康复|膳食|嘱托|其他)$/u.test(
    value.trim(),
  )
}

function resolveEditableOrderCategoryText(document: EditableMedicalRecordDocument): string {
  const category = String(document.order_category || '').trim()
  if (category) return category === '药品' ? '用药' : category
  const lines = editableOrderContentLines(document)
    .map((line) => stripEditableOrderPrefix(line))
    .filter(Boolean)
  const explicitCategory = lines.find((line) => isEditableOrderCategoryLine(line))
  if (explicitCategory) return explicitCategory === '药品' ? '用药' : explicitCategory

  const probe = [
    document.document_type,
    document.title,
    document.source_table,
    document.key,
    document.content,
  ]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (probe.includes('drug') || probe.includes('药')) return '用药'
  if (probe.includes('nursing') || probe.includes('护理')) return '护理'
  if (probe.includes('blood') || probe.includes('输血')) return '输血'
  if (probe.includes('exam') || probe.includes('检查')) return '检查'
  if (probe.includes('lab') || probe.includes('检验')) return '检验'
  if (probe.includes('surg') || probe.includes('手术')) return '手术'
  return '医嘱'
}

function resolveEditableOrderItemText(document: EditableMedicalRecordDocument): string {
  if (document.order_item?.trim()) return document.order_item.trim()
  const lines = editableOrderContentLines(document)
    .map((line) => stripEditableOrderPrefix(line))
    .filter(
      (line) => Boolean(line) && !isEditableOrderKindLine(line) && !isEditableOrderStatusLine(line),
    )
  const category = lines.find((line) => isEditableOrderCategoryLine(line))
  const candidateLines =
    category && lines.length > 1 ? lines.filter((line) => line !== category) : lines
  const firstLine =
    candidateLines[0] || stripEditableOrderPrefix(document.title || document.document_type || '')
  if (!firstLine || isEditableOrderKindLine(firstLine)) return '-'
  return firstLine.replace(/\s+/gu, ' ').slice(0, 80)
}

function resolveEditableOrderStatus(document: EditableMedicalRecordDocument): string {
  if (document.enabled === false) return '不写入'
  if (document.order_status?.trim()) return document.order_status.trim()
  const lines = editableOrderContentLines(document).map((line) => stripEditableOrderPrefix(line))
  const explicitStatus = lines.find((line) => isEditableOrderStatusLine(line))
  if (explicitStatus) return explicitStatus
  const text = `${document.title || ''} ${document.content || ''}`.toLowerCase()
  if (text.includes('停止') || text.includes('停用') || text.includes('停')) return '停止'
  if (text.includes('新开') || text.includes('开立') || document.is_new) return '新开'
  if (text.includes('执行')) return '执行中'
  return '新开'
}

export function parseEditableOrderRow(
  document: EditableMedicalRecordDocument,
): EditableCopyOrderRow {
  const orderTypeKey = resolveEditableOrderTypeKey(document)
  return {
    document,
    orderId: document.order_id?.trim() || '',
    startTime: normalizeEditableOrderTimeText(resolveEditableOrderStartTimeValue(document)),
    stopTime: normalizeEditableOrderTimeText(resolveEditableOrderStopTimeValue(document), ''),
    plannedEndTime: formatPlannedOrderEndTime(document.order_planned_end_time),
    orderType: resolveEditableOrderCategoryText(document),
    item: resolveEditableOrderItemText(document),
    status: resolveEditableOrderStatus(document),
    orderTypeKey,
  }
}

export function editableDocumentTypeLabel(documentType: string): string {
  return (
    testRecordDocumentTypeOptions.find((option) => option.value === documentType)?.label ||
    documentType ||
    '文书'
  )
}

export function editableCopyDocumentGroupKey(document: EditableMedicalRecordDocument): string {
  const probe = `${document.document_type || ''} ${document.title || ''}`.toLowerCase()
  if (isEditableOrderDocument(document)) return 'order'
  if (probe.includes('入院')) return 'admission'
  if (probe.includes('病程') || probe.includes('查房') || probe.includes('course')) return 'course'
  if (
    probe.includes('手术') ||
    probe.includes('麻醉') ||
    probe.includes('surg') ||
    probe.includes('anesthesia')
  ) {
    return 'surgery'
  }
  if (
    probe.includes('检查') ||
    probe.includes('检验') ||
    probe.includes('报告') ||
    probe.includes('影像') ||
    probe.includes('培养') ||
    probe.includes('lab') ||
    probe.includes('exam')
  ) {
    return 'exam_lab'
  }
  return 'other'
}

export function editableCopyDocumentGroupLabel(key: string): string {
  const labels: Record<string, string> = {
    admission: '入院记录',
    course: '病程记录',
    order: '医嘱',
    surgery: '手术麻醉',
    exam_lab: '检查检验',
    other: '其他文书',
  }
  return labels[key] || '其他文书'
}

export function formatEditableCopyDocumentMeta(document: EditableMedicalRecordDocument): string {
  const timeText = document.record_time || '未返回时间'
  const lengthText = `${String(document.content || '').trim().length}字`
  const stateText =
    document.enabled === false ? '已从副本删除' : document.is_new ? '新增' : '源文书'
  return `${timeText} · ${lengthText} · ${stateText}`
}

export function formatEditableCopyOrderGroupMeta(
  documents: EditableMedicalRecordDocument[],
): string {
  const longCount = documents.filter(
    (document) => resolveEditableOrderTypeKey(document) === 'long',
  ).length
  const temporaryCount = documents.filter(
    (document) => resolveEditableOrderTypeKey(document) === 'temporary',
  ).length
  return `长期 ${longCount} 条 · 临时 ${temporaryCount} 条`
}
