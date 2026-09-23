import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { Select as ASelect, Table as ATable } from 'ant-design-vue'

const mocks = vi.hoisted(() => ({
  getTaskDetail: vi.fn(),
  getTaskQcRuns: vi.fn(),
  getTaskQcRunRecordResult: vi.fn(),
  createTaskQcRun: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  user: { id: 'creator' },
}))

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

vi.mock('@/api/tasks', () => ({
  getTaskDetail: mocks.getTaskDetail,
  getTaskQcRuns: mocks.getTaskQcRuns,
  getTaskQcRunRecordResult: mocks.getTaskQcRunRecordResult,
  createTaskQcRun: mocks.createTaskQcRun,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: mocks.user }) }))
vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getSichuanWorkspaceBatchJob: mocks.getSichuanWorkspaceBatchJob,
}))

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
  props: { open?: boolean; taskId?: string | null; tab?: 'all' | 'created' | 'received' } = {},
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
    mocks.getTaskQcRuns.mockReset()
    mocks.getTaskQcRunRecordResult.mockReset()
    mocks.createTaskQcRun.mockReset()
    mocks.getSichuanWorkspaceBatchJob.mockReset()
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务甲', [record()]))
    mocks.getTaskQcRuns.mockResolvedValue({ success: true, data: [] })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: { id: 'job-1', status: 'completed', summary: { total_records: 1, success_count: 1, failed_count: 0, issue_records: 0 } } })
    mocks.getTaskQcRunRecordResult.mockResolvedValue({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'completed', result_state: 'available', rule_set_key: 'lx0609',
      items: [{ rule_code: 'LX0609-001', rule_name: '入院记录时效', status: 'non_compliant',
        is_compliant: false, conclusion: '记录超时', suggestion: '补充说明',
        evidence: [{ source_type: '文书', source_ref: 'ref-1', excerpt_kind: '时间证据', evidence_excerpt: '签署时间晚于入院时间' }] }],
    } })
    mocks.user.id = 'creator'
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

  it('现代任务显示规则集，按精确 job_id 读取运行结果并启动新运行', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('运行任务', [record()], {
      scene: 'running', rule_set_key: 'published-running', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValue({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'job-2', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-23T00:00:00Z' },
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22T00:00:00Z' },
    ] })
    mocks.getSichuanWorkspaceBatchJob.mockImplementation(async (jobId: string) => ({
      success: true, data: { id: jobId, status: 'completed', summary: { total_records: 8, success_count: 7, failed_count: 1, issue_records: 2 } },
    }))
    mocks.createTaskQcRun.mockResolvedValue({ success: true, data: { task_id: 'task-1', run_number: 3, job_id: 'job-3', run_scope: 'all', status: 'queued' } })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()

    expect(wrapper.text()).toContain('published-running')
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-2')
    expect(wrapper.get('[data-testid="task-qc-job"]').text()).toContain('job-2')
    await wrapper.get('[data-testid="task-run-1"]').trigger('click')
    await flushPromises()
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenLastCalledWith('job-1')
    expect(wrapper.get('[data-testid="task-qc-job"]').text()).toContain('job-1')
    await wrapper.get('[data-testid="task-run-2"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-start-qc-run"]').trigger('click')
    await flushPromises()
    expect(mocks.getTaskQcRuns).toHaveBeenCalledWith('task-1', 'all')
    expect(mocks.createTaskQcRun).toHaveBeenCalledWith('task-1', 'all')
  })

  it('受领人仅查看并启动本人获分配子集，同一创建人切到收到视图也不能启动 all', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('受领任务', [record({ assignee_id: 'creator' })], {
      scene: 'running', rule_set_key: 'running-set', status: 'assigned', creator_id: 'creator',
    }))
    mocks.getTaskQcRuns.mockResolvedValue({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'own-job', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-23' },
      { task_id: 'task-1', run_number: 1, job_id: 'all-job', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.createTaskQcRun.mockResolvedValue({ success: true, data: {
      task_id: 'task-1', run_number: 3, job_id: 'new-own-job', run_scope: 'assigned', status: 'queued',
    } })
    mocks.getSichuanWorkspaceBatchJob.mockImplementation(async (jobId: string) => ({
      success: true, data: { id: jobId, status: 'completed' },
    }))
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    expect(mocks.getTaskQcRuns).toHaveBeenCalledWith('task-1', 'assigned')
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('own-job')
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalledWith('all-job')
    expect(wrapper.text()).not.toContain('all-job')
    await wrapper.get('[data-testid="task-start-qc-run"]').trigger('click')
    await flushPromises()
    expect(mocks.createTaskQcRun).toHaveBeenCalledWith('task-1', 'assigned')
    expect(mocks.createTaskQcRun).not.toHaveBeenCalledWith('task-1', 'all')
  })

  it('非创建人也可在收到视图启动本人子集，零分配与门急诊均不可启动', async () => {
    mocks.user.id = 'user-1'
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('受领任务', [record()], {
      scene: 'final', rule_set_key: 'final-set', status: 'assigned',
    }))
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(true)
    expect(mocks.getTaskQcRuns).toHaveBeenCalledWith('task-1', 'assigned')

    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('零分配', [], {
      scene: 'final', rule_set_key: 'final-set', status: 'assigned',
    }))
    await wrapper.setProps({ tab: 'created' })
    await wrapper.setProps({ tab: 'received' })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)

    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('门急诊', [record()], {
      scene: 'outpatient', rule_set_key: 'outpatient-set', status: 'assigned',
    }))
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)
  })

  it('切 tab 后旧运行历史与旧作业响应不回填相同任务的新范围', async () => {
    const oldRuns = deferred<{ success: boolean; data: Array<Record<string, unknown>> }>()
    const oldJob = deferred<{ success: boolean; data: { id: string; status: string } }>()
    mocks.getTaskDetail.mockResolvedValue(detailResponse('双身份任务', [record({ assignee_id: 'creator' })], {
      scene: 'running', rule_set_key: 'running-set', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockReturnValueOnce(oldRuns.promise).mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'assigned-job', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-23' },
    ] })
    mocks.getSichuanWorkspaceBatchJob.mockReturnValueOnce(oldJob.promise)
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.setProps({ tab: 'received' })
    await flushPromises()
    expect(mocks.getTaskQcRuns).toHaveBeenLastCalledWith('task-1', 'assigned')
    oldRuns.resolve({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'all-job', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    await flushPromises()
    expect(wrapper.text()).not.toContain('all-job')
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('assigned-job')
    expect(wrapper.find('[data-testid="task-run-2"]').exists()).toBe(true)
    await wrapper.setProps({ tab: 'created' })
    await flushPromises()
    oldJob.resolve({ success: true, data: { id: 'assigned-job', status: 'completed' } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('assigned-job')
  })

  it('运行历史 403 不展示旧作业或启动按钮', async () => {
    mocks.user.id = 'user-1'
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('无权历史', [record()], {
      scene: 'running', rule_set_key: 'running-set', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: false, message: '无权限读取运行历史' })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    expect(wrapper.text()).toContain('无权限读取运行历史')
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
  })

  it('历史重试变为 403 时立即清除先前可见的批次和作业', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('权限变化任务', [record({ assignee_id: 'creator' })], {
      scene: 'running', rule_set_key: 'running-set', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'old-job', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] }).mockResolvedValueOnce({ success: false, message: '无权限读取运行历史' })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValueOnce({ success: true, data: { id: 'old-job', status: 'completed' } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    expect(wrapper.text()).toContain('old-job')
    const vm = wrapper.vm as unknown as { loadRuns: () => Promise<void> }
    await vm.loadRuns()
    await flushPromises()
    expect(wrapper.text()).toContain('无权限读取运行历史')
    expect(wrapper.text()).not.toContain('old-job')
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)
  })

  it('非创建人和门急诊任务没有启动命令，历史任务不读取运行接口', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('门急诊', [], {
      scene: 'outpatient', rule_set_key: 'outpatient-set', creator_id: 'another',
    }))
    const wrapper = mountDrawer({ tab: 'all' })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)
    expect(mocks.getTaskQcRuns).not.toHaveBeenCalled()
    await wrapper.setProps({ taskId: 'task-2' })
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('历史', [], { id: 'task-2' }))
    await flushPromises()
    expect(wrapper.text()).not.toContain('质控运行')
  })

  it('运行历史失败不展示旧作业，切换任务后晚到的作业响应不能串线', async () => {
    const oldJob = deferred<{ success: boolean; data: { id: string; status: string } }>()
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('旧任务', [], { scene: 'running', rule_set_key: 'set-1' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'old-job', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] }).mockResolvedValueOnce({ success: false, message: '无权限读取运行历史' })
    mocks.getSichuanWorkspaceBatchJob.mockReturnValueOnce(oldJob.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('old-job')
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('新任务', [], { id: 'task-2', scene: 'final', rule_set_key: 'set-2' }))
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    oldJob.resolve({ success: true, data: { id: 'old-job', status: 'completed' } })
    await flushPromises()
    expect(wrapper.text()).toContain('无权限读取运行历史')
    expect(wrapper.text()).not.toContain('old-job')
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)
  })

  it('按所选运行和关联行查询本次结果，不改任务处理状态与分数', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', score: null, defect_count: null })], {
      scene: 'running', rule_set_key: 'lx0609', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()

    expect(mocks.getTaskQcRunRecordResult).toHaveBeenCalledWith('task-1', 1, 'association-1', 'all')
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain('记录超时')
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain('机构 H1 / 患者 P1 / 就诊 V1')
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain('补充说明')
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain('签署时间晚于入院时间')
    expect(wrapper.find('[data-testid="task-detail-record-empty"]').exists()).toBe(false)
    const vm = wrapper.vm as unknown as { detail: { records: Array<{ status: string; score: number | null; defect_count: number | null }> } }
    expect(vm.detail.records[0]).toMatchObject({ status: 'pending', score: null, defect_count: null })
    expect(wrapper.text()).toContain('未处理')
    expect(wrapper.text()).toContain('未记录')
  })

  it('展示 LX0916 客户结果的发现与字符串证据，不展示诊断字段或重复结论', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record()], {
      scene: 'running', rule_set_key: 'luxian_0916_qc_v1', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'failed', result_state: 'available', rule_set_key: 'luxian_0916_qc_v1',
      items: [
        { rule_id: 'LX0916-001', rule_name: '入院记录完整性', status: 'data_quality_gap',
          findings: '签名时间缺失', conclusion: '不得重复展示的旧结论',
          evidence: ['入院记录：签名时间未提供'], suggestion: '核对原始文书',
          technical_reason: 'internal-diagnostic-secret' },
        { rule_id: 'LX0916-002', rule_name: '手术记录', status: 'not_executed',
          findings: '本次未执行', evidence: [] },
      ],
    } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="task-record-qc-result"]').text()
    expect(result).toContain('签名时间缺失')
    expect(result).toContain('入院记录：签名时间未提供')
    expect(result).toContain('核对原始文书')
    expect(result).toContain('数据不足')
    expect(result).toContain('未执行')
    expect(result).toContain('批作业部分失败，该病历结果完整')
    expect(result).not.toContain('不得重复展示的旧结论')
    expect(result).not.toContain('internal-diagnostic-secret')
  })

  it('LX0916 结果不可用时不展示诊断内容或推断无缺陷', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record()], {
      scene: 'running', rule_set_key: 'luxian_0916_qc_v1', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'failed', result_state: 'unavailable', rule_set_key: 'luxian_0916_qc_v1',
      items: [], technical_reason: 'internal-failure-secret',
    } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="task-record-qc-result"]').text()
    expect(result).toContain('结果不可用')
    expect(result).not.toContain('internal-failure-secret')
    expect(result).not.toContain('无缺陷')
  })

  it('切换运行时丢弃晚到单病例结果', async () => {
    const oldResult = deferred<{ success: boolean; data: Record<string, unknown> }>()
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record()], { scene: 'running', rule_set_key: 'lx0609' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'job-2', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-23' },
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockReturnValueOnce(oldResult.promise)
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await wrapper.get('[data-testid="task-run-1"]').trigger('click')
    await flushPromises()
    oldResult.resolve({ success: true, data: {
      task_id: 'task-1', run_number: 2, task_record_id: 'association-1', job_id: 'job-2',
      result_state: 'available', rule_set_key: 'lx0609', items: [{ rule_name: '旧结果' }],
    } })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-record-qc-result"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('旧结果')
  })

  it.each(['无权限读取', '结果尚未就绪', '服务暂不可用'])('单病例接口错误%s原样可见', async (message) => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record()], { scene: 'running', rule_set_key: 'lx0609' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: false, message })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain(message)
    expect(wrapper.text()).not.toContain('无缺陷')
  })

  it('防御空 available，不能解释为无缺陷', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record()], { scene: 'running', rule_set_key: 'lx0609' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'completed', result_state: 'available', rule_set_key: 'lx0609', items: [],
    } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain('结果不可用')
  })

  it.each([
    ['pending', '尚未形成该病历结果'],
    ['unavailable', '结果不可用'],
  ])('%s 状态不推断为无缺陷', async (resultState, expected) => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('结果任务', [record()], { scene: 'running', rule_set_key: 'lx0609' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'running', result_state: resultState, rule_set_key: 'lx0609', items: [],
    } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-record-qc-result"]').text()).toContain(expected)
  })
})
