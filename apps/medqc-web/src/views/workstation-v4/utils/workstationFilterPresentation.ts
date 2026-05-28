import type { DeptInfo } from '../types'
import type { WorkstationDateField, WorkstationDateRange } from '../composables/usePatientRecords'

const ALL_DEPARTMENTS = '全部科室'

export function buildDepartmentSelectOptions(departments: DeptInfo[]): DeptInfo[] {
  const seen = new Set<string>()
  const options: DeptInfo[] = []

  for (const dept of departments) {
    const name = (dept.name || '').trim()
    if (!name || seen.has(name)) continue
    seen.add(name)
    options.push({ ...dept, name })
  }

  if (!seen.has(ALL_DEPARTMENTS)) {
    options.unshift({
      name: ALL_DEPARTMENTS,
      total: departments.reduce((sum, dept) => sum + Number(dept.total || 0), 0),
      warningCount: departments.reduce((sum, dept) => sum + Number(dept.warningCount || 0), 0),
    })
  }

  return options.sort((a, b) => {
    if (a.name === ALL_DEPARTMENTS) return -1
    if (b.name === ALL_DEPARTMENTS) return 1
    return Number(b.total || 0) - Number(a.total || 0)
  })
}

export function buildQuickDepartments(
  departments: DeptInfo[],
  activeDept: string,
  maxCount = 7,
): DeptInfo[] {
  const options = buildDepartmentSelectOptions(departments)
  const byName = new Map(options.map((dept) => [dept.name, dept]))
  const result: DeptInfo[] = []

  const pushDept = (dept: DeptInfo | undefined) => {
    if (!dept || result.some((item) => item.name === dept.name)) return
    result.push(dept)
  }

  pushDept(byName.get(ALL_DEPARTMENTS))
  if (activeDept && activeDept !== ALL_DEPARTMENTS) {
    pushDept(byName.get(activeDept))
  }

  for (const dept of options) {
    if (dept.name === ALL_DEPARTMENTS) continue
    pushDept(dept)
    if (result.length >= maxCount) break
  }

  return result.slice(0, maxCount)
}

export function formatWorkstationDateFieldLabel(dateField: WorkstationDateField): string {
  const labelMap: Record<WorkstationDateField, string> = {
    visit: '入出院日期',
    admission: '入院日期',
    discharge: '出院日期',
    updated: '更新时间',
  }
  return labelMap[dateField] || labelMap.visit
}

export function buildWorkstationFilterSummary(options: {
  activeDept: string
  dateField: WorkstationDateField
  dateRange: WorkstationDateRange
  total: number
  stageTitle: string
  isStageQueueMode: boolean
}): string {
  const totalText = `共 ${Number(options.total || 0)} 份`
  if (options.isStageQueueMode) {
    return `当前筛选：${options.activeDept} / ${options.stageTitle} / ${totalText}`
  }

  const dateText = options.dateRange
    ? `${formatWorkstationDateFieldLabel(options.dateField)} ${options.dateRange[0]} 至 ${options.dateRange[1]}`
    : '全部日期'
  return `当前筛选：${options.activeDept} / ${dateText} / ${totalText}`
}

export function filterDepartmentOption(
  input: string,
  option?: { value?: unknown; label?: unknown },
) {
  const keyword = input.trim().toLowerCase()
  if (!keyword) return true
  const value = String(option?.value ?? option?.label ?? '').toLowerCase()
  return value.includes(keyword)
}
