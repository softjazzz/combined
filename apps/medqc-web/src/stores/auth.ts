// @ts-nocheck
import { defineStore } from 'pinia'
import { ref, computed, readonly } from 'vue'
import { ApiService } from '@/services/apiService'
import type { LoginRequest, LoginResponse, ProfileUpdateRequest, RegisterRequest } from '@/types'
import { message } from 'ant-design-vue'
import { setAccessToken, setRefreshToken } from '@/utils/auth-token'

// 简化的用户类型定义
interface User {
  id: string
  email?: string
  display_name?: string
  department?: string
  institute_id?: string | null
  hospital_id?: string
  roles?: string[]
  is_active?: boolean
  last_login?: string
  created_at?: string
  updated_at?: string
  avatar?: string
  phone?: string
  bio?: string
  role?: string
  is_demo_account?: boolean
  notifications?: {
    email: boolean
    sms: boolean
    push: boolean
  }
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref<User | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  // 计算属性
  const isAuthenticated = computed(() => !!user.value)
  const userRoles = computed(() => {
    if (!user.value) return []
    // 支持两种数据格式：roles数组 或 role字符串
    if (user.value.roles && Array.isArray(user.value.roles)) {
      return user.value.roles
    }
    if (user.value.role) {
      return [user.value.role]
    }
    return []
  })
  const userName = computed(() => {
    if (!user.value) return ''
    return user.value.display_name || user.value.email || '未知用户'
  })
  const userDepartment = computed(() => user.value?.department || '')
  const userInstituteId = computed(() => user.value?.institute_id || '')

  // 权限检查
  const hasRole = (role: string): boolean => {
    return userRoles.value.includes(role)
  }

  // 初始化认证状态
  const initialize = async () => {
    if (initialized.value) return

    try {
      loading.value = true

      // 检查是否有有效的token
      if (ApiService.isAuthenticated()) {
        // 尝试获取当前用户信息
        const response = await ApiService.getCurrentUser()
        if (response.success && response.data) {
          user.value = response.data
          localStorage.setItem('medqc_user', JSON.stringify(response.data))
          localStorage.setItem('medqc_authenticated', 'true')
          console.warn('用户已登录:', response.data.display_name)
        } else {
          // Token无效，清除本地状态
          user.value = null
          localStorage.removeItem('auth_user')
          localStorage.removeItem('medqc_user')
          localStorage.removeItem('medqc_authenticated')
        }
      } else {
        // 没有有效 access token，不恢复用户态，避免出现“前端已登录/接口 403”的假登录状态
        user.value = null
        localStorage.removeItem('auth_user')
        localStorage.removeItem('medqc_user')
        localStorage.removeItem('medqc_authenticated')
      }

      initialized.value = true
    } catch (error) {
      console.error('初始化认证状态失败:', error)
      user.value = null
      localStorage.removeItem('auth_user')
      localStorage.removeItem('medqc_user')
      localStorage.removeItem('medqc_authenticated')
    } finally {
      loading.value = false
    }
  }

  // 登录
  const signIn = async (account: string, password: string, _role?: string) => {
    try {
      loading.value = true

      // 暂时不发送role参数，因为后端在role为None时工作正常
      const loginRequest: LoginRequest = {
        account,
        password,
        // role 参数暂时注释掉
      }

      const response = await ApiService.login(loginRequest)

      if (response.success && response.data) {
        // 登录成功后，使用token拉取当前用户信息
        const me = await ApiService.getCurrentUser()
        if (me.success && me.data) {
          user.value = me.data
          // 保存正确的用户数据到localStorage
          localStorage.setItem('auth_user', JSON.stringify(me.data))
          localStorage.setItem('medqc_user', JSON.stringify(me.data))
          localStorage.setItem('medqc_authenticated', 'true')
          console.warn('✅ 登录成功:', me.data.display_name || me.data.email)
          return {
            success: true,
            data: me.data,
          }
        } else {
          // 后端未提供用户详情时的兜底：至少返回邮箱
          const fallbackEmail = account.includes('@') ? account : undefined
          const fallbackUser: User = {
            id: 'unknown',
            email: fallbackEmail,
            display_name: account,
            roles: ['user'],
            is_active: true,
          }
          user.value = fallbackUser
          localStorage.setItem('auth_user', JSON.stringify(fallbackUser))
          localStorage.setItem('medqc_user', JSON.stringify(fallbackUser))
          localStorage.setItem('medqc_authenticated', 'true')
          console.warn('⚠️ 未能获取用户详情，使用兜底用户信息')
          return {
            success: true,
            data: fallbackUser,
          }
        }
      }

      return {
        success: false,
        error: response.error || '登录失败',
      }
    } catch (error) {
      console.error('Login error:', error)
      return {
        success: false,
        error: '登录过程中发生错误',
      }
    } finally {
      loading.value = false
    }
  }

  // 扫码兑换只安装服务端签发的令牌；用户身份必须由 /auth/me 再次确认。
  const completeQrLogin = async (
    tokens: Pick<LoginResponse, 'access_token' | 'refresh_token' | 'token_type' | 'expires_in'>,
    isCurrent: () => boolean = () => true,
  ) => {
    try {
      loading.value = true
      if (!isCurrent()) return { success: false, error: '扫码登录会话已失效' }
      const me = await ApiService.getCurrentUserWithAccessToken(tokens.access_token)
      if (!isCurrent()) return { success: false, error: '扫码登录会话已失效' }
      const verifiedUser = me.success ? me.data : null
      if (
        !verifiedUser ||
        typeof verifiedUser.id !== 'string' ||
        !verifiedUser.id.trim() ||
        typeof verifiedUser.email !== 'string' ||
        !verifiedUser.email.trim() ||
        !Array.isArray(verifiedUser.roles) ||
        verifiedUser.roles.length < 1 ||
        !verifiedUser.roles.every((role) => typeof role === 'string' && Boolean(role.trim()))
      ) {
        return { success: false, error: '无法确认扫码登录用户，请重新扫码' }
      }
      setAccessToken(tokens.access_token)
      if (tokens.refresh_token) setRefreshToken(tokens.refresh_token)
      user.value = verifiedUser
      localStorage.setItem('auth_user', JSON.stringify(verifiedUser))
      localStorage.setItem('medqc_user', JSON.stringify(verifiedUser))
      localStorage.setItem('medqc_authenticated', 'true')
      return { success: true, data: verifiedUser }
    } catch {
      return { success: false, error: '无法确认扫码登录用户，请重新扫码' }
    } finally {
      loading.value = false
    }
  }

  // 注册
  const signUp = async (userData: RegisterRequest) => {
    try {
      loading.value = true

      const response = await ApiService.register(userData)

      if (response.success) {
        return {
          success: true,
          message: response.message || '注册成功，请等待管理员审核',
        }
      }

      return {
        success: false,
        error: response.error || '注册失败',
      }
    } catch (error) {
      console.error('注册失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '注册失败',
      }
    } finally {
      loading.value = false
    }
  }

  // 登出
  const signOut = async () => {
    try {
      loading.value = true

      // 调用API登出
      await ApiService.logout()

      // 清除本地状态
      user.value = null
      localStorage.removeItem('auth_user')
      localStorage.removeItem('medqc_user')
      localStorage.removeItem('medqc_authenticated')

      return { success: true }
    } catch (error) {
      console.error('登出失败:', error)
      // 即使API调用失败，也要清除本地状态
      user.value = null
      localStorage.removeItem('auth_user')
      localStorage.removeItem('medqc_user')
      localStorage.removeItem('medqc_authenticated')
      return { success: true }
    } finally {
      loading.value = false
    }
  }

  // 忘记密码
  const resetPassword = async (email: string) => {
    try {
      loading.value = true
      const response = await ApiService.forgotPassword(email)
      if (response.success) {
        message.success(response.message || '重置密码邮件已发送')
        return { success: true }
      }
      return { success: false, error: response.error || '重置密码失败' }
    } catch (error) {
      console.error('重置密码失败:', error)
      return { success: false, error: error instanceof Error ? error.message : '重置密码失败' }
    } finally {
      loading.value = false
    }
  }

  // 更新密码
  const updatePassword = async (password: string, currentPassword?: string) => {
    try {
      loading.value = true
      const response = await ApiService.updatePassword(password, currentPassword)
      if (response.success) {
        message.success(response.message || '密码更新成功')
        return { success: true }
      }
      return { success: false, error: response.error || '更新密码失败' }
    } catch (error) {
      console.error('更新密码失败:', error)
      return { success: false, error: error instanceof Error ? error.message : '更新密码失败' }
    } finally {
      loading.value = false
    }
  }

  // 更新用户档案
  const updateProfile = async (updates: ProfileUpdateRequest) => {
    try {
      loading.value = true
      const account = user.value?.id || ''
      const editable: ProfileUpdateRequest = {
        ...(updates.display_name !== undefined ? { display_name: updates.display_name } : {}),
        ...(updates.avatar !== undefined ? { avatar: updates.avatar } : {}),
        ...(updates.phone !== undefined ? { phone: updates.phone } : {}),
        ...(updates.bio !== undefined ? { bio: updates.bio } : {}),
        ...(updates.notifications !== undefined ? { notifications: updates.notifications } : {}),
      }
      const response = await ApiService.updateProfile(editable)
      if (account !== (user.value?.id || '')) {
        return { success: false, error: '账号身份已变更，请重新操作' }
      }
      if (response.success && response.data) {
        user.value = response.data
        localStorage.setItem('auth_user', JSON.stringify(response.data))
        localStorage.setItem('medqc_user', JSON.stringify(response.data))
        message.success(response.message || '用户信息更新成功')
        return { success: true }
      }
      return { success: false, error: response.error || '更新档案失败' }
    } catch (error) {
      console.error('更新档案失败:', error)
      return { success: false, error: error instanceof Error ? error.message : '更新档案失败' }
    } finally {
      loading.value = false
    }
  }

  return {
    // 状态
    user: readonly(user),
    loading: readonly(loading),
    initialized: readonly(initialized),

    // 计算属性
    isAuthenticated,
    userRoles,
    userName,
    userDepartment,
    userInstituteId,

    // 方法
    initialize,
    signIn,
    completeQrLogin,
    signUp,
    signOut,
    resetPassword,
    updatePassword,
    updateProfile,

    // 权限检查
    hasRole,
  }
})
