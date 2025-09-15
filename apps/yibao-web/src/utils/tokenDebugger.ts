/**
 * Token调试工具
 * 用于监控和调试token状态
 */

import { TokenManager } from '@/services/apiService'

export class TokenDebugger {
  private static instance: TokenDebugger | null = null
  private debugInterval: number | null = null
  private isEnabled = false

  private constructor() {}

  static getInstance(): TokenDebugger {
    if (!TokenDebugger.instance) {
      TokenDebugger.instance = new TokenDebugger()
    }
    return TokenDebugger.instance
  }

  /**
   * 启用调试模式
   */
  enable(): void {
    if (this.isEnabled) return

    console.log('🔍 启用Token调试模式')
    this.isEnabled = true

    // 立即显示一次状态
    this.logTokenStatus()

    // 每30秒显示一次token状态
    this.debugInterval = window.setInterval(() => {
      this.logTokenStatus()
    }, 30000)

    // 添加到全局对象，方便控制台调用
    ;(window as any).tokenDebugger = this
  }

  /**
   * 禁用调试模式
   */
  disable(): void {
    if (!this.isEnabled) return

    console.log('🔍 禁用Token调试模式')
    this.isEnabled = false

    if (this.debugInterval) {
      clearInterval(this.debugInterval)
      this.debugInterval = null
    }

    delete (window as any).tokenDebugger
  }

  /**
   * 记录token状态
   */
  logTokenStatus(): void {
    const token = TokenManager.getToken()
    const refreshToken = TokenManager.getRefreshToken()
    const user = TokenManager.getUserInfo()
    const isAuth = TokenManager.isAuthenticated()

    console.group('🔍 Token状态调试')
    
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        const now = Date.now()
        const expTime = payload.exp * 1000
        const timeLeft = expTime - now
        const timeLeftMin = Math.round(timeLeft / 60000)

        console.log('📄 Access Token:')
        console.log(`  - 有效期至: ${new Date(expTime).toLocaleString()}`)
        console.log(`  - 剩余时间: ${timeLeftMin}分钟 (${Math.round(timeLeft/1000)}秒)`)
        console.log(`  - 用户ID: ${payload.sub}`)
        console.log(`  - 是否过期: ${TokenManager.isTokenExpired(token) ? '是' : '否'}`)
        console.log(`  - 需要刷新: ${TokenManager.shouldRefreshToken(token) ? '是' : '否'}`)
      } catch (error) {
        console.log('📄 Access Token: 解析失败', error)
      }
    } else {
      console.log('📄 Access Token: 不存在')
    }

    if (refreshToken) {
      try {
        const payload = JSON.parse(atob(refreshToken.split('.')[1]))
        const expTime = payload.exp * 1000
        const timeLeft = expTime - Date.now()
        const timeLeftHours = Math.round(timeLeft / 3600000)

        console.log('🔄 Refresh Token:')
        console.log(`  - 有效期至: ${new Date(expTime).toLocaleString()}`)
        console.log(`  - 剩余时间: ${timeLeftHours}小时`)
        console.log(`  - 是否过期: ${TokenManager.isRefreshTokenExpired(refreshToken) ? '是' : '否'}`)
      } catch (error) {
        console.log('🔄 Refresh Token: 解析失败', error)
      }
    } else {
      console.log('🔄 Refresh Token: 不存在')
    }

    console.log('👤 用户信息:', user ? `${user.display_name || user.email} (${user.id})` : '不存在')
    console.log('🔐 认证状态:', isAuth ? '已认证' : '未认证')

    // 检查自动续期状态
    const needsRenewal = TokenManager.needsAutoRenewal()
    console.log('🔄 需要自动续期:', needsRenewal ? '是' : '否')

    // 检查localStorage状态
    const storageKeys = [
      'yibao_access_token',
      'yibao_refresh_token', 
      'yibao_user',
      'yibao_authenticated',
      'yibao_session_id',
      'yibao_token_expires_at'
    ]
    
    console.log('💾 localStorage状态:')
    storageKeys.forEach(key => {
      const value = localStorage.getItem(key)
      if (value) {
        if (key.includes('token') && value.length > 50) {
          console.log(`  - ${key}: ${value.substring(0, 20)}...${value.substring(value.length - 10)} (${value.length}字符)`)
        } else {
          console.log(`  - ${key}: ${value}`)
        }
      } else {
        console.log(`  - ${key}: 不存在`)
      }
    })

    console.groupEnd()
  }

  /**
   * 手动触发token刷新（用于测试）
   */
  async testRefresh(): Promise<void> {
    console.log('🧪 手动测试token刷新...')
    try {
      // 这里需要调用实际的刷新方法
      console.log('刷新功能需要在实际环境中测试')
    } catch (error) {
      console.error('刷新测试失败:', error)
    }
  }

  /**
   * 清除所有token（用于测试）
   */
  clearAllTokens(): void {
    console.log('🧹 清除所有token...')
    TokenManager.clearAuth()
    this.logTokenStatus()
  }

  /**
   * 模拟token即将过期（用于测试）
   */
  simulateTokenExpiring(): void {
    console.log('⏰ 模拟token即将过期...')
    const token = TokenManager.getToken()
    if (token) {
      try {
        const parts = token.split('.')
        const payload = JSON.parse(atob(parts[1]))
        
        // 设置token在2分钟后过期
        payload.exp = Math.floor(Date.now() / 1000) + 120
        
        const newPayload = btoa(JSON.stringify(payload))
        const newToken = `${parts[0]}.${newPayload}.${parts[2]}`
        
        TokenManager.setToken(newToken)
        console.log('✅ 已设置token在2分钟后过期')
        this.logTokenStatus()
      } catch (error) {
        console.error('模拟失败:', error)
      }
    } else {
      console.log('❌ 没有token可以模拟')
    }
  }

  /**
   * 获取调试状态
   */
  getStatus() {
    return {
      isEnabled: this.isEnabled,
      hasDebugInterval: !!this.debugInterval
    }
  }
}

// 导出单例实例
export const tokenDebugger = TokenDebugger.getInstance()

// 在开发环境下自动启用
if (import.meta.env.DEV) {
  console.log('🔍 开发环境检测到，可使用 tokenDebugger.enable() 启用token调试')
}
