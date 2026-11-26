import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, expect, it, vi } from 'vitest'
import Panel from '@/components/LLMEndpointSettings.vue'

const { service, auth } = vi.hoisted(() => ({ service: { load: vi.fn(), save: vi.fn() }, auth: { userRoles: ['sync_admin'] } }))
vi.mock('@/services/llmEndpointService', () => ({ llmEndpointService: service }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('ant-design-vue', () => ({ message: { success: vi.fn() } }))
const Slot = defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) })
const Drawer = defineComponent({ name: 'EndpointDrawer', props: { open: Boolean }, emits: ['update:open', 'afterOpenChange'], setup: (p, { slots }) => () => p.open ? h('aside', slots.default?.()) : null })
const Button = defineComponent({ props: { disabled: Boolean }, setup: (p, { slots }) => () => h('button', { disabled: p.disabled }, slots.default?.()) })
const Input = defineComponent({ props: { value: String, disabled: Boolean }, emits: ['update:value'], setup: (p, { emit }) => () => h('input', { value: p.value, disabled: p.disabled, onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value) }) })
const Switch = defineComponent({ props: { checked: Boolean, disabled: Boolean }, emits: ['update:checked'], setup: (p, { emit }) => () => h('input', { type: 'checkbox', checked: p.checked, disabled: p.disabled, onChange: (e: Event) => emit('update:checked', (e.target as HTMLInputElement).checked) }) })
const Alert = defineComponent({ props: { message: String }, setup: p => () => h('div', p.message) })
const view = () => ({ version: 0, editable: true, audit: [], providers: [{ provider_code: 'ollama', name: '本地服务', source: 'deployment', endpoint: 'http://old.test/v1', enabled: true, key_configured: true }] })
function render() { return mount(Panel, { global: { stubs: { 'a-drawer': Drawer, 'a-button': Button, 'a-form': Slot, 'a-form-item': Slot, 'a-input': Input, 'a-input-password': Input, 'a-switch': Switch, 'a-checkbox': Switch, 'a-select': true, 'a-alert': Alert } } }) }
beforeEach(() => { vi.clearAllMocks(); auth.userRoles = ['sync_admin']; service.load.mockResolvedValue(view()); service.save.mockResolvedValue({ ...view(), version: 1 }) })

it('普通管理员没有入口，超级管理员打开抽屉才读取且不保存', async () => {
  auth.userRoles = ['admin']
  const forbidden = render()
  expect(forbidden.find('[data-testid="endpoint-open"]').exists()).toBe(false)
  forbidden.unmount()
  auth.userRoles = ['super_admin']
  const wrapper = render()
  expect(service.load).not.toHaveBeenCalled()
  await wrapper.get('[data-testid="endpoint-open"]').trigger('click'); await flushPromises()
  expect(service.load).toHaveBeenCalledTimes(1)
  expect(wrapper.text()).toContain('已配置，密钥不回显')
  expect(service.save).not.toHaveBeenCalled()
})

it('保存密钥不回显，关闭抽屉丢弃输入', async () => {
  const wrapper = render()
  await wrapper.get('[data-testid="endpoint-open"]').trigger('click'); await flushPromises()
  await wrapper.findAll('input[type=checkbox]')[0].setValue(false)
  const inputs = wrapper.findAll('input:not([type=checkbox])')
  await inputs[0].setValue('http://new.test/v1')
  await inputs[1].setValue('synthetic-secret')
  await wrapper.get('[data-testid="endpoint-save"]').trigger('click'); await flushPromises()
  expect(service.save).toHaveBeenCalledWith('ollama', expect.objectContaining({ version: 0, endpoint: 'http://new.test/v1', api_key: 'synthetic-secret', use_deployment: false }))
  expect(wrapper.findAll('input').some(input => input.element.value === 'synthetic-secret')).toBe(false)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  await wrapper.findComponent(Drawer).vm.$emit('afterOpenChange', false)
  expect(wrapper.findAllComponents(Input)).toHaveLength(0)
})

it('冲突不自动重试或覆盖，提示重新读取', async () => {
  service.save.mockRejectedValue(new Error('配置已变化，请重新读取后确认。'))
  const wrapper = render()
  await wrapper.get('[data-testid="endpoint-open"]').trigger('click'); await flushPromises()
  await wrapper.get('[data-testid="endpoint-save"]').trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('配置已变化')
  expect(wrapper.get<HTMLButtonElement>('[data-testid="endpoint-save"]').element.disabled).toBe(true)
  expect(service.save).toHaveBeenCalledTimes(1)
})

it('Gateway配置明确不可编辑', async () => {
  service.load.mockResolvedValue({ ...view(), editable: false })
  const wrapper = render()
  await wrapper.get('[data-testid="endpoint-open"]').trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('受控 Gateway')
  expect(wrapper.get<HTMLButtonElement>('[data-testid="endpoint-save"]').element.disabled).toBe(true)
})

it('展示未放行主机告警提示，并能正确映射 422 细分错误码为可读中文提示', async () => {
  service.load.mockResolvedValue({
    ...view(),
    providers: [{ ...view().providers[0], endpoint: 'http://192.168.1.50:11434/v1', host_allowed: false }],
  })
  const wrapper = render()
  await wrapper.get('[data-testid="endpoint-open"]').trigger('click'); await flushPromises()
  expect(wrapper.find('[data-testid="endpoint-host-warning"]').exists()).toBe(true)
  expect(wrapper.text()).toContain('OUTBOUND_ALLOWLIST')

  const actualService = await vi.importActual<typeof import('@/services/llmEndpointService')>(
    '@/services/llmEndpointService',
  )
  expect(
    actualService.mapEndpointErrorMessage(422, 'llm_endpoint_key_reconfirmation_required'),
  ).toContain('重新输入新地址对应的 API 密钥')
  expect(actualService.mapEndpointErrorMessage(422, 'llm_endpoint_host_not_allowed')).toContain(
    'OUTBOUND_ALLOWLIST',
  )
  expect(
    actualService.mapEndpointErrorMessage(422, 'llm_endpoint_configuration_invalid'),
  ).toContain('http(s)://')
  expect(actualService.mapEndpointErrorMessage(422, 'unknown_code')).toBe(
    '请检查服务地址、启用状态和密钥操作。',
  )
})
