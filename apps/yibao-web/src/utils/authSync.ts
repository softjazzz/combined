/**
 * 认证状态同步工具
 * 处理多标签页之间的认证状态同步
 */

import { useAuthStore } from '@/stores/auth'

export class AuthSyncManager {
  private static instance: AuthSyncManager | null = null
  private authStore: any = null
  private isListening = false

  private constructor() {
    this.setupStorageListener()
  }

  static getInstance(): AuthSyncManager {
    if (!AuthSyncManager.instance) {
      AuthSyncManager.instance = new AuthSyncManager()
    }
    return AuthSyncManager.instance
  }

  // 初始化认证同步
  init(authStore: any) {
    this.authStore = authStore
    this.startListening()
  }

  // 开始监听存储变化
  private startListening() {
    if (this.isListening) return
    
    this.isListening = true
    console.log('开始监听认证状态变化')
  }

  // 设置存储监听器
  private setupStorageListener() {
    if (typeof window === 'undefined') return

    window.addEventListener('storage', (event) => {
      if (!this.authStore) return

      // 监听认证相关的存储变化
      if (event.key === 'yibao_authenticated') {
        this.handleAuthStatusChange(event.newValue)
      } else if (event.key === 'yibao_user') {
        this.handleUserInfoChange(event.newValue)
      } else if (event.key === 'yibao_access_token') {
        this.handleTokenChange(event.newValue)
      }
    })

    // 监听页面可见性变化，用于检测标签页切换
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.authStore) {
        this.checkAuthStatus()
      }
    })

    // 监听页面焦点变化
    window.addEventListener('focus', () => {
      if (this.authStore) {
        this.checkAuthStatus()
      }
    })
  }

  // 处理认证状态变化
  private handleAuthStatusChange(newValue: string | null) {
    if (!this.authStore) return

    console.log('🔄 检测到认证状态变化:', newValue)

    if (newValue !== 'true' && this.authStore.isAuthenticated) {
      // 其他标签页登出，当前标签页也需要登出
      console.log('🔄 其他标签页已登出，同步登出当前标签页')
      this.authStore.signOut()
    } else if (newValue === 'true' && !this.authStore.isAuthenticated) {
      // 其他标签页登录，当前标签页需要同步登录状态
      console.log('🔄 其他标签页已登录，同步登录状态')
      this.syncLoginState()
    }
  }

  // 处理用户信息变化
  private handleUserInfoChange(newValue: string | null) {
    if (!this.authStore) return

    try {
      if (newValue) {
        const newUser = JSON.parse(newValue)
        const currentUserStr = JSON.stringify(this.authStore.user)
        const newUserStr = JSON.stringify(newUser)

        if (currentUserStr !== newUserStr) {
          console.log('🔄 检测到用户信息变化，同步更新')
          this.authStore.user = newUser
        }
      } else if (this.authStore.user) {
        console.log('🔄 用户信息被清除，同步清除当前标签页')
        this.authStore.user = null
      }
    } catch (error) {
      console.warn('⚠️ 解析用户信息失败:', error)
    }
  }

  // 处理token变化
  private handleTokenChange(newValue: string | null) {
    if (!this.authStore) return

    if (!newValue && this.authStore.isAuthenticated) {
      console.log('🔄 Token被清除，同步登出')
      this.authStore.signOut()
    } else if (newValue && !this.authStore.isAuthenticated) {
      // 有新token但当前未认证，尝试同步登录状态
      console.log('🔄 检测到新token，尝试同步登录状态')
      this.syncLoginState()
    }
  }

  // 同步登录状态
  private async syncLoginState() {
    if (!this.authStore) return

    try {
      // 重新初始化认证状态
      this.authStore.initialized = false
      await this.authStore.initialize()
      console.log('✅ 登录状态同步完成')
    } catch (error) {
      console.warn('⚠️ 同步登录状态失败:', error)
    }
  }

  // 检查认证状态
  private async checkAuthStatus() {
    if (!this.authStore) return

    try {
      console.log('🔍 检查认证状态...')

      // 检查token是否仍然有效
      const isValid = await this.authStore.checkAndRefreshToken()
      if (!isValid && this.authStore.isAuthenticated) {
        console.log('❌ 认证状态检查失败，执行登出')
        await this.authStore.signOut()
      } else if (isValid) {
        console.log('✅ 认证状态检查通过')
      }
    } catch (error) {
      console.warn('⚠️ 检查认证状态失败:', error)
      // 检查失败时，如果当前显示为已认证但实际token无效，则登出
      if (this.authStore.isAuthenticated) {
        const hasValidToken = localStorage.getItem('yibao_access_token')
        if (!hasValidToken) {
          console.log('❌ 未找到有效token，执行登出')
          await this.authStore.signOut()
        }
      }
    }
  }

  // 停止监听
  stopListening() {
    this.isListening = false
    console.log('停止监听认证状态变化')
  }

  // 销毁实例
  destroy() {
    this.stopListening()
    this.authStore = null
    AuthSyncManager.instance = null
  }
}

// 导出单例实例
export const authSyncManager = AuthSyncManager.getInstance()

// 自动初始化函数
export function initAuthSync() {
  if (typeof window !== 'undefined') {
    const authStore = useAuthStore()
    authSyncManager.init(authStore)
  }
}
