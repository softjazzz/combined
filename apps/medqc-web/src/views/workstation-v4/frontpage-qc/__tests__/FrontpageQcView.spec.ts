import { flushPromises, mount } from '@vue/test-utils'
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
    listActiveFrontpageQcRuns: (...a: unknown[]) => svc.listActive(...a),
    reviewFrontpageQcFinding: (...a: unknown[]) => svc.review(...a),
  }
})
vi.mock('ant-design-vue', () => ({
  Modal: {
    name: 'Modal',
    props: ['open'],
    emits: ['cancel'],
    template: '<div v-if="open" class="modal-stub"><slot /></div>',
  },
  Pagination: { name: 'Pagination', template: '<nav />' },
  message: { error: vi.fn(), success: vi.fn() },
}))

import FrontpageQcView from '../FrontpageQcView.vue'

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

describe('FrontpageQcView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    svc.listRecords.mockResolvedValue({ items: rows, total: 2, page: 1, page_size: 15 })
    svc.getRecord.mockImplementation(async (ref: { visit_id: string }) =>
      detailFor(rows.find((row) => row.visit_id === ref.visit_id)!),
    )
    svc.getFilters.mockResolvedValue({ departments: ['内科'] })
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

    expect(svc.createRun).toHaveBeenCalledWith({ department: '', start_date: '', end_date: '', keyword: '' })
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
