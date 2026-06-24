import { isSuccessResponse, type ApiResponse } from '@/types/api'

const DEFAULT_BACKEND_PORT = '8001'

export const isApiResponse = <T>(value: unknown): value is ApiResponse<T> => {
  return (
    typeof value === 'object' && value !== null && 'success' in (value as Record<string, unknown>)
  )
}

export const resolveApiBaseUrl = (): string => {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configured) {
    return configured
  }
  const preferSameOrigin = String(import.meta.env.VITE_API_USE_SAME_ORIGIN || '')
    .trim()
    .toLowerCase()
  if (preferSameOrigin === 'true' || preferSameOrigin === '1') {
    return ''
  }
  if (import.meta.env.DEV) {
    return ''
  }
  if (typeof window !== 'undefined' && window.location) {
    const protocol = window.location.protocol || 'http:'
    const hostname = window.location.hostname || 'localhost'
    return `${protocol}//${hostname}:${DEFAULT_BACKEND_PORT}`
  }
  return ''
}

export const extractApiData = <T>(payload: unknown, context: string): T => {
  if (isApiResponse<T>(payload)) {
    if (isSuccessResponse<T>(payload)) {
      return payload.data as T
    }
    const errorMessage = payload.error || context
    throw new Error(errorMessage)
  }
  return payload as T
}
