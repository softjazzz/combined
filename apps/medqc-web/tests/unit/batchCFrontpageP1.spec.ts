import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import type {
  FrontpageQcAnalytics,
  FrontpageQcFinding,
  FrontpageQcRecordDetail,
  FrontpageQcRecordItem,
  FrontpageQcRun,
} from '@/services/frontpage-qc-v2-service'

const mockMessageError = vi.fn()
const mockMessageSuccess = vi.fn()

vi.mock('ant-design-vue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('ant-design-vue')>()),
  Modal: {
    name: 'Modal',
    props: ['open'],
    emits: ['cancel'],
    template: '<div v-if="open" class="modal-stub"><slot /></div>',
  },
  Pagination: {
    name: 'Pagination',
    props: ['current', 'pageSize', 'total', 'disabled'],
    emits: ['change'],
    template: '<nav class="pagination-stub" />',
  },
  DatePicker: {
    name: 'ADatePicker',
    props: ['value', 'id'],
    emits: ['update:value'],
    template:
      '<input :id="id" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
  message: {
    error: (...args: unknown[]) => mockMessageError(...args),
    success: (...args: unknown[]) => mockMessageSuccess(...args),
  },
}))

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: vi.fn(),
}))

const testAuth = reactive<{
  user: {
    id: string
    institute_id?: string
    hospital_id?: string
    roles?: string[]
    role?: string
    is_demo_account?: boolean
  } | null
  userRoles: string[]
}>({
  user: { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false },
  userRoles: ['admin'],
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => testAuth,
}))

const svc = {
  listRecords: vi.fn(),
  getRecord: vi.fn(),
  getFilters: vi.fn(),
  getAnalytics: vi.fn(),
  createRun: vi.fn(),
  getRun: vi.fn(),
  cancelRun: vi.fn(),
  exportRecords: vi.fn(),
  listActive: vi.fn(),
  review: vi.fn(),
}

vi.mock('@/services/frontpage-qc-v2-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/frontpage-qc-v2-service')>()
  return {
    ...actual,
    listFrontpageQcRecords: (...a: unknown[]) => svc.listRecords(...a),
    getFrontpageQcRecord: (...a: unknown[]) => svc.getRecord(...a),
    getFrontpageQcFilters: (...a: unknown[]) => svc.getFilters(...a),
    getFrontpageQcAnalytics: (...a: unknown[]) => svc.getAnalytics(...a),
    createFrontpageQcRun: (...a: unknown[]) => svc.createRun(...a),
    getFrontpageQcRun: (...a: unknown[]) => svc.getRun(...a),
    cancelFrontpageQcRun: (...a: unknown[]) => svc.cancelRun(...a),
    exportFrontpageQcRecords: (...a: unknown[]) => svc.exportRecords(...a),
    listActiveFrontpageQcRuns: (...a: unknown[]) => svc.listActive(...a),
    reviewFrontpageQcFinding: (...a: unknown[]) => svc.review(...a),
  }
})

import { FrontpageQcRequestError } from '@/services/frontpage-qc-v2-service'
import FrontpageQcAnalysisPanel from '@/views/workstation-v4/frontpage-qc/FrontpageQcAnalysisPanel.vue'
import FrontpageQcPreview from '@/views/workstation-v4/frontpage-qc/FrontpageQcPreview.vue'
import FrontpageQcView from '@/views/workstation-v4/frontpage-qc/FrontpageQcView.vue'
import {
  MAX_POLL_FAILURES,
  POLL_INTERVAL_MS,
  useFrontpageQcRun,
} from '@/views/workstation-v4/frontpage-qc/useFrontpageQcRun'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function makeRecord(alias: string, overrides: Partial<FrontpageQcRecordItem> = {}): FrontpageQcRecordItem {
  const key = `H-TEST|P-${alias}|${alias}`
  return {
    institute_id: 'H-TEST',
    patient_id: `P-${alias}`,
    visit_id: alias,
    record_key: key,
    patient_name: `患者${alias}`,
    inpat_no: `ZY-${alias}`,
    mr_no: `MR-${alias}`,
    department: '内科',
    doctor: '',
    discharge_date: '2026-09-15',
    result: {
      id: `res-${alias}`,
      run_id: 'run-0',
      record_key: key,
      department: '内科',
      discharge_date: '2026-09-15',
      score: 88,
      grade: 'qualified',
      fail_count: 2,
      hint_count: 0,
      required_missing_count: 0,
      data_gap_count: 0,
      scorable_ratio: 1,
      completeness_rate: 0.95,
      ruleset_version: '2026.10.13',
      created_at: '2026-10-13T08:00:00',
    },
    ...overrides,
  }
}

function makeFinding(id: string, overrides: Partial<FrontpageQcFinding> = {}): FrontpageQcFinding {
  return {
    id,
    rule_id: id === 'f-1' ? 'C-H21' : 'C-H22',
    rule_name: id === 'f-1' ? '手术者' : '麻醉师',
    group: 'completeness',
    section: 'diagnosis',
    severity: 'deduct',
    score_item: id === 'f-1' ? 'surgeon' : 'anesthetist',
    verdict: 'fail',
    problem: id === 'f-1' ? '手术者未填写' : '麻醉师未填写',
    reason: '',
    details: [{ field: '字段', value: '', expected: '需填写', item_index: 0 }],
    deduction: 1,
    review_status: 'pending',
    review_note: '',
    reviewed_by: '',
    reviewed_at: null,
    ...overrides,
  }
}

function makeDetail(
  item: FrontpageQcRecordItem,
  findings: FrontpageQcFinding[] = [makeFinding('f-1'), makeFinding('f-2')],
): FrontpageQcRecordDetail {
  const { result, ...rest } = item
  return {
    record: rest,
    result: result
      ? {
          ...result,
          item_scores: [],
          rule_verdicts: {},
          notes: [],
          findings,
        }
      : null,
    stale: false,
    frontpage: {
      basic: {},
      discharge_diagnoses: [],
      outpatient_diagnoses: [],
      pathology_diagnoses: [],
      surgeries: [],
      cost: null,
    },
  }
}

function makeAnalytics(overrides: Partial<FrontpageQcAnalytics> = {}): FrontpageQcAnalytics {
  return {
    summary: {
      records: 10,
      avg_score: 91.2,
      grades: { excellent: 6, qualified: 3, unqualified: 1 },
      issue_records: 4,
      hint_records: 2,
      required_missing_records: 1,
      data_gap_records: 1,
    },
    indicators: [
      { key: 'completeness', label: '首页填报完整率', numerator: 9, denominator: 10, rate: 0.9 },
    ],
    top_rules: [
      { rule_id: 'C-H21', rule_name: '手术者', severity: 'deduct', group: 'completeness', section: 'diagnosis', records: 3, rate: 0.3 },
    ],
    top_hints: [
      { rule_id: 'C-D12', rule_name: '损伤外部原因', severity: 'hint', group: 'completeness', section: 'diagnosis', records: 2, rate: 0.2 },
    ],
    top_data_gaps: [],
    departments: [
      { department: '内科', records: 10, avg_score: 91.2, excellent_rate: 0.6, issue_records: 4 },
    ],
    ...overrides,
  }
}

function makeRun(overrides: Partial<FrontpageQcRun> = {}): FrontpageQcRun {
  return {
    id: 'run-1',
    status: 'running',
    ruleset_version: '2026.10.13',
    filters: { mode: 'filtered', department: '内科' },
    total_records: 10,
    processed_records: 3,
    success_count: 3,
    failed_count: 0,
    issue_records: 1,
    data_gap_records: 0,
    failed_records: [],
    error_message: null,
    cancel_requested: false,
    created_by: 'u-1',
    created_at: null,
    started_at: null,
    finished_at: null,
    updated_at: null,
    ...overrides,
  }
}

async function createTestRouter(initialPath = '/frontpage-qc') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/frontpage-qc', component: FrontpageQcView }],
  })
  await router.push(initialPath)
  await router.isReady()
  return router
}

describe('Batch C P1-1: frontpage-qc-v2-service 全链路 AbortSignal 与导出 120s 超时', () => {
  afterEach(() => {
    vi.doUnmock('@/services/apiService')
    vi.resetModules()
  })

  it('所有 GET 与导出接口透传 signal，导出超时为 120_000ms，中止错误不被吞成普通错误', async () => {
    vi.resetModules()
    const getRaw = vi.fn().mockResolvedValue({ data: { success: true, data: {} } })
    const postRaw = vi.fn().mockResolvedValue({ data: new Blob(['ok']) })
    vi.doMock('@/services/apiService', () => ({
      ApiService: { getRaw, postRaw },
    }))
    const realSvc = await vi.importActual<typeof import('@/services/frontpage-qc-v2-service')>(
      '@/services/frontpage-qc-v2-service',
    )

    const ac = new AbortController()
    const opt = { signal: ac.signal }

    await realSvc.getFrontpageQcFilters({ data_scope: 'home' }, opt)
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/filters',
      { data_scope: 'home' },
      expect.objectContaining({ signal: ac.signal }),
    )

    await realSvc.listFrontpageQcRecords({ page: 1, page_size: 15 }, opt)
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/records',
      { page: 1, page_size: 15 },
      { signal: ac.signal },
    )

    await realSvc.getFrontpageQcRecord({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' }, opt)
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/record',
      { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' },
      { skipErrorToast: true, signal: ac.signal },
    )

    await realSvc.getFrontpageQcRun('run-9', opt)
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/runs/run-9',
      {},
      { skipErrorToast: true, signal: ac.signal },
    )

    await realSvc.listActiveFrontpageQcRuns(opt)
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/runs',
      { active: true },
      { skipErrorToast: true, signal: ac.signal },
    )

    await realSvc.getFrontpageQcAnalytics({ data_scope: 'all' }, opt)
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/analytics',
      { data_scope: 'all' },
      { signal: ac.signal },
    )

    await realSvc.exportFrontpageQcRecords({ department: '内科' }, opt)
    expect(postRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/records/export',
      { department: '内科' },
      { responseType: 'blob', skipErrorToast: true, timeout: 120_000, signal: ac.signal },
    )

    const canceledErr = Object.assign(new Error('canceled'), { code: 'ERR_CANCELED', name: 'CanceledError' })
    getRaw.mockRejectedValueOnce(canceledErr)
    await expect(realSvc.listFrontpageQcRecords({ page: 1 }, opt)).rejects.toBe(canceledErr)
    expect(realSvc.isFrontpageQcAbortError(canceledErr)).toBe(true)
  })
})

describe('Batch C P1-1: 并行加载、重查/卸载 abort 与 analysis 视图去重', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const r1 = makeRecord('A01')
    svc.listRecords.mockResolvedValue({ items: [r1], total: 1, page: 1, page_size: 15 })
    svc.getRecord.mockResolvedValue(makeDetail(r1))
    svc.getFilters.mockResolvedValue({ departments: ['内科', '外科'], home_institute: 'H-HOME' })
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  it('首屏并行发起 loadFilterOptions 与 loadList，重查和卸载时 abort 在途请求', async () => {
    const listDef1 = deferred<{ items: FrontpageQcRecordItem[]; total: number; page: number; page_size: number }>()
    const filterDef1 = deferred<{ departments: string[]; date_bounds: Record<string, unknown>; home_institute: string }>()
    const summaryDef1 = deferred<FrontpageQcAnalytics>()
    svc.listRecords.mockReturnValueOnce(listDef1.promise)
    svc.getFilters.mockReturnValueOnce(filterDef1.promise)
    svc.getAnalytics.mockReturnValueOnce(summaryDef1.promise)

    const wrapper = mount(FrontpageQcView)
    // 两者在首屏即刻并行触发，不互相等待
    expect(svc.listRecords).toHaveBeenCalledTimes(1)
    expect(svc.getFilters).toHaveBeenCalledTimes(1)
    expect(svc.getAnalytics).toHaveBeenCalledTimes(1)

    const firstListSignal = svc.listRecords.mock.calls[0][1].signal as AbortSignal
    const firstSummarySignal = svc.getAnalytics.mock.calls[0][1].signal as AbortSignal
    const firstFilterSignal = svc.getFilters.mock.calls[0][1].signal as AbortSignal
    expect(firstListSignal.aborted).toBe(false)
    expect(firstSummarySignal.aborted).toBe(false)

    // 重查触发 abort 旧请求
    const listDef2 = deferred<{ items: FrontpageQcRecordItem[]; total: number; page: number; page_size: number }>()
    const summaryDef2 = deferred<FrontpageQcAnalytics>()
    svc.listRecords.mockReturnValueOnce(listDef2.promise)
    svc.getAnalytics.mockReturnValueOnce(summaryDef2.promise)
    await wrapper.get('form').trigger('submit')

    expect(firstListSignal.aborted).toBe(true)
    expect(firstSummarySignal.aborted).toBe(true)

    const secondListSignal = svc.listRecords.mock.calls[1][1].signal as AbortSignal
    const secondSummarySignal = svc.getAnalytics.mock.calls[1][1].signal as AbortSignal
    expect(secondListSignal.aborted).toBe(false)

    // 卸载时 abort 所有在途请求
    wrapper.unmount()
    expect(firstFilterSignal.aborted).toBe(true)
    expect(secondListSignal.aborted).toBe(true)
    expect(secondSummarySignal.aborted).toBe(true)
  })

  it('loadFilterOptions 带序号守卫：先发后到的旧筛选项不会覆盖新范围科室', async () => {
    const firstFilters = deferred<{ departments: string[]; date_bounds: Record<string, unknown>; home_institute: string }>()
    const secondFilters = deferred<{ departments: string[]; date_bounds: Record<string, unknown>; home_institute: string }>()
    svc.getFilters
      .mockResolvedValueOnce({ departments: ['内科'], home_institute: 'H-HOME' })
      .mockReturnValueOnce(firstFilters.promise)
      .mockReturnValueOnce(secondFilters.promise)

    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    // 切换到 all（触发第 2 次 getFilters）
    const switchPromise = wrapper.get('[data-testid="fpqc-scope-all"]').trigger('click')
    firstFilters.resolve({ departments: ['测试旧科'], date_bounds: {}, home_institute: 'H-HOME' })
    await switchPromise
    await flushPromises()
    expect(wrapper.get('[aria-label="科室筛选"]').text()).toContain('测试旧科')

    // 重置回 home（触发第 3 次 getFilters）
    const resetPromise = wrapper.findAll('button').find((b) => b.text() === '重置')!.trigger('click')
    secondFilters.resolve({ departments: ['本院新科'], date_bounds: {}, home_institute: 'H-HOME' })
    await resetPromise
    await flushPromises()
    expect(wrapper.get('[aria-label="科室筛选"]').text()).toContain('本院新科')
    expect(wrapper.get('[aria-label="科室筛选"]').text()).not.toContain('测试旧科')
    wrapper.unmount()
  })

  it('analysis 视图切换 data_scope 与重置仅发出单次 analytics 请求，并卸载时 abort', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    svc.getAnalytics.mockClear()

    // 切到 all：仅 1 次 analytics 请求，且同步刷新顶部指标卡
    svc.getAnalytics.mockResolvedValueOnce(
      makeAnalytics({
        summary: {
          records: 25,
          avg_score: 95,
          grades: { excellent: 20, qualified: 5, unqualified: 0 },
          issue_records: 2,
          hint_records: 0,
          data_gap_records: 0,
        },
      }),
    )
    await wrapper.get('[data-testid="fpqc-scope-all"]').trigger('click')
    await flushPromises()
    expect(svc.getAnalytics).toHaveBeenCalledTimes(1)
    expect(svc.getAnalytics.mock.calls[0][0]).toMatchObject({ data_scope: 'all' })
    expect(wrapper.findAll('.fpqc-metrics__value')[0].text()).toBe('25')

    // 重置回 home：同样仅 1 次 analytics 请求
    svc.getAnalytics.mockClear()
    const resetDef = deferred<FrontpageQcAnalytics>()
    svc.getAnalytics.mockReturnValueOnce(resetDef.promise)
    await wrapper.findAll('button').find((b) => b.text() === '重置')!.trigger('click')
    await flushPromises()
    expect(svc.getAnalytics).toHaveBeenCalledTimes(1)
    expect(svc.getAnalytics.mock.calls[0][0]).toMatchObject({ data_scope: 'home' })

    const analysisSignal = svc.getAnalytics.mock.calls[0][1].signal as AbortSignal
    expect(analysisSignal.aborted).toBe(false)
    wrapper.unmount()
    expect(analysisSignal.aborted).toBe(true)
  })
})

describe('Batch C P1-2: 轮询防锁死、代次/卸载守卫与重新检查恢复', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const r1 = makeRecord('R01')
    svc.listRecords.mockResolvedValue({ items: [r1], total: 1, page: 1, page_size: 15 })
    svc.getRecord.mockResolvedValue(makeDetail(r1))
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: 'H-HOME' })
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function mountRunHook() {
    const onFinished = vi.fn()
    let api!: ReturnType<typeof useFrontpageQcRun>
    const wrapper = mount(
      defineComponent({
        setup() {
          api = useFrontpageQcRun(onFinished)
          return () => null
        },
      }),
    )
    return { api, onFinished, wrapper }
  }

  it('旧 tick 返回不覆写 cancel 状态，卸载后在途 tick 完成不触发 onFinished', async () => {
    const { api, onFinished, wrapper } = mountRunHook()
    const staleTick = deferred<FrontpageQcRun>()
    svc.createRun.mockResolvedValueOnce(makeRun({ id: 'run-a', status: 'running' }))
    svc.getRun.mockReturnValueOnce(staleTick.promise)
    svc.cancelRun.mockResolvedValueOnce(makeRun({ id: 'run-a', status: 'cancelled' }))

    await api.start({ department: '' })
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(svc.getRun).toHaveBeenCalledTimes(1)

    await api.cancel()
    expect(api.run.value?.status).toBe('cancelled')
    expect(onFinished).toHaveBeenCalledTimes(1)

    // 旧 tick 晚到返回 running，不得覆写已取消态
    staleTick.resolve(makeRun({ id: 'run-a', status: 'running', processed_records: 4 }))
    await flushPromises()
    expect(api.run.value?.status).toBe('cancelled')

    // 卸载后在途 tick 完结不得触发 onFinished
    const lateComplete = deferred<FrontpageQcRun>()
    svc.createRun.mockResolvedValueOnce(makeRun({ id: 'run-b', status: 'running' }))
    svc.getRun.mockReturnValueOnce(lateComplete.promise)
    await api.start({ department: '' })
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

    wrapper.unmount()
    lateComplete.resolve(makeRun({ id: 'run-b', status: 'completed' }))
    await flushPromises()
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('cancel() 返回仍为活跃态时调用 schedule() 恢复轮询直到结束', async () => {
    const { api, onFinished, wrapper } = mountRunHook()
    svc.createRun.mockResolvedValueOnce(makeRun({ id: 'run-c', status: 'running' }))
    svc.cancelRun.mockResolvedValueOnce(makeRun({ id: 'run-c', status: 'running', cancel_requested: true }))
    svc.getRun.mockResolvedValueOnce(makeRun({ id: 'run-c', status: 'cancelled', cancel_requested: true }))

    await api.start({ department: '' })
    await api.cancel()
    expect(api.run.value?.cancel_requested).toBe(true)
    expect(onFinished).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(svc.getRun).toHaveBeenCalledTimes(1)
    expect(api.run.value?.status).toBe('cancelled')
    expect(onFinished).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('轮询 403/上限中止后解锁 runBusy、显示“重新检查/关闭”，且刷新同步调用 resume()', async () => {
    svc.createRun.mockResolvedValueOnce(makeRun({ id: 'run-403', status: 'running' }))
    svc.getRun.mockRejectedValueOnce(new FrontpageQcRequestError('无权查看任务进度', 403))

    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    await wrapper.get('[data-testid="fpqc-run-filtered"]').trigger('click')
    await wrapper.get('[data-testid="fpqc-confirm-ok"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="fpqc-run-filtered"]').attributes('disabled')).toBeDefined()

    // 触发一次轮询 -> 403 中止
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    await flushPromises()

    // 不再永久锁死全页质控按钮，进度条渲染“重新检查”与“关闭”
    expect(wrapper.get('[data-testid="fpqc-run-filtered"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-testid="fpqc-run-retry-poll"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="fpqc-run-dismiss"]').exists()).toBe(true)

    // 点击“重新检查”恢复查询进度
    svc.getRun.mockResolvedValueOnce(makeRun({ id: 'run-403', status: 'running', processed_records: 6 }))
    await wrapper.get('[data-testid="fpqc-run-retry-poll"]').trigger('click')
    await flushPromises()
    expect(svc.getRun).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="fpqc-run-bar"]').text()).toContain('6/10')

    // 达到失败上限后允许关闭进度条
    svc.getRun.mockRejectedValue(new FrontpageQcRequestError('网络异常', 0))
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * (MAX_POLL_FAILURES + 1))
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-run-dismiss"]').exists()).toBe(true)
    await wrapper.get('[data-testid="fpqc-run-dismiss"]').trigger('click')
    expect(wrapper.find('[data-testid="fpqc-run-bar"]').exists()).toBe(false)

    // 点击“刷新”同步调用 resume()
    svc.listActive.mockClear()
    await wrapper.findAll('button').find((b) => b.text() === '刷新')!.trigger('click')
    await flushPromises()
    expect(svc.listActive).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})

describe('Batch C P1-3: 复核并发 Set<string>、跨病历隔离、草稿保护与键盘交互', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
  })

  it('支持多条问题并发复核互不覆盖、跨病历完成不误清编辑态', async () => {
    const recA = makeRecord('A')
    const recB = makeRecord('B')
    const f1 = makeFinding('f-1')
    const f2 = makeFinding('f-2')
    const fB = makeFinding('f-b', { problem: '病历B问题' })

    svc.getRecord.mockImplementation(async (ref: { visit_id: string }) =>
      ref.visit_id === 'B' ? makeDetail(recB, [fB]) : makeDetail(recA, [f1, f2]),
    )

    const rev1 = deferred<FrontpageQcFinding>()
    const rev2 = deferred<FrontpageQcFinding>()
    svc.review.mockReturnValueOnce(rev1.promise).mockReturnValueOnce(rev2.promise)

    const wrapper = mount(FrontpageQcPreview, {
      props: { record: recA, refreshKey: 0, runBusy: false },
    })
    await flushPromises()

    const cards = wrapper.findAll('[data-testid="fpqc-finding"]')
    expect(cards).toHaveLength(2)

    // 并发点击两条问题的“确认问题”
    const confirm1 = cards[0].findAll('button').find((b) => b.text() === '确认问题')!
    const confirm2 = cards[1].findAll('button').find((b) => b.text() === '确认问题')!
    await confirm1.trigger('click')
    await confirm2.trigger('click')
    // 两条各自禁用
    expect(confirm1.attributes('disabled')).toBeDefined()
    expect(confirm2.attributes('disabled')).toBeDefined()

    // 第 1 条先完成，第 2 条仍保持禁用
    rev1.resolve({ ...f1, review_status: 'confirmed' })
    await flushPromises()
    expect(wrapper.findAll('[data-testid="fpqc-finding-review-status"]')[0].text()).toBe('已确认')
    const confirm2After = wrapper.findAll('[data-testid="fpqc-finding"]')[1]
      .findAll('button')
      .find((b) => b.text() === '确认问题')!
    expect(confirm2After.attributes('disabled')).toBeDefined()

    // 切换到病历 B 并打开病历 B 的误报草稿
    await wrapper.setProps({ record: recB })
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '标记误报')!.trigger('click')
    await wrapper.get('[data-testid="fpqc-finding"] input').setValue('病历B草稿')

    // 病历 A 的 rev2 晚到完成，不得误清病历 B 的编辑态或篡改 B
    rev2.resolve({ ...f2, review_status: 'confirmed' })
    await flushPromises()
    expect((wrapper.get('[data-testid="fpqc-finding"] input').element as HTMLInputElement).value).toBe('病历B草稿')
    wrapper.unmount()
  })

  it('后台 previewRefreshKey 刷新不清空正在编辑的误报草稿；支持加载失败重试与自动聚焦/Enter/Esc', async () => {
    const rec = makeRecord('C')
    const f1 = makeFinding('f-1')
    svc.getRecord.mockRejectedValueOnce(new Error('详情接口异常'))

    const wrapper = mount(FrontpageQcPreview, {
      props: { record: rec, refreshKey: 0, runBusy: false },
      attachTo: document.body,
    })
    await flushPromises()

    // 加载错误提供重试按钮
    expect(wrapper.get('[role="alert"]').text()).toContain('详情接口异常')
    svc.getRecord.mockResolvedValue(makeDetail(rec, [f1]))
    await wrapper.get('[data-testid="fpqc-preview-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="fpqc-finding"]')).toHaveLength(1)

    // 打开误报输入框自动聚焦
    await wrapper.findAll('button').find((b) => b.text() === '标记误报')!.trigger('click')
    await flushPromises()
    const input = wrapper.get('[data-testid="fpqc-finding"] input')
    expect(document.activeElement).toBe(input.element)

    // 输入草稿期间触发后台刷新，草稿和编辑态必须保留
    await input.setValue('系统同步遗漏字段')
    await wrapper.setProps({ refreshKey: 1 })
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-finding"] input').exists()).toBe(true)
    expect((wrapper.get('[data-testid="fpqc-finding"] input').element as HTMLInputElement).value).toBe('系统同步遗漏字段')

    // Esc 取消编辑
    await wrapper.get('[data-testid="fpqc-finding"] input').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('[data-testid="fpqc-finding"] input').exists()).toBe(false)

    // 再次打开并按 Enter 提交
    svc.review.mockResolvedValueOnce({ ...f1, review_status: 'false_alarm', review_note: '确认误报' })
    await wrapper.findAll('button').find((b) => b.text() === '标记误报')!.trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="fpqc-finding"] input').setValue('确认误报')
    await wrapper.get('[data-testid="fpqc-finding"] input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(svc.review).toHaveBeenCalledWith('f-1', { status: 'false_alarm', note: '确认误报' })
    expect(wrapper.get('[data-testid="fpqc-finding-review-status"]').text()).toBe('误报')
    wrapper.unmount()
  })
})

describe('Batch C P1-4: URL 查询参数双向同步', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const r1 = makeRecord('U01')
    const r2 = makeRecord('U02')
    svc.listRecords.mockImplementation(async (query: { page?: number; page_size?: number }) => ({
      items: [r1, r2],
      total: 40,
      page: query.page ?? 1,
      page_size: query.page_size ?? 15,
    }))
    svc.getRecord.mockImplementation(async (ref: { visit_id: string }) =>
      makeDetail(ref.visit_id === 'U02' ? r2 : r1),
    )
    svc.getFilters.mockResolvedValue({ departments: ['内科', '外科'], home_institute: 'H-HOME' })
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  it('从 URL 初始化 13 个查询参数并同步交互与外部路由变化', async () => {
    const router = await createTestRouter(
      '/frontpage-qc?view=records&data_scope=all&department=%E5%86%85%E7%A7%91&start_date=2026-09-01&end_date=2026-09-30&keyword=%E5%BC%A0%E4%B8%89&grade=qualified&issue=fail&rule_id=C-H21&rule_verdict=fail&page=2&page_size=30&record_key=H-TEST%7CP-U02%7CU02',
    )
    const wrapper = mount(FrontpageQcView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(svc.listRecords).toHaveBeenCalledWith(
      expect.objectContaining({
        data_scope: 'all',
        department: '内科',
        start_date: '2026-09-01',
        end_date: '2026-09-30',
        keyword: '张三',
        grade: 'qualified',
        issue: 'fail',
        rule_id: 'C-H21',
        rule_verdict: 'fail',
        page: 2,
        page_size: 30,
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    // record_key 命中第二条病历
    expect(svc.getRecord).toHaveBeenCalledWith(
      { institute_id: 'H-TEST', patient_id: 'P-U02', visit_id: 'U02' },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    // 切换视图到 analysis -> URL 同步 view=analysis
    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.view).toBe('analysis')

    // 外部路由切回 records 且变更科室为外科 -> 页面双向同步
    await router.replace({
      query: { department: '外科', grade: 'excellent', page: '1' },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-record-table"]').exists()).toBe(true)
    expect(wrapper.get('[aria-label="科室筛选"]').element).toHaveProperty('value', '外科')
    expect(wrapper.get('[aria-label="等级筛选"]').element).toHaveProperty('value', 'excellent')
    expect(svc.listRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({ department: '外科', grade: 'excellent', page: 1 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    // 点击第一条病历 -> URL 同步 record_key
    await wrapper.findAll('[data-testid="fpqc-record-row"]')[0].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.record_key).toBe('H-TEST|P-U01|U01')

    // 在页面内修改筛选与分页 -> URL 通过 router.replace 双向写回
    await wrapper.get('[aria-label="关键词筛选"]').setValue('李四')
    await wrapper.get('#fpqc-start-date').setValue('2026-08-01')
    await wrapper.get('#fpqc-end-date').setValue('2026-08-31')
    await wrapper.get('[aria-label="问题筛选"]').setValue('required_missing')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    wrapper.getComponent({ name: 'Pagination' }).vm.$emit('change', 2, 15)
    await flushPromises()

    expect(router.currentRoute.value.query).toMatchObject({
      department: '外科',
      keyword: '李四',
      start_date: '2026-08-01',
      end_date: '2026-08-31',
      grade: 'excellent',
      issue: 'required_missing',
      page: '2',
    })
    wrapper.unmount()
  })
})

describe('Batch C P1-5: 加载失败保底、筛选口径隐藏与日期区间校验', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const r1 = makeRecord('F01')
    svc.listRecords.mockResolvedValue({ items: [r1], total: 30, page: 1, page_size: 15 })
    svc.getRecord.mockResolvedValue(makeDetail(r1))
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: 'H-HOME' })
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  it('翻页失败保留上次成功列表，点击重试恢复上次请求页码', async () => {
    const r2 = makeRecord('F02')
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    expect(wrapper.findAll('[data-testid="fpqc-record-row"]')).toHaveLength(1)

    // 翻到第 2 页失败
    svc.listRecords.mockRejectedValueOnce(new Error('第2页超时'))
    wrapper.getComponent({ name: 'Pagination' }).vm.$emit('change', 2, 15)
    await flushPromises()

    // 保留第 1 页行数据，同时展示失败提示与重试按钮
    expect(wrapper.findAll('[data-testid="fpqc-record-row"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('第2页超时')

    // 点击重试恢复请求第 2 页
    svc.listRecords.mockResolvedValueOnce({ items: [r2], total: 30, page: 2, page_size: 15 })
    await wrapper.get('[data-testid="fpqc-retry-list"]').trigger('click')
    await flushPromises()

    expect(svc.listRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.text()).toContain('患者F02')
    wrapper.unmount()
  })

  it('analysis 视图隐藏无效筛选，start_date > end_date 展示校验提示并拦截查询', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    // records 视图显示关键词/等级/问题筛选
    expect(wrapper.find('[aria-label="关键词筛选"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="等级筛选"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="问题筛选"]').exists()).toBe(true)

    // 日期区间非法时显示提示且不发出查询
    const callsBefore = svc.listRecords.mock.calls.length
    await wrapper.get('#fpqc-start-date').setValue('2026-10-15')
    await wrapper.get('#fpqc-end-date').setValue('2026-10-01')
    expect(wrapper.get('[data-testid="fpqc-date-error"]').text()).toContain('开始日期不能晚于结束日期')

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(svc.listRecords).toHaveBeenCalledTimes(callsBefore)

    // 修正日期后提示消失且允许查询
    await wrapper.get('#fpqc-end-date').setValue('2026-10-20')
    expect(wrapper.find('[data-testid="fpqc-date-error"]').exists()).toBe(false)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(svc.listRecords).toHaveBeenCalledTimes(callsBefore + 1)

    // 切到 analysis 视图隐藏关键词/等级/问题筛选，保留科室与日期
    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[aria-label="关键词筛选"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="等级筛选"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="问题筛选"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="科室筛选"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="出院日期范围"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('FrontpageQcAnalysisPanel 刷新失败保留已有统计数据，且空榜标题不显示 Top 0', async () => {
    svc.getAnalytics.mockResolvedValueOnce(
      makeAnalytics({
        top_rules: [],
        top_hints: [],
      }),
    )

    const panel = mount(FrontpageQcAnalysisPanel, {
      props: { filters: { data_scope: 'home', department: '', start_date: '', end_date: '' }, refreshKey: 0 },
    })
    await flushPromises()

    expect(panel.text()).toContain('首页填报完整率')
    expect(panel.text()).not.toContain('Top 0')
    expect(panel.text()).toContain('扣分问题')
    expect(panel.text()).toContain('提示')

    // 刷新失败时保留原有统计数据并展示错误提示与重试按钮
    svc.getAnalytics.mockRejectedValueOnce(new Error('统计服务繁忙'))
    await panel.setProps({ refreshKey: 1 })
    await flushPromises()

    expect(panel.get('[role="alert"]').text()).toContain('统计服务繁忙')
    expect(panel.find('[data-testid="fpqc-retry-analysis"]').exists()).toBe(true)
    expect(panel.text()).toContain('首页填报完整率')
    expect(panel.findAll('[data-testid="fpqc-indicator"]')).toHaveLength(1)
    panel.unmount()
  })
})
