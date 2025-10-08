declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, any>
  export default component
}

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $message: {
      success: (content: string) => void
      error: (content: string) => void
      warning: (content: string) => void
      info: (content: string) => void
    }
    $notification: {
      success: (config: { message: string; description?: string }) => void
      error: (config: { message: string; description?: string }) => void
      warning: (config: { message: string; description?: string }) => void
      info: (config: { message: string; description?: string }) => void
    }
    $modal: {
      confirm: (config: {
        title: string
        content: string
        onOk?: () => void
        onCancel?: () => void
      }) => void
    }
  }
}

// 全局类型声明
declare global {
  interface Window {
    __SUPABASE_URL__?: string
    __SUPABASE_ANON_KEY__?: string
  }
}

export {}
