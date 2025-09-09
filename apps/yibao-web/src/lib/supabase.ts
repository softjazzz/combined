import { createSupabase } from '@health-qc/web-utils'
import { setSupabase } from '@health-qc/web-utils'

// 从环境变量获取 Supabase 配置（无变量时回退为提供的项目 URL）
const url = (import.meta as any).env?.VITE_SUPABASE_URL || 'https://apkvovxrsjzwmeuuzgnc.supabase.co'
const anonKey = (import.meta as any).env?.VITE_SUPABASE_ANON_KEY || ''

// 验证必要的环境变量
if (!url || !anonKey) {
  console.warn('[Yibao Supabase] 缺少必要的环境变量 VITE_SUPABASE_URL 或 VITE_SUPABASE_ANON_KEY')
}

// 创建 Supabase 客户端实例
export const supabase = createSupabase({
  url,
  anonKey,
  clientOptions: {
    auth: {
      storageKey: 'yibao.auth', // 医保系统专用存储键
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true
    },
    db: {
      schema: 'public'
    },
    global: {
      headers: {
        'X-Client-Info': 'yibao-web@1.0.0'
      }
    }
  }
})

// 注册到 web-utils 供其他模块使用
setSupabase(supabase)

// 导出配置信息（用于调试）
export const supabaseConfig = {
  url: url ? `${url.substring(0, 20)}...` : 'Not configured',
  hasAnonKey: !!anonKey,
  storageKey: 'yibao.auth'
}


