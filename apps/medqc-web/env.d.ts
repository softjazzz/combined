/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_ANON_KEY: string
  readonly VITE_DEEPSEEK_API_URL: string
  readonly VITE_ENV: 'development' | 'production' | 'test'
  readonly VITE_API_BASE_URL?: string
  /** 设为 'true' 时登录页隐藏演示账号快速登录（默认显示，兼容现有演示部署） */
  readonly VITE_HIDE_DEMO_LOGIN?: string
  readonly DEV: boolean
  readonly PROD: boolean
  readonly MODE: string
  readonly BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
