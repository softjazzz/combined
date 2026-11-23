import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  FrontpageQcFinding,
  FrontpageQcRecordDetail,
  FrontpageQcRecordItem,
} from '@/services/frontpage-qc-v2-service'

// 脚本化服务：只用合成病例 C01/C02，不连接后端、不调用模型
const svc = {
  listRecords: vi.fn(),
  getRecord: vi.fn(),
  getFilters: vi.fn(),
  getAnalytics: vi.fn(),
  createRun: vi.fn(),
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
    exportFrontpageQcRecords: (...a: unknown[]) => svc.exportRecords(...a),
    listActiveFrontpageQcRuns: (...a: unknown[]) => svc.listActive(...a),
    reviewFrontpageQcFinding: (...a: unknown[]) => svc.review(...a),
  }
})
vi.mock('ant-design-vue', async (importOriginal) => ({
  ...await importOriginal<typeof import('ant-design-vue')>(),
  Modal: {
    name: 'Modal',
    props: ['open'],
    emits: ['cancel'],
    template: '<div v-if="open" class="modal-stub"><slot /></div>',
  },
  Pagination: { name: 'Pagination', template: '<nav />' },
  message: { error: vi.fn(), success: vi.fn() },
}))

vi.mock('../../customer-sample-validation/batchExport', () => ({ downloadBlob: vi.fn() }))

const testAuth = reactive({ user: { id: 'synthetic-admin', institute_id: 'H-TEST', roles: ['admin'] }, userRoles: ['admin'] })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => testAuth }))

import FrontpageQcView from '../FrontpageQcView.vue'
import { downloadBlob } from '../../customer-sample-validation/batchExport'

function record(alias: string, withResult: boolean): FrontpageQcRecordItem {
  return {
    institute_id: 'H-TEST',
    patient_id: `P-${alias}`,
    visit_id: alias,
    record_key: `H-TEST|P-${alias}|${alias}`,
    patient_name: alias,
    inpat_no: alias,
    mr_no: alias,
    department: '内科',
    doctor: '',
    discharge_date: '2026-09-01',
    result: withResult
      ? {
          id: `res-${alias}`,
          run_id: 'run-0',
          record_key: `H-TEST|P-${alias}|${alias}`,
          department: '内科',
          discharge_date: '2026-09-01',
          score: 88,
          grade: 'qualified',
          fail_count: 1,
          hint_count: 0,
          required_missing_count: 0,
          data_gap_count: 0,
          scorable_ratio: 1,
          completeness_rate: 0.98,
          ruleset_version: '2026.10.13',
          created_at: '2026-10-13T08:00:00',
        }
      : null,
  }
}

const finding: FrontpageQcFinding = {
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
}

function detailFor(item: FrontpageQcRecordItem): FrontpageQcRecordDetail {
  const { result, ...rest } = item
  return {
    record: rest,
    result: result ? { ...result, item_scores: [], rule_verdicts: {}, notes: [], findings: [{ ...finding }] } : null,
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

const rows = [record('C01', true), record('C02', false)]

beforeEach(() => {
    vi.resetAllMocks()
    testAuth.user.id = 'synthetic-admin'
    svc.listRecords.mockResolvedValue({ items: rows, total: 2, page: 1, page_size: 15 })
    svc.getRecord.mockImplementation(async (ref: { visit_id: string }) =>
      detailFor(rows.find((row) => row.visit_id === ref.visit_id)!),
    )
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: '' })
    svc.exportRecords.mockResolvedValue(new Blob())
    svc.getAnalytics.mockResolvedValue({
      summary: { records: 1, avg_score: 88, grades: { excellent: 0, qualified: 1, unqualified: 0 }, issue_records: 1, hint_records: 0, data_gap_records: 0 },
      indicators: [],
      top_rules: [],
      top_hints: [],
      top_data_gaps: [],
      departments: [],
    })
    svc.listActive.mockResolvedValue({ items: [] })
  })

describe('FrontpageQcView', () => {
  it('无法识别本院时隐藏范围切换，仍按本院默认范围加载', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    expect(wrapper.find('[aria-label="数据范围"]').exists()).toBe(false)
    expect(svc.listRecords).toHaveBeenCalledWith(expect.objectContaining({ data_scope: 'home' }))
    expect(wrapper.findAll('[data-testid="fpqc-record-row"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('首页质控只有一页时也能调整每页条数，空结果时隐藏分页', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    const pagination = wrapper.getComponent({ name: 'Pagination' })

    svc.listRecords.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 30 })
    pagination.vm.$emit('change', 1, 30)
    await flushPromises()

    expect(svc.listRecords).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, page_size: 30 }))
    expect(wrapper.findComponent({ name: 'Pagination' }).exists()).toBe(false)
    wrapper.unmount()
  })

  it('首页质控摘要读取失败时保留病历结果，未知计数显示为占位符', async () => {
    svc.getAnalytics.mockRejectedValueOnce(new Error('合成摘要失败'))
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('质控摘要暂不可用')
    expect(wrapper.findAll('[data-testid="fpqc-record-row"]')).toHaveLength(2)
    expect(wrapper.findAll('.fpqc-metrics__value').map((value) => value.text())).toEqual(['—', '—', '—', '—'])
    await wrapper.get('[data-testid="fpqc-retry-summary"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-retry-summary"]').exists()).toBe(false)
    expect(svc.listRecords).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('结果分析读取失败时只显示分析页的提示，重试只刷新分析', async () => {
    svc.getAnalytics
      .mockRejectedValueOnce(new Error('合成摘要失败'))
      .mockRejectedValueOnce(new Error('合成分析失败'))
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    const alerts = wrapper.findAll('[role="alert"]')
    expect(alerts).toHaveLength(1)
    expect(alerts[0].text()).toContain('合成分析失败')
    expect(wrapper.find('[data-testid="fpqc-retry-summary"]').exists()).toBe(false)

    await wrapper.get('[data-testid="fpqc-retry-analysis"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-retry-analysis"]').exists()).toBe(false)
    expect(wrapper.findAll('.fpqc-metrics__value').map((value) => value.text())).not.toEqual(['—', '—', '—', '—'])
    expect(svc.getAnalytics).toHaveBeenCalledTimes(3)
    expect(svc.listRecords).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('识别本院时显示范围切换，首次列表和指标使用本院范围', async () => {
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: 'H-HOME' })
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    expect(wrapper.get('[data-testid="fpqc-scope-home"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="fpqc-scope-all"]').attributes('aria-pressed')).toBe('false')
    expect(svc.getFilters).toHaveBeenCalledWith({ data_scope: 'home' })
    expect(svc.listRecords.mock.calls[0][0]).toMatchObject({ data_scope: 'home', page: 1 })
    expect(svc.getAnalytics).toHaveBeenCalledWith(expect.objectContaining({ data_scope: 'home' }))
    wrapper.unmount()
  })

  it('切换范围立即刷新科室、清空失效科室和勾选，并回到第一页', async () => {
    svc.getFilters.mockResolvedValueOnce({ departments: ['内科'], home_institute: 'H-HOME' })
      .mockResolvedValue({ departments: ['外科'], home_institute: 'H-HOME' })
    svc.listRecords.mockImplementation(async (query: { page: number }) => ({
      items: rows, total: 30, page: query.page, page_size: 15,
    }))
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    await wrapper.get('[aria-label="科室筛选"]').setValue('内科')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    wrapper.findComponent({ name: 'Pagination' }).vm.$emit('change', 2, 15)
    await flushPromises()
    expect(svc.listRecords).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
    await wrapper.findAll('[data-testid="fpqc-record-row"] input[type="checkbox"]')[0].setValue(true)
    await wrapper.get('[data-testid="fpqc-scope-all"]').trigger('click')
    await flushPromises()
    expect(svc.getFilters).toHaveBeenLastCalledWith({ data_scope: 'all' })
    expect(svc.listRecords).toHaveBeenLastCalledWith(expect.objectContaining({ data_scope: 'all', department: '', page: 1 }))
    expect(wrapper.get('[aria-label="科室筛选"]').element).toHaveProperty('value', '')
    expect(wrapper.get('[aria-label="科室筛选"]').text()).toContain('外科')
    expect(wrapper.get('[data-testid="fpqc-run-selected"]').attributes('disabled')).toBeDefined()
    expect(svc.getAnalytics).toHaveBeenLastCalledWith(expect.objectContaining({ data_scope: 'all', department: '' }))
    await wrapper.findAll('button').find((b) => b.text() === '重置')!.trigger('click')
    await flushPromises()
    expect(svc.getFilters).toHaveBeenLastCalledWith({ data_scope: 'home' })
    expect(svc.listRecords).toHaveBeenLastCalledWith(expect.objectContaining({ data_scope: 'home', page: 1 }))
    expect(wrapper.get('[data-testid="fpqc-scope-home"]').attributes('aria-pressed')).toBe('true')
    wrapper.unmount()
  })

  it('含测试数据范围用于分析、导出和按筛选质控，并显示确认摘要与任务标题', async () => {
    svc.getFilters.mockResolvedValue({ departments: ['内科'], home_institute: 'H-HOME' })
    svc.createRun.mockResolvedValue({
      id: 'run-all', status: 'completed', filters: { data_scope: 'all' },
      total_records: 2, processed_records: 2, success_count: 2, failed_count: 0,
      issue_records: 0, failed_records: [],
    })
    const wrapper = mount(FrontpageQcView)
    await flushPromises()
    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    svc.getAnalytics.mockClear()
    await wrapper.get('[data-testid="fpqc-scope-all"]').trigger('click')
    await flushPromises()
    // 顶部指标和已打开的分析面板都重新统计。
    expect(svc.getAnalytics.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(svc.getAnalytics.mock.calls.every(([filters]) => filters.data_scope === 'all')).toBe(true)
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    await flushPromises()
    expect(svc.exportRecords).toHaveBeenCalledWith(expect.objectContaining({ data_scope: 'all' }))
    await wrapper.get('[data-testid="fpqc-run-filtered"]').trigger('click')
    expect(wrapper.get('dl.fpqc-confirm__summary').text()).toContain('数据范围')
    expect(wrapper.get('dl.fpqc-confirm__summary').text()).toContain('含测试数据')
    await wrapper.get('[data-testid="fpqc-confirm-ok"]').trigger('click')
    await flushPromises()
    expect(svc.createRun).toHaveBeenCalledWith({ data_scope: 'all', department: '', start_date: '', end_date: '', keyword: '' })
    expect(wrapper.get('[data-testid="fpqc-run-bar"]').text()).toContain('含测试数据')
    wrapper.unmount()
  })

  it('加载列表并预览第一份的问题', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    expect(wrapper.findAll('[data-testid="fpqc-record-row"]')).toHaveLength(2)
    expect(svc.getRecord).toHaveBeenCalledWith({ institute_id: 'H-TEST', patient_id: 'P-C01', visit_id: 'C01' })
    expect(wrapper.get('[data-testid="fpqc-preview-score"]').text()).toBe('88')
    expect(wrapper.get('[data-testid="fpqc-finding"]').text()).toContain('手术者未填写')
    expect(wrapper.text()).toContain('未质控')
  })

  it('勾选后质控所选，只提交所选病历', async () => {
    svc.createRun.mockResolvedValue({
      id: 'run-1',
      status: 'completed',
      filters: { mode: 'selected' },
      total_records: 1,
      processed_records: 1,
      success_count: 1,
      failed_count: 0,
      issue_records: 0,
      failed_records: [],
    })
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    const runButton = wrapper.get('[data-testid="fpqc-run-selected"]')
    expect(runButton.attributes('disabled')).toBeDefined()

    await wrapper.findAll('[data-testid="fpqc-record-row"] input[type="checkbox"]')[1].setValue(true)
    await wrapper.get('[data-testid="fpqc-run-selected"]').trigger('click')
    await flushPromises()

    expect(svc.createRun).toHaveBeenCalledWith({
      record_refs: [{ institute_id: 'H-TEST', patient_id: 'P-C02', visit_id: 'C02' }],
    })
    expect(wrapper.text()).toContain('首页质控完成：1 份已出结果')
  })

  it('质控当前筛选先在页面内确认，确认后按当前科室与日期范围提交', async () => {
    svc.createRun.mockResolvedValue({
      id: 'run-2',
      status: 'running',
      filters: { department: '' },
      total_records: 2,
      processed_records: 0,
      success_count: 0,
      failed_count: 0,
      issue_records: 0,
      failed_records: [],
    })
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    expect(wrapper.find('[data-testid="fpqc-confirm"]').exists()).toBe(false)
    await wrapper.get('[data-testid="fpqc-run-filtered"]').trigger('click')
    expect(wrapper.get('[data-testid="fpqc-confirm"]').text()).toContain('全部科室')
    expect(svc.createRun).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="fpqc-confirm-ok"]').trigger('click')
    await flushPromises()

    expect(svc.createRun).toHaveBeenCalledWith({ data_scope: 'home', department: '', start_date: '', end_date: '', keyword: '' })
    expect(wrapper.find('[data-testid="fpqc-confirm"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('结果分析点击规则或科室，切回病历结果并按其筛选', async () => {
    svc.getAnalytics.mockResolvedValue({
      summary: { records: 1, avg_score: 88, grades: { excellent: 0, qualified: 1, unqualified: 0 }, issue_records: 1, hint_records: 0, data_gap_records: 0 },
      indicators: [],
      top_rules: [{ rule_id: 'C-H21', rule_name: '手术者', severity: 'deduct', group: '', section: '', records: 1, rate: 1 }],
      top_hints: [],
      top_data_gaps: [],
      departments: [{ department: '内科', records: 1, avg_score: 88, excellent_rate: 0, issue_records: 1 }],
    })
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="fpqc-drill-rule"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="fpqc-record-table"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="fpqc-rule-filter"]').text()).toContain('C-H21')
    expect(svc.listRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({ rule_id: 'C-H21', rule_verdict: 'fail', page: 1 }),
    )

    await wrapper.get('[aria-label="清除规则筛选"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="fpqc-rule-filter"]').exists()).toBe(false)
    expect(svc.listRecords.mock.lastCall?.[0]).not.toHaveProperty('rule_id')

    await wrapper.get('[data-testid="fpqc-view-analysis"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="fpqc-drill-department"]').trigger('click')
    await flushPromises()
    expect(svc.listRecords).toHaveBeenLastCalledWith(expect.objectContaining({ department: '内科', page: 1 }))
  })

  it('标记误报必须填写原因', async () => {
    svc.review.mockResolvedValue({ ...finding, review_status: 'false_alarm', review_note: '已在病程中补记' })
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    const card = wrapper.get('[data-testid="fpqc-finding"]')
    await card.findAll('button').find((b) => b.text() === '标记误报')!.trigger('click')
    const save = () => wrapper.get('[data-testid="fpqc-finding"]').findAll('button').find((b) => b.text() === '保存为误报')!
    expect(save().attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="fpqc-finding"] input').setValue('已在病程中补记')
    await save().trigger('click')
    await flushPromises()

    expect(svc.review).toHaveBeenCalledWith('f-1', { status: 'false_alarm', note: '已在病程中补记' })
    expect(wrapper.get('[data-testid="fpqc-finding-review-status"]').text()).toBe('误报')
  })
})


describe('首页V2导出复审保护', () => {
  function deferred<T>() {
    let resolve!: (value: T) => void
    let reject!: (reason?: unknown) => void
    const promise = new Promise<T>((res, rej) => { resolve=res; reject=rej })
    return {promise, resolve, reject}
  }
  it('未质控筛选不能静默导出已质控结果', async () => {
    const wrapper=mount(FrontpageQcView);await flushPromises()
    await wrapper.get('[aria-label="问题筛选"]').setValue('unchecked')
    await wrapper.get('form').trigger('submit');await flushPromises()
    expect(wrapper.get('[data-testid="fpqc-export-filtered"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    expect(svc.exportRecords).not.toHaveBeenCalled();wrapper.unmount()
  })
  it('当前导出成功确实下载，固定请求和文件名', async () => {
    const blob=new Blob(['synthetic'])
    svc.exportRecords.mockResolvedValue(blob)
    const wrapper=mount(FrontpageQcView);await flushPromises()
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click');await flushPromises()
    expect(downloadBlob).toHaveBeenCalledWith(blob,'首页质控-当前筛选.xlsx')
    expect(wrapper.text()).toContain('已开始下载');wrapper.unmount()
  })
  it('切换账号后旧成功不下载，旧finally不清新导出loading', async () => {
    const old=deferred<Blob>(),next=deferred<Blob>()
    svc.exportRecords.mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise)
    const wrapper=mount(FrontpageQcView);await flushPromises()
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    testAuth.user.id='synthetic-other';await flushPromises()
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    old.resolve(new Blob(['old']));await flushPromises()
    expect(downloadBlob).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="fpqc-export-filtered"]').text()).toContain('正在导出')
    next.resolve(new Blob(['new']));await flushPromises()
    expect(downloadBlob).toHaveBeenCalledTimes(1);wrapper.unmount()
  })
  it('筛选变化后旧失败不显示，卸载后旧成功不下载', async () => {
    const old=deferred<Blob>()
    svc.exportRecords.mockReturnValue(old.promise)
    const wrapper=mount(FrontpageQcView);await flushPromises()
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    await wrapper.get('[aria-label="科室筛选"]').setValue('内科');await flushPromises()
    old.reject(new Error('stale-failure'));await flushPromises()
    expect(wrapper.text()).not.toContain('stale-failure')
    const after=deferred<Blob>();svc.exportRecords.mockReturnValue(after.promise)
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click');wrapper.unmount()
    after.resolve(new Blob(['after-unmount']));await flushPromises()
    expect(downloadBlob).not.toHaveBeenCalled()
  })
})

describe('P1-G3 required_missing 筛选桶与问题列徽标', () => {
  it('仅存在必填缺项时展示“必填缺项”徽标且不误判为“无”，仅三项均为0时显示“无”', async () => {
    const requiredOnly = record('C03', true)
    requiredOnly.result!.fail_count = 0
    requiredOnly.result!.hint_count = 0
    requiredOnly.result!.required_missing_count = 2

    const cleanRecord = record('C04', true)
    cleanRecord.result!.fail_count = 0
    cleanRecord.result!.hint_count = 0
    cleanRecord.result!.required_missing_count = 0

    const customRows = [requiredOnly, cleanRecord]
    svc.listRecords.mockResolvedValue({ items: customRows, total: 2, page: 1, page_size: 15 })
    svc.getRecord.mockImplementation(async (ref: { visit_id: string }) =>
      detailFor(customRows.find((row) => row.visit_id === ref.visit_id)!),
    )

    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    const tableRows = wrapper.findAll('[data-testid="fpqc-record-row"]')
    expect(tableRows).toHaveLength(2)

    const reqCells = tableRows[0].findAll('td')
    expect(reqCells[6].get('[data-testid="fpqc-issue-required-missing"]').text()).toBe('必填缺项 2')
    expect(reqCells[6].text()).not.toContain('无')

    const cleanCells = tableRows[1].findAll('td')
    expect(cleanCells[6].find('[data-testid="fpqc-issue-required-missing"]').exists()).toBe(false)
    expect(cleanCells[6].text().trim()).toBe('无')

    wrapper.unmount()
  })

  it('问题筛选下拉提供 required_missing 选项并透传查询与导出参数', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    const issueSelect = wrapper.get('[aria-label="问题筛选"]')
    expect(issueSelect.find('option[value="required_missing"]').exists()).toBe(true)

    await issueSelect.setValue('required_missing')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(svc.listRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({ issue: 'required_missing', page: 1 }),
    )
    expect(wrapper.get('[data-testid="fpqc-export-filtered"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    await flushPromises()
    expect(svc.exportRecords).toHaveBeenCalledWith(
      expect.objectContaining({ issue: 'required_missing' }),
    )

    wrapper.unmount()
  })
})
