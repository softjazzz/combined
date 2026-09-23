/**
 * 申诉管理 API 服务
 * Appeal Management API
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'
import type {
  Appeal,
  AppealEvidence,
  AppealReview,
  AppealCreateRequest,
  AppealUpdateRequest,
  AppealReviewRequest,
  AppealListResponse,
  AppealFilters,
  AppealStats,
} from '@/types/appeal'

const API_V1_PREFIX = '/api/v1'

interface AppealDto {
  id: string
  appeal_number?: string | null
  qc_result_id: string
  record_id: string
  appeal_type: Appeal['appealType']
  defect_item?: string | null
  reason: string
  evidence?: AppealEvidence[] | string | null
  status: Appeal['status']
  priority: Appeal['priority']
  appellant_id: string
  appellant_name?: string | null
  appellant_department?: string | null
  reviewer_id?: string | null
  reviewer_name?: string | null
  review_result?: string | null
  review_date?: string | null
  resolution?: string | null
  resolution_date?: string | null
  notes?: string | null
  created_at: string
  updated_at: string
  reviews?: AppealReviewDto[]
}

interface AppealReviewDto {
  id: string
  appeal_id: string
  reviewer_id: string
  reviewer_name?: string | null
  action: AppealReview['action']
  comment?: string | null
  created_at: string
}

interface AppealPageDto {
  items: AppealDto[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

function normalizeEvidence(value: AppealDto['evidence']): AppealEvidence[] {
  let parsed: unknown = value
  if (typeof value === 'string') {
    try {
      parsed = JSON.parse(value)
    } catch {
      return []
    }
  }
  return Array.isArray(parsed)
    ? parsed.filter((item): item is AppealEvidence => typeof item === 'object' && item !== null && !Array.isArray(item))
    : []
}

function mapAppeal(dto: AppealDto): Appeal {
  return {
    id: dto.id,
    appealNumber: dto.appeal_number ?? null,
    qcResultId: dto.qc_result_id,
    recordId: dto.record_id,
    appealType: dto.appeal_type,
    defectItem: dto.defect_item ?? null,
    appealReason: dto.reason,
    evidence: normalizeEvidence(dto.evidence),
    status: dto.status,
    priority: dto.priority,
    appellantId: dto.appellant_id,
    appellantName: dto.appellant_name ?? null,
    appellantDepartment: dto.appellant_department ?? null,
    reviewerId: dto.reviewer_id ?? null,
    reviewerName: dto.reviewer_name ?? null,
    reviewResult: dto.review_result ?? null,
    reviewedAt: dto.review_date ?? null,
    resolution: dto.resolution ?? null,
    resolutionDate: dto.resolution_date ?? null,
    notes: dto.notes ?? null,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    reviews: dto.reviews?.map((review) => ({
      id: review.id,
      appealId: review.appeal_id,
      reviewerId: review.reviewer_id,
      reviewerName: review.reviewer_name ?? null,
      action: review.action,
      comment: review.comment ?? null,
      createdAt: review.created_at,
    })),
  }
}

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
  const dto = await requestOrThrow<AppealDto>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals`,
      data: {
        qc_result_id: data.qcResultId,
        record_id: data.recordId,
        appeal_type: data.appealType,
        defect_item: data.defectId,
        reason: data.appealReason,
        evidence: data.evidenceUrls?.map((url) => ({ url })) ?? [],
        priority: data.priority ?? 'medium',
      },
    },
    '创建申诉失败',
  )
  return mapAppeal(dto)
}

/**
 * 获取申诉列表
 */
export async function getAppeals(filters: AppealFilters = {}): Promise<AppealListResponse> {
  const params: Record<string, unknown> = {}

  if (filters.status) params.status = filters.status
  if (filters.appealType) params.appeal_type = filters.appealType
  if (filters.priority) params.priority = filters.priority
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  if (filters.page) params.page = filters.page
  if (filters.pageSize) params.page_size = filters.pageSize

  const dto = await requestOrThrow<AppealPageDto>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals`,
      params,
    },
    '获取申诉列表失败',
  )
  return {
    items: dto.items.map(mapAppeal),
    total: dto.total,
    page: dto.page,
    pageSize: dto.page_size,
    totalPages: dto.total_pages,
  }
}

/**
 * 获取申诉详情
 */
export async function getAppeal(appealId: string): Promise<Appeal> {
  const dto = await requestOrThrow<AppealDto>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals/${appealId}`,
    },
    '获取申诉详情失败',
  )
  return mapAppeal(dto)
}

/**
 * 更新申诉
 */
export async function updateAppeal(
  appealId: string,
  data: AppealUpdateRequest,
): Promise<Appeal> {
  const dto = await requestOrThrow<AppealDto>(
    {
      method: 'PUT',
      url: `${API_V1_PREFIX}/appeals/${appealId}`,
      data: {
        reason: data.appealReason,
        evidence: data.evidenceUrls?.map((url) => ({ url })),
        priority: data.priority,
        notes: data.notes,
      },
    },
    '更新申诉失败',
  )
  return mapAppeal(dto)
}

/**
 * 审核申诉
 */
export async function reviewAppeal(
  appealId: string,
  review: AppealReviewRequest,
): Promise<Appeal> {
  const dto = await requestOrThrow<AppealDto>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals/${appealId}/review`,
      data: review,
    },
    '审核申诉失败',
  )
  return mapAppeal(dto)
}

/**
 * 撤销申诉
 */
export async function withdrawAppeal(appealId: string): Promise<Appeal> {
  const dto = await requestOrThrow<AppealDto>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals/${appealId}/withdraw`,
      data: {},
    },
    '撤销申诉失败',
  )
  return mapAppeal(dto)
}

/**
 * 获取申诉统计
 */
export async function getAppealStats(
  filters: {
    startDate?: string
    endDate?: string
  } = {},
): Promise<AppealStats> {
  const params: Record<string, unknown> = {}

  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate

  const dto = await requestOrThrow<{
    total: number
    pending: number
    reviewing: number
    approved: number
    rejected: number
    withdrawn: number
    avg_resolution_time_hours: number | null
  }>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals/statistics/summary`,
      params,
    },
    '获取申诉统计失败',
  )
  return { ...dto, avgResolutionTimeHours: dto.avg_resolution_time_hours }
}
