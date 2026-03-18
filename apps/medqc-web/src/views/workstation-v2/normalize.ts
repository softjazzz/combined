import type { PatientRecord, QCIssueLike } from './types'

/**
 * 病历记录归一化工具
 * 收敛模板中的字段兜底和 status 判断逻辑
 */

/** 判断状态是否为"有缺陷"（兼容 has_defects 和 warning 两种值） */
export function isDefectStatus(status: string): boolean {
  return status === 'has_defects' || status === 'warning'
}

/** 获取状态的中文标签 */
export function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: '已完成',
    has_defects: '有缺陷',
    warning: '有缺陷',
    processing: '处理中',
    pending: '待处理',
  }
  return map[status] || '待处理'
}

/** 获取状态对应的样式主题色 */
export function getStatusTheme(status: string): 'emerald' | 'rose' | 'blue' | 'slate' {
  if (status === 'completed') return 'emerald'
  if (isDefectStatus(status)) return 'rose'
  if (status === 'processing') return 'blue'
  return 'slate'
}

/** 解析 visitId —— 兼容后端返回 visitId 或直接用 id */
export function resolveVisitId(record: PatientRecord): string {
  return (record as any).visitId || record.id
}

/** 归一化缺陷/质控问题，确保 id 字段存在 */
export function normalizeDefect(raw: QCIssueLike, index: number): QCIssueLike & { id: string } {
  return {
    ...raw,
    id: (raw as any).id || `defect-${index}`,
  }
}
