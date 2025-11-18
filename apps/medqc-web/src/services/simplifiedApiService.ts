/**
 * 简化的API服务
 * 只保留认证和工具类API，数据操作直接使用Supabase
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { message } from 'ant-design-vue'
import type { 
  ApiResponse, 
  LoginRequest, 
  LoginResponse,
  User
} from '@/types'

// API基础配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
const API_TIMEOUT = 30000 // 30秒超时

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

  static getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY)
  }

  static setToken(token: string): void {
    localStorage.setItem(this.TOKEN_KEY, token)
  }

  static clearTokens(): void {
    localStorage.removeItem(this.TOKEN_KEY)
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
    
    console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`)
    
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
  (error: unknown) => {
    console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
      status: error.response?.status,
      message: error.response?.data?.detail || error.message
    })

    // 处理401错误
    if (error.response?.status === 401) {
      TokenManager.clearTokens()
      message.error('登录已过期，请重新登录')
      // 可以在这里触发重定向到登录页面
      window.location.href = '/auth/login'
    }

    return Promise.reject(error)
  }
)

/**
 * 简化的API服务类
 * 只包含认证和工具类API
 */
export class SimplifiedApiService {
  
  // ==================== 认证相关API ====================
  
  /**
   * 用户登录
   */
  static async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    try {
      const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', credentials)
      
      // 保存token
      if (response.data.access_token) {
        TokenManager.setToken(response.data.access_token)
      }
      
      return {
        success: true,
        data: response.data,
        message: '登录成功'
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: {
          message: error.response?.data?.detail || '登录失败'
        }
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
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: {
          message: error.response?.data?.detail || '获取用户信息失败'
        }
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
      // 即使后端登出失败，也清除本地token
      TokenManager.clearTokens()
      return {
        success: true,
        message: '登出成功'
      }
    }
  }

  // ==================== 工具类API ====================

  /**
   * 健康检查
   */
  static async healthCheck(): Promise<ApiResponse<unknown>> {
    try {
      const response = await apiClient.get('/api/health')
      return {
        success: true,
        data: response.data
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: {
          message: error.response?.data?.detail || '健康检查失败'
        }
      }
    }
  }

  /**
   * 演示质控分析
   */
  static async analyzeDemoRecord(content: string): Promise<ApiResponse<unknown>> {
    try {
      const formData = new FormData()
      formData.append('content', content)
      
      const response = await apiClient.post('/api/qc/analyze-demo', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      return {
        success: true,
        data: response.data.data,
        message: response.data.message
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: {
          message: error.response?.data?.detail || '分析失败'
        }
      }
    }
  }

  /**
   * 文件上传
   */
  static async uploadFile(file: File): Promise<ApiResponse<unknown>> {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await apiClient.post('/api/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      return {
        success: true,
        data: response.data.data,
        message: response.data.message
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: {
          message: error.response?.data?.detail || '文件上传失败'
        }
      }
    }
  }

  /**
   * 获取演示质控规则
   */
  static async getDemoQCRules(): Promise<ApiResponse<any[]>> {
    try {
      const response = await apiClient.get('/api/demo/qc-rules')
      return {
        success: true,
        data: response.data.data,
        message: response.data.message
      }
    } catch (error: unknown) {
      return {
        success: false,
        error: {
          message: error.response?.data?.detail || '获取规则失败'
        }
      }
    }
  }

  // ==================== Token管理 ====================

  /**
   * 检查是否已登录
   */
  static isLoggedIn(): boolean {
    const token = TokenManager.getToken()
    return token !== null && !TokenManager.isTokenExpired(token)
  }

  /**
   * 获取当前token
   */
  static getToken(): string | null {
    return TokenManager.getToken()
  }

  /**
   * 清除认证信息
   */
  static clearAuth(): void {
    TokenManager.clearTokens()
  }
}

// 导出默认实例
export default SimplifiedApiService
