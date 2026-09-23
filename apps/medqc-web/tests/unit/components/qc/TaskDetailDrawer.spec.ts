import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { Select as ASelect, Table as ATable } from 'ant-design-vue'

const mocks = vi.hoisted(() => ({ getTaskDetail: vi.fn() }))

beforeAll(() => {
  const getComputedStyle = window.getComputedStyle.bind(window)
  vi.spyOn(window, 'getComputedStyle').mockImplementation((element) => getComputedStyle(element))
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
})

vi.mock('@/api/tasks', () => ({ getTaskDetail: mocks.getTaskDetail }))

import TaskDetailDrawer from '@/components/qc/TaskDetailDrawer.vue'

const DrawerStub = defineComponent({
  name: 'ADrawer',
  props: { open: Boolean, title: String },
  emits: ['close'],
  setup(props, { emit, slots }) {
    return () =>
      props.open
        ? h('section', { 'data-testid': 'drawer' }, [
            h('h2', props.title),
            h('button', { 'data-testid': 'close-drawer', onClick: () => emit('close') }, '关闭'),
            slots.default?.(),
          ])
        : null
  },
})

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

const InputStub = defineComponent({
  name: 'AInput',
  inheritAttrs: false,
  props: { value: { type: String, default: '' } },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    })
  },
})

const TableStub = defineComponent({
  name: 'ATable',
  props: {
    columns: { type: Array, default: () => [] },
    dataSource: { type: Array, default: () => [] },
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { 'data-testid': 'table-stub' },
        props.dataSource.flatMap((record) =>
          props.columns.map((column) => h('div', slots.bodyCell?.({ column, record }))),
        ),
      )
  },
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

function detailResponse(
  taskName = '任务甲',
  records: Array<Record<string, unknown>> = [],
  overrides: Record<string, unknown> = {},
) {
  return {
    success: true,
    data: {
      id: 'task-1',
      task_number: `NO-${taskName}`,
      task_name: taskName,
      task_type: 'one_time',
      status: 'in_progress',
      progress: 0,
      total_records: 8,
      completed_records: 2,
      creator_id: 'creator',
      creator_name: '质控员',
      scene: null,
      created_at: '2026-09-22T00:00:00Z',
      updated_at: '2026-09-22T00:00:00Z',
      records,
      ...overrides,
    },
  }
}

function record(overrides: Record<string, unknown> = {}) {
  return {
    id: 'association-1',
    task_id: 'task-1',
    record_id: 'record-1',
    assignee_id: 'user-1',
    assignee_name: '张医生',
    status: 'pending',
    score: null,
    defect_count: null,
    created_at: '2026-09-22T00:00:00Z',
    completed_at: null,
    error_message: null,
    ...overrides,
  }
}

function mountDrawer(
  props: { open?: boolean; taskId?: string | null; tab?: 'all' | 'received' } = {},
  options: { realTable?: boolean } = {},
) {
  return mount(TaskDetailDrawer, {
    props: {
      open: props.open ?? true,
      taskId: props.taskId ?? 'task-1',
      tab: props.tab ?? 'received',
    },
    global: {
      components: options.realTable ? { ASelect, ATable } : {},
      stubs: {
        'a-button': ButtonStub,
        'a-drawer': DrawerStub,
        'a-empty': { template: '<div data-testid="empty"><slot />{{ $attrs.description }}</div>' },
        'a-input': options.realTable ? InputStub : true,
        'a-select': options.realTable ? false : true,
        'a-skeleton': true,
        'a-table': options.realTable ? false : TableStub,
        'a-tag': { template: '<span><slot /></span>' },
        RotateCw: true,
      },
    },
  })
}

describe('TaskDetailDrawer', () => {
  beforeEach(() => {
    mocks.getTaskDetail.mockReset()
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务甲', [record()]))
  })

  it('按收到范围读取真实详情，并区分真实零值与缺失值', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse('任务甲', [
        record({ score: 0, defect_count: 0 }),
        record({ id: 'association-2', record_id: 'record-2', score: null, defect_count: null }),
      ]),
    )
    const wrapper = mountDrawer()
    await flushPromises()

    expect(mocks.getTaskDetail).toHaveBeenCalledWith('task-1', { tab: 'received' })
    expect(wrapper.text()).toContain('全任务口径')
    expect(wrapper.text()).toContain('单次任务')
    expect(wrapper.text()).toContain('创建时间')
    expect(wrapper.text()).toContain('我的病历')
    expect(wrapper.text()).toContain('0')
    expect(wrapper.text()).toContain('未记录')
    expect(wrapper.get('[data-testid="task-detail-record-count"]').text()).toBe('2 份')
  })

  it('真实空清单显示收到范围空态', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('空任务', []))
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.get('[data-testid="task-detail-record-empty"]').attributes('description')).toBe(
      '当前任务没有分配给我的病历',
    )
    expect(wrapper.find('[data-testid="task-detail-record-table"]').exists()).toBe(false)
  })

  it('请求失败保持错误并可在原范围重试恢复', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce({ success: false, message: '详情服务不可用' })
    const wrapper = mountDrawer({ tab: 'all' })
    await flushPromises()

    expect(wrapper.get('[data-testid="task-detail-error"]').text()).toContain('详情服务不可用')
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('恢复任务', [record()]))
    await wrapper.get('[data-testid="retry-task-detail"]').trigger('click')
    await flushPromises()

    expect(mocks.getTaskDetail).toHaveBeenLastCalledWith('task-1', { tab: 'all' })
    expect(wrapper.text()).toContain('恢复任务')
    expect(wrapper.find('[data-testid="task-detail-error"]').exists()).toBe(false)
  })

  it('切换任务后晚到旧响应不能覆盖新详情', async () => {
    const oldRequest = deferred<ReturnType<typeof detailResponse>>()
    const newRequest = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const wrapper = mountDrawer({ taskId: 'old-task' })

    await wrapper.setProps({ taskId: 'new-task' })
    newRequest.resolve(
      detailResponse('新任务', [record({ id: 'new-association' })], { id: 'new-task' }),
    )
    await flushPromises()
    oldRequest.resolve(
      detailResponse('旧任务', [record({ id: 'old-association' })], { id: 'old-task' }),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('新任务')
    expect(wrapper.text()).not.toContain('旧任务')
  })

  it('切换清单范围后晚到旧响应不能污染新范围', async () => {
    const allRequest = deferred<ReturnType<typeof detailResponse>>()
    const receivedRequest = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail
      .mockReturnValueOnce(allRequest.promise)
      .mockReturnValueOnce(receivedRequest.promise)
    const wrapper = mountDrawer({ tab: 'all' })

    await wrapper.setProps({ tab: 'received' })
    receivedRequest.resolve(
      detailResponse('我的范围任务', [record({ id: 'received-association' })]),
    )
    await flushPromises()
    allRequest.resolve(detailResponse('全部范围旧任务', [record({ id: 'all-association' })]))
    await flushPromises()

    expect(mocks.getTaskDetail).toHaveBeenNthCalledWith(1, 'task-1', { tab: 'all' })
    expect(mocks.getTaskDetail).toHaveBeenNthCalledWith(2, 'task-1', { tab: 'received' })
    expect(wrapper.text()).toContain('我的范围任务')
    expect(wrapper.text()).toContain('我的病历')
    expect(wrapper.text()).not.toContain('全部范围旧任务')
  })

  it('关闭时清空详情，晚到响应不能复活抽屉内容', async () => {
    const request = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail.mockReturnValueOnce(request.promise)
    const wrapper = mountDrawer()

    await wrapper.get('[data-testid="close-drawer"]').trigger('click')
    request.resolve(detailResponse('晚到任务', [record()]))
    await flushPromises()

    expect(wrapper.emitted('update:open')).toEqual([[false]])
    const vm = wrapper.vm as unknown as { detail: unknown }
    expect(vm.detail).toBeNull()
  })

  it('支持本地关键字与处理状态筛选，并保留关联id作为独立行', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse('筛选任务', [
        record({ id: 'association-a', record_id: 'same-record', assignee_name: '张医生' }),
        record({
          id: 'association-b',
          record_id: 'same-record',
          assignee_name: '李医生',
          status: 'completed',
        }),
      ]),
    )
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      keyword: string
      recordStatus: string | undefined
      filteredRecords: Array<{ id: string }>
      page: number
    }

    vm.page = 2
    vm.keyword = '李医生'
    await flushPromises()
    expect(vm.page).toBe(1)
    expect(vm.filteredRecords.map((item) => item.id)).toEqual(['association-b'])
    vm.keyword = ''
    vm.recordStatus = 'pending'
    await flushPromises()
    expect(vm.filteredRecords.map((item) => item.id)).toEqual(['association-a'])
  })

  it('完整三坐标可展示和分别检索，旧行与残缺坐标不伪装成病例身份', async () => {
    const longVisitId = `VISIT-${'长编号'.repeat(40)}`
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse('病例身份任务', [
        record({ id: 'complete', record_id: 'legacy-1', institute_id: 'HOSP-1', patient_id: 'PAT-1', visit_id: longVisitId }),
        record({ id: 'legacy', record_id: 'legacy-2', institute_id: null, patient_id: null, visit_id: null }),
        record({ id: 'partial', record_id: 'legacy-3', institute_id: 'HOSP-3', patient_id: '   ', visit_id: 'VISIT-3' }),
      ], { scene: 'outpatient' }),
    )
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.text()).toContain('HOSP-1')
    expect(wrapper.text()).toContain('PAT-1')
    expect(wrapper.text()).toContain(longVisitId)
    expect(wrapper.text()).not.toContain('历史病历号：legacy-1')
    expect(wrapper.text()).not.toContain('历史病历号：legacy-2')
    expect(wrapper.text()).not.toContain('历史病历号：legacy-3')
    expect(wrapper.findAll('.task-detail-drawer__missing-identity')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('HOSP-3')
    expect(wrapper.text()).not.toContain('VISIT-3')

    const vm = wrapper.vm as unknown as { keyword: string; filteredRecords: Array<{ id: string }> }
    for (const query of ['HOSP-1', 'PAT-1', longVisitId]) {
      vm.keyword = query
      await flushPromises()
      expect(vm.filteredRecords.map((item) => item.id)).toEqual(['complete'])
    }
    vm.keyword = 'HOSP-3'
    await flushPromises()
    expect(vm.filteredRecords).toHaveLength(0)
    vm.keyword = 'legacy-2'
    await flushPromises()
    expect(vm.filteredRecords).toHaveLength(0)
    vm.keyword = 'legacy-1'
    await flushPromises()
    expect(vm.filteredRecords).toHaveLength(0)
  })

  it('只有历史任务的旧病历号可展示和检索', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('历史任务', [record({ record_id: 'old-record' })]))
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.text()).toContain('历史病历号：old-record')
    const vm = wrapper.vm as unknown as { keyword: string; filteredRecords: Array<{ id: string }> }
    vm.keyword = 'old-record'
    await flushPromises()
    expect(vm.filteredRecords).toHaveLength(1)
  })

  it('真实表格分页可进入第二页，界面筛选后回到首个结果页', async () => {
    const records = Array.from({ length: 25 }, (_, index) => {
      const number = String(index + 1).padStart(2, '0')
      return record({ id: `association-${number}`, record_id: `PAGE-${number}` })
    })
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('分页任务', records))
    const wrapper = mountDrawer({}, { realTable: true })
    await flushPromises()

    expect(wrapper.find('.ant-table-tbody').text()).toContain('PAGE-01')
    expect(wrapper.find('.ant-table-tbody').text()).not.toContain('PAGE-11')

    await wrapper.get('.ant-pagination-item-2').trigger('click')
    await flushPromises()
    expect(wrapper.find('.ant-table-tbody').text()).toContain('PAGE-11')
    expect(wrapper.find('.ant-table-tbody').text()).not.toContain('PAGE-01')

    await wrapper.get('[data-testid="task-detail-keyword"]').setValue('PAGE-25')
    await flushPromises()
    expect(wrapper.find('.ant-table-tbody').text()).toContain('PAGE-25')
    expect(wrapper.find('.ant-table-tbody').text()).not.toContain('PAGE-11')
  })

  it.each(['custom_state', '__proto__'])('未知状态%s显示未知，超长病历号完整保留且没有文书跳转按钮', async (status) => {
    const longRecordId = `RID-${'长编号'.repeat(60)}`
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse('长编号任务', [record({ record_id: longRecordId, status })], { status }),
    )
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.text()).toContain(longRecordId)
    expect(wrapper.text()).toContain('未知')
    expect(wrapper.text()).not.toContain('打开文书')
  })

  it('兼容旧关联空值，并区分已分配但姓名缺失与真正未分配', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse(
        '旧数据任务',
        [
          record({
            id: 'legacy-assigned',
            record_id: null,
            assignee_id: 'user-legacy',
            assignee_name: null,
            status: null,
          }),
          record({
            id: 'legacy-unassigned',
            record_id: 'record-unassigned',
            assignee_id: null,
            assignee_name: null,
          }),
        ],
        { deadline: '2026-09-30', status: 'legacy_status' },
      ),
    )
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.text()).toContain('2026-09-30')
    expect(wrapper.text()).toContain('user-legacy（姓名未记录）')
    expect(wrapper.text()).toContain('未分配')
    expect(wrapper.text()).toContain('未记录')
    expect(wrapper.text()).toContain('未知')
  })

  it('成功响应的任务身份不匹配时拒绝展示详情', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse('串线任务', [record()], { id: 'another-task' }),
    )
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.get('[data-testid="task-detail-error"]').text()).toContain('身份校验失败')
    expect(wrapper.text()).not.toContain('串线任务')
  })
})
