import type { DocItem } from '../types'

export const DOC_TYPE_LABELS: Record<string, string> = {
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  consultation_record: '会诊记录',
  surgery_record: '手术记录',
  postsurg_firstcourse_record: '术后首次病程记录',
  rescue_record: '抢救记录',
  transfer_in_record: '转入记录',
  transfer_out_record: '转出记录',
  nursing_record: '护理记录',
  discharge_record: '出院记录',
}

export function normalizeDocTitle(value: string | null | undefined): string {
  return String(value || '').trim()
}

export function parseDocSortTime(value: string | null | undefined): number {
  if (!value) return Number.POSITIVE_INFINITY
  const normalized = value.endsWith('Z') ? value : value.replace(' ', 'T')
  const ts = Date.parse(normalized)
  return Number.isFinite(ts) ? ts : Number.POSITIVE_INFINITY
}

export function formatDocSortTime(value: string | null | undefined): string {
  if (!value) return ''
  const normalized = value.endsWith('Z') ? value : value.replace(' ', 'T')
  const date = new Date(normalized)
  if (!Number.isNaN(date.getTime())) {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
    const parts = formatter.formatToParts(date)
    const get = (type: Intl.DateTimeFormatPartTypes) =>
      parts.find((part) => part.type === type)?.value || ''
    return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
  }
  return value
    .replace('T', ' ')
    .replace(/\.\d+$/, '')
    .replace(/([+-]\d{2}:?\d{2}|Z)$/i, '')
    .trim()
}

export function resolveDocBaseTitle(
  doc: Pick<DocItem, 'document_title' | 'label' | 'type'>,
): string {
  return (
    normalizeDocTitle(doc.document_title) ||
    normalizeDocTitle(doc.label) ||
    DOC_TYPE_LABELS[doc.type] ||
    '病历文书'
  )
}

export function resolveDocDisplayTitle(
  doc: Pick<DocItem, 'document_title' | 'label' | 'type' | 'sort_time'>,
  includeTime = false,
): string {
  const title = resolveDocBaseTitle(doc)
  const time = formatDocSortTime(doc.sort_time)
  if (includeTime && time) return `${time} ${title}`
  return title
}
