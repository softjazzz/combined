import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'

export type AccountRole = 'admin' | 'qc_manager' | 'qc_staff' | 'doctor'
export interface ManagedAccount {
  id: string
  username: string
  email: string | null
  display_name: string
  institute_id: string | null
  department: string | null
  roles: string[]
  is_active: boolean
  created_at: string | null
  updated_at: string | null
  last_login_at: string | null
}
export interface AccountPage {
  items: ManagedAccount[]
  total: number
  actor_id: string
  managed_institute_id: string | null
  page: number
  page_size: number
}
export interface AccountBinding {
  display_name: string
  institute_id: string
  department: string
  roles: AccountRole[]
}
export interface AccountCreate extends AccountBinding {
  username: string
  email: string
  password: string
}
export interface AccountUpdate extends AccountBinding {
  is_active: boolean
  expected_updated_at: string | null
}
async function request<T>(config: Parameters<typeof ApiService.requestRaw>[0]): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    return unwrapApiEnvelope<T>(response.data)
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, '账号服务暂不可用，请刷新核对'))
  }
}
const base = '/api/v1/account-management'
export const listManagedAccounts = (params: {
  keyword?: string
  role?: AccountRole
  active?: boolean
  page: number
  page_size: number
}) => request<AccountPage>({ url: base, method: 'GET', params })
export const createManagedAccount = (data: AccountCreate) =>
  request<ManagedAccount>({ url: base, method: 'POST', data })
export const updateManagedAccount = (id: string, data: AccountUpdate) =>
  request<ManagedAccount>({ url: `${base}/${encodeURIComponent(id)}`, method: 'PUT', data })
