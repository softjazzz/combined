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
  QCAnalysisRequest
} from '@/types'

// API基础配置
// 开发环境建议将 VITE_API_BASE_URL 留空，使用同源相对路径交给 Vite 代理
const ENV_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined
const API_BASE_URL = ENV_BASE && ENV_BASE.trim() !== '' ? ENV_BASE : ''
const API_TIMEOUT = 30000 // 30秒超时

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
  (error: any) => {
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
  async (error: any) => {
    const originalRequest = error.config
    
    console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
      status: error.response?.status,
      data: error.response?.data,
      message: error.message
    })

    // Token过期处理
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      
      const refreshToken = TokenManager.getRefreshToken()
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken
          })
          
          const { access_token, refresh_token: newRefreshToken } = response.data
          TokenManager.setToken(access_token)
          if (newRefreshToken) {
            TokenManager.setRefreshToken(newRefreshToken)
          }
          
          // 重试原请求
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return apiClient(originalRequest)
        } catch (refreshError) {
          console.error('Token refresh failed:', refreshError)
          TokenManager.clearTokens()
          // 重定向到登录页
          window.location.href = '/auth/login'
          return Promise.reject(refreshError)
        }
      } else {
        TokenManager.clearTokens()
        window.location.href = '/auth/login'
      }
    }

    // 统一错误处理
    const errorMessage = error.response?.data?.message || error.message || '请求失败'
    
    // 根据状态码显示不同的错误信息
    switch (error.response?.status) {
      case 400:
        message.error(`请求参数错误: ${errorMessage}`)
        break
      case 401:
        message.error('认证失败，请重新登录')
        break
      case 403:
        message.error('权限不足，无法访问该资源')
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
        message.error('服务器内部错误，请联系管理员')
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
      console.log('🔐 ApiService.login 发送请求:', {
        email: credentials.email,
        role: credentials.role,
        roleType: typeof credentials.role,
        fullCredentials: credentials
      })

      const response = await apiClient.post<LoginResponse>('/api/auth/login', credentials)
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
    } catch (error: any) {
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
      const response = await apiClient.post<User>('/api/auth/register', userData)
      return {
        success: true,
        data: response.data,
        message: '注册成功'
      }
    } catch (error: any) {
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
      const response = await apiClient.get<User>('/api/auth/me')
      return {
        success: true,
        data: response.data
      }
    } catch (error: any) {
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
      const response = await apiClient.put<User>('/api/auth/profile', profileData)
      return {
        success: true,
        data: response.data,
        message: '资料更新成功'
      }
    } catch (error: any) {
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
      await apiClient.put('/api/auth/password', {
        new_password: newPassword,
        current_password: currentPassword
      })
      return {
        success: true,
        message: '密码修改成功'
      }
    } catch (error: any) {
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
      await apiClient.post('/api/auth/logout')
      TokenManager.clearTokens()
      return {
        success: true,
        message: '登出成功'
      }
    } catch (error: any) {
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

      const response = await apiClient.post<LoginResponse>('/api/auth/refresh', {
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
    } catch (error: any) {
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
      await apiClient.post('/api/auth/forgot-password', { email })
      return {
        success: true,
        message: '重置密码邮件已发送'
      }
    } catch (error: any) {
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
      await apiClient.post('/api/auth/reset-password', {
        token,
        new_password: newPassword
      })
      return {
        success: true,
        message: '密码重置成功'
      }
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.message || '获取医疗记录详情失败',
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
  static async getMedicalRecordsStatistics(): Promise<ApiResponse<any>> {
    try {
      const response = await apiClient.get('/api/records/statistics')
      return {
        success: true,
        data: response.data
      }
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
  static async getAnalysisProgress(analysisId: string): Promise<ApiResponse<any>> {
    try {
      const response = await apiClient.get(`/api/qc/progress/${analysisId}`)
      return {
        success: true,
        data: response.data
      }
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
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
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.message || '获取质控历史失败',
        data: null
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
