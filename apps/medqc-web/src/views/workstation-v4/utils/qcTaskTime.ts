export const QC_TASK_TIME_ZONE = 'Asia/Shanghai'

const taskTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: QC_TASK_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})

// 质控任务持久化使用 UTC，历史值没有时区后缀。
export function parseQcTaskTime(value?: string | Date | null): Date | null {
  if (!value) return null
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value : null
  const text = value.trim().replace(' ', 'T')
  if (!text) return null
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text)
  const date = new Date(hasOffset ? text : `${text}Z`)
  return Number.isFinite(date.getTime()) ? date : null
}

export function shanghaiQcTaskTimeParts(date: Date) {
  return Object.fromEntries(
    taskTimeFormatter.formatToParts(date).map(({ type, value }) => [type, value]),
  )
}

export function formatPaddedQcTaskDateTime(value?: string | Date | null): string {
  if (!value) return '-'
  const date = parseQcTaskTime(value)
  if (!date) return String(value)
  const { year, month, day, hour, minute, second } = shanghaiQcTaskTimeParts(date)
  return `${year}/${month}/${day} ${hour}:${minute}:${second}`
}

export function formatQcTaskDateTime(value?: string | Date | null): string {
  if (!value) return '-'
  const date = parseQcTaskTime(value)
  return date?.toLocaleString('zh-CN', { timeZone: QC_TASK_TIME_ZONE, hourCycle: 'h23' }) ?? String(value)
}
