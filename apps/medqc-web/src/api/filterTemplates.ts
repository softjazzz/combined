/**
 * 个人筛选模板 API（合同：docs/plans/2026-09-27-v36-filter-templates-design.md 第 2、3 节）
 *
 * 只能读写本人模板；更新与删除均携带 version 做 CAS。
 * 409 业务码：name_conflict（重名）、limit_reached（超出 20 个上限）、version_conflict（版本已变化）。
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type { RecordLatestReviewState } from '@/views/workstation-v4/types'

export type FilterTemplatePageKey =
  | 'v5_records_inpatient'
  | 'v5_records_discharged'
  | 'v5_records_outpatient_emergency'
export type FilterTemplateDateField = 'visit' | 'admission' | 'discharge' | 'updated'
export type FilterTemplateInpatientSort = 'default' | 'longest' | 'recent'
export type FilterTemplateConflictCode = 'name_conflict' | 'limit_reached' | 'version_conflict'

/** 模板保存的筛选条件：仅服务端白名单键，不含页码与分页大小。 */
export interface FilterTemplateFilters {
  dept?: string
  doctor?: string
  keyword?: string
  start_date?: string
  end_date?: string
  date_field?: FilterTemplateDateField
  inpatient_sort?: FilterTemplateInpatientSort
  review_state?: RecordLatestReviewState[]
}

export interface FilterTemplate {
  id: string
  page_key: FilterTemplatePageKey
  name: string
  /** null 表示存量内容已不可用（服务端校验失败），前端不得当作空筛选应用。 */
  filters: FilterTemplateFilters | null
  is_default: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface FilterTemplateCreatePayload {
  page_key: FilterTemplatePageKey
  name: string
  filters: FilterTemplateFilters
  is_default?: boolean
}

export interface FilterTemplateUpdatePayload {
  version: number
  name?: string
  filters?: FilterTemplateFilters
  is_default?: boolean
}

export interface FilterTemplateApiResult<T> {
  success: boolean
  data?: T
  message?: string
  /** HTTP 状态码；网络异常时为 undefined。 */
  status?: number
  /** 409 结构化错误的业务 code；其他错误为 undefined。 */
  code?: FilterTemplateConflictCode
}

const CONFLICT_CODES: readonly FilterTemplateConflictCode[] = [
  'name_conflict',
  'limit_reached',
  'version_conflict',
]

function isConflictCode(value: unknown): value is FilterTemplateConflictCode {
  return typeof value === 'string' && (CONFLICT_CODES as readonly string[]).includes(value)
}

/**
 * 读取 409 结构化 detail。
 * 后端统一异常包装把 HTTPException.detail 放在 `error` 字段；直连 FastAPI 时位于 `detail`。
 */
function extractConflictDetail(error: unknown): {
  code?: FilterTemplateConflictCode
  message?: string
} {
  if (!isAxiosError(error)) return {}
  const body: unknown = error.response?.data
  if (typeof body !== 'object' || body === null) return {}
  for (const key of ['detail', 'error'] as const) {
    const candidate: unknown = (body as Record<string, unknown>)[key]
    if (typeof candidate === 'object' && candidate !== null) {
      const { code, message } = candidate as Record<string, unknown>
      if (isConflictCode(code)) {
        return {
          code,
          message: typeof message === 'string' && message.trim() ? message : undefined,
        }
      }
    }
  }
  return {}
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallback: string,
): Promise<FilterTemplateApiResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
      status: response.status,
    }
  } catch (error) {
    const detail = extractConflictDetail(error)
    return {
      success: false,
      message: detail.message || extractApiErrorMessageFromError(error, fallback),
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: detail.code,
    }
  }
}

/** 本人在该页的全部模板（服务端按默认优先、再按名称排序）。 */
export async function listFilterTemplates(
  pageKey: FilterTemplatePageKey,
): Promise<FilterTemplateApiResult<FilterTemplate[]>> {
  const result = await request<FilterTemplate[] | { items?: FilterTemplate[] }>(
    { method: 'GET', url: '/api/v1/filter-templates', params: { page_key: pageKey } },
    '读取筛选模板失败',
  )
  if (!result.success) return { ...result, data: undefined }
  // 合同未限定外层形状：兼容直接数组与 {items} 两种返回；其他形状视为失败，不伪造空列表。
  const raw = result.data
  const items = Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : null
  if (!items) return { success: false, status: result.status, message: '筛选模板返回格式无法识别' }
  return { ...result, data: items }
}

export async function createFilterTemplate(payload: FilterTemplateCreatePayload) {
  return request<FilterTemplate>(
    { method: 'POST', url: '/api/v1/filter-templates', data: payload },
    '保存筛选模板失败',
  )
}

export async function updateFilterTemplate(id: string, payload: FilterTemplateUpdatePayload) {
  return request<FilterTemplate>(
    { method: 'PUT', url: `/api/v1/filter-templates/${encodeURIComponent(id)}`, data: payload },
    '更新筛选模板失败',
  )
}

export async function removeFilterTemplate(id: string, version: number) {
  return request<unknown>(
    {
      method: 'DELETE',
      url: `/api/v1/filter-templates/${encodeURIComponent(id)}`,
      params: { version },
    },
    '删除筛选模板失败',
  )
}
