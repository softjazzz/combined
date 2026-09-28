import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  cancel: vi.fn(), create: vi.fn(), exchange: vi.fn(), status: vi.fn(), complete: vi.fn(),
}))
vi.mock('@/api/qrLogin', () => ({
  cancelQrLogin: api.cancel,
  createQrLoginSession: api.create,
  exchangeQrLogin: api.exchange,
  getQrLoginStatus: api.status,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ completeQrLogin: api.complete }) }))
vi.mock('qrcode.vue', () => ({
  default: defineComponent({
    name: 'QrcodeVue', props: { value: String },
    setup(props) { return () => h('div', { class: 'qr-value', 'data-value': props.value }) },
  }),
}))

import QrLoginPanel from '@/components/auth/QrLoginPanel.vue'

const session = {
  session_id: 'sid-1', browser_secret: 'secret-1', verification_code: '804211',
  expires_at: '2026-09-28T12:00:00Z', poll_interval_ms: 1000,
}

describe('QrLoginPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    api.create.mockResolvedValue({ success: true, data: session })
    api.cancel.mockResolvedValue({ success: true, data: { session_id: 'sid-1', status: 'cancelled', expires_at: session.expires_at } })
  })
  afterEach(() => vi.useRealTimers())

  it('二维码URL仅携带session_id，不泄漏secret或确认码', async () => {
    const wrapper = mount(QrLoginPanel, { global: { stubs: { ASpin: true } } })
    await flushPromises()
    const value = wrapper.get('.qr-value').attributes('data-value')
    expect(value).toContain('/auth/qr-confirm?session_id=sid-1')
    expect(value).not.toContain('secret-1')
    expect(value).not.toContain('804211')
  })

  it('pending不兑换，approved后只兑换一次并完成认证', async () => {
    api.status
      .mockResolvedValueOnce({ success: true, data: { session_id: 'sid-1', status: 'pending', expires_at: session.expires_at } })
      .mockResolvedValueOnce({ success: true, data: { session_id: 'sid-1', status: 'approved', expires_at: session.expires_at } })
    api.exchange.mockResolvedValue({ success: true, data: { access_token: 'access', refresh_token: 'refresh', token_type: 'bearer', expires_in: 3600 } })
    api.complete.mockResolvedValue({ success: true, data: { id: 'u1' } })
    const wrapper = mount(QrLoginPanel, { global: { stubs: { ASpin: true } } })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)
    expect(api.exchange).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    expect(api.exchange).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('authenticated')).toHaveLength(1)
  })

  it('卸载后迟到状态不兑换并取消当前会话', async () => {
    let resolveStatus!: (value: unknown) => void
    api.status.mockReturnValue(new Promise((resolve) => { resolveStatus = resolve }))
    const wrapper = mount(QrLoginPanel, { global: { stubs: { ASpin: true } } })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)
    wrapper.unmount()
    resolveStatus({ success: true, data: { session_id: 'sid-1', status: 'approved', expires_at: session.expires_at } })
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledWith('sid-1', 'secret-1')
    expect(api.exchange).not.toHaveBeenCalled()
  })

  it('卸载后迟到创建结果会立即取消且不展示二维码', async () => {
    let resolveCreate!: (value: unknown) => void
    api.create.mockReturnValue(new Promise((resolve) => { resolveCreate = resolve }))
    const wrapper = mount(QrLoginPanel, { global: { stubs: { ASpin: true } } })
    await flushPromises()
    wrapper.unmount()
    resolveCreate({ success: true, data: session })
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledWith('sid-1', 'secret-1')
  })

  it('兑换期间卸载使store提交门禁失效且不发送成功事件', async () => {
    api.status.mockResolvedValue({ success: true, data: { session_id: 'sid-1', status: 'approved', expires_at: session.expires_at } })
    api.exchange.mockResolvedValue({ success: true, data: { access_token: 'access', refresh_token: 'refresh', token_type: 'bearer', expires_in: 3600 } })
    let resolveComplete!: (value: unknown) => void
    let isCurrent!: () => boolean
    api.complete.mockImplementation((_tokens, guard) => {
      isCurrent = guard
      return new Promise((resolve) => { resolveComplete = resolve })
    })
    const wrapper = mount(QrLoginPanel, { global: { stubs: { ASpin: true } } })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    wrapper.unmount()
    expect(isCurrent()).toBe(false)
    resolveComplete({ success: false, error: '扫码登录会话已失效' })
    await flushPromises()
    expect(wrapper.emitted('authenticated')).toBeUndefined()
  })
})
