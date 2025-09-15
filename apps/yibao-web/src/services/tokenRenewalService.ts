/**
 * Token自动续期服务
 * 负责定期检查token状态并自动刷新
 */

import { TokenManager } from './apiService'

export class TokenRenewalService {
  private static instance: TokenRenewalService | null = null
  private renewalTimer: number | null = null
  private heartbeatTimer: number | null = null
  private isRunning = false
  
  // 配置参数
  private readonly CHECK_INTERVAL = 5 * 60 * 1000 // 每5分钟检查一次，避免过于频繁
  private readonly HEARTBEAT_INTERVAL = 10 * 60 * 1000 // 每10分钟心跳一次
  private readonly MAX_RETRY_ATTEMPTS = 3
  
  private retryCount = 0
  private lastRenewalTime = 0
  private lastHeartbeatTime = 0

  private constructor() {
    this.setupEventListeners()
  }

  /**
   * 获取单例实例
   */
  static getInstance(): TokenRenewalService {
    if (!TokenRenewalService.instance) {
      TokenRenewalService.instance = new TokenRenewalService()
    }
    return TokenRenewalService.instance
  }

  /**
   * 启动自动续期服务
   */
  start(): void {
    if (this.isRunning) {
      console.log('Token续期服务已在运行中')
      return
    }

    console.log('启动Token自动续期服务')
    this.isRunning = true
    this.retryCount = 0
    
    // 立即检查一次
    this.checkAndRenewToken()
    
    // 设置定期检查
    this.renewalTimer = window.setInterval(() => {
      this.checkAndRenewToken()
    }, this.CHECK_INTERVAL)
    
    // 设置心跳检查
    this.heartbeatTimer = window.setInterval(() => {
      this.sendHeartbeat()
    }, this.HEARTBEAT_INTERVAL)
  }

  /**
   * 停止自动续期服务
   */
  stop(): void {
    if (!this.isRunning) {
      return
    }

    console.log('停止Token自动续期服务')
    this.isRunning = false
    
    if (this.renewalTimer) {
      clearInterval(this.renewalTimer)
      this.renewalTimer = null
    }
    
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
   * 检查并续期token
   */
  private async checkAndRenewToken(): Promise<void> {
    try {
      // 检查是否已认证
      if (!TokenManager.isAuthenticated()) {
        console.log('用户未认证，停止续期服务')
        this.stop()
        return
      }

      const token = TokenManager.getToken()
      if (!token) {
        console.log('无有效token，停止续期服务')
        this.stop()
        return
      }

      // 检查是否需要续期
      if (TokenManager.shouldRefreshToken(token) || TokenManager.needsAutoRenewal()) {
        console.log('Token即将过期，开始自动续期...')
        await this.performRenewal()
      } else {
        // 重置重试计数
        this.retryCount = 0
      }
    } catch (error) {
      console.error('Token续期检查失败:', error)
      this.handleRenewalError(error)
    }
  }

  /**
   * 执行token续期
   */
  private async performRenewal(): Promise<void> {
    try {
      const refreshToken = TokenManager.getRefreshToken()
      if (!refreshToken) {
        throw new Error('缺少refresh token')
      }

      if (TokenManager.isRefreshTokenExpired(refreshToken)) {
        throw new Error('Refresh token已过期')
      }

      // 调用刷新API（这里需要根据实际API调整）
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          refresh_token: refreshToken
        })
      })

      if (!response.ok) {
        throw new Error(`续期失败: HTTP ${response.status}`)
      }

      const data = await response.json()
      
      // 更新token
      TokenManager.setToken(data.access_token)
      if (data.refresh_token) {
        TokenManager.setRefreshToken(data.refresh_token)
      }
      if (data.expires_in) {
        TokenManager.setTokenExpiration(data.expires_in)
      }

      this.lastRenewalTime = Date.now()
      this.retryCount = 0
      
      console.log('Token自动续期成功')
      
      // 触发续期成功事件
      window.dispatchEvent(new CustomEvent('token-auto-renewed', {
        detail: { timestamp: this.lastRenewalTime }
      }))

    } catch (error) {
      console.error('Token自动续期失败:', error)
      throw error
    }
  }

  /**
   * 处理续期错误
   */
  private handleRenewalError(error: any): void {
    this.retryCount++
    
    if (this.retryCount >= this.MAX_RETRY_ATTEMPTS) {
      console.error(`Token续期失败超过最大重试次数(${this.MAX_RETRY_ATTEMPTS})，停止服务`)
      this.stop()
      
      // 触发续期失败事件
      window.dispatchEvent(new CustomEvent('token-renewal-failed', {
        detail: { 
          error: error.message, 
          retryCount: this.retryCount,
          timestamp: Date.now()
        }
      }))
      
      // 清除认证信息
      TokenManager.clearAuth()
    } else {
      console.warn(`Token续期失败，将在下次检查时重试 (${this.retryCount}/${this.MAX_RETRY_ATTEMPTS})`)
    }
  }

  /**
   * 发送心跳检查
   */
  private async sendHeartbeat(): Promise<void> {
    try {
      if (!TokenManager.isAuthenticated()) {
        return
      }

      const token = TokenManager.getToken()
      if (!token) {
        return
      }

      // 发送心跳请求（可选功能）
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/auth/heartbeat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        this.lastHeartbeatTime = Date.now()
        console.log('心跳检查成功')
      } else {
        console.warn('心跳检查失败:', response.status)
      }
    } catch (error) {
      console.warn('心跳检查异常:', error)
    }
  }

  /**
   * 设置事件监听器
   */
  private setupEventListeners(): void {
    // 监听认证状态变化
    window.addEventListener('auth-token-refreshed', () => {
      console.log('检测到token刷新，重置续期状态')
      this.retryCount = 0
      this.lastRenewalTime = Date.now()
    })

    window.addEventListener('auth-token-expired', () => {
      console.log('检测到token过期，停止续期服务')
      this.stop()
    })

    window.addEventListener('auth-cleared', () => {
      console.log('检测到认证清除，停止续期服务')
      this.stop()
    })

    // 监听页面可见性变化
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && this.isRunning) {
        // 页面重新可见时立即检查token状态
        console.log('页面重新可见，检查token状态')
        this.checkAndRenewToken()
      }
    })

    // 监听网络状态变化
    window.addEventListener('online', () => {
      if (this.isRunning) {
        console.log('网络重新连接，检查token状态')
        this.checkAndRenewToken()
      }
    })
  }

  /**
   * 获取服务状态
   */
  getStatus() {
    return {
      isRunning: this.isRunning,
      retryCount: this.retryCount,
      lastRenewalTime: this.lastRenewalTime,
      lastHeartbeatTime: this.lastHeartbeatTime,
      nextCheckIn: this.renewalTimer ? this.CHECK_INTERVAL : null
    }
  }
}

// 导出单例实例
export const tokenRenewalService = TokenRenewalService.getInstance()
