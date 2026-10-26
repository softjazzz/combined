import type { EditableMedicalRecordDocument } from './types'
import { formatDocSortTime } from '../utils/documentDisplay'

export type MedicalOrderTypeKey = 'long' | 'temporary'

export type MedicalOrderRow = {
  document: EditableMedicalRecordDocument
  orderId: string
  startTime: string
  plannedEndTime: string
  stopTime: string
  orderType: string
  item: string
  specification: string
  dosage: string
  frequency: string
  route: string
  quantity: string
  prescribedDoctor: string
  status: string
  orderTypeKey: MedicalOrderTypeKey
}

function contentLines(document: EditableMedicalRecordDocument): string[] {
  return String(document.content || '')
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean)
}

function stripOrderPrefix(value: string): string {
  return value
    .replace(/^(长期医嘱|临时医嘱|医嘱记录|医嘱)[:：]\s*/u, '')
    .replace(/^(长期|临时)(医嘱)?[:：]?\s*/u, '')
    .trim()
}

function isOrderKindLine(value: string): boolean {
  return /^(长期|临时)(医嘱)?[:：]?$/u.test(value.replace(/\s+/gu, ''))
}

function isOrderStatusLine(value: string): boolean {
  return /^(新开|开立|停止|停用|作废|撤销|执行中|已执行|未执行)$/u.test(value.trim())
}

function isOrderCategoryLine(value: string): boolean {
  return /^(用药|药品|护理|治疗|处置|检查|检验|手术|麻醉|输血|会诊|康复|膳食|嘱托|其他)$/u.test(
    value.trim(),
  )
}

function normalizeOrderTime(value?: string, fallback = '-'): string {
  const raw = String(value || '').trim()
  if (!raw) return fallback
  return raw
    .replace('T', ' ')
    .replace(/(?:Z|[+-]\d{2}:?\d{2})$/u, '')
    .slice(0, 19)
}

export function formatPlannedOrderEndTime(value?: string): string {
  const raw = String(value || '').trim()
  if (!raw) return ''
  // 有明确时区的计划时间按医院北京时间显示；无时区值保留来源钟表时间。
  if (/[T ]\d{2}:\d{2}.*(?:Z|[+-]\d{2}:?\d{2})$/iu.test(raw)) return formatDocSortTime(raw)
  return normalizeOrderTime(raw, '')
}

function resolveOrderTypeKey(document: EditableMedicalRecordDocument): MedicalOrderTypeKey {
  const firstLine = contentLines(document)[0]?.replace(/\s+/gu, '') || ''
  if (/^长期(医嘱)?[:：]?/u.test(firstLine)) return 'long'
  if (/^临时(医嘱)?[:：]?/u.test(firstLine)) return 'temporary'
  const probe = [document.document_type, document.title, document.source_table, document.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  return probe.includes('long') || probe.includes('长期') ? 'long' : 'temporary'
}

function resolveOrderCategory(document: EditableMedicalRecordDocument): string {
  const explicit = String(document.order_category || '').trim()
  if (explicit) return explicit === '药品' ? '用药' : explicit
  const categoryFromContent = contentLines(document)
    .map((line) => stripOrderPrefix(line))
    .find((line) => isOrderCategoryLine(line))
  if (categoryFromContent) return categoryFromContent === '药品' ? '用药' : categoryFromContent
  const probe = `${document.document_type || ''} ${document.source_table || ''} ${
    document.title || ''
  } ${document.content || ''}`.toLowerCase()
  if (probe.includes('nursing') || probe.includes('护理')) return '护理'
  if (probe.includes('blood') || probe.includes('输血')) return '输血'
  if (probe.includes('exam') || probe.includes('检查')) return '检查'
  if (probe.includes('lab') || probe.includes('检验')) return '检验'
  if (probe.includes('surg') || probe.includes('手术')) return '手术'
  if (!probe.includes('nondrug') && (probe.includes('drug') || probe.includes('药'))) return '用药'
  return '其他'
}

function resolveOrderItem(document: EditableMedicalRecordDocument): string {
  const explicit = String(document.order_item || '').trim()
  if (explicit) return explicit
  const lines = contentLines(document)
    .map((line) => stripOrderPrefix(line))
    .filter((line) => Boolean(line) && !isOrderKindLine(line) && !isOrderStatusLine(line))
  const category = lines.find((line) => isOrderCategoryLine(line))
  const candidateLines =
    category && lines.length > 1 ? lines.filter((line) => line !== category) : lines
  const firstLine =
    candidateLines[0] || stripOrderPrefix(document.title || document.document_type || '')
  return firstLine ? firstLine.replace(/\s+/gu, ' ').slice(0, 120) : '-'
}

function resolveOrderStatus(document: EditableMedicalRecordDocument): string {
  const explicit = String(document.order_status || '').trim()
  if (explicit) return explicit
  const text = `${document.title || ''} ${document.content || ''}`.toLowerCase()
  if (text.includes('作废')) return '作废'
  if (text.includes('撤销')) return '撤销'
  if (text.includes('停止') || text.includes('停用')) return '停止'
  if (text.includes('已执行')) return '已执行'
  if (text.includes('执行中')) return '执行中'
  return '新开'
}

function resolveOrderField(document: EditableMedicalRecordDocument, ...keys: string[]): string {
  const source = document as unknown as Record<string, unknown>
  for (const key of keys) {
    const value = String(source[key] || '').trim()
    if (value) return value
  }
  return ''
}

function joinOrderValue(value: string, unit: string): string {
  if (value && unit) return `${value}${unit}`
  return value || unit
}

function orderTimeValue(document: EditableMedicalRecordDocument): number {
  const raw = String(
    document.order_start_time || document.record_time || document.submit_time || '',
  ).trim()
  const parsed = Date.parse(raw.includes('T') ? raw : raw.replace(' ', 'T'))
  return Number.isFinite(parsed) ? parsed : 0
}

export function buildMedicalOrderRow(document: EditableMedicalRecordDocument): MedicalOrderRow {
  const dosage = joinOrderValue(
    resolveOrderField(document, 'order_dosage', 'dosage', 'dose', 'single_dose'),
    resolveOrderField(document, 'dose_unit', 'single_dose_unit'),
  )
  const quantity = joinOrderValue(
    resolveOrderField(document, 'order_quantity', 'quantity'),
    resolveOrderField(document, 'quantity_unit'),
  )
  return {
    document,
    orderId: document.order_id?.trim() || '',
    startTime:
      formatPlannedOrderEndTime(
        document.order_start_time || document.record_time || document.submit_time,
      ) || '-',
    stopTime: normalizeOrderTime(document.order_stop_time, ''),
    plannedEndTime: formatPlannedOrderEndTime(document.order_planned_end_time),
    orderType: resolveOrderCategory(document),
    item: resolveOrderItem(document),
    specification: resolveOrderField(
      document,
      'order_specification',
      'specification',
      'drug_specification',
    ),
    dosage,
    frequency: resolveOrderField(document, 'order_frequency', 'drug_frequency', 'frequency'),
    route: resolveOrderField(document, 'order_route', 'drug_apply_method', 'route'),
    quantity,
    prescribedDoctor: resolveOrderField(
      document,
      'order_prescribed_doctor',
      'prescribed_doctor',
      'doctor_name',
    ),
    status: resolveOrderStatus(document),
    orderTypeKey: resolveOrderTypeKey(document),
  }
}

export function compareMedicalOrderByTimeDesc(
  left: EditableMedicalRecordDocument,
  right: EditableMedicalRecordDocument,
): number {
  return orderTimeValue(right) - orderTimeValue(left)
}

export function resolveMedicalOrderTypeKey(
  document: EditableMedicalRecordDocument,
): MedicalOrderTypeKey {
  return resolveOrderTypeKey(document)
}
