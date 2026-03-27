/**
 * 申诉管理 API 服务
 * Appeal Management API
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'
import type {
  Appeal,
  AppealCreateRequest,
  AppealUpdateRequest,
  AppealReviewRequest,
  AppealListResponse,
  AppealFilters,
  AppealStats,
} from '@/types/appeal'

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
 * 创建申诉
 */
export async function createAppeal(data: AppealCreateRequest): Promise<Appeal> {
  return requestOrThrow<Appeal>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals`,
      data,
    },
    '创建申诉失败',
  )
}

/**
 * 获取申诉列表
 */
export async function getAppeals(filters: AppealFilters = {}): Promise<AppealListResponse> {
  const params: Record<string, unknown> = {}

  if (filters.status) params.status = filters.status
  if (filters.appealType) params.appeal_type = filters.appealType
  if (filters.appellantId) params.appellant_id = filters.appellantId
  if (filters.departmentId) params.department_id = filters.departmentId
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  if (filters.page) params.page = filters.page
  if (filters.pageSize) params.page_size = filters.pageSize

  return requestOrThrow<AppealListResponse>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals`,
      params,
    },
    '获取申诉列表失败',
  )
}

/**
 * 获取申诉详情
 */
export async function getAppeal(appealId: string): Promise<Appeal> {
  return requestOrThrow<Appeal>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals/${appealId}`,
    },
    '获取申诉详情失败',
  )
}

/**
 * 更新申诉
 */
export async function updateAppeal(
  appealId: string,
  data: AppealUpdateRequest,
): Promise<Appeal> {
  return requestOrThrow<Appeal>(
    {
      method: 'PUT',
      url: `${API_V1_PREFIX}/appeals/${appealId}`,
      data,
    },
    '更新申诉失败',
  )
}

/**
 * 审核申诉
 */
export async function reviewAppeal(
  appealId: string,
  review: AppealReviewRequest,
): Promise<Appeal> {
  return requestOrThrow<Appeal>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals/${appealId}/review`,
      data: review,
    },
    '审核申诉失败',
  )
}

/**
 * 撤销申诉
 */
export async function withdrawAppeal(appealId: string): Promise<Appeal> {
  return requestOrThrow<Appeal>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals/${appealId}/withdraw`,
    },
    '撤销申诉失败',
  )
}

/**
 * 获取申诉统计
 */
export async function getAppealStats(
  filters: {
    departmentId?: string
    startDate?: string
    endDate?: string
  } = {},
): Promise<AppealStats> {
  const params: Record<string, unknown> = {}

  if (filters.departmentId) params.department_id = filters.departmentId
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate

  return requestOrThrow<AppealStats>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals/stats`,
      params,
    },
    '获取申诉统计失败',
  )
}
