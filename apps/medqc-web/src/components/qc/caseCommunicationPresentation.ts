import type { Communication } from '@/api/caseCommunications'
import type { MqIconName } from '@/components/icons/mqIcons'

export const communicationLabels = { urge: '病历催办', opinion: '质控意见', withdraw: '催办撤回' }
export const communicationStatus = (item: Pick<Communication, 'withdrawn' | 'is_read'>) =>
  item.withdrawn ? '已撤回' : item.is_read ? '已读' : '未读'
export const communicationStatusClass = (item: Pick<Communication, 'withdrawn' | 'is_read'>) =>
  !item.withdrawn && !item.is_read ? 'mq-status--info' : ''
export const communicationIcon = (action: Communication['action']): MqIconName =>
  action === 'withdraw' ? 'history' : action === 'opinion' ? 'doc' : 'task'
export function formatCommunicationTime(value?: string | null) {
  if (!value) return '时间未提供'
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}
