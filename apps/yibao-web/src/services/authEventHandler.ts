/**
 * 认证事件处理器
 * 统一处理认证相关的事件，提供更好的用户体验
 */

import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import { tokenRenewalService } from './tokenRenewalService'

export class AuthEventHandler {
  private static instance: AuthEventHandler | null = null
  private isInitialized = false

  private constructor() {}

  static getInstance(): AuthEventHandler {
    if (!AuthEventHandler.instance) {
      AuthEventHandler.instance = new AuthEventHandler()
    }
    return AuthEventHandler.instance
  }

  /**
   * 初始化事件监听器
   */
  initialize(): void {
    if (this.isInitialized) {
      return
    }

    console.log('初始化认证事件处理器')

    // 监听token刷新成功事件
    window.addEventListener('auth-token-refreshed', this.handleTokenRefreshed.bind(this))

    // 监听token过期事件
    window.addEventListener('auth-token-expired', this.handleTokenExpired.bind(this))

    // 监听认证清除事件
    window.addEventListener('auth-cleared', this.handleAuthCleared.bind(this))

    // 监听自动续期成功事件
    window.addEventListener('token-auto-renewed', this.handleAutoRenewalSuccess.bind(this))

    // 监听自动续期失败事件
    window.addEventListener('token-renewal-failed', this.handleAutoRenewalFailed.bind(this))

    // 监听页面可见性变化
    document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this))

    // 监听网络状态变化
    window.addEventListener('online', this.handleNetworkOnline.bind(this))
    window.addEventListener('offline', this.handleNetworkOffline.bind(this))

    // 监听页面卸载
    window.addEventListener('beforeunload', this.handleBeforeUnload.bind(this))

    this.isInitialized = true
  }

  /**
   * 销毁事件监听器
   */
  destroy(): void {
    if (!this.isInitialized) {
      return
    }

    console.log('销毁认证事件处理器')

    window.removeEventListener('auth-token-refreshed', this.handleTokenRefreshed.bind(this))
    window.removeEventListener('auth-token-expired', this.handleTokenExpired.bind(this))
    window.removeEventListener('auth-cleared', this.handleAuthCleared.bind(this))
    window.removeEventListener('token-auto-renewed', this.handleAutoRenewalSuccess.bind(this))
    window.removeEventListener('token-renewal-failed', this.handleAutoRenewalFailed.bind(this))
    document.removeEventListener('visibilitychange', this.handleVisibilityChange.bind(this))
    window.removeEventListener('online', this.handleNetworkOnline.bind(this))
    window.removeEventListener('offline', this.handleNetworkOffline.bind(this))
    window.removeEventListener('beforeunload', this.handleBeforeUnload.bind(this))

    this.isInitialized = false
  }

  /**
   * 处理token刷新成功事件
   */
  private handleTokenRefreshed(event: CustomEvent): void {
    const { user, timestamp } = event.detail
    console.log('Token刷新成功事件:', { user: user?.email, timestamp })
    
    // 可以在这里添加一些UI反馈，比如显示一个小的成功提示
    // message.success('认证状态已更新', 1)
  }

  /**
   * 处理token过期事件
   */
  private handleTokenExpired(event: CustomEvent): void {
    const { reason, url, timestamp } = event.detail
    console.log('Token过期事件:', { reason, url, timestamp })

    // 停止自动续期服务
    tokenRenewalService.stop()

    // 清除认证状态
    const authStore = useAuthStore()
    if (authStore.isAuthenticated) {
      authStore.signOut()
    }

    // 根据原因显示不同的提示
    if (reason.includes('REFRESH_TOKEN_EXPIRED')) {
      message.warning('登录会话已过期，请重新登录', 3)
    } else if (reason.includes('NETWORK_ERROR')) {
      message.error('网络连接失败，请检查网络后重新登录', 3)
    } else {
      message.warning('认证已失效，请重新登录', 3)
    }
  }

  /**
   * 处理认证清除事件
   */
  private handleAuthCleared(event: CustomEvent): void {
    const { timestamp } = event.detail
    console.log('认证清除事件:', { timestamp })

    // 停止自动续期服务
    tokenRenewalService.stop()
  }

  /**
   * 处理自动续期成功事件
   */
  private handleAutoRenewalSuccess(event: CustomEvent): void {
    const { timestamp } = event.detail
    console.log('自动续期成功:', { timestamp })
    
    // 显示一个不打扰的成功提示
    message.success('认证状态已自动更新', 1)
  }

  /**
   * 处理自动续期失败事件
   */
  private handleAutoRenewalFailed(event: CustomEvent): void {
    const { error, retryCount, timestamp } = event.detail
    console.log('自动续期失败:', { error, retryCount, timestamp })

    // 显示错误提示
    message.error(`认证自动续期失败: ${error}`, 3)

    // 如果是最终失败，引导用户重新登录
    if (retryCount >= 3) {
      setTimeout(() => {
        message.warning('请重新登录以继续使用', 5)
        const currentPath = window.location.pathname
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      }, 2000)
    }
  }

  /**
   * 处理页面可见性变化
   */
  private handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      console.log('页面重新可见，检查认证状态')
      
      // 页面重新可见时，检查认证状态
      const authStore = useAuthStore()
      if (authStore.isAuthenticated) {
        // 如果用户已认证，检查token状态
        authStore.checkAndRefreshToken().catch(error => {
          console.warn('页面可见时token检查失败:', error)
        })
      }
    } else {
      console.log('页面不可见')
    }
  }

  /**
   * 处理网络重新连接
   */
  private handleNetworkOnline(): void {
    console.log('网络重新连接')
    message.success('网络连接已恢复', 2)

    // 网络恢复时，重新启动自动续期服务
    const authStore = useAuthStore()
    if (authStore.isAuthenticated) {
      tokenRenewalService.start()
      
      // 立即检查token状态
      authStore.checkAndRefreshToken().catch(error => {
        console.warn('网络恢复时token检查失败:', error)
      })
    }
  }

  /**
   * 处理网络断开
   */
  private handleNetworkOffline(): void {
    console.log('网络连接断开')
    message.warning('网络连接已断开，部分功能可能受限', 3)

    // 网络断开时，暂停自动续期服务
    tokenRenewalService.stop()
  }

  /**
   * 处理页面卸载前
   */
  private handleBeforeUnload(): void {
    console.log('页面即将卸载，清理资源')
    
    // 停止自动续期服务
    tokenRenewalService.stop()
  }

  /**
   * 手动触发认证状态检查
   */
  checkAuthStatus(): void {
    const authStore = useAuthStore()
    if (authStore.isAuthenticated) {
      authStore.checkAndRefreshToken().catch(error => {
        console.warn('手动认证检查失败:', error)
      })
    }
  }

  /**
   * 获取当前状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      renewalServiceStatus: tokenRenewalService.getStatus()
    }
  }
}

// 导出单例实例
export const authEventHandler = AuthEventHandler.getInstance()
