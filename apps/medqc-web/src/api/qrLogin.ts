import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/auth/qr/sessions'

export type QrLoginStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'cancelled'
  | 'expired'
  | 'consumed'

export interface QrLoginSession {
  session_id: string
  browser_secret: string
  verification_code: string
  expires_at: string
  poll_interval_ms: number
}

export interface QrLoginState {
  session_id: string
  status: QrLoginStatus
  expires_at: string
}

export interface QrLoginTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export type QrLoginResult<T> =
  | { success: true; data: T }
  | { success: false; message: string }

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && Boolean(value.trim())
}

function isIsoDate(value: unknown): value is string {
  return isNonEmptyString(value) && Number.isFinite(Date.parse(value))
}

function isStatus(value: unknown): value is QrLoginStatus {
  return ['pending', 'approved', 'rejected', 'cancelled', 'expired', 'consumed'].includes(
    String(value),
  )
}

function normalizeSession(value: unknown): QrLoginSession | null {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.session_id)
    || !isNonEmptyString(value.browser_secret)
    || !isNonEmptyString(value.verification_code)
    || !isIsoDate(value.expires_at)
    || typeof value.poll_interval_ms !== 'number'
    || !Number.isInteger(value.poll_interval_ms)
    || value.poll_interval_ms < 500
    || value.poll_interval_ms > 30_000
  ) return null
  return {
    session_id: value.session_id.trim(),
    browser_secret: value.browser_secret.trim(),
    verification_code: value.verification_code.trim(),
    expires_at: value.expires_at,
    poll_interval_ms: value.poll_interval_ms,
  }
}

function normalizeState(value: unknown): QrLoginState | null {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.session_id)
    || !isStatus(value.status)
    || !isIsoDate(value.expires_at)
  ) return null
  return {
    session_id: value.session_id.trim(),
    status: value.status,
    expires_at: value.expires_at,
  }
}

function normalizeLoginResponse(value: unknown): QrLoginTokens | null {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.access_token)
    || !isNonEmptyString(value.refresh_token)
    || typeof value.token_type !== 'string'
    || value.token_type.toLowerCase() !== 'bearer'
    || typeof value.expires_in !== 'number'
    || !Number.isInteger(value.expires_in)
    || value.expires_in <= 0
  ) return null
  return {
    access_token: value.access_token.trim(),
    refresh_token: value.refresh_token.trim(),
    token_type: 'bearer',
    expires_in: value.expires_in,
  }
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  normalize: (value: unknown) => T | null,
  fallback: string,
): Promise<QrLoginResult<T>> {
  try {
    const response = await ApiService.requestRaw(config)
    const envelope = normalizeApiSuccess<unknown>(response.data)
    const data = envelope.success ? normalize(envelope.data) : null
    return data
      ? { success: true, data }
      : { success: false, message: envelope.message || `${fallback}：服务端返回格式异常` }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, fallback) }
  }
}

export function createQrLoginSession(): Promise<QrLoginResult<QrLoginSession>> {
  return request({ method: 'POST', url: BASE_URL }, normalizeSession, '创建扫码登录会话失败')
}

export function getQrLoginStatus(
  sessionId: string,
  browserSecret: string,
): Promise<QrLoginResult<QrLoginState>> {
  return request(
    { method: 'POST', url: `${BASE_URL}/${encodeURIComponent(sessionId)}/status`, data: { browser_secret: browserSecret } },
    normalizeState,
    '读取扫码登录状态失败',
  )
}

export function getQrLoginConfirmation(sessionId: string): Promise<QrLoginResult<QrLoginState>> {
  return request(
    { method: 'GET', url: `${BASE_URL}/${encodeURIComponent(sessionId)}/confirmation` },
    normalizeState,
    '读取扫码确认信息失败',
  )
}

export function confirmQrLogin(
  sessionId: string,
  verificationCode: string,
): Promise<QrLoginResult<QrLoginState>> {
  return request(
    { method: 'POST', url: `${BASE_URL}/${encodeURIComponent(sessionId)}/confirm`, data: { verification_code: verificationCode.trim() } },
    normalizeState,
    '确认扫码登录失败',
  )
}

export function rejectQrLogin(sessionId: string): Promise<QrLoginResult<QrLoginState>> {
  return request(
    { method: 'POST', url: `${BASE_URL}/${encodeURIComponent(sessionId)}/reject` },
    normalizeState,
    '拒绝扫码登录失败',
  )
}

export function cancelQrLogin(
  sessionId: string,
  browserSecret: string,
): Promise<QrLoginResult<QrLoginState>> {
  return request(
    { method: 'POST', url: `${BASE_URL}/${encodeURIComponent(sessionId)}/cancel`, data: { browser_secret: browserSecret } },
    normalizeState,
    '取消扫码登录失败',
  )
}

export function exchangeQrLogin(
  sessionId: string,
  browserSecret: string,
): Promise<QrLoginResult<QrLoginTokens>> {
  return request(
    { method: 'POST', url: `${BASE_URL}/${encodeURIComponent(sessionId)}/exchange`, data: { browser_secret: browserSecret } },
    normalizeLoginResponse,
    '兑换扫码登录结果失败',
  )
}
