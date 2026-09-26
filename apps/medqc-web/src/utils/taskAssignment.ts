/**
 * 任务分配策略的纯展示辅助：业务错误码文案与分配来源分布。
 * 只搬运后端给出的事实，字段缺失时不补 0、不推断。
 */
import type { TaskApiErrorDetail, TaskAssignReasonCounts } from '@/api/tasks'

export const TASK_ASSIGN_ERROR_CODES = [
  'original_reviewer_unmatched',
  'department_missing',
  'department_unassigned',
  'method_unavailable',
] as const

export type TaskAssignErrorCode = (typeof TASK_ASSIGN_ERROR_CODES)[number]

export function isTaskAssignErrorCode(code: unknown): code is TaskAssignErrorCode {
  return typeof code === 'string' && (TASK_ASSIGN_ERROR_CODES as readonly string[]).includes(code)
}

/** 把分配相关业务错误码转成中文提示；非已知业务码返回 undefined，由调用方沿用原有文案。 */
export function describeTaskAssignError(
  detail: TaskApiErrorDetail | undefined,
  status?: number,
): string | undefined {
  if (!detail || !isTaskAssignErrorCode(detail.code)) return undefined
  const reason = detail.reason || detail.message
  const suffix = reason ? `（${reason}）` : ''
  switch (detail.code) {
    case 'original_reviewer_unmatched':
      if (status !== undefined && status !== 409) return undefined
      return typeof detail.unmatched_count === 'number'
        ? `有 ${detail.unmatched_count} 条病历无原质控员或原质控员不在选定人员中，已拒绝分配。可增选人员或改为“按比例分给选定人员”。`
        : '部分病历无原质控员或原质控员不在选定人员中，已拒绝分配。可增选人员或改为“按比例分给选定人员”。'
    case 'department_missing':
      if (status !== undefined && status !== 409) return undefined
      return '存在缺少科室的病历（历史任务或来源缺科室），无法按科室分配。'
    case 'department_unassigned':
      if (status !== undefined && status !== 409) return undefined
      return detail.departments?.length
        ? `以下科室没有对应科室的受领人：${detail.departments.join('、')}。请增选这些科室的质控员。`
        : '部分科室没有对应科室的受领人，请增选对应科室的质控员。'
    case 'method_unavailable':
      if (status !== undefined && status !== 422) return undefined
      return `该分配方式当前不可用${suffix}`
    default:
      return undefined
  }
}

export interface AssignReasonPart {
  key: keyof TaskAssignReasonCounts
  label: string
  count: number
}

const REASON_LABELS: Array<[keyof TaskAssignReasonCounts, string]> = [
  ['original_reviewer', '原质控员'],
  ['department', '科室'],
  ['ratio_fallback', '按比例补充'],
]

/** 来源分布：只列出后端给出的合法非负整数字段。 */
export function assignReasonParts(counts: TaskAssignReasonCounts | undefined | null): AssignReasonPart[] {
  if (!counts || typeof counts !== 'object') return []
  return REASON_LABELS.flatMap(([key, label]) => {
    const value = counts[key]
    return typeof value === 'number' && Number.isInteger(value) && value >= 0
      ? [{ key, label, count: value }]
      : []
  })
}
