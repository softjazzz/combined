import { ApiService } from '@/services/apiService'
import {
  extractApiErrorMessageFromError,
  isApiEnvelope,
  unwrapApiEnvelope,
} from '@/utils/api-envelope'
import type { AccountRole } from './accountManagement'

export type RegistrationState = 'pending' | 'approved' | 'rejected'
export interface RegistrationResult {
  user_id: string
  status: RegistrationState
  requested_institute_id: string
  requested_department: string
  version: number
  review_comment: string | null
  submitted_at: string
  reviewed_at: string | null
  updated_at: string
  is_active?: boolean
  display_name?: string
  institute_id?: string | null
  department?: string | null
  roles?: string[]
}
export interface RegistrationApplication {
  username: string
  email: string
  display_name: string
  institute_id: string
  department: string
  phone?: string
  password: string
}
export interface RegistrationItem extends RegistrationResult {
  username: string
  email: string
  display_name: string
}
export interface RegistrationDetail extends RegistrationItem {
  history: Array<{
    id: string
    actor_id: string
    action: 'submit' | 'approve' | 'reject'
    version: number
    comment: string
    institute_id: string
    department: string
    roles_json: string
    created_at: string
  }>
}
export interface RegistrationPage {
  items: RegistrationItem[]
  total: number
  page: number
  page_size: number
}
export interface RegistrationReview {
  expected_version: number
  decision: 'approve' | 'reject'
  comment: string
  institute_id?: string
  department?: string
  roles?: AccountRole[]
}

async function request<T>(config: Parameters<typeof ApiService.requestRaw>[0]): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    if (isApiEnvelope(response.data) && !response.data.success)
      throw new Error(response.data.message || response.data.error || '注册审批请求失败')
    return unwrapApiEnvelope<T>(response.data)
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, '注册审批服务暂不可用，请稍后核对'))
  }
}
export const submitRegistration = (data: RegistrationApplication) =>
  request<RegistrationResult>({ url: '/api/v1/auth/register', method: 'POST', data })
export const queryRegistrationStatus = (account: string, password: string) =>
  request<RegistrationResult>({
    url: '/api/v1/auth/registration-status',
    method: 'POST',
    data: { account, password },
  })
export const getOwnRegistration = () =>
  request<RegistrationResult>({ url: '/api/v1/auth/registration', method: 'GET' })
const base = '/api/v1/account-management/registrations'
export const listRegistrations = (params: {
  status: RegistrationState
  page: number
  page_size: number
}) => request<RegistrationPage>({ url: `${base}/list`, method: 'GET', params })
export const getRegistrationDetail = (id: string) =>
  request<RegistrationDetail>({ url: `${base}/${encodeURIComponent(id)}`, method: 'GET' })
export const reviewRegistration = (id: string, data: RegistrationReview) =>
  request<RegistrationResult>({
    url: `${base}/${encodeURIComponent(id)}/review`,
    method: 'POST',
    data,
  })
