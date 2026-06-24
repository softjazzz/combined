import { getAccessToken } from '@/utils/auth-token'

type FetchHeadersInit = globalThis.HeadersInit
type FetchRequestInfo = Parameters<typeof fetch>[0]
type FetchRequestInit = Parameters<typeof fetch>[1]

export function withAuthHeaders(headers?: FetchHeadersInit): Headers {
  const merged = new Headers(headers)
  const token = getAccessToken()
  if (token && !merged.has('Authorization')) {
    merged.set('Authorization', `Bearer ${token}`)
  }
  return merged
}

export function authFetch(input: FetchRequestInfo, init?: FetchRequestInit) {
  return fetch(input, {
    ...init,
    headers: withAuthHeaders(init?.headers),
  })
}
