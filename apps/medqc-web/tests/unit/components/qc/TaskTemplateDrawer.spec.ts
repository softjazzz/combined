import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskTemplates: vi.fn(),
  getTaskRuleSets: vi.fn(),
  createTaskTemplate: vi.fn(),
  updateTaskTemplate: vi.fn(),
  deleteTaskTemplate: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirm: vi.fn(),
}))
const authState = vi.hoisted(() => ({ user: { id: 'u-1' } as { id: string } | null }))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/api/tasks', () => ({
  getTaskTemplates: mocks.getTaskTemplates,
  getTaskRuleSets: mocks.getTaskRuleSets,
  createTaskTemplate: mocks.createTaskTemplate,
  updateTaskTemplate: mocks.updateTaskTemplate,
  deleteTaskTemplate: mocks.deleteTaskTemplate,
}))
vi.mock('ant-design-vue', () => ({
  Modal: { confirm: mocks.confirm },
  message: mocks.message,
}))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return { DeleteOutlined: icon, EditOutlined: icon, PlusOutlined: icon }
})

import TaskTemplateDrawer from '@/components/qc/TaskTemplateDrawer.vue'
import type { TaskTemplate, TaskTemplateConfig } from '@/api/tasks'

const config: TaskTemplateConfig = {
  scene: 'final',
  rule_set_key: 'final-rules',
  date_range: { start: '2026-09-01', end: '2026-09-20' },
  department_filter: ['内科'],
  sampling_method: 'count',
  sampling_config: { total: 20, by_department: true },
  assign_method: 'by_ratio',
  assignee_config: {},
}

const template: TaskTemplate = {
  id: 'tpl-1', name: '常用模板', config, usable: true, unavailable_reason: null,
  version: 1, created_at: '2026-09-27T00:00:00', updated_at: '2026-09-27T00:00:00',
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return shallowMount(TaskTemplateDrawer, {
    props: { open: true, ...props },
    global: {
      stubs: {
        'a-alert': { props: ['message'], template: '<div><span>{{ message }}</span><slot name="action" /></div>' },
        'a-button': { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'a-checkbox': true,
        'a-date-picker': true,
        'a-drawer': { template: '<div><slot /></div>' },
        'a-empty': true,
        'a-form': { template: '<form><slot /></form>' },
        'a-form-item': { template: '<div><slot /></div>' },
        'a-input': true,
        'a-input-number': true,
        'a-radio': { template: '<label><slot /></label>' },
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-range-picker': true,
        'a-select': true,
        'a-spin': true,
        'a-tag': { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('TaskTemplateDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.user = { id: 'u-1' }
    mocks.getTaskTemplates.mockResolvedValue({
      success: true, data: { items: [template], max_templates: 20 },
    })
    mocks.getTaskRuleSets.mockResolvedValue({
      success: true,
      data: { items: [{ rule_set_key: 'final-rules', rule_set_name: '终末规则', rule_set_version: 'v1', scope: 'final' }] },
    })
    mocks.createTaskTemplate.mockResolvedValue({ success: true, data: template })
    mocks.updateTaskTemplate.mockResolvedValue({ success: true, data: { ...template, version: 2 } })
    mocks.deleteTaskTemplate.mockResolvedValue({ success: true, data: { id: 'tpl-1', deleted: true } })
  })

  it('仅列出当前账号模板并显式套用可用配置', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    expect(mocks.getTaskTemplates).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('常用模板')

    ;(wrapper.vm as unknown as { applyTemplate: (item: TaskTemplate) => void }).applyTemplate(template)
    expect(wrapper.emitted('apply')?.[0]?.[0]).toEqual(config)
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false])
  })

  it('损坏模板不可套用，但可进入显式修复编辑', async () => {
    const damaged = { ...template, config: null, usable: false, unavailable_reason: '配置损坏' }
    mocks.getTaskTemplates.mockResolvedValue({
      success: true, data: { items: [damaged], max_templates: 20 },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      applyTemplate: (item: TaskTemplate) => void
      startEdit: (item: TaskTemplate) => void
      editorOpen: boolean
    }
    vm.applyTemplate(damaged)
    expect(wrapper.emitted('apply')).toBeUndefined()
    vm.startEdit(damaged)
    expect(vm.editorOpen).toBe(true)
  })

  it('seed配置可保存为新模板且请求不含动态任务字段', async () => {
    const wrapper = mountDrawer({ seedConfig: config })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      editor: { name: string }
      saveTemplate: () => Promise<void>
    }
    vm.editor.name = '  新模板  '
    await vm.saveTemplate()
    expect(mocks.createTaskTemplate).toHaveBeenCalledWith({ name: '新模板', config })
    const request = mocks.createTaskTemplate.mock.calls[0][0]
    expect(request.config).not.toHaveProperty('task_name')
    expect(request.config).not.toHaveProperty('deadline')
    expect(request.config).not.toHaveProperty('record_refs')
  })

  it('抽屉关闭后晚到旧请求不能写回模板', async () => {
    const pending = deferred<{ success: boolean; data: { items: TaskTemplate[]; max_templates: number } }>()
    mocks.getTaskTemplates.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    await wrapper.setProps({ open: false })
    pending.resolve({ success: true, data: { items: [template], max_templates: 20 } })
    await flushPromises()
    const vm = wrapper.vm as unknown as { templates: TaskTemplate[] }
    expect(vm.templates).toEqual([])
  })
})
