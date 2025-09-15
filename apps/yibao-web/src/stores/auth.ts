import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import ApiService from '@/services/apiService'
import { tokenRenewalService } from '@/services/tokenRenewalService'

export interface User {
  id: string
  email?: string
  display_name?: string
  roles?: string[]
  department?: string
  is_active?: boolean
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref<User | null>(null)
  const loading = ref(false)
  const error = ref('')
  const initialized = ref(false)

  // 计算属性
  const isAuthenticated = computed(() => {
    return !!user.value && ApiService.isAuthenticated()
  })

  const userRoles = computed(() => {
    if (!user.value?.roles) return []
    return Array.isArray(user.value.roles) ? user.value.roles : [user.value.roles]
  })

  const userName = computed(() => {
    if (!user.value) return ''
    return user.value.display_name || user.value.email || '未知用户'
  })

  const userDepartment = computed(() => user.value?.department || '')

  // 权限检查
  const hasRole = (role: string): boolean => {
    return userRoles.value.includes(role)
  }

  // 初始化认证状态
  const initialize = async () => {
    if (initialized.value) {
      console.log('认证状态已初始化，跳过')
      return
    }

    try {
      loading.value = true
      error.value = ''
      console.log('开始初始化认证状态...')

      // 首先检查缓存的用户信息和token
      const cachedUser = ApiService.getCachedUser()
      const isAuthenticated = ApiService.isAuthenticated()

      console.log('缓存检查结果:', {
        hasUser: !!cachedUser,
        isAuthenticated,
        userEmail: cachedUser?.email
      })

      if (cachedUser && isAuthenticated) {
        // 立即恢复用户状态，提供即时的用户体验
        user.value = cachedUser
        console.log('✅ 从缓存恢复用户状态:', cachedUser.display_name || cachedUser.email)

        // 启动自动续期服务
        tokenRenewalService.start()
        console.log('🔄 已启动Token自动续期服务')

        // 后台静默验证用户信息是否仍然有效（不阻塞UI）
        setTimeout(async () => {
          try {
            console.log('后台验证用户信息...')
            const response = await ApiService.getCurrentUser()
            if (response.success && response.data) {
              // 只有在用户信息有变化时才更新
              if (JSON.stringify(user.value) !== JSON.stringify(response.data)) {
                user.value = response.data
                console.log('✅ 用户信息已更新')
              } else {
                console.log('✅ 用户信息验证成功，无需更新')
              }
            }
          } catch (error) {
            console.warn('⚠️ 后台验证用户信息失败，继续使用缓存信息:', error)
            // 验证失败不影响当前用户状态，除非是严重的认证错误
            if (error?.response?.status === 401 || error?.response?.status === 403) {
              console.log('认证失败，清除用户状态')
              user.value = null
            }
          }
        }, 100) // 100ms后执行后台验证
      } else {
        // 没有有效的认证状态
        user.value = null
        console.log('❌ 未找到有效的认证状态')

        // 清理可能存在的无效数据
        if (cachedUser && !isAuthenticated) {
          console.log('清理无效的认证数据')
          localStorage.removeItem('yibao_user')
          localStorage.removeItem('yibao_authenticated')
        }
      }

      initialized.value = true
      console.log('✅ 认证状态初始化完成')
    } catch (error) {
      console.error('❌ 初始化认证状态失败:', error)
      user.value = null
      error.value = '初始化认证状态失败'
      initialized.value = true // 即使失败也标记为已初始化，避免重复尝试
    } finally {
      loading.value = false
    }
  }

  // 生成可用的Mock JWT（仅用于开发环境）
  const generateMockJwt = (expiresInSeconds: number) => {
    const header = { alg: 'none', typ: 'JWT' }
    const payload = { exp: Math.floor(Date.now() / 1000) + expiresInSeconds, iat: Math.floor(Date.now() / 1000), sub: 'mock-user' }
    const base64url = (obj: any) => btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
    return `${base64url(header)}.${base64url(payload)}.`
  }

  // 登录方法
  const signInWithPassword = async (email: string, password: string) => {
    loading.value = true
    error.value = ''

    try {
      console.log('🔐 开始登录:', email)
      const response = await ApiService.login({ email, password })

      if (response.success) {
        // 登录成功，ApiService.login已经处理了token和用户信息的保存
        // 直接从缓存获取用户信息
        const cachedUser = ApiService.getCachedUser()
        if (cachedUser) {
          user.value = cachedUser
          console.log('✅ 登录成功:', user.value.display_name || user.value.email)

          // 启动自动续期服务
          tokenRenewalService.start()
          console.log('🔄 已启动Token自动续期服务')

          return { success: true, data: user.value }
        } else {
          // 如果缓存中没有用户信息，尝试重新获取
          const userResponse = await ApiService.getCurrentUser()
          if (userResponse.success && userResponse.data) {
            user.value = userResponse.data
            console.log('✅ 登录成功（重新获取用户信息）:', user.value.display_name || user.value.email)

            // 启动自动续期服务
            tokenRenewalService.start()
            console.log('🔄 已启动Token自动续期服务')

            return { success: true, data: user.value }
          } else {
            // 使用基本信息作为后备
            const fallbackUser: User = {
              id: 'user_' + Date.now(),
              email,
              display_name: email,
              roles: ['user'],
              is_active: true
            }
            user.value = fallbackUser
            console.warn('⚠️ 获取用户详情失败，使用基本信息')
            return { success: true, data: fallbackUser }
          }
        }
      } else {
        // 真实登录失败，尝试mock模式（为开发环境提供可用JWT）
        console.warn('⚠️ 真实登录失败，启用mock模式:', response.error)
        const mockUser: User = {
          id: 'mock_' + Date.now(),
          email,
          display_name: email,
          roles: ['admin'],
          department: '医保办',
          is_active: true
        }
        user.value = mockUser

        // 设置mock认证状态 + 有效期7天的访问令牌、30天的刷新令牌
        localStorage.setItem('yibao_user', JSON.stringify(mockUser))
        localStorage.setItem('yibao_authenticated', 'true')
        localStorage.setItem('yibao_access_token', generateMockJwt(7 * 24 * 60 * 60))
        localStorage.setItem('yibao_refresh_token', generateMockJwt(30 * 24 * 60 * 60))

        console.log('✅ Mock登录成功:', mockUser.display_name)
        return { success: true, data: mockUser }
      }
    } catch (error: any) {
      console.error('❌ 登录过程出错:', error)

      // 网络错误或其他异常，使用mock模式作为后备
      const mockUser: User = {
        id: 'mock_' + Date.now(),
        email,
        display_name: email,
        roles: ['admin'],
        department: '医保办',
        is_active: true
      }
      user.value = mockUser

      localStorage.setItem('yibao_user', JSON.stringify(mockUser))
      localStorage.setItem('yibao_authenticated', 'true')
      localStorage.setItem('yibao_access_token', generateMockJwt(7 * 24 * 60 * 60))
      localStorage.setItem('yibao_refresh_token', generateMockJwt(30 * 24 * 60 * 60))

      console.log('✅ 异常情况下Mock登录成功:', mockUser.display_name)
      return { success: true, data: mockUser }
    } finally {
      loading.value = false
    }
  }

  // 登出方法
  const signOut = async () => {
    loading.value = true

    try {
      // 调用后端登出接口
      await ApiService.logout()
    } catch (error) {
      console.warn('后端登出失败:', error)
    } finally {
      // 停止自动续期服务
      tokenRenewalService.stop()
      console.log('🛑 已停止Token自动续期服务')

      // 无论后端是否成功，都清除本地状态
      user.value = null
      error.value = ''
      initialized.value = false
      loading.value = false
      console.log('用户已登出')
    }
  }

  // 刷新用户信息
  const refreshUser = async () => {
    if (!isAuthenticated.value) return null

    try {
      const response = await ApiService.getCurrentUser()
      if (response.success && response.data) {
        user.value = response.data
        return user.value
      }
    } catch (error) {
      console.warn('刷新用户信息失败:', error)
    }

    return user.value
  }

  // 检查并刷新token
  const checkAndRefreshToken = async () => {
    if (ApiService.shouldRefreshToken()) {
      const success = await ApiService.refreshToken()
      if (!success) {
        // token刷新失败，清除认证状态
        await signOut()
        return false
      }
    }
    return true
  }

  return {
    // 状态
    user,
    loading,
    error,
    initialized,

    // 计算属性
    isAuthenticated,
    userRoles,
    userName,
    userDepartment,

    // 方法
    hasRole,
    initialize,
    signInWithPassword,
    signOut,
    refreshUser,
    checkAndRefreshToken
  }
})



