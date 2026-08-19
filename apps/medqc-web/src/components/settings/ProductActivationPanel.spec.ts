import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProductActivationPanel from './ProductActivationPanel.vue'
import { activateProduct, getProductActivationStatus } from '@/api/productActivation'

vi.mock('@/api/productActivation', () => ({
  activateProduct: vi.fn(),
  getProductActivationStatus: vi.fn(),
}))

const statusApi = vi.mocked(getProductActivationStatus)
const activateApi = vi.mocked(activateProduct)

const stubs = {
  'a-alert': { props: ['message'], template: '<div>{{ message }}<slot /></div>' },
  'a-descriptions': { template: '<div><slot /></div>' },
  'a-descriptions-item': { props: ['label'], template: '<div>{{ label }}<slot /></div>' },
  'a-textarea': {
    props: ['value'],
    emits: ['update:value'],
    template: '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
  'a-button': {
    props: ['disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-space': { template: '<div><slot /></div>' },
}

function mountPanel() {
  return mount(ProductActivationPanel, { global: { stubs } })
}

describe('ProductActivationPanel', () => {
  beforeEach(() => {
    statusApi.mockResolvedValue({
      success: true,
      data: {
        status: 'missing',
        required: true,
      },
    })
    activateApi.mockResolvedValue({
      success: true,
      data: {
        status: 'active',
        required: true,
        customer: '演示医院',
        edition: 'customer',
        serial: 'DEMO-001',
        expires_at: '2027-08-19T00:00:00Z',
      },
    })
  })

  it('加载状态、激活成功后刷新状态并清空输入', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(statusApi).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('产品尚未激活')

    await wrapper.find('textarea').setValue('MQ1.example-code')
    const activateButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('激活产品'))
    expect(activateButton).toBeDefined()
    await activateButton!.trigger('click')
    await flushPromises()

    expect(activateApi).toHaveBeenCalledWith('MQ1.example-code')
    expect(wrapper.text()).toContain('产品已激活')
    expect(wrapper.find('textarea').element.value).toBe('')
    expect(wrapper.text()).toContain('演示医院')
  })

  it('激活接口失败时保留输入，便于重新粘贴或修正', async () => {
    activateApi.mockResolvedValueOnce({ success: false, message: '激活码无效或已过期' })
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('textarea').setValue('bad-code')
    const activateButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('激活产品'))
    await activateButton!.trigger('click')
    await flushPromises()

    expect(wrapper.find('textarea').element.value).toBe('bad-code')
    expect(wrapper.text()).toContain('产品尚未激活')
  })
})
