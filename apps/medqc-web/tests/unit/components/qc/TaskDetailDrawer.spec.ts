import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { Select as ASelect, Table as ATable } from 'ant-design-vue'

const mocks = vi.hoisted(() => ({
  getTaskDetail: vi.fn(),
  getTaskQcRuns: vi.fn(),
  getTaskQcRunRecordResult: vi.fn(),
  createTaskQcRun: vi.fn(),
  startTaskRecord: vi.fn(),
  completeTaskRecord: vi.fn(),
  syncTaskRecords: vi.fn(),
  getTaskRecordSyncJob: vi.fn(),
  getLatestTaskRecordSyncJob: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  authStore: null as null | { user: { id: string } | null; userRoles: string[] },
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

enableAutoUnmount(afterEach)

vi.mock('@/api/tasks', () => ({
  getTaskDetail: mocks.getTaskDetail,
  getTaskQcRuns: mocks.getTaskQcRuns,
  getTaskQcRunRecordResult: mocks.getTaskQcRunRecordResult,
  createTaskQcRun: mocks.createTaskQcRun,
  startTaskRecord: mocks.startTaskRecord,
  completeTaskRecord: mocks.completeTaskRecord,
  syncTaskRecords: mocks.syncTaskRecords,
  getTaskRecordSyncJob: mocks.getTaskRecordSyncJob,
  getLatestTaskRecordSyncJob: mocks.getLatestTaskRecordSyncJob,
}))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  const authStore = reactive({ user: { id: 'creator' } as { id: string } | null, userRoles: [] as string[] })
  mocks.authStore = authStore
  return { useAuthStore: () => authStore }
})
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

const TaskRecordDocumentDrawerStub = defineComponent({
  name: 'TaskRecordDocumentDrawer',
  props: { open: Boolean, taskId: String, record: Object },
  setup(props) {
    return () => props.open ? h('div', { 'data-testid': 'task-document-drawer' }) : null
  },
})

const TaskRecordReviewPanelStub = defineComponent({
  name: 'TaskRecordReviewPanel',
  props: { taskId: String, taskRecordId: String, runNumber: Number, jobId: String, userId: String },
  setup() {
    return () => h('div', { 'data-testid': 'task-record-review-stub' })
  },
})

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
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

function modernRecord(overrides: Record<string, unknown> = {}) {
  return record({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', assignee_id: 'creator', ...overrides })
}

function syncJob(jobId = 'sync-1', overrides: Record<string, unknown> = {}) {
  return { job_id: jobId, status: 'completed', total: 1, ready_count: 1, failed_count: 0,
    contract_version: 'task-record-sync-v1', records: [{ task_record_id: 'association-1', status: 'ready' }], ...overrides }
}

function mountDrawer(
  props: {
    open?: boolean; taskId?: string | null; tab?: 'all' | 'created' | 'received'
    focusTaskRecordId?: string | null; focusRunNumber?: number | null
  } = {},
  options: { realTable?: boolean } = {},
) {
  return mount(TaskDetailDrawer, {
    props: {
      open: props.open ?? true,
      taskId: props.taskId ?? 'task-1',
      tab: props.tab ?? 'received',
      focusTaskRecordId: props.focusTaskRecordId ?? null,
      focusRunNumber: props.focusRunNumber ?? null,
    },
    global: {
      components: options.realTable ? { ASelect, ATable } : {},
      stubs: {
        'a-button': ButtonStub,
        'a-drawer': DrawerStub,
        'a-empty': { template: '<div data-testid="empty"><slot />{{ $attrs.description }}</div>' },
        'a-input': InputStub,
        'a-select': options.realTable ? false : true,
        'a-skeleton': true,
        'a-table': options.realTable ? false : TableStub,
        'a-tag': { template: '<span><slot /></span>' },
        TaskRecordDocumentDrawer: TaskRecordDocumentDrawerStub,
        TaskRecordReviewPanel: TaskRecordReviewPanelStub,
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
    mocks.startTaskRecord.mockReset()
    mocks.completeTaskRecord.mockReset()
    mocks.syncTaskRecords.mockReset()
    mocks.getTaskRecordSyncJob.mockReset()
    mocks.getLatestTaskRecordSyncJob.mockReset()
    mocks.getSichuanWorkspaceBatchJob.mockReset()
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务甲', [record()]))
    mocks.getTaskQcRuns.mockResolvedValue({ success: true, data: [] })
    mocks.getLatestTaskRecordSyncJob.mockResolvedValue({ success: false, status: 404 })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: { id: 'job-1', status: 'completed', summary: { total_records: 1, success_count: 1, failed_count: 0, issue_records: 0 } } })
    mocks.getTaskQcRunRecordResult.mockResolvedValue({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'completed', result_state: 'available', rule_set_key: 'lx0609',
      items: [{ rule_code: 'LX0609-001', rule_name: '入院记录时效', status: 'non_compliant',
        is_compliant: false, conclusion: '记录超时', suggestion: '补充说明',
        evidence: [{ source_type: '文书', source_ref: 'ref-1', excerpt_kind: '时间证据', evidence_excerpt: '签署时间晚于入院时间' }] }],
    } })
    mocks.authStore!.user = { id: 'creator' }
    mocks.authStore!.userRoles.length = 0
  })

  it('仅本人受领的现代住院病历提供文书入口，切换任务关闭文书', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('住院任务', [
      modernRecord({ record_id: 'association-1' }),
      modernRecord({ id: 'association-2', record_id: 'association-2', assignee_id: 'other' }),
    ], { scene: 'running' }))
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.find('[data-testid="task-record-documents-association-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-record-documents-association-2"]').exists()).toBe(false)
    await wrapper.get('[data-testid="task-record-documents-association-1"]').trigger('click')
    expect(wrapper.getComponent(TaskRecordDocumentDrawerStub).props()).toMatchObject({
      open: true, taskId: 'task-1', record: expect.objectContaining({ id: 'association-1' }),
    })

    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('另一任务', [], { id: 'task-2', scene: 'running' }))
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    expect(wrapper.getComponent(TaskRecordDocumentDrawerStub).props('open')).toBe(false)
  })

  it('只将已保存的运行 active 范围显示为当前在院，历史缺字段不作推断', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('在院任务', [], {
      scene: 'running', sampling_config: { case_scope: 'active' },
    }))
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.find('[data-testid="task-detail-case-scope"]').text()).toBe('当前在院')

    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('历史任务', [], { id: 'task-2', scene: 'running' }))
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-detail-case-scope"]').text()).toBe('未明确（历史任务）')
  })

  it('按收到范围读取真实详情，并区分真实零值与缺失值', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(
      detailResponse('任务甲', [
        record({ status: 'completed', score: 0, defect_count: 0 }),
        record({ id: 'association-2', record_id: 'record-2', status: 'completed', score: null, defect_count: null }),
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

  it('未完成病历不将抽样占位零值展示为评分或缺陷结论', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('待处理任务', [
      record({ score: 0, defect_count: 0 }),
    ]))
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.get('[data-testid="task-detail-record-table"]').text().match(/待评估/g)).toHaveLength(2)
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

  it('切换账号后立即清空，晚到的旧账号详情不能覆盖新账号详情', async () => {
    const oldRequest = deferred<ReturnType<typeof detailResponse>>()
    const newRequest = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const wrapper = mountDrawer()

    mocks.authStore!.user = { id: 'user-2' }
    await flushPromises()
    newRequest.resolve(detailResponse('新账号任务', [record({ assignee_id: 'user-2' })]))
    await flushPromises()
    oldRequest.resolve(detailResponse('旧账号任务', [record({ assignee_id: 'creator' })]))
    await flushPromises()

    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('新账号任务')
    expect(wrapper.text()).not.toContain('旧账号任务')
  })

  it('切换账号后丢弃旧账号的作业与单病历结果响应', async () => {
    const oldJob = deferred<{ success: boolean; data: { id: string; status: string } }>()
    const oldResult = deferred<{ success: boolean; data: Record<string, unknown> }>()
    mocks.getTaskDetail
      .mockResolvedValueOnce(detailResponse('旧账号运行任务', [modernRecord()], {
        scene: 'running', rule_set_key: 'lx0609', status: 'assigned', creator_id: 'creator',
      }))
      .mockResolvedValueOnce(detailResponse('新账号任务', [record({ assignee_id: 'user-2' })]))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'old-job', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getSichuanWorkspaceBatchJob.mockReturnValueOnce(oldJob.promise)
    mocks.getTaskQcRunRecordResult.mockReturnValueOnce(oldResult.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')

    mocks.authStore!.user = { id: 'user-2' }
    await flushPromises()
    oldJob.resolve({ success: true, data: { id: 'old-job', status: 'completed' } })
    oldResult.resolve({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'old-job',
      result_state: 'available', rule_set_key: 'lx0609', items: [{ rule_name: '旧账号结果' }],
    } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { selectedJob: unknown; recordResult: unknown }
    expect(vm.selectedJob).toBeNull()
    expect(vm.recordResult).toBeNull()
    expect(wrapper.text()).not.toContain('old-job')
    expect(wrapper.text()).not.toContain('旧账号结果')
  })

  it('角色权限变化重新读取同一任务，角色集合顺序变化不重复读取', async () => {
    const oldRequest = deferred<ReturnType<typeof detailResponse>>()
    const newRequest = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const wrapper = mountDrawer()

    mocks.authStore!.userRoles.push('qc_manager', 'admin')
    await flushPromises()
    newRequest.resolve(detailResponse('管理员权限任务', [record()]))
    await flushPromises()
    oldRequest.resolve(detailResponse('普通权限旧任务', [record()]))
    await flushPromises()
    expect(wrapper.text()).toContain('管理员权限任务')
    expect(wrapper.text()).not.toContain('普通权限旧任务')
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)

    mocks.authStore!.userRoles.reverse()
    await flushPromises()
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
  })

  it.each(['success', 'failure'] as const)('注销立即清空详情，晚到%s响应无副作用且不以空账号重读', async (outcome) => {
    const request = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail.mockReturnValueOnce(request.promise)
    const wrapper = mountDrawer()
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(1)

    mocks.authStore!.user = null
    await flushPromises()
    if (outcome === 'success') request.resolve(detailResponse('注销后晚到任务', [record()]))
    else request.reject(new Error('注销后晚到失败'))
    await flushPromises()

    const vm = wrapper.vm as unknown as { detail: unknown; error: string }
    expect(vm.detail).toBeNull()
    expect(vm.error).toBe('')
    expect(wrapper.text()).not.toContain('注销后晚到任务')
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(1)
  })

  it('卸载时使在途详情失效', async () => {
    const request = deferred<ReturnType<typeof detailResponse>>()
    mocks.getTaskDetail.mockReturnValueOnce(request.promise)
    const wrapper = mountDrawer()
    const vm = wrapper.vm as unknown as { detail: unknown; error: string }

    wrapper.unmount()
    request.resolve(detailResponse('卸载后晚到任务', [record()]))
    await flushPromises()

    expect(vm.detail).toBeNull()
    expect(vm.error).toBe('')
    expect(mocks.getTaskQcRuns).not.toHaveBeenCalled()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
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
      scene: 'running', rule_set_key: 'published-running', rule_set_version: '2026-06-09', status: 'assigned',
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
    expect(wrapper.text()).toContain('2026-06-09')
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

  it('历史任务缺少冻结版本时保留运行历史但禁止启动新运行', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('旧任务', [record()], {
      scene: 'running', rule_set_key: 'running-set', rule_set_version: null, status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'old-job', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValueOnce({ success: true, data: {
      id: 'old-job', status: 'completed',
    } })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()

    expect(wrapper.text()).toContain('running-set · 未冻结版本')
    expect(mocks.getTaskQcRuns).toHaveBeenCalledWith('task-1', 'all')
    expect(wrapper.get('[data-testid="task-qc-job"]').text()).toContain('old-job')
    expect(wrapper.find('[data-testid="task-start-qc-run"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('任务未冻结规则集版本，无法执行质控')
    expect(mocks.createTaskQcRun).not.toHaveBeenCalled()
  })

  it('受领人仅查看并启动本人获分配子集，同一创建人切到收到视图也不能启动 all', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('受领任务', [record({ assignee_id: 'creator' })], {
      scene: 'running', rule_set_key: 'running-set', rule_set_version: '2026-06-09', status: 'assigned', creator_id: 'creator',
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
    mocks.authStore!.user = { id: 'user-1' }
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('受领任务', [record()], {
      scene: 'final', rule_set_key: 'final-set', rule_set_version: '2026-04-24', status: 'assigned',
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
    mocks.authStore!.user = { id: 'user-1' }
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

  it('SC 结论不确定时显示待确认而非符合', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('终末任务', [record()], {
      scene: 'final', rule_set_key: 'sc_content_v1', status: 'assigned',
    }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'all', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 1, task_record_id: 'association-1', job_id: 'job-1',
      job_status: 'completed', result_state: 'available', rule_set_key: 'sc_content_v1',
      items: [{ rule_id: 'SC-023', rule_name: '诊疗经过', status: 'uncertain', findings: '需人工核对' }],
    } })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="task-record-qc-result"]').text()
    expect(result).toContain('结论待确认')
    expect(result).toContain('需人工核对')
    expect(result).not.toContain('状态待确认')
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

  it('仅已受领且有三坐标的 pending 病历显示开始处理，不把完成的质控作业当成人工完成', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-record-start-association-1"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('未处理')
    expect(mocks.startTaskRecord).not.toHaveBeenCalled()
  })

  it('同步病历只向创建人开放，历史缺坐标任务禁用', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord({ visit_id: null })], { scene: 'running', total_records: 1 }))
    const creator = mountDrawer({ tab: 'created' })
    await flushPromises()
    expect(creator.get('[data-testid="task-sync-records"]').attributes('disabled')).toBeDefined()
    expect(creator.get('[data-testid="task-sync-unavailable"]').text()).toContain('未记录病例坐标')
    await creator.get('[data-testid="task-sync-records"]').trigger('click')
    expect(mocks.syncTaskRecords).not.toHaveBeenCalled()
    creator.unmount()

    mocks.authStore!.user = { id: 'other' }
    const other = mountDrawer({ tab: 'all' })
    await flushPromises()
    expect(other.find('[data-testid="task-sync-records"]').exists()).toBe(false)
  })

  it('管理员可在全部页同步非本人任务，质控主管不能借管理员入口', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('他人任务', [modernRecord()], {
      creator_id: 'other', scene: 'running', total_records: 1,
    }))
    mocks.authStore!.user = { id: 'admin-user' }
    mocks.authStore!.userRoles.push('admin')
    const admin = mountDrawer({ tab: 'all' })
    await flushPromises()
    expect(admin.get('[data-testid="task-sync-records"]').attributes('disabled')).toBeUndefined()
    admin.unmount()

    mocks.authStore!.userRoles.length = 0
    mocks.authStore!.userRoles.push('qc_manager')
    const manager = mountDrawer({ tab: 'all' })
    await flushPromises()
    expect(manager.find('[data-testid="task-sync-records"]').exists()).toBe(false)
    manager.unmount()
  })

  it('同步成功后展示就绪计数，仍由用户手动启动质控', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', rule_set_key: 'lx0609', rule_set_version: 'v1', status: 'assigned', total_records: 1,
    }))
    mocks.syncTaskRecords.mockResolvedValue({ success: true, data: { job_id: 'sync-1', status: 'queued', reused: false } })
    mocks.getTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob() })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(mocks.syncTaskRecords).toHaveBeenCalledWith('task-1')
    expect(mocks.getTaskRecordSyncJob).toHaveBeenCalledWith('task-1', 'sync-1')
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('已就绪 1 / 1 份；失败 0 份')
    expect(mocks.createTaskQcRun).not.toHaveBeenCalled()
  })

  it('部分失败可显式重试，不展示服务端病历原文', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord(), modernRecord({ id: 'association-2' })], {
      scene: 'running', total_records: 2,
    }))
    mocks.syncTaskRecords.mockResolvedValueOnce({ success: true, data: { job_id: 'sync-1', status: 'queued', reused: false } })
      .mockResolvedValueOnce({ success: true, data: { job_id: 'sync-2', status: 'queued', reused: false } })
    mocks.getTaskRecordSyncJob.mockResolvedValueOnce({ success: true, data: syncJob('sync-1', {
      status: 'failed', total: 2, ready_count: 1, failed_count: 1,
      records: [{ task_record_id: 'association-1', status: 'ready' },
        { task_record_id: 'association-2', status: 'failed', reason_code: 'workspace_not_ready', message: '患者原文不应展示' }],
    }) }).mockResolvedValueOnce({ success: true, data: syncJob('sync-2', {
      total: 2, ready_count: 2,
      records: [{ task_record_id: 'association-1', status: 'ready' }, { task_record_id: 'association-2', status: 'ready' }],
    }) })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('失败 1 份，可重试同步')
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('第 2 份：本地病历资料尚未就绪')
    expect(wrapper.text()).not.toContain('患者原文不应展示')
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(2)
    expect(mocks.getTaskRecordSyncJob).toHaveBeenLastCalledWith('task-1', 'sync-2')
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('失败 0 份')
  })

  it('作业提交中和轮询中重复点击不再 POST', async () => {
    const pending = deferred<{ success: boolean; data: { job_id: string; status: string; reused: boolean } }>()
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.syncTaskRecords.mockReturnValue(pending.promise)
    mocks.getTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob('sync-1', {
      status: 'running', ready_count: 0, records: [],
    }) })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(1)
    pending.resolve({ success: true, data: { job_id: 'sync-1', status: 'queued', reused: false } })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('正在同步任务病历')
    wrapper.unmount()
  })

  it('关闭后晚到的提交响应不会继续查询或复活状态', async () => {
    const pending = deferred<{ success: boolean; data: { job_id: string; status: string; reused: boolean } }>()
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.syncTaskRecords.mockReturnValue(pending.promise)
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await wrapper.setProps({ open: false })
    pending.resolve({ success: true, data: { job_id: 'sync-1', status: 'queued', reused: false } })
    await flushPromises()
    expect(mocks.getTaskRecordSyncJob).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="task-sync-result"]').exists()).toBe(false)
  })

  it('重新打开从 latest 恢复既有作业，不再提交新作业', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.getLatestTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob('existing-job') })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    expect(mocks.getLatestTaskRecordSyncJob).toHaveBeenCalledWith('task-1')
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('已就绪 1 / 1 份')
    expect(mocks.syncTaskRecords).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('POST 超时后只查询 latest，确认当前 job 后轮询同一 job', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.getLatestTaskRecordSyncJob.mockResolvedValueOnce({ success: false, status: 404 })
      .mockResolvedValueOnce({ success: true, data: syncJob('recovered-job', {
        status: 'running', ready_count: 0, records: [],
      }) })
    mocks.syncTaskRecords.mockResolvedValue({ success: false, message: '请求超时' })
    mocks.getTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob('recovered-job') })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-error"]').text()).toContain('状态未知')
    await wrapper.get('[data-testid="task-sync-verify"]').trigger('click')
    await flushPromises()
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('正在同步任务病历')
    await new Promise((resolve) => setTimeout(resolve, 1550))
    await flushPromises()
    expect(mocks.getTaskRecordSyncJob).toHaveBeenCalledWith('task-1', 'recovered-job')
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('已就绪 1 / 1 份')
    wrapper.unmount()
  })

  it('POST 状态未知后重查 latest 为 404，可再次显式提交', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.getLatestTaskRecordSyncJob.mockResolvedValue({ success: false, status: 404 })
    mocks.syncTaskRecords.mockResolvedValueOnce({ success: false, message: '请求超时' })
      .mockResolvedValueOnce({ success: true, data: { job_id: 'new-job', status: 'queued', reused: false } })
    mocks.getTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob('new-job') })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-records"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="task-sync-verify"]').trigger('click')
    await flushPromises()
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="task-sync-records"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(2)
    expect(mocks.getTaskRecordSyncJob).toHaveBeenCalledWith('task-1', 'new-job')
    wrapper.unmount()
  })

  it.each([
    [403, '没有同步任务病历的权限'],
    [409, '当前任务状态冲突'],
    [422, '任务病例不满足同步条件'],
    [429, '同步队列繁忙'],
  ])('POST 明确拒绝 %s 时显示白名单文案，不进入未知态或查询', async (status, label) => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.syncTaskRecords.mockResolvedValue({ success: false, status, message: '患者原文不应展示' })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-error"]').text()).toContain(label)
    expect(wrapper.text()).not.toContain('患者原文不应展示')
    expect(wrapper.find('[data-testid="task-sync-verify"]').exists()).toBe(false)
    expect(mocks.getLatestTaskRecordSyncJob).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskRecordSyncJob).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('按 job_id 查询失败时只能重查同 job，不能误发新 POST', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.syncTaskRecords.mockResolvedValue({ success: true, data: { job_id: 'sync-1', status: 'queued', reused: false } })
    mocks.getTaskRecordSyncJob.mockResolvedValueOnce({ success: false, message: '请求超时' })
      .mockResolvedValueOnce({ success: true, data: syncJob('sync-1') })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-records"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    expect(mocks.syncTaskRecords).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="task-sync-verify"]').trigger('click')
    await flushPromises()
    expect(mocks.getTaskRecordSyncJob).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('已就绪 1 / 1 份')
    wrapper.unmount()
  })

  it('派发失败没有逐份结果时仍可显示失败并显式创建新 job', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.getLatestTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob('dispatch-failed', {
      status: 'failed', ready_count: 0, failed_count: 1, records: [],
    }) })
    mocks.syncTaskRecords.mockResolvedValue({ success: true, data: { job_id: 'new-job', status: 'queued', reused: false } })
    mocks.getTaskRecordSyncJob.mockResolvedValue({ success: true, data: syncJob('new-job') })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-result"]').text()).toContain('失败 1 份')
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(mocks.syncTaskRecords).toHaveBeenCalledOnce()
    expect(mocks.getTaskRecordSyncJob).toHaveBeenCalledWith('task-1', 'new-job')
    wrapper.unmount()
  })

  it('按 job_id 读取到另一作业时拒绝展示，仍只允许查询原 job', async () => {
    mocks.getTaskDetail.mockResolvedValue(detailResponse('任务', [modernRecord()], {
      scene: 'running', total_records: 1,
    }))
    mocks.syncTaskRecords.mockResolvedValue({ success: true, data: { job_id: 'sync-1', status: 'queued', reused: false } })
    mocks.getTaskRecordSyncJob.mockResolvedValueOnce({ success: true, data: syncJob('foreign-job') })
      .mockResolvedValueOnce({ success: true, data: syncJob('sync-1') })
    const wrapper = mountDrawer({ tab: 'created' })
    await flushPromises()
    await wrapper.get('[data-testid="task-sync-records"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-sync-error"]').text()).toContain('校验失败')
    expect(wrapper.find('[data-testid="task-sync-result"]').exists()).toBe(false)
    await wrapper.get('[data-testid="task-sync-verify"]').trigger('click')
    await flushPromises()
    expect(mocks.getTaskRecordSyncJob).toHaveBeenLastCalledWith('task-1', 'sync-1')
    expect(mocks.syncTaskRecords).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it.each([
    ['全部页', 'all' as const, modernRecord(), { scene: 'running' }],
    ['创建页', 'created' as const, modernRecord(), { scene: 'running' }],
    ['他人病历', 'received' as const, modernRecord({ assignee_id: 'other' }), { scene: 'running' }],
    ['已处理中', 'received' as const, modernRecord({ status: 'in_progress' }), { scene: 'running' }],
    ['任务未开始', 'received' as const, modernRecord(), { scene: 'running', status: 'assigned' }],
    ['旧任务', 'received' as const, modernRecord(), {}],
    ['缺病例坐标', 'received' as const, modernRecord({ visit_id: null }), { scene: 'running' }],
    ['关联任务不符', 'received' as const, modernRecord({ task_id: 'other' }), { scene: 'running' }],
  ])('%s 不允许单病历开始处理', async (_reason, tab, item, taskOverrides) => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('受限任务', [item], taskOverrides))
    const wrapper = mountDrawer({ tab })
    await flushPromises()
    expect(wrapper.find('[data-testid="task-record-start-association-1"]').exists()).toBe(false)
  })

  it('成功后只读复查身份和状态，保留当前筛选与运行批次', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('现代任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.startTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', status: 'in_progress',
    } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-detail-keyword"]').setValue('H1')
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    await flushPromises()
    expect(mocks.startTaskRecord).toHaveBeenCalledOnce()
    expect(mocks.getTaskDetail).toHaveBeenLastCalledWith('task-1', { tab: 'received' })
    expect(wrapper.text()).toContain('处理中')
    expect(wrapper.find('[data-testid="task-record-start-association-1"]').exists()).toBe(false)
    expect((wrapper.get('[data-testid="task-detail-keyword"]').element as HTMLInputElement).value).toBe('H1')
    expect(wrapper.find('[data-testid="task-run-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-qc-job"]').exists()).toBe(true)
  })

  it('请求未完成时阻止重复点击，服务失败保留可信详情并允许重试', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
    const pending = deferred<{ success: boolean; message: string }>()
    mocks.startTaskRecord.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    expect(mocks.startTaskRecord).toHaveBeenCalledTimes(1)
    pending.resolve({ success: false, message: '无权开始' })
    await flushPromises()
    expect(wrapper.text()).toContain('无权开始')
    expect(wrapper.text()).toContain('病历尚未开始，可重试')
    expect(wrapper.text()).toContain('现代任务')
    expect(wrapper.find('[data-testid="task-record-start-association-1"]').exists()).toBe(true)
  })

  it('提交已生效但响应丢失时只读复查，不重复开始处理', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('现代任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
    mocks.startTaskRecord.mockResolvedValueOnce({ success: false, message: '请求超时' })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    await flushPromises()
    expect(mocks.startTaskRecord).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('处理中')
    expect(wrapper.find('[data-testid="task-record-start-association-1"]').exists()).toBe(false)
  })

  it('响应身份错配不伪造成功；复查确认仍未处理后才允许重试', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('现代任务', [modernRecord()], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('现代任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
    mocks.startTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'other-task', task_record_id: 'association-1', status: 'in_progress',
    } }).mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', status: 'in_progress',
    } })
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('响应身份或状态校验失败')
    expect(wrapper.find('[data-testid="task-record-start-association-1"]').exists()).toBe(false)
    await wrapper.get('[data-testid="task-record-verify-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('病历尚未开始，可重试')
    expect(mocks.startTaskRecord).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('处理中')
    expect(wrapper.find('[data-testid="task-record-verify-association-1"]').exists()).toBe(false)
    expect(mocks.startTaskRecord).toHaveBeenCalledTimes(2)
  })

  it('切换任务后忽略旧启动响应和旧复查，不污染新任务', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('旧任务', [modernRecord()], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('新任务', [modernRecord({ id: 'association-2', task_id: 'task-2' })], { id: 'task-2', scene: 'running' }))
    const pending = deferred<{ success: boolean; data: { task_id: string; task_record_id: string; status: string } }>()
    mocks.startTaskRecord.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer({ tab: 'received' })
    await flushPromises()
    await wrapper.get('[data-testid="task-record-start-association-1"]').trigger('click')
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    pending.resolve({ success: true, data: { task_id: 'task-1', task_record_id: 'association-1', status: 'in_progress' } })
    await flushPromises()
    expect(wrapper.text()).toContain('新任务')
    expect(wrapper.text()).not.toContain('旧任务')
    expect(wrapper.find('[data-testid="task-record-start-association-2"]').exists()).toBe(true)
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
  })

  function prepareCompletion(resultState = 'available', items: Array<Record<string, unknown>> = [{ rule_name: '检查项', status: 'compliant' }]) {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('待完成任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'job-2', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 2, task_record_id: 'association-1', job_id: 'job-2',
      job_status: 'completed', result_state: resultState, rule_set_key: 'lx0609', items,
    } })
  }

  it('本人所选 assigned 运行有可用结果时显式完成，并以 GET 确认而非 POST 乐观更新', async () => {
    prepareCompletion()
    const refreshed = deferred<ReturnType<typeof detailResponse>>()
    mocks.completeTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', run_number: 2,
      status: 'completed', idempotent: false, score: null, defect_count: null,
    } })
    mocks.getTaskDetail.mockReturnValueOnce(refreshed.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    expect(mocks.completeTaskRecord).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    expect(mocks.completeTaskRecord).toHaveBeenCalledWith('task-1', 'association-1', 2)
    expect(wrapper.text()).toContain('处理中')
    expect(wrapper.emitted('task-updated')).toBeUndefined()
    refreshed.resolve(detailResponse('待完成任务', [modernRecord({ status: 'completed', score: null, defect_count: null })], { scene: 'running' }))
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toEqual([['task-1']])
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('未记录')
    expect(wrapper.find('[data-testid="task-record-complete"]').exists()).toBe(false)
  })

  it('POST 网络失败后 GET 确认未完成则可重试；复查失败只能重新查询', async () => {
    prepareCompletion()
    mocks.completeTaskRecord.mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValueOnce({ success: true, data: { task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed' } })
    mocks.getTaskDetail.mockResolvedValueOnce({ success: false, message: 'read failed' })
      .mockResolvedValueOnce(detailResponse('待完成任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
      .mockResolvedValueOnce(detailResponse('待完成任务', [modernRecord({ status: 'completed' })], { scene: 'running' }))
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
    expect(wrapper.find('[data-testid="task-record-complete"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="task-record-complete-verify"]').exists()).toBe(true)
    await wrapper.get('[data-testid="task-record-complete-verify"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
    expect(wrapper.text()).toContain('病历尚未完成，可重试')
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    expect(mocks.completeTaskRecord).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.emitted('task-updated')).toEqual([['task-1']])
  })

  it.each([
    ['读取失败', { success: false, message: 'read failed' }],
    ['缺病历清单', detailResponse('待完成任务', [modernRecord({ status: 'completed' })], { records: null })],
    ['错任务', detailResponse('待完成任务', [modernRecord({ status: 'completed' })], { id: 'other-task' })],
    ['错关联任务', detailResponse('待完成任务', [modernRecord({ status: 'completed', task_id: 'other-task' })])],
    ['错受领人', detailResponse('待完成任务', [modernRecord({ status: 'completed', assignee_id: 'other-user' })])],
    ['缺病例坐标', detailResponse('待完成任务', [modernRecord({ status: 'completed', visit_id: null })])],
    ['仍处理中', detailResponse('待完成任务', [modernRecord({ status: 'in_progress' })])],
  ])('POST 成功但 GET %s 时不通知父列表', async (_reason, response) => {
    prepareCompletion()
    mocks.completeTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed',
    } })
    mocks.getTaskDetail.mockResolvedValueOnce(response)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('GET 完成复查尚未返回时切换任务，不通知新任务列表', async () => {
    prepareCompletion()
    const refreshed = deferred<ReturnType<typeof detailResponse>>()
    mocks.completeTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed',
    } })
    mocks.getTaskDetail.mockReturnValueOnce(refreshed.promise)
      .mockResolvedValueOnce(detailResponse('新任务', [modernRecord({ id: 'association-2', task_id: 'task-2' })], { id: 'task-2', scene: 'running' }))
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    refreshed.resolve(detailResponse('旧任务', [modernRecord({ status: 'completed' })]))
    await flushPromises()
    expect(wrapper.text()).toContain('新任务')
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('GET 完成复查尚未返回时切换运行，不通知旧批次完成', async () => {
    prepareCompletion()
    mocks.getTaskQcRuns.mockReset().mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'job-2', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-23' },
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    const refreshed = deferred<ReturnType<typeof detailResponse>>()
    mocks.completeTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed',
    } })
    mocks.getTaskDetail.mockReturnValueOnce(refreshed.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-run-1"]').trigger('click')
    refreshed.resolve(detailResponse('旧批次', [modernRecord({ status: 'completed' })]))
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('GET 完成复查尚未返回时切换登录人，不通知原受领人完成', async () => {
    prepareCompletion()
    const refreshed = deferred<ReturnType<typeof detailResponse>>()
    mocks.completeTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed',
    } })
    mocks.getTaskDetail.mockReturnValueOnce(refreshed.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    mocks.authStore!.user = { id: 'other-user' }
    refreshed.resolve(detailResponse('原受领人任务', [modernRecord({ status: 'completed' })]))
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('GET 完成复查网络异常时不通知父列表，只保留重新查询入口', async () => {
    prepareCompletion()
    mocks.completeTaskRecord.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed',
    } })
    mocks.getTaskDetail.mockRejectedValueOnce(new Error('network error'))
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('task-updated')).toBeUndefined()
    expect(wrapper.find('[data-testid="task-record-complete-verify"]').exists()).toBe(true)
  })

  it.each([['pending', []], ['unavailable', []], ['available', []]])('结果 %s 无有效条目时没有完成命令', async (state, items) => {
    prepareCompletion(state, items)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="task-record-complete"]').exists()).toBe(false)
    expect(mocks.completeTaskRecord).not.toHaveBeenCalled()
  })

  it('切换任务后丢弃迟到的完成响应，不对新任务复查', async () => {
    prepareCompletion()
    const pending = deferred<{ success: boolean; data: Record<string, unknown> }>()
    mocks.completeTaskRecord.mockReturnValueOnce(pending.promise)
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('新任务', [modernRecord({ id: 'association-2', task_id: 'task-2' })], { id: 'task-2', scene: 'running' }))
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    pending.resolve({ success: true, data: { task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed' } })
    await flushPromises()
    expect(wrapper.text()).toContain('新任务')
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('切换运行后丢弃旧完成响应，不读取旧批次的完成状态', async () => {
    prepareCompletion()
    mocks.getTaskQcRuns.mockReset().mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 2, job_id: 'job-2', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-23' },
      { task_id: 'task-1', run_number: 1, job_id: 'job-1', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    const pending = deferred<{ success: boolean; data: Record<string, unknown> }>()
    mocks.completeTaskRecord.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    await wrapper.get('[data-testid="task-run-1"]').trigger('click')
    await flushPromises()
    pending.resolve({ success: true, data: { task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed' } })
    await flushPromises()
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="task-record-qc-result"]').exists()).toBe(false)
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('切换登录身份后丢弃旧受领人的完成响应', async () => {
    prepareCompletion()
    const pending = deferred<{ success: boolean; data: Record<string, unknown> }>()
    mocks.completeTaskRecord.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-record-complete"]').trigger('click')
    mocks.authStore!.user = { id: 'other-user' }
    pending.resolve({ success: true, data: { task_id: 'task-1', task_record_id: 'association-1', run_number: 2, status: 'completed' } })
    await flushPromises()
    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('task-updated')).toBeUndefined()
  })

  it('本人 assigned 运行结果可用时挂载病历审核面板并传入当前上下文', async () => {
    prepareCompletion()
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.find('[data-testid="task-record-review-stub"]').exists()).toBe(false)
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.getComponent(TaskRecordReviewPanelStub).props()).toEqual({
      taskId: 'task-1', taskRecordId: 'association-1', runNumber: 2, jobId: 'job-2', userId: 'creator',
    })
  })

  it('结果不可用时不挂载病历审核面板', async () => {
    prepareCompletion('unavailable', [])
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.get('[data-testid="task-record-result-association-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="task-record-review-stub"]').exists()).toBe(false)
  })

  it('下钻定位按指定运行序号选中运行并自动打开该病历结果', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('待审核任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 3, job_id: 'job-3', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-23' },
      { task_id: 'task-1', run_number: 2, job_id: 'job-2', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-22' },
    ] })
    mocks.getTaskQcRunRecordResult.mockResolvedValueOnce({ success: true, data: {
      task_id: 'task-1', run_number: 2, task_record_id: 'association-1', job_id: 'job-2',
      job_status: 'completed', result_state: 'available', rule_set_key: 'lx0609', items: [{ rule_name: '检查项', status: 'compliant' }],
    } })
    const wrapper = mountDrawer({ focusTaskRecordId: 'association-1', focusRunNumber: 2 })
    await flushPromises()
    expect(mocks.getTaskQcRunRecordResult).toHaveBeenCalledWith('task-1', 2, 'association-1', 'assigned')
    expect(wrapper.getComponent(TaskRecordReviewPanelStub).props()).toMatchObject({ taskRecordId: 'association-1', runNumber: 2, jobId: 'job-2' })
  })

  it('下钻病历不在本人清单时不自动读取结果，仍选中最新运行', async () => {
    mocks.getTaskDetail.mockResolvedValueOnce(detailResponse('待审核任务', [modernRecord({ status: 'in_progress' })], { scene: 'running' }))
    mocks.getTaskQcRuns.mockResolvedValueOnce({ success: true, data: [
      { task_id: 'task-1', run_number: 3, job_id: 'job-3', run_scope: 'assigned', triggered_by: 'creator', created_at: '2026-09-23' },
    ] })
    mountDrawer({ focusTaskRecordId: 'association-x', focusRunNumber: 9 })
    await flushPromises()
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-3')
    expect(mocks.getTaskQcRunRecordResult).not.toHaveBeenCalled()
  })
})

