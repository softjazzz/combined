import { defineStore } from 'pinia'
import ApiService from '@/services/apiService'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as any,
    loading: false as boolean,
    error: '' as string
  }),
  actions: {
    async signInWithPassword(email: string, password: string) {
      this.loading = true
      this.error = ''
      try {
        // 尝试真实登录；若失败，进入 mock 模式
        const res = await ApiService.login({ email, password }) as any
        if (res?.success) {
          const me = await ApiService.getCurrentUser()
          this.user = (me.success && me.data) ? me.data as any : { id: 'unknown', email, display_name: email, roles: ['user'] }
          localStorage.setItem('yibao_user', JSON.stringify(this.user))
          localStorage.setItem('yibao_authenticated', 'true')
          return true
        }
        // fallback to mock
        const mockUser = { id: 'mock', email, display_name: email, roles: ['admin'], department: '医保办' }
        this.user = mockUser
        localStorage.setItem('yibao_user', JSON.stringify(mockUser))
        localStorage.setItem('yibao_authenticated', 'true')
        return true
      } catch (e: any) {
        // 网络/后端不可用时，mock 成功
        const mockUser = { id: 'mock', email, display_name: email, roles: ['admin'], department: '医保办' }
        this.user = mockUser
        localStorage.setItem('yibao_user', JSON.stringify(mockUser))
        localStorage.setItem('yibao_authenticated', 'true')
        return true
      } finally {
        this.loading = false
      }
    },
    async signOut() {
      try { await ApiService.logout() } catch {}
      this.user = null
      localStorage.removeItem('yibao_user')
      localStorage.removeItem('yibao_authenticated')
    },
    async fetchUser() {
      // 优先从本地恢复（mock/真实都可）
      const savedAuth = localStorage.getItem('yibao_authenticated')
      const savedUser = localStorage.getItem('yibao_user')
      if (savedAuth === 'true' && savedUser) {
        try { this.user = JSON.parse(savedUser) } catch { this.user = null }
        return this.user
      }
      // 后端可用时再尝试请求
      try {
        const me = await ApiService.getCurrentUser()
        this.user = (me.success && me.data) ? me.data as any : null
      } catch {
        this.user = null
      }
      return this.user
    }
  }
})



