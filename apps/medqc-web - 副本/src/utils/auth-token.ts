const ACCESS_TOKEN_KEY = 'medqc_access_token'
const REFRESH_TOKEN_KEY = 'medqc_refresh_token'

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || ''
}

export function setAccessToken(token: string): void {
  const normalized = token.trim()
  if (!normalized) {
    return
  }
  localStorage.setItem(ACCESS_TOKEN_KEY, normalized)
}

export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || ''
}

export function setRefreshToken(token: string): void {
  const normalized = token.trim()
  if (!normalized) {
    return
  }
  localStorage.setItem(REFRESH_TOKEN_KEY, normalized)
}

export function clearRefreshToken(): void {
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function clearAuthTokens(): void {
  clearAccessToken()
  clearRefreshToken()
}
