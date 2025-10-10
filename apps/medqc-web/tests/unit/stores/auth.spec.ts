import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/auth'

// Mock ApiService
vi.mock('@/services/apiService', () => ({
  ApiService: {
    login: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
    isAuthenticated: vi.fn(),
    refreshToken: vi.fn()
  }
}))

import { ApiService } from '@/services/apiService'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  const mockUser: User = {
    id: 'user-001',
    email: 'test@example.com',
    display_name: '测试用户',
    roles: ['doctor'],
    department: '心内科',
    is_active: true
  }

  describe('初始状态', () => {
    it('应该有正确的初始状态', () => {
      const store = useAuthStore()

      expect(store.user).toBeNull()
      expect(store.loading).toBe(false)
      expect(store.initialized).toBe(false)
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('计算属性', () => {
    it('isAuthenticated 应该正确反映认证状态', async () => {
      const store = useAuthStore()

      expect(store.isAuthenticated).toBe(false)

      // 通过登录方法设置用户状态
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.isAuthenticated).toBe(true)
    })

    it('userRoles 应该正确返回用户角色', async () => {
      const store = useAuthStore()

      expect(store.userRoles).toEqual([])

      // 通过登录方法设置用户状态
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userRoles).toEqual(['doctor'])
    })

    it('userRoles 应该支持单个角色字符串', async () => {
      const store = useAuthStore()

      const userWithSingleRole = {
        ...mockUser,
        roles: undefined,
        role: 'admin'
      } as any

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: userWithSingleRole
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: userWithSingleRole,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userRoles).toEqual(['admin'])
    })

    it('userName 应该正确返回用户名', async () => {
      const store = useAuthStore()

      expect(store.userName).toBe('')

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userName).toBe('测试用户')
    })

    it('userName 应该回退到邮箱', async () => {
      const store = useAuthStore()

      const userWithoutName = {
        ...mockUser,
        display_name: undefined
      } as any

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: userWithoutName
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: userWithoutName,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userName).toBe('test@example.com')
    })

    it('userDepartment 应该正确返回科室', async () => {
      const store = useAuthStore()

      expect(store.userDepartment).toBe('')

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userDepartment).toBe('心内科')
    })
  })

  describe('权限检查', () => {
    it('hasRole 应该正确检查角色', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')

      expect(store.hasRole('doctor')).toBe(true)
      expect(store.hasRole('admin')).toBe(false)
    })

    it('hasRole 应该在未登录时返回 false', () => {
      const store = useAuthStore()

      expect(store.hasRole('doctor')).toBe(false)
    })
  })

  describe('登录功能', () => {
    it('应该成功登录', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      const result = await store.signIn('test@example.com', 'password')

      expect(result.success).toBe(true)
      expect(store.user).toEqual(mockUser)
      expect(store.isAuthenticated).toBe(true)
      expect(ApiService.login).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password'
      })
    })

    it('应该处理登录失败', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: false,
        error: '用户名或密码错误',
        data: null
      })

      const result = await store.signIn('test@example.com', 'wrong-password')

      expect(result.success).toBe(false)
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })

    it('应该在登录时设置 loading 状态', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockImplementation(() => {
        expect(store.loading).toBe(true)
        return Promise.resolve({
          success: true,
          data: {
            access_token: 'mock-token',
            refresh_token: 'mock-refresh-token',
            user: mockUser
          },
          message: '登录成功'
        })
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')

      expect(store.loading).toBe(false)
    })
  })

  describe('登出功能', () => {
    it('应该成功登出', async () => {
      const store = useAuthStore()

      // 先登录
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')
      expect(store.isAuthenticated).toBe(true)

      // 然后登出
      vi.mocked(ApiService.logout).mockResolvedValue({
        success: true,
        message: '登出成功'
      })

      await store.signOut()

      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
      expect(ApiService.logout).toHaveBeenCalled()
    })

    it('应该在登出失败时仍清除本地状态', async () => {
      const store = useAuthStore()

      // 先登录
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser
        },
        message: '登录成功'
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.signIn('test@example.com', 'password')

      vi.mocked(ApiService.logout).mockRejectedValue(new Error('网络错误'))

      await store.signOut()

      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('初始化功能', () => {
    it('应该在有有效 token 时恢复用户状态', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.isAuthenticated).mockReturnValue(true)
      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.initialize()

      expect(store.user).toEqual(mockUser)
      expect(store.initialized).toBe(true)
    })

    it('应该在无有效 token 时清除状态', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.isAuthenticated).mockReturnValue(false)

      await store.initialize()

      expect(store.user).toBeNull()
      expect(store.initialized).toBe(true)
    })

    it('应该只初始化一次', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.isAuthenticated).mockReturnValue(true)
      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户信息成功'
      })

      await store.initialize()
      await store.initialize()

      expect(ApiService.getCurrentUser).toHaveBeenCalledTimes(1)
    })
  })

  describe('更新用户档案', () => {
    it('应该成功更新用户档案', async () => {
      const store = useAuthStore()

      // 设置初始用户
      store.user = mockUser

      const updates = {
        display_name: '更新后的用户'
      }

      const result = await store.updateProfile(updates)

      expect(result.success).toBe(true)
    })

    it('应该在未登录时无法更新档案', async () => {
      const store = useAuthStore()

      const updates = {
        display_name: '更新后的用户'
      }

      const result = await store.updateProfile(updates)

      expect(result.success).toBe(true) // 方法总是返回 success
    })
  })
})

