import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TaskRecordDocumentDrawer from '@/components/qc/TaskRecordDocumentDrawer.vue'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  render: vi.fn(),
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  getEditableMedicalRecordDocuments: mocks.list,
  getEditableMedicalRecordDocument: mocks.render,
}))

const DrawerStub = defineComponent({
  name: 'ADrawer',
  props: { open: Boolean },
  setup(props, { slots }) {
    return () => props.open ? h('section', slots.default?.()) : null
  },
})

const document = {
  key: 'course::D1',
  title: '首次病程记录',
  document_type: 'course',
  record_time: '2026-09-25',
  content: '已保存正文',
}

function taskRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 'record-1', task_id: 'task-1', record_id: 'record-1',
    institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', status: 'in_progress',
    ...overrides,
  }
}

function mountDrawer(record = taskRecord()) {
  return mount(TaskRecordDocumentDrawer, {
    props: { open: true, taskId: 'task-1', record },
    global: {
      stubs: {
        'a-drawer': DrawerStub,
        'a-spin': true,
        'a-alert': { template: '<div role="alert">{{ $attrs.message }}<slot name="action" /></div>' },
        'a-empty': { template: '<div>{{ $attrs.description }}</div>' },
        'a-button': { template: '<button><slot /></button>' },
        ReadonlyMedicalDocumentContent: {
          props: ['document'],
          template: '<article data-testid="document-body">{{ document.content }}</article>',
        },
      },
    },
  })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('TaskRecordDocumentDrawer', () => {
  beforeEach(() => {
    mocks.list.mockReset()
    mocks.render.mockReset()
    mocks.list.mockResolvedValue({ success: true, data: { documents: [document] } })
    mocks.render.mockResolvedValue({ success: true, data: document })
  })

  it('仅用任务病历三坐标读取已保存目录与正文', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith('V1', {
      task_id: 'task-1', task_record_id: 'record-1', institute_id: 'H1',
      patient_id: 'P1', visit_id: 'V1', source_view: 'saved', view: 'summary',
    })
    expect(mocks.render).toHaveBeenCalledWith('V1', document, {
      task_id: 'task-1', task_record_id: 'record-1', institute_id: 'H1',
      patient_id: 'P1', visit_id: 'V1', source_view: 'saved',
    })
    expect(wrapper.get('[data-testid="document-body"]').text()).toBe('已保存正文')
  })

  it('旧单键病历拒绝发文书请求', async () => {
    const wrapper = mountDrawer(taskRecord({ record_id: 'V1', institute_id: null }))
    await flushPromises()
    expect(wrapper.text()).toContain('任务病历身份不完整')
    expect(mocks.list).not.toHaveBeenCalled()
  })

  it('任务切换后丢弃先前目录请求', async () => {
    const first = deferred<{ success: boolean; data: { documents: typeof document[] } }>()
    mocks.list.mockReturnValueOnce(first.promise)
    const wrapper = mountDrawer()
    await wrapper.setProps({ taskId: 'task-2', record: taskRecord({ id: 'record-2', task_id: 'task-2', record_id: 'record-2', visit_id: 'V2' }) })
    await flushPromises()
    first.resolve({ success: true, data: { documents: [{ ...document, title: '旧任务文书' }] } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('旧任务文书')
    expect(mocks.render).toHaveBeenCalledTimes(1)
    expect(mocks.render).toHaveBeenCalledWith('V2', document, expect.objectContaining({ task_id: 'task-2' }))
  })

  it('服务失败显示错误，不伪装为空文书', async () => {
    mocks.list.mockResolvedValueOnce({ success: false, message: '文书授权暂不可用' })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('文书授权暂不可用')
    expect(wrapper.text()).not.toContain('暂无已保存文书')
  })
})
