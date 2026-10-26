// @ts-nocheck
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/auth'

declare global {
  interface ImportMetaEnv {
    readonly VITE_SUPABASE_URL?: string
    readonly VITE_SUPABASE_ANON_KEY?: string
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv
  }
}

// Mock ApiService
vi.mock('@/services/apiService', () => ({
  ApiService: {
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    getCurrentUser: vi.fn(),
    isAuthenticated: vi.fn(),
    refreshToken: vi.fn(),
    updateProfile: vi.fn(),
    forgotPassword: vi.fn(),
    updatePassword: vi.fn(),
  },
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
    is_active: true,
  }

  it('keeps auth identity fields without logging passwords or session tokens', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const password = 'synthetic-login-secret'
    const token = 'synthetic-session-secret'
    vi.mocked(ApiService.login).mockResolvedValue({ success: true, data: { access_token: token } })
    vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
      success: true, data: { ...mockUser, institute_id: 'A' },
    })
    try {
      const store = useAuthStore()
      expect((await store.signIn('synthetic-account', password)).success).toBe(true)
      expect(store.user?.institute_id).toBe('A')
      expect(store.user?.is_active).toBe(true)
      const logged = JSON.stringify(warn.mock.calls)
      expect(logged).not.toContain(password)
      expect(logged).not.toContain(token)
    } finally {
      warn.mockRestore()
    }
  })

  describe('initial state', () => {
    it('should have the correct initial state', () => {
      const store = useAuthStore()

      expect(store.user).toBeNull()
      expect(store.loading).toBe(false)
      expect(store.initialized).toBe(false)
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('computed state', () => {
    it('isAuthenticated should reflect auth state', async () => {
      const store = useAuthStore()

      expect(store.isAuthenticated).toBe(false)

      // 閫氳繃鐧诲綍鏂规硶璁剧疆鐢ㄦ埛鐘舵€?
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.isAuthenticated).toBe(true)
    })

    it('userRoles should return the current roles', async () => {
      const store = useAuthStore()

      expect(store.userRoles).toEqual([])

      // 閫氳繃鐧诲綍鏂规硶璁剧疆鐢ㄦ埛鐘舵€?
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userRoles).toEqual(['doctor'])
    })

    it('userRoles should support a single role field', async () => {
      const store = useAuthStore()

      const userWithSingleRole = {
        ...mockUser,
        roles: undefined,
        role: 'admin',
      } as any

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: userWithSingleRole,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: userWithSingleRole,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userRoles).toEqual(['admin'])
    })

    it('userName should return the display name', async () => {
      const store = useAuthStore()

      expect(store.userName).toBe('')

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userName).toBe('测试用户')
    })

    it('userName should fall back to email', async () => {
      const store = useAuthStore()

      const userWithoutName = {
        ...mockUser,
        display_name: undefined,
      } as any

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: userWithoutName,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: userWithoutName,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userName).toBe('test@example.com')
    })

    it('userDepartment should return the department', async () => {
      const store = useAuthStore()

      expect(store.userDepartment).toBe('')

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.userDepartment).toBe('心内科')
    })
  })

  describe('permission checks', () => {
    it('hasRole should check roles correctly', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')

      expect(store.hasRole('doctor')).toBe(true)
      expect(store.hasRole('admin')).toBe(false)
    })

    it('hasRole should return false when not signed in', () => {
      const store = useAuthStore()

      expect(store.hasRole('doctor')).toBe(false)
    })
  })

  describe('sign in', () => {
    it('should sign in successfully', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      const result = await store.signIn('test@example.com', 'password')

      expect(result.success).toBe(true)
      expect(store.user).toEqual(mockUser)
      expect(store.isAuthenticated).toBe(true)
      expect(ApiService.login).toHaveBeenCalledWith({
        account: 'test@example.com',
        password: 'password',
      })
    })

    it('should handle sign-in failures', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: false,
        error: '鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒',
        data: null,
      })

      const result = await store.signIn('test@example.com', 'wrong-password')

      expect(result.success).toBe(false)
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })

    it('should set loading while signing in', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockImplementation(() => {
        expect(store.loading).toBe(true)
        return Promise.resolve({
          success: true,
          data: {
            access_token: 'mock-token',
            refresh_token: 'mock-refresh-token',
            user: mockUser,
          },
          message: '鐧诲綍鎴愬姛',
        })
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')

      expect(store.loading).toBe(false)
    })
  })

  describe('sign out', () => {
    it('should sign out successfully', async () => {
      const store = useAuthStore()

      // 鍏堢櫥褰?
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')
      expect(store.isAuthenticated).toBe(true)

      // 鐒跺悗鐧诲嚭
      vi.mocked(ApiService.logout).mockResolvedValue({
        success: true,
        message: '鐧诲嚭鎴愬姛',
      })

      await store.signOut()

      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
      expect(ApiService.logout).toHaveBeenCalled()
    })

    it('should still clear local state when sign-out fails', async () => {
      const store = useAuthStore()

      // 鍏堢櫥褰?
      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '鐧诲綍鎴愬姛',
      })

      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.signIn('test@example.com', 'password')

      vi.mocked(ApiService.logout).mockRejectedValue(new Error('缃戠粶閿欒'))

      await store.signOut()

      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('initialize', () => {
    it('should restore user state when token is valid', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.isAuthenticated).mockReturnValue(true)
      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.initialize()

      expect(store.user).toEqual(mockUser)
      expect(store.initialized).toBe(true)
    })

    it('should clear state when token is invalid', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.isAuthenticated).mockReturnValue(false)

      await store.initialize()

      expect(store.user).toBeNull()
      expect(store.initialized).toBe(true)
    })

    it('should initialize only once', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.isAuthenticated).mockReturnValue(true)
      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '鑾峰彇鐢ㄦ埛淇℃伅鎴愬姛',
      })

      await store.initialize()
      await store.initialize()

      expect(ApiService.getCurrentUser).toHaveBeenCalledTimes(1)
    })
  })

  describe('update profile', () => {
    it('should update the profile successfully', async () => {
      const store = useAuthStore()

      vi.mocked(ApiService.login).mockResolvedValue({
        success: true,
        data: {
          access_token: 'mock-token',
          refresh_token: 'mock-refresh-token',
          user: mockUser,
        },
        message: '登录成功',
      })
      vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
        success: true,
        data: mockUser,
        message: '获取用户成功',
      })
      await store.signIn('test@example.com', 'password')

      const updates = {
        display_name: '鏇存柊鍚庣殑鐢ㄦ埛',
      }

      vi.mocked(ApiService.updateProfile).mockResolvedValue({
        success: true,
        data: { ...mockUser, ...updates },
        message: '更新成功',
      })

      const result = await store.updateProfile(updates)

      expect(result.success).toBe(true)
      expect(store.user?.display_name).toBe(updates.display_name)
    })

    it('should no-op when updating without sign-in', async () => {
      const store = useAuthStore()

      const updates = {
        display_name: '鏇存柊鍚庣殑鐢ㄦ埛',
      }

      vi.mocked(ApiService.updateProfile).mockResolvedValue({
        success: false,
        error: '未登录',
      })

      const result = await store.updateProfile(updates)

      expect(result.success).toBe(false)
      expect(store.user).toBeNull()
    })
  })
})
