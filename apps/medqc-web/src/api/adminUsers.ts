import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/admin/users'
/** 列表筛选“未分配科室”的哨兵值，与后端约定一致。 */
export const UNASSIGNED_DEPARTMENT = '__unassigned__'
export const DEPARTMENT_MAX_LENGTH = 100

export interface AdminUser {
  id: string
  username: string
  display_name: string
  institute_id: string | null
  department: string | null
  roles: string[]
  is_active: boolean
  updated_at: string
}

export interface AdminUserPage {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
  departments: string[]
}

export interface UserScopeOption {
  institute_id: string
  department: string
}

export interface UserScopeOptions {
  items: UserScopeOption[]
  institutes: string[]
}

export type ApiResult<T> = { success: true; data: T } | { success: false; message: string }
export type UserScopeUpdateResult =
  | { success: true; data: AdminUser; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isUser(value: unknown): value is AdminUser {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    Boolean(value.id) &&
    typeof value.username === 'string' &&
    typeof value.display_name === 'string' &&
    (value.institute_id === null || typeof value.institute_id === 'string') &&
    (value.department === null || typeof value.department === 'string') &&
    Array.isArray(value.roles) &&
    value.roles.every((role) => typeof role === 'string') &&
    typeof value.is_active === 'boolean' &&
    typeof value.updated_at === 'string' &&
    !Number.isNaN(Date.parse(value.updated_at))
  )
}

function isScopeOptions(value: unknown): value is UserScopeOptions {
  return (
    isRecord(value) &&
    Array.isArray(value.institutes) &&
    value.institutes.every((item) => typeof item === 'string' && Boolean(item.trim())) &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.institute_id === 'string' &&
        Boolean(item.institute_id.trim()) &&
        typeof item.department === 'string' &&
        Boolean(item.department.trim()),
    )
  )
}

function isPage(value: unknown): value is AdminUserPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isUser) &&
    Number.isInteger(value.total) &&
    Number(value.total) >= 0 &&
    Number.isInteger(value.page) &&
    Number(value.page) >= 1 &&
    Number.isInteger(value.page_size) &&
    Number(value.page_size) >= 1 &&
    Array.isArray(value.departments) &&
    value.departments.every((item) => typeof item === 'string')
  )
}

function errorStatus(error: unknown): number | undefined {
  if (!isRecord(error) || !isRecord(error.response)) return undefined
  return typeof error.response.status === 'number' ? error.response.status : undefined
}

export async function listAdminUsers(params: {
  page: number
  page_size: number
  q?: string
  department?: string
}): Promise<ApiResult<AdminUserPage>> {
  const q = params.q?.trim() || ''
  const department = params.department?.trim() || ''
  try {
    const response = await ApiService.requestRaw({
      method: 'GET',
      url: BASE_URL,
      params: {
        page: params.page,
        page_size: params.page_size,
        ...(q ? { q } : {}),
        ...(department ? { department } : {}),
      },
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    return normalized.success && isPage(normalized.data)
      ? { success: true, data: normalized.data }
      : { success: false, message: '账号列表回执格式异常' }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, '账号列表暂不可用') }
  }
}

export async function getUserScopeOptions(): Promise<ApiResult<UserScopeOptions>> {
  try {
    const response = await ApiService.requestRaw({
      method: 'GET',
      url: `${BASE_URL}/scope-options`,
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    return normalized.success && isScopeOptions(normalized.data)
      ? { success: true, data: normalized.data }
      : { success: false, message: '医院科室选项回执格式异常' }
  } catch (error) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, '医院科室选项暂不可用'),
    }
  }
}

/** 按账号版本 CAS 设置医院与科室；两者必须同时设置或同时清空。 */
export async function updateUserScope(
  userId: string,
  payload: { institute_id: string; department: string; expected_updated_at: string },
): Promise<UserScopeUpdateResult> {
  const instituteId = payload.institute_id.trim()
  const department = payload.department.trim()
  if (Boolean(instituteId) !== Boolean(department)) {
    return {
      success: false,
      message: '医院与科室必须同时设置或同时清空',
      resultUnknown: false,
      conflict: false,
    }
  }
  if (department.length > DEPARTMENT_MAX_LENGTH) {
    return {
      success: false,
      message: `科室不能超过 ${DEPARTMENT_MAX_LENGTH} 个字符`,
      resultUnknown: false,
      conflict: false,
    }
  }
  try {
    const response = await ApiService.requestRaw({
      method: 'PUT',
      url: `${BASE_URL}/${encodeURIComponent(userId)}/department`,
      data: {
        institute_id: instituteId || null,
        department: department || null,
        expected_updated_at: payload.expected_updated_at,
      },
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const data = normalized.data
    if (
      !normalized.success ||
      !isUser(data) ||
      data.id !== userId ||
      (data.institute_id ?? '') !== instituteId ||
      (data.department ?? '') !== department
    ) {
      return {
        success: false,
        message: '归属保存结果无法确认，请刷新列表核对',
        resultUnknown: true,
        conflict: false,
      }
    }
    return { success: true, data, resultUnknown: false, conflict: false }
  } catch (error) {
    const status = errorStatus(error)
    const confirmed = [401, 403, 404, 409, 422].includes(status || 0)
    return {
      success: false,
      message: confirmed
        ? extractApiErrorMessageFromError(
            error,
            status === 409 ? '账号已被修改，请刷新后重试' : '医院科室保存被拒绝',
          )
        : '归属保存结果无法确认，请刷新列表核对',
      resultUnknown: !confirmed,
      conflict: status === 409,
    }
  }
}
