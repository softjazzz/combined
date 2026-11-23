import { RUNTIME_BUILD_QUERY_TIMEOUT_MS } from '@/config/requestTimeouts'
import { apiClient } from '@/services/apiService'

export interface FrontendBuildIdentity {
  development: boolean
  buildId: string | null
  gitCommit: string | null
}

export interface RuntimeBuild {
  available: boolean
  build_id: string | null
  git_commit: string | null
  started_at: string
  pid: number
  reason?: string
}

export type RuntimeBuildResult =
  | { kind: 'ready'; data: RuntimeBuild }
  | { kind: 'unavailable'; message: string }
  | { kind: 'connection_error'; message: string }

export type RuntimeBuildState = 'development' | 'matching' | 'mismatch' | 'unknown' | 'error'

function identityText(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function getFrontendBuildIdentity(): FrontendBuildIdentity {
  // 必须取当前已加载 JS 的编译常量，不能从服务器元数据推测前端版本。
  return {
    development: import.meta.env.DEV,
    buildId: identityText(import.meta.env.VITE_MEDQC_BUILD_ID),
    gitCommit: identityText(import.meta.env.VITE_MEDQC_GIT_COMMIT),
  }
}

function parseRuntimeBuild(value: unknown): RuntimeBuild | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const row = value as Record<string, unknown>
  if (
    typeof row.available !== 'boolean' ||
    !(row.build_id === null || typeof row.build_id === 'string') ||
    !(row.git_commit === null || typeof row.git_commit === 'string') ||
    typeof row.started_at !== 'string' ||
    !/(?:Z|\+00:00)$/.test(row.started_at) ||
    !Number.isFinite(Date.parse(row.started_at)) ||
    typeof row.pid !== 'number' ||
    !Number.isSafeInteger(row.pid) ||
    row.pid <= 0 ||
    (row.reason !== undefined && typeof row.reason !== 'string')
  )
    return null
  return {
    available: row.available,
    build_id: identityText(row.build_id),
    git_commit: identityText(row.git_commit),
    started_at: row.started_at,
    pid: row.pid,
    ...(typeof row.reason === 'string' ? { reason: row.reason } : {}),
  }
}

export async function fetchRuntimeBuild(): Promise<RuntimeBuildResult> {
  try {
    const response = await apiClient.get<unknown>('/api/v1/runtime-build', {
      params: { _t: Date.now() },
      headers: { 'Cache-Control': 'no-cache, no-store' },
      timeout: RUNTIME_BUILD_QUERY_TIMEOUT_MS,
      // 轮询中的旧后端 404 由状态按钮解释，不弹出全局 HTTP 错误提示。
      validateStatus: () => true,
    })
    if (response.status === 404) return { kind: 'unavailable', message: '后端尚未提供版本信息' }
    if (response.status !== 200)
      return { kind: 'connection_error', message: '后端版本信息请求失败' }
    const data = parseRuntimeBuild(response.data)
    return data
      ? { kind: 'ready', data }
      : { kind: 'unavailable', message: '后端版本信息不完整或格式无效' }
  } catch {
    return { kind: 'connection_error', message: '无法连接后端，请稍后刷新' }
  }
}

export function compareRuntimeBuild(
  frontend: FrontendBuildIdentity,
  result: RuntimeBuildResult | null,
): RuntimeBuildState {
  if (frontend.development) return 'development'
  if (result?.kind === 'connection_error') return 'error'
  if (!frontend.buildId || !frontend.gitCommit || result?.kind !== 'ready') return 'unknown'
  const backend = result.data
  if (!backend.available || !backend.build_id || !backend.git_commit) return 'unknown'
  return frontend.buildId === backend.build_id && frontend.gitCommit === backend.git_commit
    ? 'matching'
    : 'mismatch'
}
