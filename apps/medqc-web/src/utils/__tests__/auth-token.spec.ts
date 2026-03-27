import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearAccessToken,
  clearAuthTokens,
  clearRefreshToken,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '@/utils/auth-token'

describe('auth-token', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('only reads canonical access token key', () => {
    localStorage.setItem('access_token', 'legacy-access')
    expect(getAccessToken()).toBe('')
    expect(localStorage.getItem('medqc_access_token')).toBeNull()
    expect(localStorage.getItem('access_token')).toBe('legacy-access')
  })

  it('only reads canonical refresh token key', () => {
    localStorage.setItem('refresh_token', 'legacy-refresh')
    expect(getRefreshToken()).toBe('')
    expect(localStorage.getItem('medqc_refresh_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBe('legacy-refresh')
  })

  it('writes trimmed canonical access token without touching legacy keys', () => {
    localStorage.setItem('token', 'legacy-token')

    setAccessToken('  access-123  ')

    expect(localStorage.getItem('medqc_access_token')).toBe('access-123')
    expect(localStorage.getItem('token')).toBe('legacy-token')
  })

  it('clears only canonical access token key', () => {
    localStorage.setItem('medqc_access_token', 'access-123')
    localStorage.setItem('auth_token', 'legacy-token')

    clearAccessToken()

    expect(localStorage.getItem('medqc_access_token')).toBeNull()
    expect(localStorage.getItem('auth_token')).toBe('legacy-token')
  })

  it('writes and clears canonical refresh token key only', () => {
    localStorage.setItem('refresh_token', 'legacy-refresh')

    setRefreshToken('  refresh-456  ')
    expect(localStorage.getItem('medqc_refresh_token')).toBe('refresh-456')
    expect(localStorage.getItem('refresh_token')).toBe('legacy-refresh')

    clearRefreshToken()
    expect(localStorage.getItem('medqc_refresh_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBe('legacy-refresh')
  })

  it('clears both canonical tokens together', () => {
    localStorage.setItem('medqc_access_token', 'access-123')
    localStorage.setItem('medqc_refresh_token', 'refresh-456')

    clearAuthTokens()

    expect(localStorage.getItem('medqc_access_token')).toBeNull()
    expect(localStorage.getItem('medqc_refresh_token')).toBeNull()
  })
})
