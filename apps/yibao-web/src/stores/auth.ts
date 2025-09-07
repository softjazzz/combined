import { defineStore } from 'pinia'
import { supabase } from '@/lib/supabase'

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
        const { data, error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        this.user = data.user
        return true
      } catch (e: any) {
        this.error = e?.message || '登录失败'
        return false
      } finally {
        this.loading = false
      }
    },
    async signOut() {
      await supabase.auth.signOut()
      this.user = null
    },
    async fetchUser() {
      const { data } = await supabase.auth.getUser()
      this.user = data.user
      return this.user
    }
  }
})



