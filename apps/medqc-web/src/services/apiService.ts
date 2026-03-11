import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { message } from 'ant-design-vue'
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
  MedicalRecordDocumentsResponse,
  MedicalRecordDocumentPayload
} from '@/types'
import type { RecordDocumentInfo } from '@/types/quality-control'
import { mockLogin, mockGetCurrentUser, mockRegister, mockRefreshToken } from '@/data/mock-auth'

// Mock 配置
const USE_AUTH_MOCK = import.meta.env.VITE_USE_AUTH_MOCK !== 'false' // 默认启用 Mock

// API基础配置
const ENV_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined

function computeBaseURL(): string {
  // 优先使用环境变量
  let base = ENV_BASE && ENV_BASE.trim() !== '' ? ENV_BASE.trim() : ''

  // 开发环境使用vite代理，避免CORS问题
  if (import.meta.env.DEV) {
    // 开发环境优先使用显式配置的地址；否则继续走 Vite 代理
    if (base) {
      return base
    }
    return '' // 使用相对路径，通过 Vite 代理转发到后端
  }

  try {
    if (typeof window !== 'undefined') {
      const host = window.location.hostname
      const isLocalHost = ['localhost', '127.0.0.1', '::1'].includes(host)
      const isPrivateIPv4 = /^10\.|^192\.168\.|^172\.(1[6-9]|2\d|3[0-1])\./.test(host)
      // 本地/内网环境强制指向本机后端，避免误用线上域名导致证书/跨域问题
      if (isLocalHost || isPrivateIPv4) {
        base = 'http://127.0.0.1:8001'
      }
    }
  } catch { }
  return base
}

const API_BASE_URL = computeBaseURL()
const API_TIMEOUT = 15000 // 15秒超时，避免过长等待
const LOGIN_TIMEOUT = 10000 // 登录请求10秒超时

// 调试信息
console.log('🔧 API Configuration:')
console.log('  VITE_API_BASE_URL:', ENV_BASE)
console.log('  Final API_BASE_URL:', API_BASE_URL || '[same-origin]')

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 全局刷新控制，避免并发重复刷新与竞态
let refreshPromise: Promise<string> | null = null

// Token管理
class TokenManager {
  private static readonly TOKEN_KEY = 'medqc_access_token'
  private static readonly REFRESH_TOKEN_KEY = 'medqc_refresh_token'

  static getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY)
  }

  static setToken(token: string): void {
    localStorage.setItem(this.TOKEN_KEY, token)
  }

  static getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY)
  }

  static setRefreshToken(token: string): void {
    localStorage.setItem(this.REFRESH_TOKEN_KEY, token)
  }

  static clearTokens(): void {
    localStorage.removeItem(this.TOKEN_KEY)
    localStorage.removeItem(this.REFRESH_TOKEN_KEY)
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
apiClient.interceptors.request.use((config: AxiosRequestConfig) => {
  const token = TokenManager.getToken()
  if (token && !TokenManager.isTokenExpired(token)) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }

  // 添加请求ID用于调试
  config.headers = config.headers || {}
  config.headers['X-Request-ID'] = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

  console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
    headers: config.headers,
    data: config.data,
    params: config.params
  })

  return config
},
  (error: unknown) => {
    console.error('❌ Request interceptor error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use((response: AxiosResponse) => {
  console.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`, {
    status: response.status,
    data: response.data
  })
  return response
},
  async (error: unknown) => {
    const originalRequest = error.config

    // 跳过对认证接口401/403错误的日志打印（这些是正常的未登录状态）
    const isAuthMeEndpoint = error.config?.url?.includes('/api/v1/auth/me')
    const isAuthError = error.response?.status === 401 || error.response?.status === 403

    // 只在开发环境或非认证错误时记录详细错误
    if (process.env.NODE_ENV === 'development' || error.response?.status !== 401) {
      // 对于auth/me接口的403错误，不打印日志（用户未登录或访问demo页面时是正常的）
      if (!(isAuthMeEndpoint && isAuthError)) {
        console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
          status: error.response?.status,
          data: error.response?.data,
          message: error.message
        })
      }
    }

    // Token过期处理（带单航刷新，避免并发冲突）
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 避免对登录/刷新接口自身进行循环处理
      const url: string = originalRequest?.url || ''
      if (url.includes('/api/v1/auth/login') || url.includes('/api/v1/auth/refresh')) {
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
        refreshPromise = axios
          .post(`${API_BASE_URL}/api/v1/auth/refresh`, { refresh_token: refreshToken })
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
    const traceId = data.traceId

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
        message.error('请求的资源不存在')
        break
      case 422:
        message.error(`数据验证失败: ${errorMessage}`)
        break
      case 429:
        message.error('请求过于频繁，请稍后再试')
        break
      case 500:
        message.error(traceId ? `服务器错误（${traceId}），请联系管理员` : '服务器内部错误，请联系管理员')
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
  }
)

// API服务类
export class ApiService {
  // ==================== 用户认证相关API (B1任务 - 9个接口) ====================

  /**
   * 用户登录
   */
  static async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    try {
      // 每次登录前清除旧 Token，避免 Mock/过期 Token 残留
      TokenManager.clearTokens()

      console.log('🔐 ApiService.login 发送请求:', {
        email: credentials.email,
        role: credentials.role,
        roleType: typeof credentials.role,
        fullCredentials: credentials,
        useMock: USE_AUTH_MOCK
      })

      // Mock 模式
      if (USE_AUTH_MOCK) {
        console.log('🎭 使用 Mock 认证')
        const mockResponse = mockLogin(credentials.email, credentials.password)

        if (!mockResponse) {
          return {
            success: false,
            error: '用户名或密码错误',
            data: null
          }
        }

        // 保存token
        TokenManager.setToken(mockResponse.access_token)
        TokenManager.setRefreshToken(mockResponse.refresh_token)

        console.log('✅ Mock 登录成功:', mockResponse.user.display_name)

        return {
          success: true,
          data: mockResponse,
          message: '登录成功'
        }
      }

      // 真实 API 模式
      const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', credentials)
      console.log('📡 ApiService.login 收到响应:', response.data)

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
        message: '登录成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '登录失败',
        data: null
      }
    }
  }

  /**
   * 用户注册
   */
  static async register(userData: RegisterRequest): Promise<ApiResponse<User>> {
    try {
      const response = await apiClient.post<User>('/api/v1/auth/register', userData)
      return {
        success: true,
        data: response.data,
        message: '注册成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '注册失败',
        data: null
      }
    }
  }

  /**
   * 获取当前用户信息
   */
  static async getCurrentUser(): Promise<ApiResponse<User>> {
    try {
      // Mock 模式
      if (USE_AUTH_MOCK) {
        const token = TokenManager.getToken()
        if (!token) {
          return {
            success: false,
            error: '未登录',
            data: null
          }
        }

        const mockUser = mockGetCurrentUser(token)
        if (!mockUser) {
          return {
            success: false,
            error: '无效的token',
            data: null
          }
        }

        return {
          success: true,
          data: mockUser
        }
      }

      // 真实 API 模式
      const response = await apiClient.get<User>('/api/v1/auth/me')
      return {
        success: true,
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取用户信息失败',
        data: null
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
        message: '资料更新成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '资料更新失败',
        data: null
      }
    }
  }

  /**
   * 修改密码
   */
  static async updatePassword(newPassword: string, currentPassword?: string): Promise<ApiResponse<void>> {
    try {
      await apiClient.put('/api/v1/auth/password', {
        new_password: newPassword,
        current_password: currentPassword
      })
      return {
        success: true,
        message: '密码修改成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '密码修改失败'
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
        message: '登出成功'
      }
    } catch (error: unknown) {
      // 即使API调用失败，也要清除本地token
      TokenManager.clearTokens()
      return {
        success: true,
        message: '登出成功'
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
        refresh_token: refreshToken
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
        data: response.data
      }
    } catch (error: unknown) {
      TokenManager.clearTokens()
      return {
        success: false,
        error: error.response?.data?.message || 'Token刷新失败'
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
        message: '重置密码邮件已发送'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '发送重置邮件失败'
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
        new_password: newPassword
      })
      return {
        success: true,
        message: '密码重置成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '密码重置失败'
      }
    }
  }

  // ==================== 医疗记录相关API (B2任务 - 10个接口) ====================

  /**
   * 获取医疗记录列表
   */
  static async getMedicalRecords(params?: SearchParams): Promise<ApiResponse<PaginatedResponse<MedicalRecord>>> {
    try {
      const queryParams = new URLSearchParams()

      if (params?.keyword) queryParams.append('keyword', params.keyword)
      if (params?.filters?.department) queryParams.append('department', params.filters.department)
      if (params?.filters?.status) queryParams.append('status', params.filters.status)
      if (params?.filters?.record_type) queryParams.append('record_type', params.filters.record_type)
      if (params?.sort?.field) queryParams.append('sort_field', params.sort.field)
      if (params?.sort?.order) queryParams.append('sort_order', params.sort.order)
      if (params?.pagination?.page) queryParams.append('page', params.pagination.page.toString())
      if (params?.pagination?.pageSize) queryParams.append('page_size', params.pagination.pageSize.toString())

      const response = await apiClient.get<PaginatedResponse<MedicalRecord>>(`/api/records?${queryParams}`)
      return {
        success: true,
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取医疗记录失败',
        data: null
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
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取医疗记录详情失败',
        data: null
      }
    }
  }

  /**
   * 获取指定医疗记录的文书列表（带适配）
   */
  static async getMedicalRecordDocuments(recordId: string): Promise<ApiResponse<RecordDocumentInfo[]>> {
    try {
      const response = await apiClient.get<MedicalRecordDocumentsResponse | { data: MedicalRecordDocumentsResponse }>(
        `/api/medical-records/${recordId}/documents`
      )

      const rawPayload = (response.data as { data?: MedicalRecordDocumentsResponse }).data
        ?? (response.data as MedicalRecordDocumentsResponse)
      const documents: RecordDocumentInfo[] = []

      if (rawPayload && Array.isArray(rawPayload.categories)) {
        const seenIds = new Set<string>()
        let generatedIndex = 0

        rawPayload.categories.forEach(category => {
          const categoryDocs = Array.isArray(category.documents) ? category.documents : []
          categoryDocs.forEach((doc: MedicalRecordDocumentPayload) => {
            generatedIndex += 1

            let docId = (doc.id && String(doc.id)) || `${recordId}-doc-${generatedIndex}`
            while (seenIds.has(docId)) {
              generatedIndex += 1
              docId = `${recordId}-doc-${generatedIndex}`
            }
            seenIds.add(docId)

            const typeCode =
              (typeof doc.type === 'string' && doc.type) ||
              (doc.type_info && typeof doc.type_info.type_code === 'string' ? doc.type_info.type_code : undefined) ||
              (category.category_code || '')

            const titleCandidates = [
              doc.title,
              doc.type_info?.type_name,
              typeof doc.type === 'string' ? doc.type : undefined,
              category.category_name,
              '未命名文书'
            ]
            const title = String(titleCandidates.find(candidate => !!candidate && String(candidate).trim().length > 0) ?? '未命名文书').trim()

            documents.push({
              id: docId,
              title,
              type: typeCode || undefined,
              content: typeof doc.content === 'string' ? doc.content : '',
              created_at: typeof doc.created_at === 'string'
                ? doc.created_at
                : (typeof doc.updated_at === 'string' ? doc.updated_at : undefined)
            })
          })
        })
      }

      return {
        success: true,
        data: documents
      }
    } catch (error: any) {
      return {
        success: false,
        error: error?.response?.data?.message || error?.message || '获取医疗文书失败',
        data: null
      }
    }
  }

  /**
   * 创建医疗记录
   */
  static async createMedicalRecord(recordData: CreateMedicalRecordRequest): Promise<ApiResponse<MedicalRecord>> {
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
          'Content-Type': 'multipart/form-data'
        }
      })

      return {
        success: true,
        data: response.data,
        message: '医疗记录创建成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '创建医疗记录失败',
        data: null
      }
    }
  }

  /**
   * 更新医疗记录
   */
  static async updateMedicalRecord(id: string, recordData: UpdateMedicalRecordRequest): Promise<ApiResponse<MedicalRecord>> {
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
          'Content-Type': 'multipart/form-data'
        }
      })

      return {
        success: true,
        data: response.data,
        message: '医疗记录更新成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '更新医疗记录失败',
        data: null
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
        message: '医疗记录删除成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '删除医疗记录失败'
      }
    }
  }

  /**
   * 批量删除医疗记录
   */
  static async batchDeleteRecords(ids: string[]): Promise<ApiResponse<void>> {
    try {
      await apiClient.delete('/api/records/batch', {
        data: { record_ids: ids }
      })
      return {
        success: true,
        message: '批量删除成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '批量删除失败'
      }
    }
  }

  /**
   * 导出医疗记录
   */
  static async exportRecords(ids: string[]): Promise<ApiResponse<{ download_url: string }>> {
    try {
      const response = await apiClient.post<{ download_url: string }>('/api/records/export', {
        record_ids: ids
      })
      return {
        success: true,
        data: response.data,
        message: '导出任务创建成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '导出失败',
        data: null
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
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取统计信息失败',
        data: null
      }
    }
  }

  /**
   * 上传医疗记录文件
   */
  static async uploadRecordFile(file: File): Promise<ApiResponse<{ file_url: string; file_name: string }>> {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.post<{ file_url: string; file_name: string }>('/api/records/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      return {
        success: true,
        data: response.data,
        message: '文件上传成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '文件上传失败',
        data: null
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
        message: '记录复制成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '记录复制失败',
        data: null
      }
    }
  }

  // ==================== 质控分析相关API (B3任务 - 9个接口) ====================

  /**
   * 开始质控分析
   */
  static async analyzeRecord(recordId: string, analysisParams?: QCAnalysisRequest): Promise<ApiResponse<{ analysis_id: string }>> {
    try {
      const response = await apiClient.post<{ analysis_id: string }>(`/api/qc/analyze/${recordId}`, analysisParams || {})
      return {
        success: true,
        data: response.data,
        message: '质控分析已开始'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '开始分析失败',
        data: null
      }
    }
  }

  /**
   * 批量质控分析
   */
  static async batchAnalyzeRecords(recordIds: string[]): Promise<ApiResponse<{ analysis_ids: string[] }>> {
    try {
      const response = await apiClient.post<{ analysis_ids: string[] }>('/api/qc/analyze/batch', {
        record_ids: recordIds
      })
      return {
        success: true,
        data: response.data,
        message: '批量分析已开始'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '批量分析失败',
        data: null
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
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取分析结果失败',
        data: null
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
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取分析进度失败',
        data: null
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
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取质控规则失败',
        data: null
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
        message: '质控规则创建成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '创建质控规则失败',
        data: null
      }
    }
  }

  /**
   * 更新质控规则
   */
  static async updateQCRule(ruleId: string, ruleData: Partial<QCRule>): Promise<ApiResponse<QCRule>> {
    try {
      const response = await apiClient.put<QCRule>(`/api/qc/rules/${ruleId}`, ruleData)
      return {
        success: true,
        data: response.data,
        message: '质控规则更新成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '更新质控规则失败',
        data: null
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
        message: '质控规则删除成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '删除质控规则失败'
      }
    }
  }

  /**
   * 获取质控历史记录
   */
  static async getQCHistory(params?: { page?: number; pageSize?: number }): Promise<ApiResponse<any[]>> {
    try {
      const queryParams = new URLSearchParams()
      if (params?.page) queryParams.append('page', params.page.toString())
      if (params?.pageSize) queryParams.append('page_size', params.pageSize.toString())

      const response = await apiClient.get<any[]>(`/api/qc/history?${queryParams}`)
      return {
        success: true,
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: error.response?.data?.message || '获取质控历史失败',
        data: null
      }
    }
  }

  // ==================== 工具方法 ====================

  /**
   * 通用 POST 请求方法
   */
  static async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.post<T>(url, data, config)
      return {
        success: true,
        data: response.data,
        message: '请求成功'
      }
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.message || error.response?.data?.detail || (error.code === 'ECONNABORTED' ? '请求超时' : '请求失败'),
        data: null
      }
    }
  }

  /**
   * 通用 GET 请求方法
   */
  static async get<T = any>(url: string, params?: any): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.get<T>(url, { params })
      return {
        success: true,
        data: response.data,
        message: '请求成功'
      }
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.message || error.response?.data?.detail || '请求失败',
        data: null
      }
    }
  }

  /**
   * 检查API连接状态
   */
  static async checkConnection(): Promise<boolean> {
    try {
      await apiClient.get('/api/v1/health')
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
    const hasValidAccess = token !== null && !TokenManager.isTokenExpired(token)
    // 若存在刷新令牌，则视为可恢复的已登录态，避免短暂重定向抖动
    const hasRefresh = TokenManager.getRefreshToken() !== null
    return hasValidAccess || hasRefresh
  }
}

// 导出默认实例
export default ApiService

