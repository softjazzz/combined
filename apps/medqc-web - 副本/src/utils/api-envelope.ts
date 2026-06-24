export interface ApiEnvelope<T = unknown> {
  success: boolean
  data?: T
  error?: string
  code?: string
  trace_id?: string
  message?: string
  details?: unknown
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function isApiEnvelope<T = unknown>(value: unknown): value is ApiEnvelope<T> {
  return isObject(value) && typeof value.success === 'boolean'
}

export function unwrapApiEnvelope<T = unknown>(value: unknown): T {
  if (isApiEnvelope<T>(value)) {
    if (value.success === false) {
      return value as T
    }
    return (value.data as T) ?? ({} as T)
  }
  return value as T
}

export function extractApiErrorMessage(value: unknown, fallback = '请求失败'): string {
  if (!isObject(value)) {
    return fallback
  }
  const detail = value.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  const error = value.error
  if (typeof error === 'string' && error.trim()) {
    return error
  }
  const message = value.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }
  return fallback
}

export function extractApiErrorMessageFromError(
  error: unknown,
  fallback = '请求失败',
): string {
  if (isObject(error)) {
    const responseData = (error as Record<string, unknown>).response
    if (isObject(responseData) && 'data' in responseData) {
      return extractApiErrorMessage((responseData as Record<string, unknown>).data, fallback)
    }

    const message = (error as Record<string, unknown>).message
    if (typeof message === 'string' && message.trim()) {
      return message
    }
  }

  return fallback
}

export function normalizeApiSuccess<T = unknown>(
  value: unknown,
): { success: boolean; data?: T; message?: string } {
  if (isApiEnvelope<T>(value)) {
    return {
      success: value.success,
      data: value.data,
      message: value.message,
    }
  }

  return {
    success: true,
    data: value as T,
  }
}
