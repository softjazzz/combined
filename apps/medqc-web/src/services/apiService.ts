// @ts-nocheck
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { message } from 'ant-design-vue'
import {
  clearAuthTokens,
  getAccessToken as readAccessToken,
  getRefreshToken as readRefreshToken,
  setAccessToken as writeAccessToken,
  setRefreshToken as writeRefreshToken,
} from '@/utils/auth-token'
import { extractApiErrorMessage, unwrapApiEnvelope } from '@/utils/api-envelope'
import type { RegistrationResult } from '@/api/accountRegistration'
import {
  attachTraceIdToError,
  ensureTraceHeaders,
  extractTraceIdFromHeaders,
  extractTraceIdFromResponse,
} from '@/utils/trace'
import type {
  ApiResponse,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
  MedicalRecord,
  CreateMedicalRecordRequest,
  UpdateMedicalRecordRequest,
  SearchParams,
  PaginatedResponse,
  QCResult,
  QCRule,
  QCAnalysisRequest,
} from '@/types'

// API基础配置
const ENV_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined

function isLoopbackHost(host: string): boolean {
  return ['localhost', '127.0.0.1', '::1'].includes(host)
}

function computeBaseURL(): string {
  // 优先使用环境变量
  let base = ENV_BASE && ENV_BASE.trim() !== '' ? ENV_BASE.trim() : ''

  // 开发环境使用vite代理，避免CORS问题
  if (import.meta.env.DEV) {
    return '' // 使用相对路径，通过vite代理转发到后端
  }

  // 生产/客户部署默认走同源 /api，由静态服务反向代理到后端。
  // 只有显式配置了绝对地址时才使用绝对基址，避免浏览器直接请求 :8001 触发 CORS，
  // 同时兼容局域网通过前端入口访问的场景。
  return base
}

const API_BASE_URL = computeBaseURL()
const API_TIMEOUT = 15000 // 15秒超时，避免过长等待
const LOGIN_TIMEOUT = 10000 // 登录请求10秒超时
const API_DEBUG =
  import.meta.env.DEV && String(import.meta.env.VITE_API_DEBUG || '').toLowerCase() === 'true'
const DEBUG_REDACTED = '[REDACTED]'
const DEBUG_SENSITIVE_KEYS = new Set([
  'activation_code',
  'password',
  'password_hash',
  'new_password',
  'old_password',
  'access_token',
  'refresh_token',
])

function redactDebugSensitiveValues(value: unknown, seen = new WeakSet<object>()): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => redactDebugSensitiveValues(item, seen))
  }
  if (!value || typeof value !== 'object') return value
  if (seen.has(value)) return '[Circular]'
  const prototype = Object.getPrototypeOf(value)
  if (prototype !== Object.prototype && prototype !== null) return value

  seen.add(value)
  const redacted = Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => [
      key,
      DEBUG_SENSITIVE_KEYS.has(key) ? DEBUG_REDACTED : redactDebugSensitiveValues(item, seen),
    ]),
  )
  seen.delete(value)
  return redacted
}

// 调试信息
if (API_DEBUG) {
  console.log('🔧 API Configuration:')
  console.log('  VITE_API_BASE_URL:', ENV_BASE)
  console.log('  Final API_BASE_URL:', API_BASE_URL || '[same-origin]')
}

// 创建axios实例
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 全局刷新控制，避免并发重复刷新与竞态
let refreshPromise: Promise<string> | null = null

function shouldSuppressExpected404(url: string | undefined, status: number | undefined): boolean {
  if (status !== 404 || !url) return false
  return (
    url.includes('/api/medical-records/frontpage-sheet/') ||
    url.includes('/api/medical-records/settlement/') ||
    url.includes('/api/medical-records/ai-frontpage-draft/')
  )
}

// Token管理
class TokenManager {
  static getToken(): string | null {
    const token = readAccessToken()
    return token || null
  }

  static setToken(token: string): void {
    writeAccessToken(token)
  }

  static getRefreshToken(): string | null {
    const token = readRefreshToken()
    return token || null
  }

  static setRefreshToken(token: string): void {
    writeRefreshToken(token)
  }

  static clearTokens(): void {
    clearAuthTokens()
  }

  static isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.exp * 1000 < Date.now()
    } catch {
      return true
    }
  }
}

// 请求拦截器
apiClient.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    const token = TokenManager.getToken()
    if (token && !TokenManager.isTokenExpired(token)) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }

    const { headers: traceHeaders, traceId } = ensureTraceHeaders(
      config.headers as Record<string, unknown>,
    )
    config.headers = traceHeaders

    if (API_DEBUG) {
      console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
        traceId,
        headers: config.headers,
        data: redactDebugSensitiveValues(config.data),
        params: config.params,
      })
    }

    return config
  },
  (error: unknown) => {
    console.error('❌ Request interceptor error:', error)
    return Promise.reject(error)
  },
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    if (API_DEBUG) {
      console.log(
        `✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`,
        {
          status: response.status,
          data: redactDebugSensitiveValues(response.data),
        },
      )
    }
    return response
  },
  async (error: unknown) => {
    const originalRequest = error.config
    const requestUrl: string | undefined = error.config?.url
    const responseStatus: number | undefined = error.response?.status
    const traceId = extractTraceIdFromResponse(error.response) || extractTraceIdFromResponse(error)
    attachTraceIdToError(error, traceId)

    // 只在开发环境或非认证错误时记录详细错误
    if (
      !shouldSuppressExpected404(requestUrl, responseStatus) &&
      (process.env.NODE_ENV === 'development' || responseStatus !== 401)
    ) {
      console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${requestUrl}`, {
        status: responseStatus,
        data: error.response?.data,
        message: error.message,
        traceId,
      })
    }

    // Token过期处理（带单航刷新，避免并发冲突）
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 登录外的口令查询失败不是会话过期，不刷新令牌或重放注册写入。
      const url: string = originalRequest?.url || ''
      if (
        url.includes('/api/v1/auth/login') ||
        url.includes('/api/v1/auth/refresh') ||
        url.includes('/api/v1/auth/registration-status') ||
        url.endsWith('/api/v1/auth/register')
      ) {
        return Promise.reject(error)
      }

      originalRequest._retry = true

      const refreshToken = TokenManager.getRefreshToken()
      if (!refreshToken) {
        // 无刷新令牌：清理并抛错，由上层处理登录跳转
        TokenManager.clearTokens()
        return Promise.reject(error)
      }

      // 复用正在进行的刷新请求
      if (!refreshPromise) {
        const inheritedTraceId =
          extractTraceIdFromHeaders(originalRequest?.headers) || traceId || undefined
        const { headers: refreshHeaders } = ensureTraceHeaders({}, inheritedTraceId)
        refreshPromise = axios
          .post(
            `${API_BASE_URL}/api/v1/auth/refresh`,
            { refresh_token: refreshToken },
            { headers: refreshHeaders },
          )
          .then((response) => {
            const { access_token, refresh_token: newRefreshToken } = response.data
            if (access_token) TokenManager.setToken(access_token)
            if (newRefreshToken) TokenManager.setRefreshToken(newRefreshToken)
            return access_token as string
          })
          .catch((refreshError) => {
            console.error('Token refresh failed:', refreshError)
            TokenManager.clearTokens()
            throw refreshError
          })
          .finally(() => {
            refreshPromise = null
          })
      }

      // 等待刷新完成后重试原请求
      try {
        const newAccessToken = await refreshPromise
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return apiClient(originalRequest)
      } catch (e) {
        return Promise.reject(e)
      }
    }

    // 统一错误处理（兼容后端统一错误结构）
    const data = error.response?.data || {}
    const errorMessage = data.message || data.error || data.detail || error.message || '请求失败'
    const traceIdFromPayload = traceId || data.trace_id || data.traceId

    // 根据状态码显示不同的错误信息
    switch (error.response?.status) {
      case 400:
        message.error(`请求参数错误: ${errorMessage}`)
        break
      case 401:
        message.error('认证失败，请重新登录')
        break
      case 403:
        message.error(`权限不足：${errorMessage}`)
        break
      case 404:
        if (!shouldSuppressExpected404(requestUrl, responseStatus)) {
          message.error('请求的资源不存在')
        }
        break
      case 422:
        message.error(`数据验证失败: ${errorMessage}`)
        break
      case 429:
        message.error('请求过于频繁，请稍后再试')
        break
      case 500:
        message.error(
          traceIdFromPayload
            ? `服务器错误（${traceIdFromPayload}），请联系管理员`
            : '服务器内部错误，请联系管理员',
        )
        break
      case 502:
      case 503:
      case 504:
        message.error('服务暂时不可用，请稍后再试')
        break
      default:
        if (error.code === 'ECONNABORTED') {
          message.error('请求超时，请检查网络连接')
        } else if (error.code === 'ERR_NETWORK') {
          message.error('网络连接失败，请检查网络设置')
        } else {
          message.error(`请求失败: ${errorMessage}`)
        }
    }

    return Promise.reject(error)
  },
)

// API服务类
export class ApiService {
  // Generic HTTP helpers used by legacy/new modules.
  static async requestRaw<T = unknown>(config: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return apiClient.request<T>(config)
  }

  static async getRaw<T = unknown>(
    url: string,
    params?: Record<string, unknown>,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> {
    return apiClient.get<T>(url, { ...(config || {}), params })
  }

  static async postRaw<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> {
    return apiClient.post<T>(url, data, config)
  }

  static async putRaw<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> {
    return apiClient.put<T>(url, data, config)
  }

  static async deleteRaw<T = unknown>(
    url: string,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> {
    return apiClient.delete<T>(url, config)
  }

  static async get<T = unknown>(
    url: string,
    params?: Record<string, unknown>,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.get<T>(url, { ...(config || {}), params })
      return { success: true, data: unwrapApiEnvelope<T>(response.data) }
    } catch (error: any) {
      return {
        success: false,
        error: extractApiErrorMessage(
          error?.response?.data,
          error?.message || 'GET request failed',
        ),
        data: null as any,
      }
    }
  }

  static async post<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.post<T>(url, data, config)
      return { success: true, data: unwrapApiEnvelope<T>(response.data) }
    } catch (error: any) {
      return {
        success: false,
        error: extractApiErrorMessage(
          error?.response?.data,
          error?.message || 'POST request failed',
        ),
        data: null as any,
      }
    }
  }

  static async put<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.put<T>(url, data, config)
      return { success: true, data: unwrapApiEnvelope<T>(response.data) }
    } catch (error: any) {
      return {
        success: false,
        error: extractApiErrorMessage(
          error?.response?.data,
          error?.message || 'PUT request failed',
        ),
        data: null as any,
      }
    }
  }

  static async delete<T = unknown>(
    url: string,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.delete<T>(url, config)
      return { success: true, data: unwrapApiEnvelope<T>(response.data) }
    } catch (error: any) {
      return {
        success: false,
        error: extractApiErrorMessage(
          error?.response?.data,
          error?.message || 'DELETE request failed',
        ),
        data: null as any,
      }
    }
  }

  // ==================== 用户认证相关API (B1任务 - 9个接口) ====================

  /**
   * 用户登录
   */
  static async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    try {
      const account = credentials.account || credentials.email || ''
      const payload: LoginRequest = {
        ...credentials,
        account,
      }
      console.log('🔐 ApiService.login 发送请求:', {
        account,
        role: credentials.role,
        roleType: typeof credentials.role,
        hasPassword: Boolean(credentials.password),
      })

      const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', payload)
      console.log('📡 ApiService.login 收到响应:', redactDebugSensitiveValues(response.data))

      // 保存token
      if (response.data.access_token) {
        TokenManager.setToken(response.data.access_token)
      }
      if (response.data.refresh_token) {
        TokenManager.setRefreshToken(response.data.refresh_token)
      }

      return {
        success: true,
        data: response.data,
        message: '登录成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '登录失败',
        data: null,
      }
    }
  }

  /**
   * 用户注册
   */
  static async register(userData: RegisterRequest): Promise<ApiResponse<RegistrationResult>> {
    try {
      const response = await apiClient.post('/api/v1/auth/register', userData)
      return {
        success: true,
        data: unwrapApiEnvelope<RegistrationResult>(response.data),
        message: response.data.message || '注册申请已保存，请等待管理员审批',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '注册失败',
        data: null,
      }
    }
  }

  /**
   * 获取当前用户信息
   */
  static async getCurrentUser(): Promise<ApiResponse<User>> {
    try {
      const response = await apiClient.get<User>('/api/v1/auth/me')
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取用户信息失败',
        data: null,
      }
    }
  }

  /**
   * 更新用户资料
   */
  static async updateProfile(profileData: Partial<User>): Promise<ApiResponse<User>> {
    try {
      const response = await apiClient.put<User>('/api/v1/auth/profile', profileData)
      return {
        success: true,
        data: response.data,
        message: '资料更新成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '资料更新失败',
        data: null,
      }
    }
  }

  /**
   * 修改密码
   */
  static async updatePassword(
    newPassword: string,
    currentPassword?: string,
  ): Promise<ApiResponse<void>> {
    try {
      await apiClient.put('/api/v1/auth/password', {
        new_password: newPassword,
        current_password: currentPassword,
      })
      return {
        success: true,
        message: '密码修改成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '密码修改失败',
      }
    }
  }

  /**
   * 用户登出
   */
  static async logout(): Promise<ApiResponse<void>> {
    try {
      await apiClient.post('/api/v1/auth/logout')
      TokenManager.clearTokens()
      return {
        success: true,
        message: '登出成功',
      }
    } catch (error: unknown) {
      // 即使API调用失败，也要清除本地token
      TokenManager.clearTokens()
      return {
        success: true,
        message: '登出成功',
      }
    }
  }

  /**
   * 刷新token
   */
  static async refreshToken(): Promise<ApiResponse<LoginResponse>> {
    try {
      const refreshToken = TokenManager.getRefreshToken()
      if (!refreshToken) {
        throw new Error('No refresh token available')
      }

      const response = await apiClient.post<LoginResponse>('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      })

      // 更新token
      if (response.data.access_token) {
        TokenManager.setToken(response.data.access_token)
      }
      if (response.data.refresh_token) {
        TokenManager.setRefreshToken(response.data.refresh_token)
      }

      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      TokenManager.clearTokens()
      return {
        success: false,
        error: error.response?.data?.message || 'Token刷新失败',
      }
    }
  }

  /**
   * 忘记密码
   */
  static async forgotPassword(email: string): Promise<ApiResponse<void>> {
    try {
      await apiClient.post('/api/v1/auth/forgot-password', { email })
      return {
        success: true,
        message: '重置密码邮件已发送',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '发送重置邮件失败',
      }
    }
  }

  /**
   * 重置密码
   */
  static async resetPassword(token: string, newPassword: string): Promise<ApiResponse<void>> {
    try {
      await apiClient.post('/api/v1/auth/reset-password', {
        token,
        new_password: newPassword,
      })
      return {
        success: true,
        message: '密码重置成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '密码重置失败',
      }
    }
  }

  // ==================== 医疗记录相关API (B2任务 - 10个接口) ====================

  /**
   * 获取医疗记录列表
   */
  static async getMedicalRecords(
    params?: SearchParams,
  ): Promise<ApiResponse<PaginatedResponse<MedicalRecord>>> {
    try {
      const queryParams = new URLSearchParams()

      if (params?.keyword) queryParams.append('keyword', params.keyword)
      if (params?.filters?.department) queryParams.append('department', params.filters.department)
      if (params?.filters?.status) queryParams.append('status', params.filters.status)
      if (params?.filters?.record_type)
        queryParams.append('record_type', params.filters.record_type)
      if (params?.sort?.field) queryParams.append('sort_field', params.sort.field)
      if (params?.sort?.order) queryParams.append('sort_order', params.sort.order)
      if (params?.pagination?.page) queryParams.append('page', params.pagination.page.toString())
      if (params?.pagination?.pageSize)
        queryParams.append('page_size', params.pagination.pageSize.toString())

      const response = await apiClient.get<PaginatedResponse<MedicalRecord>>(
        `/api/records?${queryParams}`,
      )
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取医疗记录失败',
        data: null,
      }
    }
  }

  /**
   * 获取单个医疗记录详情
   */
  static async getMedicalRecord(id: string): Promise<ApiResponse<MedicalRecord>> {
    try {
      const response = await apiClient.get<MedicalRecord>(`/api/records/${id}`)
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取医疗记录详情失败',
        data: null,
      }
    }
  }

  /**
   * 创建医疗记录
   */
  static async createMedicalRecord(
    recordData: CreateMedicalRecordRequest,
  ): Promise<ApiResponse<MedicalRecord>> {
    try {
      const formData = new FormData()

      // 添加基本字段
      formData.append('patient_name', recordData.patient_name)
      formData.append('patient_age', recordData.patient_age.toString())
      formData.append('patient_gender', recordData.patient_gender)
      formData.append('department', recordData.department)
      formData.append('admission_date', recordData.admission_date)
      formData.append('record_type', recordData.record_type)
      formData.append('content', recordData.content)

      // 添加文件（如果有）
      if (recordData.file) {
        formData.append('file', recordData.file)
      }

      const response = await apiClient.post<MedicalRecord>('/api/records', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      return {
        success: true,
        data: response.data,
        message: '医疗记录创建成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '创建医疗记录失败',
        data: null,
      }
    }
  }

  /**
   * 更新医疗记录
   */
  static async updateMedicalRecord(
    id: string,
    recordData: UpdateMedicalRecordRequest,
  ): Promise<ApiResponse<MedicalRecord>> {
    try {
      const formData = new FormData()

      // 添加基本字段
      if (recordData.patient_name) formData.append('patient_name', recordData.patient_name)
      if (recordData.patient_age) formData.append('patient_age', recordData.patient_age.toString())
      if (recordData.patient_gender) formData.append('patient_gender', recordData.patient_gender)
      if (recordData.department) formData.append('department', recordData.department)
      if (recordData.admission_date) formData.append('admission_date', recordData.admission_date)
      if (recordData.record_type) formData.append('record_type', recordData.record_type)
      if (recordData.content) formData.append('content', recordData.content)

      // 添加文件（如果有）
      if (recordData.file) {
        formData.append('file', recordData.file)
      }

      const response = await apiClient.put<MedicalRecord>(`/api/records/${id}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      return {
        success: true,
        data: response.data,
        message: '医疗记录更新成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '更新医疗记录失败',
        data: null,
      }
    }
  }

  /**
   * 删除医疗记录
   */
  static async deleteMedicalRecord(id: string): Promise<ApiResponse<void>> {
    try {
      await apiClient.delete(`/api/records/${id}`)
      return {
        success: true,
        message: '医疗记录删除成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '删除医疗记录失败',
      }
    }
  }

  /**
   * 批量删除医疗记录
   */
  static async batchDeleteRecords(ids: string[]): Promise<ApiResponse<void>> {
    try {
      await apiClient.delete('/api/records/batch', {
        data: { record_ids: ids },
      })
      return {
        success: true,
        message: '批量删除成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '批量删除失败',
      }
    }
  }

  /**
   * 导出医疗记录
   */
  static async exportRecords(ids: string[]): Promise<ApiResponse<{ download_url: string }>> {
    try {
      const response = await apiClient.post<{ download_url: string }>('/api/records/export', {
        record_ids: ids,
      })
      return {
        success: true,
        data: response.data,
        message: '导出任务创建成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '导出失败',
        data: null,
      }
    }
  }

  /**
   * 获取医疗记录统计信息
   */
  static async getMedicalRecordsStatistics(): Promise<ApiResponse<unknown>> {
    try {
      const response = await apiClient.get('/api/records/statistics')
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取统计信息失败',
        data: null,
      }
    }
  }

  /**
   * 上传医疗记录文件
   */
  static async uploadRecordFile(
    file: File,
  ): Promise<ApiResponse<{ file_url: string; file_name: string }>> {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.post<{ file_url: string; file_name: string }>(
        '/api/records/upload',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        },
      )

      return {
        success: true,
        data: response.data,
        message: '文件上传成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '文件上传失败',
        data: null,
      }
    }
  }

  /**
   * 复制医疗记录
   */
  static async duplicateRecord(id: string): Promise<ApiResponse<MedicalRecord>> {
    try {
      const response = await apiClient.post<MedicalRecord>(`/api/records/${id}/duplicate`)
      return {
        success: true,
        data: response.data,
        message: '记录复制成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '记录复制失败',
        data: null,
      }
    }
  }

  // ==================== 质控分析相关API (B3任务 - 9个接口) ====================

  /**
   * 开始质控分析
   */
  static async analyzeRecord(
    recordId: string,
    analysisParams?: QCAnalysisRequest,
  ): Promise<ApiResponse<{ analysis_id: string }>> {
    try {
      const response = await apiClient.post<{ analysis_id: string }>(
        `/api/qc/analyze/${recordId}`,
        analysisParams || {},
      )
      return {
        success: true,
        data: response.data,
        message: '质控分析已开始',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '开始分析失败',
        data: null,
      }
    }
  }

  /**
   * 批量质控分析
   */
  static async batchAnalyzeRecords(
    recordIds: string[],
  ): Promise<ApiResponse<{ analysis_ids: string[] }>> {
    try {
      const response = await apiClient.post<{ analysis_ids: string[] }>('/api/qc/analyze/batch', {
        record_ids: recordIds,
      })
      return {
        success: true,
        data: response.data,
        message: '批量分析已开始',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '批量分析失败',
        data: null,
      }
    }
  }

  /**
   * 获取质控分析结果
   */
  static async getQCResult(recordId: string): Promise<ApiResponse<QCResult>> {
    try {
      const response = await apiClient.get<QCResult>(`/api/qc/result/${recordId}`)
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取分析结果失败',
        data: null,
      }
    }
  }

  /**
   * 获取分析进度
   */
  static async getAnalysisProgress(analysisId: string): Promise<ApiResponse<unknown>> {
    try {
      const response = await apiClient.get(`/api/qc/progress/${analysisId}`)
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取分析进度失败',
        data: null,
      }
    }
  }

  /**
   * 获取质控规则列表
   */
  static async getQCRules(): Promise<ApiResponse<QCRule[]>> {
    try {
      const response = await apiClient.get<QCRule[]>('/api/qc/rules')
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取质控规则失败',
        data: null,
      }
    }
  }

  /**
   * 创建质控规则
   */
  static async createQCRule(ruleData: Partial<QCRule>): Promise<ApiResponse<QCRule>> {
    try {
      const response = await apiClient.post<QCRule>('/api/qc/rules', ruleData)
      return {
        success: true,
        data: response.data,
        message: '质控规则创建成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '创建质控规则失败',
        data: null,
      }
    }
  }

  /**
   * 更新质控规则
   */
  static async updateQCRule(
    ruleId: string,
    ruleData: Partial<QCRule>,
  ): Promise<ApiResponse<QCRule>> {
    try {
      const response = await apiClient.put<QCRule>(`/api/qc/rules/${ruleId}`, ruleData)
      return {
        success: true,
        data: response.data,
        message: '质控规则更新成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '更新质控规则失败',
        data: null,
      }
    }
  }

  /**
   * 删除质控规则
   */
  static async deleteQCRule(ruleId: string): Promise<ApiResponse<void>> {
    try {
      await apiClient.delete(`/api/qc/rules/${ruleId}`)
      return {
        success: true,
        message: '质控规则删除成功',
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '删除质控规则失败',
      }
    }
  }

  /**
   * 获取质控历史记录
   */
  static async getQCHistory(params?: {
    page?: number
    pageSize?: number
  }): Promise<ApiResponse<any[]>> {
    try {
      const queryParams = new URLSearchParams()
      if (params?.page) queryParams.append('page', params.page.toString())
      if (params?.pageSize) queryParams.append('page_size', params.pageSize.toString())

      const response = await apiClient.get<any[]>(`/api/qc/history?${queryParams}`)
      return {
        success: true,
        data: response.data,
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取质控历史失败',
        data: null,
      }
    }
  }

  // ==================== 工具方法 ====================

  /**
   * 检查API连接状态
   */
  static async checkConnection(): Promise<boolean> {
    try {
      await apiClient.get('/api/health')
      return true
    } catch {
      return false
    }
  }

  /**
   * 获取API基础URL
   */
  static getBaseURL(): string {
    return API_BASE_URL
  }

  /**
   * 检查用户是否已登录
   */
  static isAuthenticated(): boolean {
    const token = TokenManager.getToken()
    return token !== null && !TokenManager.isTokenExpired(token)
  }
}

// 导出默认实例
export default ApiService
