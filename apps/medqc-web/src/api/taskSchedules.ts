import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/task-schedules'

export const TASK_SCHEDULE_TIMEZONE = 'Asia/Shanghai' as const

export type TaskScheduleState = 'active' | 'paused' | 'ended' | 'cancelled'
export type TaskScheduleRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type TaskScheduleTriggerType = 'scheduled' | 'manual'
export type TaskScheduleSamplingMethod = import('./tasks').SamplingMethod
export type TaskScheduleAssignMethod = 'by_ratio' | 'by_original_reviewer' | 'by_department'

export interface TaskScheduleTimingOnce {
  kind: 'once'
  timezone: typeof TASK_SCHEDULE_TIMEZONE
  run_at: string
}

export interface TaskScheduleTimingDaily {
  kind: 'daily'
  timezone: typeof TASK_SCHEDULE_TIMEZONE
  time: string
  start_date: string
  end_date: string | null
}

export interface TaskScheduleTimingWeekly {
  kind: 'weekly'
  timezone: typeof TASK_SCHEDULE_TIMEZONE
  time: string
  start_date: string
  end_date: string | null
  weekdays: number[]
}

export interface TaskScheduleTimingMonthly {
  kind: 'monthly'
  timezone: typeof TASK_SCHEDULE_TIMEZONE
  time: string
  start_date: string
  end_date: string | null
  day: number
}

export type TaskScheduleTiming =
  | TaskScheduleTimingOnce
  | TaskScheduleTimingDaily
  | TaskScheduleTimingWeekly
  | TaskScheduleTimingMonthly

export interface TaskScheduleCreateRequest {
  source_task_id: string
  source_configuration_version: number
  timing_config: TaskScheduleTiming
}

export interface TaskScheduleActionRequest {
  version: number
}

export interface TaskScheduleTaskConfig {
  date_range: null
  department_filter: string[]
  sampling_method: TaskScheduleSamplingMethod
  sampling_config: Record<string, unknown>
  assign_method: TaskScheduleAssignMethod
  assignee_config: Record<string, unknown>
}

export interface TaskScheduleResponse {
  id: string
  source_task_id: string
  owner_id: string
  name: string
  scene: 'running' | 'final'
  rule_set_key: string
  rule_set_version: string
  task_config: TaskScheduleTaskConfig
  timing_config: TaskScheduleTiming
  state: TaskScheduleState
  next_fire_at: string | null
  last_fire_at: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface TaskScheduleListResponse {
  items: TaskScheduleResponse[]
  total: number
  page: number
  page_size: number
}

export interface TaskScheduleRunResponse {
  id: string
  schedule_id: string
  trigger_type: TaskScheduleTriggerType
  scheduled_fire_at: string
  idempotency_key: string
  status: TaskScheduleRunStatus
  generated_task_id: string | null
  async_job_id: string | null
  attempt_count: number
  heartbeat_at: string | null
  started_at: string | null
  finished_at: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface TaskScheduleRunListResponse {
  items: TaskScheduleRunResponse[]
  total: number
  page: number
  page_size: number
}

export type TaskScheduleErrorCode =
  | 'schedule_not_found'
  | 'schedule_forbidden'
  | 'schedule_invalid'
  | 'version_conflict'
  | 'state_conflict'
  | 'schedule_unavailable'
  | 'task_schedule_not_found'
  | 'task_schedule_forbidden'
  | 'task_schedule_invalid'
  | 'task_schedule_unavailable'
  | 'run_conflict'
  | 'request_conflict'

export interface TaskScheduleResult<T> {
  success: boolean
  data?: T
  message?: string
  status?: number
  code?: TaskScheduleErrorCode
  uncertain: boolean
}

const ERROR_CODES = new Set<TaskScheduleErrorCode>([
  'schedule_not_found',
  'schedule_forbidden',
  'schedule_invalid',
  'version_conflict',
  'state_conflict',
  'schedule_unavailable',
  'task_schedule_not_found',
  'task_schedule_forbidden',
  'task_schedule_invalid',
  'task_schedule_unavailable',
  'run_conflict',
  'request_conflict',
])
const SCHEDULE_STATES = new Set<TaskScheduleState>(['active', 'paused', 'ended', 'cancelled'])
const RUN_STATUSES = new Set<TaskScheduleRunStatus>([
  'queued',
  'running',
  'succeeded',
  'failed',
  'cancelled',
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

function isPositiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) > 0
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0
}

function parseTiming(value: unknown): TaskScheduleTiming {
  if (!isObject(value) || value.timezone !== TASK_SCHEDULE_TIMEZONE)
    throw new Error('定时计划响应格式无效')
  if (value.kind === 'once') {
    if (!isNonBlank(value.run_at)) throw new Error('定时计划响应格式无效')
    return value as unknown as TaskScheduleTimingOnce
  }
  if (value.kind !== 'daily' && value.kind !== 'weekly' && value.kind !== 'monthly') {
    throw new Error('定时计划响应格式无效')
  }
  if (
    !/^([01]\d|2[0-3]):[0-5]\d$/.test(String(value.time || '')) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(String(value.start_date || '')) ||
    !(value.end_date === null || /^\d{4}-\d{2}-\d{2}$/.test(String(value.end_date || '')))
  ) {
    throw new Error('定时计划响应格式无效')
  }
  if (value.kind === 'weekly') {
    if (
      !Array.isArray(value.weekdays) ||
      !value.weekdays.length ||
      value.weekdays.some((item) => !Number.isInteger(item) || item < 1 || item > 7) ||
      new Set(value.weekdays).size !== value.weekdays.length ||
      value.weekdays.some((item, index) => index > 0 && item <= value.weekdays[index - 1])
    ) {
      throw new Error('定时计划响应格式无效')
    }
  }
  if (
    value.kind === 'monthly' &&
    (!Number.isInteger(value.day) || Number(value.day) < 1 || Number(value.day) > 31)
  ) {
    throw new Error('定时计划响应格式无效')
  }
  return value as unknown as TaskScheduleTiming
}

function parseTaskConfig(value: unknown): TaskScheduleTaskConfig {
  if (
    !isObject(value) ||
    value.date_range !== null ||
    !Array.isArray(value.department_filter) ||
    value.department_filter.some((item) => typeof item !== 'string') ||
    (value.sampling_method !== 'all' &&
      value.sampling_method !== 'count' &&
      value.sampling_method !== 'percentage' &&
      value.sampling_method !== 'department_count' &&
      value.sampling_method !== 'department_ratio' &&
      value.sampling_method !== 'qc_physician_count' &&
      value.sampling_method !== 'qc_physician_ratio' &&
      value.sampling_method !== 'qc_reviewer_count' &&
      value.sampling_method !== 'qc_reviewer_ratio') ||
    !isObject(value.sampling_config) ||
    (value.assign_method !== 'by_ratio' &&
      value.assign_method !== 'by_original_reviewer' &&
      value.assign_method !== 'by_department') ||
    !isObject(value.assignee_config)
  ) {
    throw new Error('定时计划响应格式无效')
  }
  return value as unknown as TaskScheduleTaskConfig
}

function parseSchedule(value: unknown, expectedId?: string): TaskScheduleResponse {
  if (
    !isObject(value) ||
    !isNonBlank(value.id) ||
    (expectedId !== undefined && value.id !== expectedId) ||
    !isNonBlank(value.source_task_id) ||
    !isNonBlank(value.owner_id) ||
    !isNonBlank(value.name) ||
    (value.scene !== 'running' && value.scene !== 'final') ||
    !isNonBlank(value.rule_set_key) ||
    !isNonBlank(value.rule_set_version) ||
    !SCHEDULE_STATES.has(value.state as TaskScheduleState) ||
    !isNullableString(value.next_fire_at) ||
    !isNullableString(value.last_fire_at) ||
    !isPositiveInteger(value.version) ||
    !isNonBlank(value.created_at) ||
    !isNonBlank(value.updated_at)
  ) {
    throw new Error('定时计划响应格式无效')
  }
  parseTaskConfig(value.task_config)
  parseTiming(value.timing_config)
  return value as unknown as TaskScheduleResponse
}

function parseScheduleList(value: unknown): TaskScheduleListResponse {
  if (
    !isObject(value) ||
    !Array.isArray(value.items) ||
    !isNonNegativeInteger(value.total) ||
    !isPositiveInteger(value.page) ||
    !isPositiveInteger(value.page_size)
  ) {
    throw new Error('定时计划列表响应格式无效')
  }
  return {
    items: value.items.map((item) => parseSchedule(item)),
    total: value.total,
    page: value.page,
    page_size: value.page_size,
  }
}

function parseRun(value: unknown, expectedScheduleId?: string): TaskScheduleRunResponse {
  if (
    !isObject(value) ||
    !isNonBlank(value.id) ||
    !isNonBlank(value.schedule_id) ||
    (expectedScheduleId !== undefined && value.schedule_id !== expectedScheduleId) ||
    (value.trigger_type !== 'scheduled' && value.trigger_type !== 'manual') ||
    !isNonBlank(value.scheduled_fire_at) ||
    !isNonBlank(value.idempotency_key) ||
    !RUN_STATUSES.has(value.status as TaskScheduleRunStatus) ||
    !isNullableString(value.generated_task_id) ||
    !isNullableString(value.async_job_id) ||
    !isNonNegativeInteger(value.attempt_count) ||
    !isNullableString(value.heartbeat_at) ||
    !isNullableString(value.started_at) ||
    !isNullableString(value.finished_at) ||
    !isNullableString(value.error_code) ||
    !isNullableString(value.error_message) ||
    !isNonBlank(value.created_at) ||
    !isNonBlank(value.updated_at)
  ) {
    throw new Error('定时运行历史响应格式无效')
  }
  return value as unknown as TaskScheduleRunResponse
}

function parseRunList(value: unknown, scheduleId: string): TaskScheduleRunListResponse {
  if (
    !isObject(value) ||
    !Array.isArray(value.items) ||
    !isNonNegativeInteger(value.total) ||
    !isPositiveInteger(value.page) ||
    !isPositiveInteger(value.page_size)
  ) {
    throw new Error('定时运行历史响应格式无效')
  }
  return {
    items: value.items.map((item) => parseRun(item, scheduleId)),
    total: value.total,
    page: value.page,
    page_size: value.page_size,
  }
}

function extractStructuredError(error: unknown): {
  code?: TaskScheduleErrorCode
  message?: string
} {
  if (!isAxiosError(error) || !isObject(error.response?.data)) return {}
  const body = error.response.data
  for (const key of ['detail', 'error'] as const) {
    const raw = body[key]
    if (!isObject(raw)) continue
    const code =
      typeof raw.code === 'string' && ERROR_CODES.has(raw.code as TaskScheduleErrorCode)
        ? (raw.code as TaskScheduleErrorCode)
        : undefined
    const message = isNonBlank(raw.message) ? raw.message : undefined
    if (code || message) return { code, message }
  }
  return {}
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  parser: (value: unknown) => T,
  write = false,
): Promise<TaskScheduleResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    if (!normalized.success || normalized.data === undefined || normalized.data === null) {
      return {
        success: false,
        status: response.status,
        message: normalized.message || '定时计划响应格式无效',
        uncertain: write && response.status >= 200 && response.status < 300,
      }
    }
    return {
      success: true,
      status: response.status,
      data: parser(normalized.data),
      uncertain: false,
    }
  } catch (error) {
    if (error instanceof Error && !isAxiosError(error)) {
      return { success: false, message: error.message, uncertain: write }
    }
    const status = isAxiosError(error) ? error.response?.status : undefined
    const structured = extractStructuredError(error)
    return {
      success: false,
      status,
      code: structured.code,
      message:
        structured.message || extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
      uncertain: write && (status === undefined || status >= 500),
    }
  }
}

export function listTaskSchedules(
  params: { state?: TaskScheduleState; page?: number; page_size?: number } = {},
) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value))
  })
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request({ method: 'GET', url: `${BASE_URL}${suffix}` }, parseScheduleList)
}

export function createTaskSchedule(data: TaskScheduleCreateRequest, idempotencyKey: string) {
  return request(
    {
      method: 'POST',
      url: BASE_URL,
      headers: { 'Idempotency-Key': idempotencyKey },
      data,
    },
    parseSchedule,
    true,
  )
}

export function getTaskSchedule(scheduleId: string) {
  return request({ method: 'GET', url: `${BASE_URL}/${encodeURIComponent(scheduleId)}` }, (value) =>
    parseSchedule(value, scheduleId),
  )
}

function changeScheduleState(
  scheduleId: string,
  action: 'pause' | 'resume' | 'cancel',
  data: TaskScheduleActionRequest,
) {
  return request(
    { method: 'PATCH', url: `${BASE_URL}/${encodeURIComponent(scheduleId)}/${action}`, data },
    (value) => parseSchedule(value, scheduleId),
    true,
  )
}

export const pauseTaskSchedule = (scheduleId: string, data: TaskScheduleActionRequest) =>
  changeScheduleState(scheduleId, 'pause', data)

export const resumeTaskSchedule = (scheduleId: string, data: TaskScheduleActionRequest) =>
  changeScheduleState(scheduleId, 'resume', data)

export const cancelTaskSchedule = (scheduleId: string, data: TaskScheduleActionRequest) =>
  changeScheduleState(scheduleId, 'cancel', data)

export function listTaskScheduleRuns(
  scheduleId: string,
  params: { status?: TaskScheduleRunStatus; page?: number; page_size?: number } = {},
) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value))
  })
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request(
    { method: 'GET', url: `${BASE_URL}/${encodeURIComponent(scheduleId)}/runs${suffix}` },
    (value) => parseRunList(value, scheduleId),
  )
}

export function runTaskScheduleNow(scheduleId: string, idempotencyKey: string) {
  return request(
    {
      method: 'POST',
      url: `${BASE_URL}/${encodeURIComponent(scheduleId)}/run-now`,
      headers: { 'Idempotency-Key': idempotencyKey },
    },
    (value) => parseRun(value, scheduleId),
    true,
  )
}

export function retryTaskScheduleRun(runId: string) {
  return request(
    { method: 'POST', url: `${BASE_URL}/runs/${encodeURIComponent(runId)}/retry` },
    (value) => parseRun(value),
    true,
  )
}
