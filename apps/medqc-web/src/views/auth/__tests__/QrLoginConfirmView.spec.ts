import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(), get: vi.fn(), reject: vi.fn(),
  route: { query: { session_id: 'sid-1' } as Record<string, unknown> },
  auth: { user: { id: 'u1' }, userRoles: ['doctor'] },
}))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/api/qrLogin', () => ({
  confirmQrLogin: mocks.confirm,
  getQrLoginConfirmation: mocks.get,
  rejectQrLogin: mocks.reject,
}))
import QrLoginConfirmView from '@/views/auth/QrLoginConfirmView.vue'

const AInputStub = defineComponent({
  name: 'AInput',
  props: { value: String },
  emits: ['update:value'],
  setup(props, { emit, attrs }) {
    return () => h('input', {
      ...attrs,
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    })
  },
})
const AButtonStub = defineComponent({
  name: 'AButton',
  props: { type: String, disabled: Boolean },
  emits: ['click'],
  setup(props, { emit, slots }) {
    return () => h('button', {
      class: props.type === 'primary' ? 'ant-btn-primary' : '',
      disabled: props.disabled,
      onClick: () => emit('click'),
    }, slots.default?.())
  },
})

describe('QrLoginConfirmView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ success: true, data: {
      session_id: 'sid-1', status: 'pending', expires_at: '2026-09-28T12:00:00Z',
    } })
  })

  it('打开确认页只读取状态，不自动批准', async () => {
    mount(QrLoginConfirmView, { global: { stubs: { ASpin: true, AInput: true, AButton: true, AResult: true, AAlert: true } } })
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledWith('sid-1')
    expect(mocks.confirm).not.toHaveBeenCalled()
  })

  it('明确输入电脑码后才批准', async () => {
    mocks.confirm.mockResolvedValue({ success: true, data: {
      session_id: 'sid-1', status: 'approved', expires_at: '2026-09-28T12:00:00Z',
    } })
    const wrapper = mount(QrLoginConfirmView, {
      global: { stubs: { ASpin: true, AInput: AInputStub, AButton: AButtonStub, AResult: true, AAlert: true } },
    })
    await flushPromises()
    await wrapper.get('input').setValue('804211')
    await wrapper.get('.ant-btn-primary').trigger('click')
    await flushPromises()
    expect(mocks.confirm).toHaveBeenCalledWith('sid-1', '804211')
  })
})
