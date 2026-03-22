// @ts-nocheck
import { defineStore } from 'pinia'
import { ref, computed, readonly } from 'vue'
import { ApiService } from '@/services/apiService'
import type { LoginRequest, RegisterRequest } from '@/types'
import { message } from 'ant-design-vue'

// 简化的用户类型定义
interface User {
  id: string
  email?: string
  display_name?: string
  department?: string
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
          localStorage.removeItem('medqc_user')
          localStorage.removeItem('medqc_authenticated')
        }
      } else {
        // 没有有效token，检查本地存储的用户信息
        const savedUser = localStorage.getItem('medqc_user')
        const savedAuth = localStorage.getItem('medqc_authenticated')

        if (savedUser && savedAuth === 'true') {
          try {
            user.value = JSON.parse(savedUser)
            console.warn('从本地存储恢复用户:', user.value.display_name)
          } catch (error) {
            console.error('解析用户数据失败:', error)
            localStorage.removeItem('medqc_user')
            localStorage.removeItem('medqc_authenticated')
          }
        }
      }

      initialized.value = true
    } catch (error) {
      console.error('初始化认证状态失败:', error)
      user.value = null
    } finally {
      loading.value = false
    }
  }

  // 登录
  const signIn = async (email: string, password: string, _role?: string) => {
    try {
      loading.value = true

      // 暂时不发送role参数，因为后端在role为None时工作正常
      const loginRequest: LoginRequest = {
        email,
        password,
        // role 参数暂时注释掉
      }

      console.warn('🔐 Auth Store 登录请求:', loginRequest)
      const response = await ApiService.login(loginRequest)
      console.warn('📡 API 响应:', response)

      if (response.success && response.data) {
        // 登录成功后，使用token拉取当前用户信息
        const me = await ApiService.getCurrentUser()
        if (me.success && me.data) {
          user.value = me.data
          // 保存正确的用户数据到localStorage
          localStorage.setItem('medqc_user', JSON.stringify(me.data))
          localStorage.setItem('medqc_authenticated', 'true')
          console.warn('✅ 登录成功:', me.data.display_name || me.data.email)
          return {
            success: true,
            data: me.data,
          }
        } else {
          // 后端未提供用户详情时的兜底：至少返回邮箱
          const fallbackUser: User = {
            id: 'unknown',
            email,
            display_name: email,
            roles: ['user'],
            is_active: true,
          }
          user.value = fallbackUser
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
      localStorage.removeItem('medqc_user')
      localStorage.removeItem('medqc_authenticated')

      return { success: true }
    } catch (error) {
      console.error('登出失败:', error)
      // 即使API调用失败，也要清除本地状态
      user.value = null
      localStorage.removeItem('medqc_user')
      localStorage.removeItem('medqc_authenticated')
      return { success: true }
    } finally {
      loading.value = false
    }
  }

  // 重置密码（模拟）
  const resetPassword = async (_email: string) => {
    try {
      loading.value = true

      // 模拟重置密码逻辑
      message.info('密码重置邮件已发送（模拟）')

      return { success: true }
    } catch (error) {
      console.error('重置密码失败:', error)
      return { success: false, error: error instanceof Error ? error.message : '重置密码失败' }
    } finally {
      loading.value = false
    }
  }

  // 更新密码（模拟）
  const updatePassword = async (_password: string) => {
    try {
      loading.value = true

      // 模拟更新密码逻辑
      message.success('密码更新成功（模拟）')

      return { success: true }
    } catch (error) {
      console.error('更新密码失败:', error)
      return { success: false, error: error instanceof Error ? error.message : '更新密码失败' }
    } finally {
      loading.value = false
    }
  }

  // 更新用户档案（模拟）
  const updateProfile = async (updates: Partial<User>) => {
    try {
      loading.value = true

      if (user.value) {
        // 更新本地用户信息
        user.value = { ...user.value, ...updates }
        localStorage.setItem('auth_user', JSON.stringify(user.value))
        message.success('用户信息更新成功')
      }

      return { success: true }
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

    // 方法
    initialize,
    signIn,
    signUp,
    signOut,
    resetPassword,
    updatePassword,
    updateProfile,

    // 权限检查
    hasRole,
  }
})
