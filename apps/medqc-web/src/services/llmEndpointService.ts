import { authFetch } from '@/utils/auth-fetch'

export interface EndpointRow {
  provider_code: string
  name: string
  source: 'saved' | 'deployment'
  endpoint: string
  enabled: boolean
  key_configured: boolean
}
export interface EndpointView {
  version: number
  editable: boolean
  providers: EndpointRow[]
  audit: { version: number; provider: string; actor: string; at: string; action: string }[]
}
export interface EndpointUpdate {
  version: number
  use_deployment: boolean
  endpoint: string
  enabled: boolean
  api_key?: string
  clear_key: boolean
}

async function request(provider?: string, payload?: EndpointUpdate): Promise<EndpointView> {
  // 不经过会打印Axios请求对象的错误拦截器，密钥只在当前请求内使用。
  const response = await authFetch(`/api/v1/llm/endpoints${provider ? `/${encodeURIComponent(provider)}` : ''}`, {
    method: payload ? 'PUT' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  })
  if (!response.ok) {
    if (response.status === 409) throw new Error('配置已变化或当前为受控 Gateway，请重新读取后确认。')
    if (response.status === 403) throw new Error('仅超级管理员可管理推理服务连接。')
    if (response.status === 422) throw new Error('请检查服务地址、启用状态和密钥操作。')
    throw new Error('推理连接配置暂不可用；未切换到其他服务。')
  }
  const result: { data: EndpointView } = await response.json()
  return result.data
}

export const llmEndpointService = { load: () => request(), save: (provider: string, payload: EndpointUpdate) => request(provider, payload) }
