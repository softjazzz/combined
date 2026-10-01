/**
 * 申诉管理 API 服务
 * Appeal Management API
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'
import { AppealStatus } from '@/types/appeal'
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
  AppealCandidates,
  AppealCaseIdentity,
  AppealScene,
  AppealTargetKind,
} from '@/types/appeal'

const API_V1_PREFIX = '/api/v1'

interface AppealDto {
  id: string
  appeal_number?: string | null
  qc_result_id?: string | null
  record_id?: string | null
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
  target_kind?: AppealTargetKind | null
  target_id?: string | null
  institute_id?: string | null
  patient_id?: string | null
  visit_id?: string | null
  scene?: AppealScene | null
  root_job_id?: string | null
  envelope_id?: string | null
  rule_set_key?: string | null
  rule_set_version?: string | null
  case_department?: string | null
}

interface AppealCandidatesDto {
  institute_id: string
  patient_id: string
  visit_id: string
  case_department?: string | null
  canonical: {
    state: 'ready' | 'no_result' | 'unavailable'
    scene?: AppealScene | null
    job_id?: string | null
    envelope_id?: string | null
    items: Array<{ rule_id: string; rule_name?: string | null; conclusion?: string | null }>
  }
  manual_defects: Array<{
    defect_id: string
    rule_code?: string | null
    rule_name?: string | null
    description?: string | null
    scene: AppealScene
  }>
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
    ? parsed.filter(
        (item): item is AppealEvidence =>
          typeof item === 'object' && item !== null && !Array.isArray(item),
      )
    : []
}

function mapAppeal(dto: AppealDto): Appeal {
  if (!Object.values(AppealStatus).includes(dto.status)) {
    throw new Error('申诉响应包含未知状态，已停止写入页面')
  }
  return {
    id: dto.id,
    appealNumber: dto.appeal_number ?? null,
    qcResultId: dto.qc_result_id ?? '',
    recordId: dto.record_id ?? '',
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
    targetKind: dto.target_kind ?? null,
    targetId: dto.target_id ?? null,
    instituteId: dto.institute_id ?? null,
    patientId: dto.patient_id ?? null,
    visitId: dto.visit_id ?? null,
    scene: dto.scene ?? null,
    rootJobId: dto.root_job_id ?? null,
    envelopeId: dto.envelope_id ?? null,
    ruleSetKey: dto.rule_set_key ?? null,
    ruleSetVersion: dto.rule_set_version ?? null,
    caseDepartment: dto.case_department ?? null,
  }
}

function requireIdentity(identity: AppealCaseIdentity): AppealCaseIdentity {
  const normalized = {
    instituteId: identity.instituteId.trim(),
    patientId: identity.patientId.trim(),
    visitId: identity.visitId.trim(),
  }
  if (!normalized.instituteId || !normalized.patientId || !normalized.visitId) {
    throw new Error('病例三坐标不完整，无法发起申诉')
  }
  return normalized
}

function isAppealScene(value: unknown): value is AppealScene {
  return value === 'running' || value === 'final' || value === 'outpatient_emergency'
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
  const identity = requireIdentity(data)
  const target =
    data.targetKind === 'canonical_defect'
      ? {
          expected_job_id: data.expectedJobId,
          expected_envelope_id: data.expectedEnvelopeId,
          rule_id: data.ruleId,
        }
      : {
          defect_id: data.defectId,
          ...(data.expectedJobId ? { expected_job_id: data.expectedJobId } : {}),
          ...(data.expectedEnvelopeId ? { expected_envelope_id: data.expectedEnvelopeId } : {}),
        }
  const dto = await requestOrThrow<AppealDto>(
    {
      method: 'POST',
      url: `${API_V1_PREFIX}/appeals/modern`,
      data: {
        target_kind: data.targetKind,
        institute_id: identity.instituteId,
        patient_id: identity.patientId,
        visit_id: identity.visitId,
        scene: data.scene,
        ...target,
        reason: data.appealReason,
        evidence: data.evidence ?? [],
        priority: data.priority ?? 'medium',
      },
    },
    '创建申诉失败',
  )
  return mapAppeal(dto)
}

export async function getAppealCandidates(identity: AppealCaseIdentity): Promise<AppealCandidates> {
  const normalized = requireIdentity(identity)
  const dto = await requestOrThrow<AppealCandidatesDto>(
    {
      method: 'GET',
      url: `${API_V1_PREFIX}/appeals/modern/candidates`,
      params: {
        institute_id: normalized.instituteId,
        patient_id: normalized.patientId,
        visit_id: normalized.visitId,
      },
    },
    '读取可申诉问题失败',
  )
  if (
    dto.institute_id !== normalized.instituteId ||
    dto.patient_id !== normalized.patientId ||
    dto.visit_id !== normalized.visitId
  ) {
    throw new Error('可申诉问题与当前病例不一致，已停止展示')
  }
  if (!['ready', 'no_result', 'unavailable'].includes(dto.canonical.state)) {
    throw new Error('可申诉问题包含未知来源状态，已停止展示')
  }
  if (dto.canonical.scene != null && !isAppealScene(dto.canonical.scene)) {
    throw new Error('可申诉问题包含未知质控场景，已停止展示')
  }
  if (dto.manual_defects.some((item) => !isAppealScene(item.scene))) {
    throw new Error('人工缺陷包含未知质控场景，已停止展示')
  }
  return {
    ...normalized,
    caseDepartment: dto.case_department ?? null,
    canonical: {
      state: dto.canonical.state,
      scene: dto.canonical.scene ?? null,
      jobId: dto.canonical.job_id ?? null,
      envelopeId: dto.canonical.envelope_id ?? null,
      items: dto.canonical.items.map((item) => ({
        ruleId: item.rule_id,
        ruleName: item.rule_name ?? null,
        conclusion: item.conclusion ?? null,
      })),
    },
    manualDefects: dto.manual_defects.map((item) => ({
      defectId: item.defect_id,
      ruleCode: item.rule_code ?? null,
      ruleName: item.rule_name ?? null,
      description: item.description ?? null,
      scene: item.scene,
    })),
  }
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
  if (filters.scene) params.scene = filters.scene
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
export async function updateAppeal(appealId: string, data: AppealUpdateRequest): Promise<Appeal> {
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
export async function reviewAppeal(appealId: string, review: AppealReviewRequest): Promise<Appeal> {
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
