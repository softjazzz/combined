import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { message } from 'ant-design-vue'

// Local minimal types to avoid missing '@/types'
export type ApiResponse<T = any> = {
  success: boolean
  data?: T
  error?: any
  message?: string
}

export interface LoginRequest { email: string; password: string; role?: string }
export interface LoginResponse { access_token: string; refresh_token?: string }
export interface User { id: string; email?: string; display_name?: string; roles?: string[] }

const ENV_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined
const API_BASE_URL = ENV_BASE && ENV_BASE.trim() !== '' ? ENV_BASE : ''
const API_TIMEOUT = 30000

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: { 'Content-Type': 'application/json' }
})

class TokenManager {
  private static readonly TOKEN_KEY = 'yibao_access_token'
  private static readonly REFRESH_TOKEN_KEY = 'yibao_refresh_token'
  static getToken(): string | null { return localStorage.getItem(this.TOKEN_KEY) }
  static setToken(token: string): void { localStorage.setItem(this.TOKEN_KEY, token) }
  static getRefreshToken(): string | null { return localStorage.getItem(this.REFRESH_TOKEN_KEY) }
  static setRefreshToken(token: string): void { localStorage.setItem(this.REFRESH_TOKEN_KEY, token) }
  static clearTokens(): void { localStorage.removeItem(this.TOKEN_KEY); localStorage.removeItem(this.REFRESH_TOKEN_KEY) }
  static isTokenExpired(token: string): boolean {
    try { const payload = JSON.parse(atob(token.split('.')[1])); return payload.exp * 1000 < Date.now() } catch { return true }
  }
}

apiClient.interceptors.request.use((config: any) => {
  const token = TokenManager.getToken()
  if (token && !TokenManager.isTokenExpired(token)) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers = config.headers || {}
  config.headers['X-Request-ID'] = `req_${Date.now()}_${Math.random().toString(36).slice(2)}`
  return config
})

apiClient.interceptors.response.use((response: AxiosResponse) => response, async (error: any) => {
  const originalRequest = error.config || {}
  const url: string = originalRequest.url || ''
  if (error.response?.status === 401 && !originalRequest._retry) {
    originalRequest._retry = true
    const refreshToken = TokenManager.getRefreshToken()
    if (refreshToken) {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken })
        const { access_token, refresh_token: newRefreshToken } = response.data
        TokenManager.setToken(access_token)
        if (newRefreshToken) TokenManager.setRefreshToken(newRefreshToken)
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return apiClient(originalRequest)
      } catch {
        TokenManager.clearTokens()
        window.location.href = '/auth/login'
      }
    } else {
      TokenManager.clearTokens()
      window.location.href = '/auth/login'
    }
  }
  // 静默处理：未登录时轮询当前用户等接口不提示
  const shouldSilent = url.includes('/api/auth/me') || url.includes('/api/auth/refresh')
  const errorMessage = error.response?.data?.message || error.message || '请求失败'
  if (!shouldSilent) {
    message.error(errorMessage)
  }
  return Promise.reject(error)
})

export class ApiService {
  static async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    try {
      const response = await apiClient.post<LoginResponse>('/api/auth/login', credentials)
      if (response.data.access_token) TokenManager.setToken(response.data.access_token)
      if (response.data.refresh_token) TokenManager.setRefreshToken(response.data.refresh_token)
      return { success: true, data: response.data, message: '登录成功' }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || '登录失败', data: null as any }
    }
  }

  static async getCurrentUser(): Promise<ApiResponse<User>> {
    try { const response = await apiClient.get<User>('/api/auth/me'); return { success: true, data: response.data } }
    catch (error: any) { return { success: false, error: error.response?.data?.message || '获取用户信息失败', data: null as any } }
  }

  static async logout(): Promise<ApiResponse<void>> {
    try { await apiClient.post('/api/auth/logout'); TokenManager.clearTokens(); return { success: true, message: '登出成功' } }
    catch { TokenManager.clearTokens(); return { success: true, message: '登出成功' } }
  }

  static async get(url: string, config?: AxiosRequestConfig): Promise<any> {
    try {
      const response = await apiClient.get(url, config)
      return response.data
    } catch (error: any) {
      throw error
    }
  }

  static async post(url: string, data?: any, config?: AxiosRequestConfig): Promise<any> {
    try {
      const response = await apiClient.post(url, data, config)
      return response.data
    } catch (error: any) {
      throw error
    }
  }

  static async put(url: string, data?: any, config?: AxiosRequestConfig): Promise<any> {
    try {
      const response = await apiClient.put(url, data, config)
      return response.data
    } catch (error: any) {
      throw error
    }
  }

  static async delete(url: string, config?: AxiosRequestConfig): Promise<any> {
    try {
      const response = await apiClient.delete(url, config)
      return response.data
    } catch (error: any) {
      throw error
    }
  }

  static isAuthenticated(): boolean { const token = TokenManager.getToken(); return token !== null && !TokenManager.isTokenExpired(token) }
}

// 创建一个实例供导入使用
export const apiService = new ApiService()

export default ApiService


