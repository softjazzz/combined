import dayjs from 'dayjs'

/**
 * 抽查任务的场景病例范围（与后端 validate_scene_case_scope 同一合同）。
 * 运行 = 当前在院；终末 = 期间出院（终末口径 B，2026-09-30：归档状态未核验）。
 */
export type TaskCaseScope = 'active' | 'discharged'

const SCENE_CASE_SCOPE: Record<string, TaskCaseScope> = {
  running: 'active',
  final: 'discharged',
}

export const CASE_SCOPE_LABELS: Record<TaskCaseScope, string> = {
  active: '当前在院',
  discharged: '已出院（未核验归档）',
}

/** 该场景新建任务必须选择的病例范围；门急诊等场景没有病例范围。 */
export function sceneCaseScope(scene: string | null | undefined): TaskCaseScope | undefined {
  return scene ? SCENE_CASE_SCOPE[scene] : undefined
}

export function caseScopeLabel(scope: unknown): string {
  return scope === 'active' || scope === 'discharged' ? CASE_SCOPE_LABELS[scope] : ''
}

export const MAX_DISCHARGE_WINDOW_DAYS = 31

function hospitalToday() {
  return dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))
}

function validDate(value: string | null | undefined): value is string {
  return (
    !!value &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    dayjs(value).isValid() &&
    dayjs(value).format('YYYY-MM-DD') === value
  )
}

/** 终末（已出院）任务的出院日期窗：起止必填、起不晚于止、止不晚于今天（医院时区）、最多 31 天。 */
export function dischargedDateRangeError(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  const from = start?.trim()
  const to = end?.trim()
  if (!from || !to) return '终末任务必须选择出院开始日期和结束日期'
  if (!validDate(from) || !validDate(to)) return '出院日期范围格式无效，请选择有效日期'
  if (dayjs(from).isAfter(dayjs(to), 'day')) return '出院开始日期不能晚于结束日期'
  if (dayjs(to).isAfter(hospitalToday(), 'day')) return '出院结束日期不能晚于今天'
  if (dayjs(to).diff(dayjs(from), 'day') + 1 > MAX_DISCHARGE_WINDOW_DAYS)
    return `出院日期范围最多 ${MAX_DISCHARGE_WINDOW_DAYS} 天`
  return ''
}
