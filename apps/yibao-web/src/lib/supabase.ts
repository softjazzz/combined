import { createSupabase, setSupabase } from '@health-qc/web-utils'

const url = (import.meta as any).env?.VITE_SUPABASE_URL || ''
const anonKey = (import.meta as any).env?.VITE_SUPABASE_ANON_KEY || ''

export const supabase = createSupabase({
  url,
  anonKey,
  clientOptions: {
    auth: {
      storageKey: 'yibao.auth',
      persistSession: true,
      autoRefreshToken: true
    }
  }
})

// Make client available to web-utils helpers like ApiWrapper.uploadFile
setSupabase(supabase)


