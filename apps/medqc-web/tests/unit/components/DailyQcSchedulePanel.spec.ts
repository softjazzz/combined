import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, type PropType } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DailyQcSchedulePanel from '@/views/workstation-v4/components/system-config/DailyQcSchedulePanel.vue'
import type { DailyQcDefinition, DailyQcPlan } from '@/services/dailyQcScheduleService'

const { service, auth } = vi.hoisted(() => ({
  service: { list: vi.fn(), options: vi.fn(), save: vi.fn(), remove: vi.fn(), history: vi.fn() },
  auth: { userRoles: ['sync_admin'] },
}))
vi.mock('@/services/dailyQcScheduleService', () => ({ dailyQcScheduleService: service }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('ant-design-vue', () => ({ message: { success: vi.fn() } }))
const Slot = defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) })
const Button = defineComponent({ props: { disabled: Boolean }, setup: (props, { slots }) => () => h('button', { disabled: props.disabled }, slots.default?.()) })
const Select = defineComponent({
  props: { value: { type: String, default: '' }, options: { type: Array as PropType<Array<{ value: string; label: string }>>, default: () => [] } },
  emits: ['update:value', 'change'],
  setup: (props, { emit }) => () => h('select', { value: props.value, onChange: (event: Event) => {
    const value = (event.target as HTMLSelectElement).value
    emit('update:value', value); emit('change', value)
  } }, props.options.map(item => h('option', { value: item.value }, item.label))),
})
const Input = defineComponent({
  props: { value: { type: String, default: '' } }, emits: ['update:value'],
  setup: (props, { emit }) => () => h('input', { value: props.value, onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value) }),
})
const InputNumber = defineComponent({
  props: { value: { type: Number as PropType<number | null>, default: null } },
  emits: ['update:value'],
  setup: (props, { emit }) => () =>
    h('input', {
      type: 'number',
      value: props.value ?? '',
      onInput: (event: Event) => {
        const raw = (event.target as HTMLInputElement).value
        emit('update:value', raw === '' ? null : Number(raw))
      },
    }),
})
const Modal = defineComponent({
  props: { open: Boolean, okButtonProps: { type: Object, default: () => ({}) } }, emits: ['ok', 'cancel'],
  setup: (props, { slots, emit }) => () => props.open ? h('div', { 'data-testid': 'editor' }, [slots.default?.(), h('button', { 'data-testid': 'save', disabled: props.okButtonProps.disabled, onClick: () => emit('ok') }, '保存')]) : null,
})
const Alert = defineComponent({ props: { message: { type: String, default: '' }, description: { type: String, default: '' } }, setup: props => () => h('div', { role: 'alert' }, `${props.message} ${props.description}`) })

function plan(id = 'synthetic-plan'): DailyQcPlan {
  return { id, revision: 1, name: '已有计划', enabled: false, time_of_day: '02:00', timezone: 'Asia/Shanghai',
    institute_id: 'A', scope: 'final', department: '', date_field: 'discharge', lookback_days: 1,
    end_offset_days: 1, rule_set_key: 'luxian_0609_qc_v1', rule_ids: [], max_records: 200,
    next_run_at: '2026-11-03T18:00:00Z', last_status: 'skipped_overlap', last_job_id: null }
}
async function render() {
  const wrapper = mount(DailyQcSchedulePanel, { global: { stubs: {
    'a-space': Slot, 'a-tag': Slot, 'a-form': Slot, 'a-form-item': Slot, 'a-input-number': InputNumber,
    'a-button': Button, 'a-modal': Modal, 'a-select': Select, 'a-input': Input, 'a-switch': true,
    'a-alert': Alert, 'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
    'a-empty': { props: ['description'], template: '<p>{{ description }}</p>' },
  } } })
  await flushPromises()
  return wrapper
}
beforeEach(() => {
  vi.clearAllMocks()
  auth.userRoles = ['sync_admin']
  service.list.mockResolvedValue({ items: [], scheduler_enabled: false, local_process_active: false })
  service.options.mockResolvedValue({ institutes: ['A'], departments: ['ICU'], rule_sets: [{ key: 'luxian_0609_qc_v1', name: '正式规则', scope: 'all' }] })
  service.save.mockResolvedValue(plan())
  service.remove.mockResolvedValue({ id: 'synthetic-plan', deleted: true })
  service.history.mockResolvedValue([])
})

describe('每日定时质控配置', () => {
  it('默认关闭，选项来自接口，保存不触发质控', async () => {
    const wrapper = await render()
    expect(wrapper.text()).toContain('后台自动触发未启用')
    await wrapper.findAll('button').find(item => item.text() === '新增计划')?.trigger('click')
    await flushPromises()
    await wrapper.get('input[data-testid="schedule-name"]').setValue('每日终末')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    const saved = service.save.mock.calls[0][0] as DailyQcDefinition
    expect(saved).toMatchObject({ name: '每日终末', enabled: false, institute_id: 'A', end_offset_days: 1, lookback_days: 1 })
    expect(service.options).toHaveBeenCalledWith('A', 'final')
    expect(Object.keys(service)).not.toContain('run')
    wrapper.unmount()
  })

  it('编辑携带版本，失败不把页面已有计划清空', async () => {
    const item = plan()
    service.list.mockResolvedValue({ items: [item], scheduler_enabled: false, local_process_active: false })
    const wrapper = await render()
    expect(wrapper.text()).toContain('上一轮未结束，已跳过')
    await wrapper.findAll('button').find(button => button.text() === '编辑／启停')?.trigger('click')
    await flushPromises()
    service.save.mockRejectedValueOnce(new Error('conflict'))
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(service.save.mock.calls[0][1]).toEqual(item)
    expect(wrapper.text()).toContain('保存失败')
    expect(wrapper.find('[data-testid="schedule-synthetic-plan"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('目录迟到响应不能覆盖刚选择的机构', async () => {
    service.options.mockResolvedValue({ institutes: ['A', 'B'], departments: [], rule_sets: [] })
    const wrapper = await render()
    await wrapper.findAll('button').find(item => item.text() === '新增计划')?.trigger('click')
    await flushPromises()
    let resolveFirst: ((value: { institutes: string[]; departments: string[]; rule_sets: [] }) => void) | undefined
    service.options.mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
    await wrapper.findAll('select')[1].setValue('A')
    await wrapper.findAll('select')[1].setValue('B')
    await flushPromises()
    resolveFirst?.({ institutes: ['A', 'B'], departments: ['旧机构科室'], rule_sets: [] })
    await flushPromises()
    expect(wrapper.findAll('select')[1].element.value).toBe('B')
    expect(wrapper.text()).not.toContain('旧机构科室')
    wrapper.unmount()
  })

  it('读取失败明确提示，不能伪装成没有计划', async () => {
    service.list.mockRejectedValueOnce(new Error('migration unavailable'))
    const wrapper = await render()
    expect(wrapper.text()).toContain('064迁移')
    expect(wrapper.text()).not.toContain('暂无每日质控计划')
    expect(wrapper.findAll('button').find(item => item.text() === '新增计划')?.element.disabled).toBe(true)
    wrapper.unmount()
  })

  it('非管理账号不读取计划且不能创建', async () => {
    auth.userRoles = ['doctor']
    const wrapper = await render()
    expect(service.list).not.toHaveBeenCalled()
    expect(wrapper.findAll('button').find(item => item.text() === '新增计划')?.element.disabled).toBe(true)
    wrapper.unmount()
  })

  it('横幅准确区分 scheduler_enabled 与 local_process_active 状态', async () => {
    service.list.mockResolvedValueOnce({ items: [], scheduler_enabled: true, local_process_active: false })
    const wrapper = await render()
    expect(wrapper.text()).toContain('当前进程调度器未运行')
    wrapper.unmount()

    service.list.mockResolvedValueOnce({ items: [], scheduler_enabled: true, local_process_active: true })
    const activeWrapper = await render()
    expect(activeWrapper.text()).toContain('当前进程调度器运行中')
    activeWrapper.unmount()
  })

  it('保存前裁剪计划名称、拦截清空数字框并区分 422 与 409 错误', async () => {
    const wrapper = await render()
    await wrapper.findAll('button').find(item => item.text() === '新增计划')?.trigger('click')
    await flushPromises()
    await wrapper.get('input[data-testid="schedule-name"]').setValue('  每日终末  ')
    const numberInputs = wrapper.findAll('input[type="number"]')
    await numberInputs[0].setValue('')
    expect(wrapper.get('[data-testid="save"]').attributes('disabled')).toBeDefined()
    await numberInputs[0].setValue('1')
    expect(wrapper.get('[data-testid="save"]').attributes('disabled')).toBeUndefined()

    service.save.mockRejectedValueOnce({ isAxiosError: true, response: { status: 422, data: { detail: '所选科室不在当前机构和场景中' } } })
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('参数校验未通过')
    expect(wrapper.text()).toContain('所选科室不在当前机构和场景中')
    expect((service.save.mock.calls[0][0] as DailyQcDefinition).name).toBe('每日终末')

    service.save.mockRejectedValueOnce({ isAxiosError: true, response: { status: 409, data: { detail: '计划已变化' } } })
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('版本或上限冲突')
    wrapper.unmount()
  })

  it('点击删除需二次确认后调用 remove 接口并刷新列表', async () => {
    const item = plan()
    service.list
      .mockResolvedValueOnce({ items: [item], scheduler_enabled: true, local_process_active: true })
      .mockResolvedValueOnce({ items: [], scheduler_enabled: true, local_process_active: true })
    const wrapper = await render()
    await wrapper.get(`[data-testid="delete-schedule-${item.id}"]`).trigger('click')
    await flushPromises()
    expect(service.remove).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('确定删除计划')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(service.remove).toHaveBeenCalledWith(item.id)
    expect(wrapper.find(`[data-testid="schedule-${item.id}"]`).exists()).toBe(false)
    wrapper.unmount()
  })
})
