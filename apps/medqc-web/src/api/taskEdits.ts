import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/task-edits'

export type TaskEditScene = 'running' | 'final' | 'outpatient'
export type TaskEditType = 'one_time' | 'scheduled'
export type TaskEditSamplingMethod =
  | 'all'
  | 'count'
  | 'percentage'
  | 'department_count'
  | 'department_ratio'
export type TaskEditableAssignMethod = 'by_ratio' | 'by_original_reviewer' | 'by_department'
export type TaskEditAssignMethod = TaskEditableAssignMethod | 'keep' | 'by_type' | 'by_record_type'
export type TaskEditField =
  | 'task_name'
  | 'deadline'
  | 'date_range'
  | 'department_filter'
  | 'record_refs'
  | 'sampling_method'
  | 'sampling_config'
  | 'assign_method'
  | 'assignee_config'

export interface TaskEditCaseRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface TaskEditDateRange {
  start: string | null
  end: string | null
}

export interface TaskEditDetail {
  id: string
  task_number: string
  task_name: string
  task_type: string
  status: string
  scene: TaskEditScene | null
  rule_set_key: string | null
  rule_set_version: string | null
  deadline: string | null
  date_range: TaskEditDateRange | null
  department_filter: string[] | null
  record_refs: TaskEditCaseRef[] | null
  sampling_method: TaskEditSamplingMethod | null
  sampling_config: Record<string, unknown> | null
  assign_method: TaskEditAssignMethod | null
  assignee_config: Record<string, unknown> | null
  configuration_version: number
  editable_fields: TaskEditField[]
  updated_at: string | null
}

export interface TaskDraftConfigurationUpdate {
  configuration_version: number
  task_name: string
  deadline: string | null
  date_range: TaskEditDateRange | null
  department_filter: string[]
  record_refs: TaskEditCaseRef[]
  sampling_method: TaskEditSamplingMethod
  sampling_config: Record<string, unknown>
  assign_method: TaskEditableAssignMethod
  assignee_config: Record<string, unknown>
}

export interface TaskMetadataUpdate {
  configuration_version: number
  task_name?: string
  deadline?: string | null
}

export type TaskEditErrorCode =
  | 'task_not_found'
  | 'task_edit_forbidden'
  | 'version_conflict'
  | 'state_conflict'
  | 'association_conflict'
  | 'task_edit_invalid'
  | 'task_edit_unavailable'

export interface TaskEditResult {
  success: boolean
  data?: TaskEditDetail
  message?: string
  status?: number
  code?: TaskEditErrorCode
  /** 网络、5xx 或畸形 2xx 无法证明写入结果，调用方必须刷新后才能重试。 */
  uncertain: boolean
}

const EDITABLE_FIELDS = new Set<TaskEditField>([
  'task_name',
  'deadline',
  'date_range',
  'department_filter',
  'record_refs',
  'sampling_method',
  'sampling_config',
  'assign_method',
  'assignee_config',
])
const ERROR_CODES = new Set<TaskEditErrorCode>([
  'task_not_found',
  'task_edit_forbidden',
  'version_conflict',
  'state_conflict',
  'association_conflict',
  'task_edit_invalid',
  'task_edit_unavailable',
])

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonBlank(value: unknown): value is string {
  return typeof value === 'string' && !!value.trim()
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isTaskEditDateRange(value: unknown): value is TaskEditDateRange | null {
  if (value === null) return true
  return isObject(value) && isNullableString(value.start) && isNullableString(value.end)
}

function isTaskEditCaseRef(value: unknown): value is TaskEditCaseRef {
  if (!isObject(value)) return false
  return (
    isNonBlank(value.institute_id) && isNonBlank(value.patient_id) && isNonBlank(value.visit_id)
  )
}

function parseTaskEditDetail(value: unknown, expectedTaskId: string): TaskEditDetail {
  if (!isObject(value)) throw new Error('任务编辑响应格式无效')
  const refs = value.record_refs
  const departments = value.department_filter
  const fields = value.editable_fields
  if (
    value.id !== expectedTaskId ||
    !isNonBlank(value.task_number) ||
    !isNonBlank(value.task_name) ||
    !isNonBlank(value.task_type) ||
    !isNonBlank(value.status) ||
    (value.scene !== null &&
      value.scene !== 'running' &&
      value.scene !== 'final' &&
      value.scene !== 'outpatient') ||
    (value.rule_set_key !== null && !isNonBlank(value.rule_set_key)) ||
    (value.rule_set_version !== null && !isNonBlank(value.rule_set_version)) ||
    !isNullableString(value.deadline) ||
    !isTaskEditDateRange(value.date_range) ||
    (departments !== null &&
      (!Array.isArray(departments) || departments.some((item) => typeof item !== 'string'))) ||
    (refs !== null && (!Array.isArray(refs) || refs.some((item) => !isTaskEditCaseRef(item)))) ||
    (value.sampling_method !== null &&
      !['all', 'count', 'percentage', 'department_count', 'department_ratio'].includes(
        String(value.sampling_method),
      )) ||
    (value.sampling_config !== null && !isObject(value.sampling_config)) ||
    (value.assign_method !== null &&
      value.assign_method !== 'by_ratio' &&
      value.assign_method !== 'by_original_reviewer' &&
      value.assign_method !== 'by_department' &&
      value.assign_method !== 'keep' &&
      value.assign_method !== 'by_type' &&
      value.assign_method !== 'by_record_type') ||
    (value.assignee_config !== null && !isObject(value.assignee_config)) ||
    !Number.isInteger(value.configuration_version) ||
    Number(value.configuration_version) <= 0 ||
    !Array.isArray(fields) ||
    fields.some(
      (item) => typeof item !== 'string' || !EDITABLE_FIELDS.has(item as TaskEditField),
    ) ||
    new Set(fields).size !== fields.length ||
    (value.updated_at !== null && !isNonBlank(value.updated_at))
  ) {
    throw new Error('任务编辑响应格式无效')
  }
  const refKeys = new Set<string>()
  for (const ref of (refs || []) as TaskEditCaseRef[]) {
    const key = `${ref.institute_id.trim()}\u0000${ref.patient_id.trim()}\u0000${ref.visit_id.trim()}`
    if (refKeys.has(key)) throw new Error('任务编辑响应格式无效')
    refKeys.add(key)
  }
  return value as unknown as TaskEditDetail
}

function extractStructuredError(error: unknown): { code?: TaskEditErrorCode; message?: string } {
  if (!isAxiosError(error) || !isObject(error.response?.data)) return {}
  const body = error.response.data
  for (const key of ['detail', 'error'] as const) {
    const raw = body[key]
    if (!isObject(raw)) continue
    const code =
      typeof raw.code === 'string' && ERROR_CODES.has(raw.code as TaskEditErrorCode)
        ? (raw.code as TaskEditErrorCode)
        : undefined
    const message = isNonBlank(raw.message) ? raw.message : undefined
    if (code || message) return { code, message }
  }
  return {}
}

async function requestTaskEdit(
  taskId: string,
  config: Parameters<typeof ApiService.requestRaw>[0],
): Promise<TaskEditResult> {
  try {
    const response = await ApiService.requestRaw<TaskEditDetail>(config)
    const normalized = normalizeApiSuccess<TaskEditDetail>(response.data)
    if (!normalized.success || !normalized.data) {
      return {
        success: false,
        status: response.status,
        message: normalized.message || '任务编辑响应格式无效',
        uncertain: response.status >= 200 && response.status < 300,
      }
    }
    return {
      success: true,
      status: response.status,
      data: parseTaskEditDetail(normalized.data, taskId),
      uncertain: false,
    }
  } catch (error) {
    if (error instanceof Error && !isAxiosError(error)) {
      return { success: false, message: error.message, uncertain: true }
    }
    const status = isAxiosError(error) ? error.response?.status : undefined
    const structured = extractStructuredError(error)
    return {
      success: false,
      status,
      code: structured.code,
      message:
        structured.message || extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
      uncertain: status === undefined || status >= 500,
    }
  }
}

export function getTaskEdit(taskId: string): Promise<TaskEditResult> {
  return requestTaskEdit(taskId, {
    method: 'GET',
    url: `${BASE_URL}/${encodeURIComponent(taskId)}`,
  })
}

export function updateTaskDraftConfiguration(
  taskId: string,
  data: TaskDraftConfigurationUpdate,
): Promise<TaskEditResult> {
  return requestTaskEdit(taskId, {
    method: 'PUT',
    url: `${BASE_URL}/${encodeURIComponent(taskId)}/draft-configuration`,
    data,
  })
}

export function updateTaskMetadata(
  taskId: string,
  data: TaskMetadataUpdate,
): Promise<TaskEditResult> {
  if (
    !Object.prototype.hasOwnProperty.call(data, 'task_name') &&
    !Object.prototype.hasOwnProperty.call(data, 'deadline')
  ) {
    return Promise.resolve({
      success: false,
      message: '请至少修改任务名称或截止日期',
      uncertain: false,
    })
  }
  return requestTaskEdit(taskId, {
    method: 'PATCH',
    url: `${BASE_URL}/${encodeURIComponent(taskId)}/metadata`,
    data,
  })
}
