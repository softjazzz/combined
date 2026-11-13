import { afterEach, describe, expect, it, vi } from 'vitest'
import { feedbackRequest } from '../demoFeedback'
import { setAccessToken, clearAccessToken } from '@/utils/auth-token'

afterEach(() => { clearAccessToken(); vi.unstubAllGlobals() })
describe('演示反馈会话', () => {
  it('未登录不发送请求', async () => {
    clearAccessToken()
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    await expect(feedbackRequest('/api/v1/demo/feedbacks')).rejects.toThrow('登录')
    expect(fetch).not.toHaveBeenCalled()
  })
  it.each([401, 403, 500])('拒绝 %s 响应，不能作为导出文件下载', async status => {
    setAccessToken('synthetic')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }))
    await expect(feedbackRequest('/api/v1/demo/feedbacks/export')).rejects.toThrow()
  })
  it.each(['GET', 'POST', 'DELETE'])('%s 带当前令牌且保留正文', async method => {
    setAccessToken('synthetic')
    const response = { ok: true }
    const fetch = vi.fn().mockResolvedValue(response); vi.stubGlobal('fetch', fetch)
    expect(await feedbackRequest('/api/v1/demo/feedbacks', { method, body: 'synthetic' })).toBe(response)
    const init = fetch.mock.calls[0][1]
    expect(init.headers.get('Authorization')).toBe('Bearer synthetic')
    expect(init.method).toBe(method); expect(init.body).toBe('synthetic')
  })
  it('不向外部地址发送令牌', async () => {
    setAccessToken('synthetic')
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    await expect(feedbackRequest('https://invalid.example/')).rejects.toThrow()
    expect(fetch).not.toHaveBeenCalled()
  })
})
