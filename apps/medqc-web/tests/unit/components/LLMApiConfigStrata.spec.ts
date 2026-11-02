import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, type PropType } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LLMApiConfig from '@/components/LLMApiConfig.vue'

const { service, auth, reload } = vi.hoisted(() => ({
  service: {
    getDefaultSummary: vi.fn(), getProviders: vi.fn(), getModelsByProvider: vi.fn(),
    saveConfig: vi.fn(), testConfig: vi.fn(), addCustomModel: vi.fn(),
    deleteCustomModel: vi.fn(), resetDefaultSummary: vi.fn(),
  },
  auth: { userRoles: ['sync_admin'] },
  reload: vi.fn(),
}))

vi.mock('@/services/llmConfigService', () => ({ llmConfigService: service }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/utils/auth-fetch', () => ({ authFetch: reload }))
vi.mock('ant-design-vue', () => ({ message: { success: vi.fn(), error: vi.fn() } }))

const Select = defineComponent({
  props: { value: { type: String, default: '' }, options: { type: Array as PropType<Array<{ value: string; label: string }>>, default: undefined }, disabled: Boolean }, emits: ['update:value', 'change'],
  setup(props, { emit, slots }) {
    return () => h('select', {
      value: props.value, disabled: props.disabled,
      onChange: (event: Event) => {
        const value = (event.target as HTMLSelectElement).value
        emit('update:value', value)
        emit('change', value)
      },
    }, props.options ? props.options.map((item: { value: string; label: string }) => h('option', { value: item.value }, item.label)) : slots.default?.())
  },
})
const Slot = defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) })
const Alert = defineComponent({ props: { message: { type: String, default: '' }, description: { type: String, default: '' } }, setup: (props) => () => h('div', `${props.message} ${props.description}`) })
const Button = defineComponent({ props: { disabled: Boolean }, setup: (props, { slots }) => () => h('button', { disabled: props.disabled }, slots.default?.()) })

async function render() {
  const wrapper = mount(LLMApiConfig, { global: { stubs: {
    'a-select': Select, 'a-select-option': { props: ['value'], template: '<option :value="value"><slot /></option>' },
    'a-alert': Alert, 'a-button': Button, 'a-tag': Slot, 'a-space-compact': Slot,
    'a-slider': true, 'a-input': true, 'a-input-number': true,
  } } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  auth.userRoles = ['sync_admin']
  service.getDefaultSummary.mockResolvedValue({ provider_code: 'alibaba', model_code: 'cloud-model',
    custom_parameters: {}, source: 'database+env', readonly: false })
  service.getProviders.mockResolvedValue([
    { provider_code: 'alibaba', provider_name: '阿里云百炼' },
    { provider_code: 'strata', provider_name: '本地 Strata' },
    { provider_code: 'ollama', provider_name: '内部 Ollama' },
  ])
  service.getModelsByProvider.mockImplementation(async (provider: string) => [{
    model_code: provider === 'strata' ? 'Local/CaseModel' : 'cloud-model',
    model_name: provider === 'strata' ? 'Local/CaseModel' : 'cloud-model',
  }])
  service.saveConfig.mockResolvedValue({ id: 'synthetic' })
  reload.mockResolvedValue({ ok: true })
})

describe('后台云端与Strata选择', () => {
  it('保留百炼/Ollama并显示Strata部署模型和本地提示', async () => {
    const wrapper = await render()
    expect(wrapper.findAll('select')[0].text()).toContain('阿里云百炼')
    expect(wrapper.findAll('select')[0].text()).toContain('内部 Ollama')
    await wrapper.findAll('select')[0].setValue('strata')
    await flushPromises()
    expect(wrapper.findAll('select')[1].element.value).toBe('Local/CaseModel')
    expect(wrapper.text()).toContain('不会自动切到云端')
    expect(wrapper.find('input[type="password"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('保存原样模型名并重载后端，不提交地址和密钥', async () => {
    const wrapper = await render()
    await wrapper.findAll('select')[0].setValue('strata')
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text() === '保存配置')
    expect(button).toBeDefined()
    await button?.trigger('click')
    await flushPromises()
    expect(service.saveConfig).toHaveBeenCalledWith(expect.objectContaining({ provider_code: 'strata', model_code: 'Local/CaseModel' }))
    expect(service.saveConfig.mock.calls[0][0]).not.toHaveProperty('custom_endpoint')
    expect(service.saveConfig.mock.calls[0][0]).not.toHaveProperty('api_key')
    expect(reload).toHaveBeenCalledWith('/api/v1/qc/sichuan/reload-config', expect.objectContaining({ method: 'POST' }))
    wrapper.unmount()
  })

  it('非管理账号不能编辑或保存模型配置', async () => {
    auth.userRoles = ['doctor']
    const wrapper = await render()
    expect(wrapper.findAll('select').every((item) => item.element.disabled)).toBe(true)
    expect(wrapper.findAll('button').find((item) => item.text() === '保存配置')?.element.disabled).toBe(true)
    expect(service.saveConfig).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('模型列表加载中不能保存，旧服务商迟到响应不会覆盖当前模型', async () => {
    const wrapper = await render()
    let finish: ((value: Array<{ model_code: string; model_name: string }>) => void) | undefined
    service.getModelsByProvider.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    await wrapper.findAll('select')[0].setValue('strata')
    await flushPromises()
    expect(wrapper.findAll('button').find((item) => item.text() === '保存配置')?.element.disabled).toBe(true)
    await wrapper.findAll('select')[0].setValue('alibaba')
    await flushPromises()
    finish?.([{ model_code: 'Local/LateModel', model_name: 'Local/LateModel' }])
    await flushPromises()
    expect(wrapper.findAll('select')[1].element.value).toBe('cloud-model')
    expect(wrapper.text()).not.toContain('Local/LateModel')
    wrapper.unmount()
  })
})
