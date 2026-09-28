import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  confirmQrLogin,
  createQrLoginSession,
  exchangeQrLogin,
  getQrLoginStatus,
} from '@/api/qrLogin'

function response(data: unknown) {
  return {
    data: { success: true, data }, status: 200, statusText: 'OK', headers: {}, config: { headers: {} },
  } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

describe('扫码登录 API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('创建会话并保持浏览器密钥只在请求结果中', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      session_id: 'sid-1', browser_secret: 'secret-1', verification_code: '804211',
      expires_at: '2026-09-28T12:00:00Z', poll_interval_ms: 1000,
    }))
    const result = await createQrLoginSession()
    expect(result.success && result.data.browser_secret).toBe('secret-1')
  })

  it('状态轮询仅提交密钥且拒绝带token的畸形状态', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      session_id: 'sid-1', status: 'pending', expires_at: '2026-09-28T12:00:00Z',
      access_token: 'must-not-be-used',
    }))
    const result = await getQrLoginStatus('sid-1', 'secret-1')
    expect(result.success).toBe(true)
    expect(request).toHaveBeenCalledWith(expect.objectContaining({
      url: '/api/v1/auth/qr/sessions/sid-1/status', data: { browser_secret: 'secret-1' },
    }))
    expect(result.success && 'access_token' in result.data).toBe(false)
  })

  it('确认码只进入手机确认请求体', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      session_id: 'sid-1', status: 'approved', expires_at: '2026-09-28T12:00:00Z',
    }))
    await confirmQrLogin('sid-1', ' 804211 ')
    expect(request).toHaveBeenCalledWith(expect.objectContaining({
      url: '/api/v1/auth/qr/sessions/sid-1/confirm', data: { verification_code: '804211' },
    }))
  })

  it('只有exchange接受严格登录令牌响应', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      access_token: 'access', refresh_token: 'refresh', token_type: 'bearer', expires_in: 3600,
    }))
    const result = await exchangeQrLogin('sid-1', 'secret-1')
    expect(result.success && result.data.access_token).toBe('access')
  })

  it('exchange缺少refresh或可信用户投影时失败关闭', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      access_token: 'access', token_type: 'bearer', expires_in: 3600,
    }))
    expect((await exchangeQrLogin('sid-1', 'secret-1')).success).toBe(false)
  })
})
