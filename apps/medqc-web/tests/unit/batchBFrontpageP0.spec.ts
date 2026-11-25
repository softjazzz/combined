import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import type {
  FrontpageQcAnalytics,
  FrontpageQcFinding,
  FrontpageQcIssueFilter,
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
  Pagination: { name: 'Pagination', template: '<nav />' },
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
  user: { id: 'demo-user', institute_id: '', roles: ['admin'], is_demo_account: true },
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

import FrontpageQcAnalysisPanel from '@/views/workstation-v4/frontpage-qc/FrontpageQcAnalysisPanel.vue'
import FrontpageQcPreview from '@/views/workstation-v4/frontpage-qc/FrontpageQcPreview.vue'
import FrontpageQcRecordTable from '@/views/workstation-v4/frontpage-qc/FrontpageQcRecordTable.vue'
import FrontpageQcRunBar from '@/views/workstation-v4/frontpage-qc/FrontpageQcRunBar.vue'
import FrontpageQcView from '@/views/workstation-v4/frontpage-qc/FrontpageQcView.vue'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function makeRecord(
  alias: string,
  overrides: Partial<FrontpageQcRecordItem> = {},
  resultOverrides: Partial<NonNullable<FrontpageQcRecordItem['result']>> = {},
): FrontpageQcRecordItem {
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
    discharge_date: '2026-09-01',
    result: {
      id: `res-${alias}`,
      run_id: 'run-0',
      record_key: key,
      department: '内科',
      discharge_date: '2026-09-01',
      score: 88,
      grade: 'qualified',
      fail_count: 1,
      hint_count: 2,
      required_missing_count: 1,
      data_gap_count: 1,
      scorable_ratio: 0.92,
      completeness_rate: 0.95,
      ruleset_version: '2026.10.13',
      created_at: '2026-10-13T08:00:00',
      ...resultOverrides,
    },
    ...overrides,
  }
}

function makeFinding(overrides: Partial<FrontpageQcFinding> = {}): FrontpageQcFinding {
  return {
    id: 'f-1',
    rule_id: 'C-H21',
    rule_name: '手术者',
    group: 'completeness',
    section: 'diagnosis',
    severity: 'deduct',
    score_item: 'surgeon',
    verdict: 'fail',
    problem: '手术者未填写',
    reason: '',
    details: [{ field: '第1条手术 手术者', value: '', expected: '填写手术者姓名', item_index: 0 }],
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
  findings: FrontpageQcFinding[] = [
    makeFinding(),
    makeFinding({
      id: 'f-hint',
      rule_id: 'C-D12',
      rule_name: '损伤外部原因',
      severity: 'hint',
      verdict: 'fail',
      problem: '请核实损伤外部原因',
      deduction: 0,
    }),
    makeFinding({
      id: 'f-gap',
      rule_id: 'C-H30',
      rule_name: '编码员',
      severity: 'deduct',
      verdict: 'data_gap',
      problem: '编码员字段缺失',
      reason: '首页同步未带入编码员字段',
      deduction: 0,
    }),
  ],
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
      avg_score: 89.5,
      grades: { excellent: 5, qualified: 4, unqualified: 1 },
      issue_records: 5,
      hint_records: 3,
      required_missing_records: 2,
      data_gap_records: 4,
    },
    indicators: [
      { key: 'completeness', label: '首页填报完整率', numerator: 8, denominator: 10, rate: 0.8 },
    ],
    top_rules: [
      { rule_id: 'C-H21', rule_name: '手术者', severity: 'deduct', group: 'completeness', section: 'diagnosis', records: 3, rate: 0.3 },
    ],
    top_hints: [
      { rule_id: 'C-D12', rule_name: '损伤外部原因', severity: 'hint', group: 'completeness', section: 'diagnosis', records: 2, rate: 0.2 },
    ],
    top_data_gaps: [
      { rule_id: 'C-H30', rule_name: '编码员', severity: 'deduct', group: 'completeness', section: 'hospitalization', records: 4, rate: 0.4 },
    ],
    departments: [
      { department: '未填科室', records: 2, avg_score: 75, excellent_rate: 0, issue_records: 2 },
      { department: '内科', records: 8, avg_score: 91, excellent_rate: 0.625, issue_records: 3 },
    ],
    ...overrides,
  }
}

function makeRun(overrides: Partial<FrontpageQcRun> = {}): FrontpageQcRun {
  return {
    id: 'run-1',
    status: 'completed_with_errors',
    ruleset_version: '2026.10.13',
    filters: { mode: 'filtered', department: '内科', data_scope: 'all' },
    total_records: 10,
    processed_records: 10,
    success_count: 9,
    failed_count: 1,
    issue_records: 2,
    data_gap_records: 0,
    failed_records: [
      {
        institute_id: 'H-TEST',
        patient_id: 'P-ERR',
        visit_id: 'V-ERR',
        error: 'SQLOperationalError',
        message: '内部数据库连接异常',
      },
    ],
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

describe('Batch B Frontpage QC P0: 演示账号全模块隔离与范围切换权限', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const row1 = makeRecord('A01')
    const row2 = makeRecord('A02', {}, { fail_count: 0, required_missing_count: 0, hint_count: 3, data_gap_count: 1 })
    svc.listRecords.mockResolvedValue({ items: [row1, row2], total: 2, page: 1, page_size: 15 })
    svc.getRecord.mockImplementation(async (ref: { visit_id: string }) => {
      const target = ref.visit_id === 'A02' ? row2 : row1
      return makeDetail(target)
    })
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: 'H-HOME' })
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  it('演示账号在 FrontpageQcView / Table / Preview / Analysis / RunBar 中完整隔离内部与非确定项', async () => {
    testAuth.user = { id: 'demo-admin', institute_id: '', roles: ['admin'], is_demo_account: true }
    testAuth.userRoles = ['admin']

    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    // 1. FrontpageQcView: 隐藏范围切换、hint/data_gap 筛选选项、确认弹窗数据范围
    expect(wrapper.find('[aria-label="数据范围"]').exists()).toBe(false)
    const issueSelect = wrapper.get('[aria-label="问题筛选"]')
    expect(issueSelect.find('option[value="hint"]').exists()).toBe(false)
    expect(issueSelect.find('option[value="data_gap"]').exists()).toBe(false)
    expect(issueSelect.find('option[value="fail"]').exists()).toBe(true)
    expect(issueSelect.find('option[value="required_missing"]').exists()).toBe(true)

    await wrapper.get('[data-testid="fpqc-run-filtered"]').trigger('click')
    expect(wrapper.get('[data-testid="fpqc-confirm"]').text()).not.toContain('数据范围')
    await wrapper.get('[data-testid="fpqc-confirm"]').find('button').trigger('click')

    // 2. FrontpageQcRecordTable: 隐藏“提示”徽标；仅含提示时显示“无”
    const rows = wrapper.findAll('[data-testid="fpqc-record-row"]')
    expect(rows[0].find('[data-testid="fpqc-issue-hint"]').exists()).toBe(false)
    expect(rows[0].text()).toContain('扣分 1')
    expect(rows[0].text()).toContain('必填缺项 1')
    expect(rows[1].find('[data-testid="fpqc-issue-hint"]').exists()).toBe(false)
    expect(rows[1].findAll('td')[6].text().trim()).toBe('无')

    // 3. FrontpageQcPreview: 隐藏 scorable_ratio、提示/资料不足计数及折叠块与同步排查原因
    const preview = wrapper.get('[data-testid="fpqc-preview"]')
    expect(preview.find('[data-testid="fpqc-preview-scorable-ratio"]').exists()).toBe(false)
    expect(preview.text()).not.toContain('可评分项')
    expect(preview.find('[data-testid="fpqc-preview-hints"]').exists()).toBe(false)
    expect(preview.find('[data-testid="fpqc-preview-data-gaps"]').exists()).toBe(false)
    expect(preview.text()).not.toContain('首页同步未带入编码员字段')
    expect(preview.get('[aria-label="问题数量"]').findAll('dt').map((n) => n.text())).toEqual(['扣分问题', '必填缺项'])

    // 4. FrontpageQcAnalysisPanel: 隐藏“提示 Top”和“资料不足来源”
    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-analysis-hints"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="fpqc-analysis-data-gaps"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="fpqc-analysis"]').text()).toContain('扣分问题 Top 1')
    expect(wrapper.get('[data-testid="fpqc-analysis"]').text()).toContain('科室排名')
    wrapper.unmount()

    // 5. FrontpageQcRunBar: 隐藏 failed_records 内部报错明细与“含测试数据”标题片段
    const runBar = mount(FrontpageQcRunBar, {
      props: { run: makeRun(), error: '', cancelling: false },
    })
    expect(runBar.find('[data-testid="fpqc-run-failed-details"]').exists()).toBe(false)
    expect(runBar.text()).not.toContain('内部数据库连接异常')
    expect(runBar.text()).not.toContain('含测试数据')
    runBar.unmount()
  })

  it('非演示账号展示完整提示/资料不足/可评分项/失败明细，且仅跨机构全局管理员可见数据范围切换', async () => {
    // 1. 绑定院区的 admin（非演示）不可见范围切换
    testAuth.user = { id: 'bound-admin', institute_id: 'H-01', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const boundAdminView = mount(FrontpageQcView)
    await flushPromises()
    expect(boundAdminView.find('[aria-label="数据范围"]').exists()).toBe(false)
    expect(boundAdminView.get('[aria-label="问题筛选"]').find('option[value="hint"]').exists()).toBe(true)
    expect(boundAdminView.get('[aria-label="问题筛选"]').find('option[value="data_gap"]').exists()).toBe(true)
    expect(boundAdminView.find('[data-testid="fpqc-preview-scorable-ratio"]').exists()).toBe(true)
    expect(boundAdminView.find('[data-testid="fpqc-preview-hints"]').exists()).toBe(true)
    expect(boundAdminView.find('[data-testid="fpqc-preview-data-gaps"]').exists()).toBe(true)
    boundAdminView.unmount()

    // 2. 绑定院区的 super_admin 不可见范围切换
    testAuth.user = { id: 'bound-super', institute_id: 'H-01', roles: ['super_admin'], is_demo_account: false }
    testAuth.userRoles = ['super_admin']
    const boundSuperView = mount(FrontpageQcView)
    await flushPromises()
    expect(boundSuperView.find('[aria-label="数据范围"]').exists()).toBe(false)
    boundSuperView.unmount()

    // 3. qc_manager 不可见范围切换
    testAuth.user = { id: 'qc-mgr', institute_id: '', roles: ['qc_manager'], is_demo_account: false }
    testAuth.userRoles = ['qc_manager']
    const qcMgrView = mount(FrontpageQcView)
    await flushPromises()
    expect(qcMgrView.find('[aria-label="数据范围"]').exists()).toBe(false)
    qcMgrView.unmount()

    // 4. 未绑定院区的全局 admin（非演示）可见范围切换
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const globalAdminView = mount(FrontpageQcView)
    await flushPromises()
    expect(globalAdminView.find('[aria-label="数据范围"]').exists()).toBe(true)
    globalAdminView.unmount()

    // 5. sync_admin（即使带演示标记或机构号）属于跨机构全局管理员且可见全部结果与范围切换
    testAuth.user = { id: 'sync-1', institute_id: 'H-01', roles: ['sync_admin'], is_demo_account: true }
    testAuth.userRoles = ['sync_admin']
    const syncView = mount(FrontpageQcView)
    await flushPromises()
    expect(syncView.find('[aria-label="数据范围"]').exists()).toBe(true)
    await syncView.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    expect(syncView.find('[data-testid="fpqc-analysis-hints"]').exists()).toBe(true)
    expect(syncView.find('[data-testid="fpqc-analysis-data-gaps"]').exists()).toBe(true)
    syncView.unmount()

    const runBar = mount(FrontpageQcRunBar, {
      props: { run: makeRun(), error: '', cancelling: false },
    })
    expect(runBar.find('[data-testid="fpqc-run-failed-details"]').exists()).toBe(true)
    expect(runBar.text()).toContain('内部数据库连接异常')
    expect(runBar.text()).toContain('含测试数据')
    runBar.unmount()
  })

  it('演示账号在 FrontpageQcRecordTable 仅展示确定问题，提示数不阻断“无”展示', () => {
    testAuth.user = { id: 'demo-user', roles: ['coder'], is_demo_account: true }
    testAuth.userRoles = ['coder']
    const hintOnly = makeRecord('H01', {}, { fail_count: 0, required_missing_count: 0, hint_count: 4 })
    const table = mount(FrontpageQcRecordTable, {
      props: { rows: [hintOnly], selected: [], activeKey: hintOnly.record_key, emptyMessage: '' },
    })
    expect(table.find('[data-testid="fpqc-issue-hint"]').exists()).toBe(false)
    expect(table.findAll('td')[6].text().trim()).toBe('无')
    table.unmount()
  })
})

describe('Batch B Frontpage QC P0: 预览区切病历防跨病历错位', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
  })

  it('切换病历瞬间清空旧详情与得分，杜绝新患者名配旧患者分数，并拒绝错位响应', async () => {
    const recA = makeRecord('P1', { patient_name: '张三' }, { score: 96, grade: 'excellent' })
    const recB = makeRecord('P2', { patient_name: '李四' }, { score: 62, grade: 'unqualified' })
    const reqA = deferred<FrontpageQcRecordDetail>()
    const reqB = deferred<FrontpageQcRecordDetail>()
    svc.getRecord.mockReturnValueOnce(reqA.promise).mockReturnValueOnce(reqB.promise)

    const wrapper = mount(FrontpageQcPreview, {
      props: { record: recA, refreshKey: 0, runBusy: false },
    })

    reqA.resolve(makeDetail(recA))
    await flushPromises()
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.get('[data-testid="fpqc-preview-score"]').text()).toBe('96')

    // 切换到李四，B 的请求尚未返回
    await wrapper.setProps({ record: recB })
    expect(wrapper.text()).toContain('李四')
    expect(wrapper.find('[data-testid="fpqc-preview-score"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('正在读取质控结果')

    // 即使后端错误地返回了张三的 detail，也因 record_key 校验不通过而不展示旧分数
    reqB.resolve(makeDetail(recA))
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-preview-score"]').exists()).toBe(false)

    // 刷新后拿到正确匹配的李四 detail 才展示 62 分
    svc.getRecord.mockResolvedValueOnce(makeDetail(recB))
    await wrapper.setProps({ refreshKey: 1 })
    await flushPromises()
    expect(wrapper.get('[data-testid="fpqc-preview-score"]').text()).toBe('62')
    wrapper.unmount()
  })

  it('加载中清空 props.record 为 null 时立即重置 loading 与错误状态', async () => {
    const recA = makeRecord('P3', { patient_name: '王五' }, { score: 85 })
    const pending = deferred<FrontpageQcRecordDetail>()
    svc.getRecord.mockReturnValueOnce(pending.promise)

    const wrapper = mount(FrontpageQcPreview, {
      props: { record: recA, refreshKey: 0, runBusy: false },
    })
    expect(wrapper.text()).toContain('正在读取质控结果')

    await wrapper.setProps({ record: null })
    expect(wrapper.text()).toContain('点击左侧任一病历')
    expect(wrapper.text()).not.toContain('正在读取质控结果')

    // 旧请求失败也不影响已清空状态
    pending.reject(new Error('late error'))
    await flushPromises()
    expect(wrapper.text()).not.toContain('late error')
    wrapper.unmount()
  })
})

describe('Batch B Frontpage QC P0: 分析页“未填科室”禁用下钻', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: '' })
    svc.listRecords.mockResolvedValue({ items: [makeRecord('D1')], total: 1, page: 1, page_size: 15 })
    svc.getRecord.mockResolvedValue(makeDetail(makeRecord('D1')))
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  it('分析面板对“未填科室”和空科室禁用下钻按钮并给出提示，正常科室可点击下钻', async () => {
    svc.getAnalytics.mockResolvedValueOnce(
      makeAnalytics({
        departments: [
          { department: '未填科室', records: 2, avg_score: 75, excellent_rate: 0, issue_records: 2 },
          { department: '   ', records: 1, avg_score: 80, excellent_rate: 0, issue_records: 1 },
          { department: '内科', records: 5, avg_score: 92, excellent_rate: 0.8, issue_records: 1 },
        ],
      }),
    )

    const panel = mount(FrontpageQcAnalysisPanel, {
      props: { filters: { data_scope: 'home', department: '', start_date: '', end_date: '' }, refreshKey: 0 },
    })
    await flushPromises()

    const drillButtons = panel.findAll('[data-testid="fpqc-drill-department"]')
    expect(drillButtons).toHaveLength(1)
    expect(drillButtons[0].text()).toBe('内科')

    const unfilled = panel.findAll('[data-testid="fpqc-department-unfilled"]')
    expect(unfilled).toHaveLength(2)
    expect(unfilled[0].element.tagName).toBe('SPAN')
    expect(unfilled[0].attributes('title')).toContain('暂不支持按科室下钻')
    await unfilled[0].trigger('click')
    expect(panel.emitted('drill-department')).toBeUndefined()

    await drillButtons[0].trigger('click')
    expect(panel.emitted('drill-department')).toEqual([['内科']])
    panel.unmount()
  })

  it('FrontpageQcView 即使收到“未填科室”下钻事件也拒绝写入 draft.department', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()

    const listCallsBefore = svc.listRecords.mock.calls.length
    const panel = wrapper.getComponent(FrontpageQcAnalysisPanel)
    panel.vm.$emit('drill-department', '未填科室')
    panel.vm.$emit('drill-department', '')
    await flushPromises()

    expect(wrapper.find('[data-testid="fpqc-analysis"]').exists()).toBe(true)
    expect(svc.listRecords.mock.calls.length).toBe(listCallsBefore)
    expect(wrapper.get('[aria-label="科室筛选"]').element).toHaveProperty('value', '')
    wrapper.unmount()
  })
})

describe('Batch B Frontpage QC P0: apiService 拦截器与 frontpage-qc-v2-service 错误协议', () => {
  afterEach(() => {
    vi.doUnmock('axios')
    vi.doUnmock('@/services/apiService')
    vi.resetModules()
  })

  async function loadRealApiService() {
    vi.resetModules()
    mockMessageError.mockClear()
    let responseRejected: ((error: any) => Promise<any>) | undefined

    const apiClientMock: any = vi.fn(async (cfg: any) => ({ status: 200, data: { retried: true }, config: cfg }))
    apiClientMock.interceptors = {
      request: { use: vi.fn(() => 0) },
      response: {
        use: vi.fn((_fulfilled: any, rejected: any) => {
          responseRejected = rejected
          return 0
        }),
      },
    }
    apiClientMock.get = vi.fn()
    apiClientMock.post = vi.fn()
    apiClientMock.put = vi.fn()
    apiClientMock.delete = vi.fn()

    const axiosMock = {
      create: vi.fn(() => apiClientMock),
      post: vi.fn(),
    }

    vi.doMock('axios', () => ({ default: axiosMock }))
    const { ApiService } = await import('@/services/apiService')
    return { ApiService, responseRejected: responseRejected!, apiClientMock, axiosMock }
  }

  it('对象型 data.error（409 { message, run }）正确提取中文 message，绝不产生 [object Object]', async () => {
    const { responseRejected } = await loadRealApiService()
    const errorLog = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    try {
      const err = {
        config: { method: 'post', url: '/api/v1/other-endpoint' },
        response: {
          status: 409,
          data: {
            success: false,
            error: {
              message: '已有进行中的首页质控任务，请等待完成或取消后再发起',
              run: { id: 'run-active', status: 'running' },
            },
          },
        },
        message: 'Request failed with status code 409',
      }
      await expect(responseRejected(err)).rejects.toBe(err)
      expect(mockMessageError).toHaveBeenCalledTimes(1)
      expect(mockMessageError).toHaveBeenCalledWith(
        '请求失败: 已有进行中的首页质控任务，请等待完成或取消后再发起',
      )
      expect(String(mockMessageError.mock.calls[0][0])).not.toContain('[object Object]')
    } finally {
      errorLog.mockRestore()
    }
  })

  it('skipErrorToast: true 抑制全局弹窗（含 409/422 Blob/500/网络异常），并保留 traceId 与 401 刷新能力', async () => {
    const { responseRejected, axiosMock, apiClientMock } = await loadRealApiService()
    const errorLog = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    try {
      // 409 / 422 Blob / 500 / ERR_NETWORK with skipErrorToast: true -> 0 toasts
      const cases = [
        {
          config: { method: 'post', url: '/api/v1/frontpage-qc/runs', skipErrorToast: true },
          response: { status: 409, headers: { 'x-trace-id': 'tr-409' }, data: { error: { message: '冲突' } } },
        },
        {
          config: { method: 'post', url: '/api/v1/frontpage-qc/records/export', responseType: 'blob', skipErrorToast: true },
          response: { status: 422, data: new Blob([JSON.stringify({ error: '当前范围内没有已质控的首页' })]) },
          message: 'Request failed with status code 422',
        },
        {
          config: { method: 'get', url: '/api/v1/frontpage-qc/runs/run-1', skipErrorToast: true },
          code: 'ERR_NETWORK',
          message: 'Network Error',
        },
      ]
      for (const err of cases) {
        await expect(responseRejected(err)).rejects.toBe(err)
      }
      expect(mockMessageError).not.toHaveBeenCalled()
      expect((cases[0] as any).traceId).toBe('tr-409')

      // 401 token refresh still works when skipErrorToast: true
      localStorage.setItem('medqc_refresh_token', 'valid-refresh')
      axiosMock.post.mockResolvedValueOnce({
        data: { access_token: 'new-access', refresh_token: 'new-refresh' },
      })
      const retryErr = {
        config: { method: 'get', url: '/api/v1/frontpage-qc/record', headers: {}, skipErrorToast: true },
        response: { status: 401, data: { detail: 'expired' } },
      }
      const retried = await responseRejected(retryErr)
      expect(retried).toMatchObject({ status: 200, data: { retried: true } })
      expect(apiClientMock).toHaveBeenCalledTimes(1)
      expect(mockMessageError).not.toHaveBeenCalled()
    } finally {
      localStorage.clear()
      errorLog.mockRestore()
    }
  })

  it('/api/v1/workstation/analytics/luxian-0609 加入 pageOwnedGet：5xx/网络/超时/取消不弹全局错，403 仍提示', async () => {
    const { responseRejected } = await loadRealApiService()
    const errorLog = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    try {
      for (const err of [
        { config: { method: 'get', url: '/api/v1/workstation/analytics/luxian-0609' }, response: { status: 503 } },
        { config: { method: 'get', url: '/api/v1/workstation/analytics/luxian-0609' }, code: 'ERR_NETWORK' },
        { config: { method: 'get', url: '/api/v1/workstation/analytics/luxian-0609' }, code: 'ECONNABORTED' },
        { config: { method: 'get', url: '/api/v1/workstation/analytics/luxian-0609' }, code: 'ERR_CANCELED' },
      ]) {
        await expect(responseRejected(err)).rejects.toBe(err)
      }
      expect(mockMessageError).not.toHaveBeenCalled()

      const forbidden = {
        config: { method: 'get', url: '/api/v1/workstation/analytics/luxian-0609' },
        response: { status: 403, data: { error: '无统计权限' } },
      }
      await expect(responseRejected(forbidden)).rejects.toBe(forbidden)
      expect(mockMessageError).toHaveBeenCalledTimes(1)
      expect(mockMessageError).toHaveBeenCalledWith('权限不足：无统计权限')
    } finally {
      errorLog.mockRestore()
    }
  })

  it('frontpage-qc-v2-service 对页内自处理接口透传 skipErrorToast: true 且补齐 required_missing 类型', async () => {
    vi.resetModules()
    const getRaw = vi.fn().mockResolvedValue({ data: { success: true, data: {} } })
    const postRaw = vi.fn().mockResolvedValue({ data: { success: true, data: {} } })
    vi.doMock('@/services/apiService', () => ({
      ApiService: { getRaw, postRaw },
    }))
    const realSvc = await vi.importActual<typeof import('@/services/frontpage-qc-v2-service')>(
      '@/services/frontpage-qc-v2-service',
    )

    // 类型回归校验：required_missing 和 required_missing_records 可无断言直接赋值
    const issue: FrontpageQcIssueFilter = 'required_missing'
    const analyticsSummary: FrontpageQcAnalytics['summary'] = {
      records: 1,
      avg_score: 90,
      grades: { excellent: 1, qualified: 0, unqualified: 0 },
      issue_records: 0,
      hint_records: 0,
      required_missing_records: 1,
      data_gap_records: 0,
    }
    expect(issue).toBe('required_missing')
    expect(analyticsSummary.required_missing_records).toBe(1)

    await realSvc.createFrontpageQcRun({ department: '内科' })
    expect(postRaw).toHaveBeenLastCalledWith('/api/v1/frontpage-qc/runs', { department: '内科' }, { skipErrorToast: true })

    await realSvc.getFrontpageQcRun('run-123')
    expect(getRaw).toHaveBeenLastCalledWith('/api/v1/frontpage-qc/runs/run-123', {}, { skipErrorToast: true })

    await realSvc.listActiveFrontpageQcRuns()
    expect(getRaw).toHaveBeenLastCalledWith('/api/v1/frontpage-qc/runs', { active: true }, { skipErrorToast: true })

    await realSvc.cancelFrontpageQcRun('run-123')
    expect(postRaw).toHaveBeenLastCalledWith('/api/v1/frontpage-qc/runs/run-123/cancel', {}, { skipErrorToast: true })

    await realSvc.getFrontpageQcRecord({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' })
    expect(getRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/record',
      { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' },
      { skipErrorToast: true },
    )

    await realSvc.reviewFrontpageQcFinding('f-1', { status: 'confirmed', note: '' })
    expect(postRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/findings/f-1/review',
      { status: 'confirmed', note: '' },
      { skipErrorToast: true },
    )

    const blobErrBody = new Blob([JSON.stringify({ success: false, error: '当前范围内没有已质控的首页，无法导出' })], {
      type: 'application/json',
    })
    postRaw.mockRejectedValueOnce(
      Object.assign(new Error('Request failed with status code 422'), {
        response: { status: 422, data: blobErrBody },
      }),
    )
    await expect(realSvc.exportFrontpageQcRecords({ department: '内科' })).rejects.toThrow(
      '当前范围内没有已质控的首页，无法导出',
    )
    expect(postRaw).toHaveBeenLastCalledWith(
      '/api/v1/frontpage-qc/records/export',
      { department: '内科' },
      { responseType: 'blob', skipErrorToast: true, timeout: 120_000 },
    )
  })
})
