import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, type PropType } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LLMApiConfig from '@/components/LLMApiConfig.vue'

const { service, auth, reload } = vi.hoisted(() => ({
  service: {
    getDefaultSummary: vi.fn(), getProviders: vi.fn(), getModelsByProvider: vi.fn(),
    saveConfig: vi.fn(), testConfig: vi.fn(), addCustomModel: vi.fn(),
    deleteCustomModel: vi.fn(), resetDefaultSummary: vi.fn(), getLocalModelOptions: vi.fn(),
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
const Segmented = defineComponent({
  props: { value: String, options: { type: Array as PropType<Array<{ value: string; label: string }>>, default: () => [] }, disabled: Boolean },
  emits: ['change'],
  setup: (props, { emit }) => () => h('div', props.options.map((option) => h('button', {
    disabled: props.disabled, 'aria-pressed': props.value === option.value,
    onClick: () => emit('change', option.value),
  }, option.label))),
})
const Input = defineComponent({
  props: { value: String, disabled: Boolean }, emits: ['update:value'],
  setup: (props, { emit }) => () => h('input', { value: props.value, disabled: props.disabled,
    onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value) }),
})

async function render() {
  const wrapper = mount(LLMApiConfig, { global: { stubs: {
    LLMEndpointSettings: true, 'a-select': Select, 'a-select-option': { props: ['value'], template: '<option :value="value"><slot /></option>' },
    'a-alert': Alert, 'a-button': Button, 'a-tag': Slot, 'a-space-compact': Slot,
    'a-segmented': Segmented, 'a-slider': true, 'a-input': Input, 'a-input-number': true,
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
  service.getLocalModelOptions.mockResolvedValue([
    { provider_code: 'strata', provider_name: '本地 Strata', enabled: true, models: [
      { model_code: 'Local/CaseModel', model_name: 'Local/CaseModel', configuration_ready: true, unavailable_reason: '' },
      { model_code: 'Local/OtherModel', model_name: 'Local/OtherModel', configuration_ready: true, unavailable_reason: '' },
    ] },
    { provider_code: 'ollama', provider_name: '内部 Ollama', enabled: true, models: [
      { model_code: 'Local/Ollama', model_name: 'Local/Ollama', configuration_ready: true, unavailable_reason: '' },
    ] },
  ])
  service.getModelsByProvider.mockImplementation(async (provider: string) => [{
    model_code: provider === 'strata' ? 'Local/CaseModel' : 'cloud-model',
    model_name: provider === 'strata' ? 'Local/CaseModel' : 'cloud-model',
  }])
  service.saveConfig.mockResolvedValue({ id: 'synthetic' })
  service.addCustomModel.mockResolvedValue(undefined)
  service.deleteCustomModel.mockResolvedValue(undefined)
  reload.mockResolvedValue({ ok: true })
})

describe('后台云端与Strata选择', () => {
  it('用途默认继承，单独选型进入保存载荷且不测试模型', async () => {
    const wrapper = await render()
    expect(wrapper.findAll('[data-testid^="task-role-provider-"]').length).toBe(3)
    expect(wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-fact_extraction"]').element.value).toBe('inherit')
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-fact_extraction"]').setValue('alibaba')
    await flushPromises()
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-model-fact_extraction"]').setValue('cloud-model')
    await flushPromises()
    await wrapper.findAll('button').find((item) => item.text() === '保存配置')?.trigger('click')
    await flushPromises()
    expect(service.saveConfig).toHaveBeenCalledWith(expect.objectContaining({ custom_parameters: expect.objectContaining({
      task_role_models: { fact_extraction: { provider_code: 'alibaba', model_code: 'cloud-model' },
        judgment_analysis: null, specialty_verification: null },
    }) }))
    expect(service.testConfig).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('已有用途回显，重新继承后保存null', async () => {
    service.getDefaultSummary.mockResolvedValue({ provider_code: 'alibaba', model_code: 'cloud-model',
      custom_parameters: { task_role_models: { fact_extraction: null, judgment_analysis: null,
        specialty_verification: { provider_code: 'strata', model_code: 'Local/OtherModel' } } },
      readonly: false, source: 'database+env' })
    const wrapper = await render()
    expect(wrapper.get<HTMLSelectElement>('[data-testid="task-role-model-specialty_verification"]').element.value).toBe('Local/OtherModel')
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-specialty_verification"]').setValue('inherit')
    await flushPromises()
    await wrapper.findAll('button').find((item) => item.text() === '保存配置')?.trigger('click')
    await flushPromises()
    expect(service.saveConfig.mock.calls[0][0].custom_parameters.task_role_models.specialty_verification).toBeNull()
    wrapper.unmount()
  })

  it('用途未选模型不能保存，目录失败不修改其他用途', async () => {
    const wrapper = await render()
    service.getModelsByProvider.mockRejectedValueOnce(new Error('synthetic'))
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-fact_extraction"]').setValue('alibaba')
    await flushPromises()
    expect(wrapper.text()).toContain('模型目录读取失败')
    expect(wrapper.findAll('button').find((item) => item.text() === '保存配置')?.element.disabled).toBe(true)
    expect(wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-judgment_analysis"]').element.value).toBe('inherit')
    expect(service.saveConfig).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('用途目录迟到响应不改变已选本地模型', async () => {
    const wrapper = await render()
    let finish: ((items: Array<{ model_code: string; model_name: string }>) => void) | undefined
    service.getModelsByProvider.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-fact_extraction"]').setValue('alibaba')
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-provider-fact_extraction"]').setValue('strata')
    await flushPromises()
    await wrapper.get<HTMLSelectElement>('[data-testid="task-role-model-fact_extraction"]').setValue('Local/OtherModel')
    finish?.([{ model_code: 'late-cloud', model_name: 'Late Cloud' }])
    await flushPromises()
    expect(wrapper.get<HTMLSelectElement>('[data-testid="task-role-model-fact_extraction"]').element.value).toBe('Local/OtherModel')
    wrapper.unmount()
  })

  it('保留百炼/Ollama并显示Strata部署模型和本地提示', async () => {
    const wrapper = await render()
    expect(wrapper.findAll('select')[0].text()).toContain('阿里云百炼')
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
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
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    await wrapper.findAll('select')[1].setValue('Local/OtherModel')
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text() === '保存配置')
    expect(button).toBeDefined()
    await button?.trigger('click')
    await flushPromises()
    expect(service.saveConfig).toHaveBeenCalledWith(expect.objectContaining({ provider_code: 'strata', model_code: 'Local/OtherModel' }))
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
    await wrapper.findAll('select')[0].setValue('alibaba')
    await flushPromises()
    expect(wrapper.findAll('button').find((item) => item.text() === '保存配置')?.element.disabled).toBe(true)
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    finish?.([{ model_code: 'Local/LateModel', model_name: 'Local/LateModel' }])
    await flushPromises()
    expect(wrapper.findAll('select')[1].element.value).toBe('Local/CaseModel')
    expect(wrapper.text()).not.toContain('Local/LateModel')
    wrapper.unmount()
  })

  it('未配置本地服务仍有明确入口，可登记多个模型但不能测试或启用', async () => {
    const roster = [{ provider_code: 'strata', provider_name: '本地 Strata', enabled: false,
      models: [] as Array<{ model_code: string; model_name: string; configuration_ready: boolean; unavailable_reason: string; is_custom: boolean }> }]
    service.getProviders.mockResolvedValue([{ provider_code: 'alibaba', provider_name: '阿里云百炼' }])
    service.getLocalModelOptions.mockResolvedValue(roster)
    service.addCustomModel.mockImplementation(async (_provider: string, code: string) => {
      roster[0].models.push({ model_code: code, model_name: code, is_custom: true,
        configuration_ready: false, unavailable_reason: 'provider_not_enabled' })
    })
    const wrapper = await render()
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('尚未启用')
    for (const code of ['Local/Qwen-FLASH', 'Local/Qwen-35B']) {
      await wrapper.get('input').setValue(code)
      await wrapper.findAll('button').find((button) => button.text() === '添加')?.trigger('click')
      await flushPromises()
      expect(wrapper.findAll('select')[1].element.value).toBe(code)
    }
    expect(wrapper.findAll('select')[1].findAll('option')).toHaveLength(2)
    expect(wrapper.findAll('button').find((button) => button.text() === '测试连接')?.element.disabled).toBe(true)
    expect(wrapper.findAll('button').find((button) => button.text() === '保存配置')?.element.disabled).toBe(true)
    expect(service.saveConfig).not.toHaveBeenCalled()
    expect(service.testConfig).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('仅所选模型缺配置时禁止启用，切换到已配置模型可保存', async () => {
    service.getLocalModelOptions.mockResolvedValue([{ provider_code: 'strata', provider_name: '本地 Strata', enabled: true, models: [
      { model_code: 'Local/Ready', model_name: 'Local/Ready', configuration_ready: true, unavailable_reason: '' },
      { model_code: 'Local/Pending', model_name: 'Local/Pending', configuration_ready: false, unavailable_reason: 'model_configuration_incomplete' },
    ] }])
    const wrapper = await render()
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    await wrapper.findAll('select')[1].setValue('Local/Pending')
    expect(wrapper.text()).toContain('运行配置尚未齐备')
    expect(wrapper.findAll('button').find((button) => button.text() === '保存配置')?.element.disabled).toBe(true)
    await wrapper.findAll('select')[1].setValue('Local/Ready')
    expect(wrapper.findAll('button').find((button) => button.text() === '保存配置')?.element.disabled).toBe(false)
    wrapper.unmount()
  })

  it('读取本地目录失败不冒充空目录，也不阻塞现有云端模型', async () => {
    service.getLocalModelOptions.mockRejectedValue(new Error('synthetic unavailable'))
    const wrapper = await render()
    expect(wrapper.findAll('select')[1].element.value).toBe('cloud-model')
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('本地模型选项读取失败')
    expect(wrapper.findAll('button').find((button) => button.text() === '保存配置')?.element.disabled).toBe(true)
    expect(service.saveConfig).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('本地模型添加的迟到响应不会清空已切回的云端模型', async () => {
    const wrapper = await render()
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    let finish: (() => void) | undefined
    service.addCustomModel.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve }))
    await wrapper.get('input').setValue('Local/NewModel')
    await wrapper.findAll('button').find((button) => button.text() === '添加')?.trigger('click')
    await wrapper.get('button[aria-pressed="false"]').trigger('click')
    await flushPromises()
    finish?.()
    await flushPromises()
    expect(wrapper.findAll('select')[1].element.value).toBe('cloud-model')
    expect(service.saveConfig).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
