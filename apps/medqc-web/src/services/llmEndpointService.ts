import { authFetch } from '@/utils/auth-fetch'

export interface EndpointRow {
  provider_code: string
  name: string
  source: 'saved' | 'deployment'
  endpoint: string
  enabled: boolean
  key_configured: boolean
  host_allowed?: boolean
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

const ENDPOINT_422_MESSAGES: Record<string, string> = {
  llm_endpoint_key_reconfirmation_required:
    '更换服务地址的主机或端口时，为防止密钥泄漏，请重新输入新地址对应的 API 密钥，或勾选“明确清除已保存密钥”。',
  llm_endpoint_host_not_allowed:
    '该服务地址的主机不在允许范围内（禁止云元数据及非允许的内网地址；云端服务或自定义内网主机如需放行，请将其加入部署白名单 OUTBOUND_ALLOWLIST）。',
  llm_endpoint_configuration_invalid:
    '服务地址格式无效：仅支持不含账号密码、查询参数（?）和片段（#）的 http(s):// 地址。',
  llm_endpoint_key_action_conflict:
    '不能同时填写新密钥并勾选“明确清除已保存密钥”，请二选一。',
  llm_endpoint_configuration_incomplete:
    '启用该推理服务前，请先填写有效的 API 地址（云端服务还需配置 API 密钥）。',
  llm_endpoint_provider_unsupported: '不支持的推理服务类型。',
}

export function mapEndpointErrorMessage(status: number, errorCode?: string): string {
  const code = String(errorCode || '').trim()
  if (status === 409) {
    if (code === 'llm_endpoint_gateway_deployment_managed') {
      return '当前为受控 Gateway 模式，连接与令牌由部署管理，不能改为直连。'
    }
    return '配置已变化或当前为受控 Gateway，请重新读取后确认。'
  }
  if (status === 403) return '仅超级管理员可管理推理服务连接。'
  if (status === 422) {
    return ENDPOINT_422_MESSAGES[code] || '请检查服务地址、启用状态和密钥操作。'
  }
  return '推理连接配置暂不可用；未切换到其他服务。'
}

async function extractErrorCode(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: unknown; detail?: unknown } | null
    if (typeof body?.error === 'string' && body.error.trim()) return body.error.trim()
    if (typeof body?.detail === 'string' && body.detail.trim()) return body.detail.trim()
  } catch {
    // 忽略非 JSON 或空响应体，按状态码兜底提示
  }
  return ''
}

async function request(provider?: string, payload?: EndpointUpdate): Promise<EndpointView> {
  // 不经过会打印Axios请求对象的错误拦截器，密钥只在当前请求内使用。
  const response = await authFetch(`/api/v1/llm/endpoints${provider ? `/${encodeURIComponent(provider)}` : ''}`, {
    method: payload ? 'PUT' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  })
  if (!response.ok) {
    const code = await extractErrorCode(response)
    throw new Error(mapEndpointErrorMessage(response.status, code))
  }
  const result: { data: EndpointView } = await response.json()
  return result.data
}

export const llmEndpointService = { load: () => request(), save: (provider: string, payload: EndpointUpdate) => request(provider, payload) }
