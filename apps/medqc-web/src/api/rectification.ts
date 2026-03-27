/**
 * 整改管理 API 服务
 * Rectification Management API
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'
import type {
  RectificationTask,
  RectificationTaskCreateRequest,
  RectificationTaskUpdateRequest,
  TaskAssignmentRequest,
  TaskSubmissionRequest,
  TaskReviewRequest,
  RectificationTaskListResponse,
  TaskFilters,
  TaskStats,
} from '@/types/rectification'

const API_V1_PREFIX = '/api/v1'

async function requestOrThrow<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallback: string,
): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    return unwrapApiEnvelope<T>(response.data)
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, fallback))
  }
}

/**
 * 创建整改任务
 */
export async function createRectificationTask(
  data: RectificationTaskCreateRequest,
): Promise<RectificationTask> {
  return requestOrThrow<RectificationTask>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/rectifications`,
      data,
    },
    '创建整改任务失败',
  )
}

/**
 * 获取整改任务列表
 */
export async function getRectificationTasks(
  filters: TaskFilters = {},
): Promise<RectificationTaskListResponse> {
  const params: Record<string, unknown> = {}

  if (filters.status) params.status = filters.status
  if (filters.severity) params.severity = filters.severity
  if (filters.assigneeId) params.assignee_id = filters.assigneeId
  if (filters.assignerId) params.assigner_id = filters.assignerId
  if (filters.departmentId) params.department_id = filters.departmentId
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  if (filters.overdueOnly) params.overdue_only = 'true'
  if (filters.page) params.page = filters.page
  if (filters.pageSize) params.page_size = filters.pageSize

  return requestOrThrow<RectificationTaskListResponse>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/rectifications`,
      params,
    },
    '获取整改任务列表失败',
  )
}

/**
 * 获取我的整改任务
 */
export async function getMyTasks(status?: string): Promise<RectificationTask[]> {
  const params: Record<string, unknown> = {}
  if (status) params.status = status

  return requestOrThrow<RectificationTask[]>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/rectifications/my-tasks`,
      params,
    },
    '获取我的任务失败',
  )
}

/**
 * 获取整改任务详情
 */
export async function getRectificationTask(taskId: string): Promise<RectificationTask> {
  return requestOrThrow<RectificationTask>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/rectifications/${taskId}`,
    },
    '获取整改任务详情失败',
  )
}

/**
 * 更新整改任务
 */
export async function updateRectificationTask(
  taskId: string,
  data: RectificationTaskUpdateRequest,
): Promise<RectificationTask> {
  return requestOrThrow<RectificationTask>(
    {
      method: 'PUT',
      url: `${API_V1_PREFIX}/rectifications/${taskId}`,
      data,
    },
    '更新整改任务失败',
  )
}

/**
 * 分配/重新分配整改任务
 */
export async function assignTask(
  taskId: string,
  assignment: TaskAssignmentRequest,
): Promise<RectificationTask> {
  return requestOrThrow<RectificationTask>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/rectifications/${taskId}/assign`,
      data: assignment,
    },
    '分配任务失败',
  )
}

/**
 * 提交整改
 */
export async function submitRectification(
  taskId: string,
  submission: TaskSubmissionRequest,
): Promise<RectificationTask> {
  return requestOrThrow<RectificationTask>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/rectifications/${taskId}/submit`,
      data: submission,
    },
    '提交整改失败',
  )
}

/**
 * 验收整改
 */
export async function reviewRectification(
  taskId: string,
  review: TaskReviewRequest,
): Promise<RectificationTask> {
  return requestOrThrow<RectificationTask>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/rectifications/${taskId}/review`,
      data: review,
    },
    '验收整改失败',
  )
}

/**
 * 获取整改任务统计
 */
export async function getTaskStats(filters: {
  departmentId?: string
  assigneeId?: string
  startDate?: string
  endDate?: string
} = {}): Promise<TaskStats> {
  const params: Record<string, unknown> = {}

  if (filters.departmentId) params.department_id = filters.departmentId
  if (filters.assigneeId) params.assignee_id = filters.assigneeId
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate

  return requestOrThrow<TaskStats>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/rectifications/stats`,
      params,
    },
    '获取整改统计失败',
  )
}
