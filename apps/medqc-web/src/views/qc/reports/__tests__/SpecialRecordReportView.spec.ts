import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SpecialRecordReportView from '../SpecialRecordReportView.vue'

const mocks = vi.hoisted(() => ({
  report: vi.fn(),
  records: vi.fn(),
  defects: vi.fn(),
  export: vi.fn(),
}))
vi.mock('@/api/specialRecordReports', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/specialRecordReports')>()),
  getSpecialRecordReport: mocks.report,
  getSpecialReportRecords: mocks.records,
  getSpecialReportDefects: mocks.defects,
  exportSpecialRecordReport: mocks.export,
}))
const actor = reactive({ id: 'synthetic-A', institute_id: 'H1' })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: actor, hasRole: () => false }) }))
const types = [
  'death',
  'critical',
  'difficult',
  'consultation',
  'transfusion',
  'surgery',
  'surgery_ge3',
  'surgery_ge4',
]
const report = {
  scope: { institute_id: 'H1', timezone: 'Asia/Shanghai', classification_version_seq: 1 },
  summary: { cohort_total: 2, record_total: 1, unavailable_result_total: 1, unknown_type_total: 1 },
  types: types.map((key) => ({
    key,
    label: key,
    count: null,
    known_positive_total: 1,
    unknown_total: 1,
    status: 'partial',
  })),
  top_departments: [{ name: '合成科室', count: 1 }],
  grade_distribution: null,
  top_defects: null,
  score_standard: {
    status: 'no_standard',
    standard_id: null,
    standard_version_seq: null,
    binding_version_seq: null,
  },
}
const row = {
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  patient_name: '合成病例',
  department: '合成科室',
  discharged_at: '2026-10-02',
  types: Object.fromEntries(
    types.map((key) => [key, { state: 'unknown', reason_code: 'missing' }]),
  ),
  report_score_status: 'unknown',
  report_score: null,
  report_grade: null,
  reason_code: 'no_standard',
  standard_id: null,
  standard_version_seq: null,
  historical_score: null,
  historical_grade: null,
}
const defects = {
  scope: report.scope,
  score_standard: report.score_standard,
  total: 1,
  page: 1,
  page_size: 20,
  items: [
    {
      rule_id: 'R1',
      name: '合成缺陷',
      severity: null,
      category: null,
      type: null,
      document: null,
      is_veto: null,
      count: 1,
      ratio: 1,
    },
  ],
}
const stubs = {
  SpecialReportConfigDrawer: true,
  SpecialReportCharts: true,
  'a-button': {
    props: ['htmlType', 'disabled'],
    template: '<button :type="htmlType || \'button\'" :disabled="disabled"><slot /></button>',
  },
  'a-input': {
    props: ['value'],
    emits: ['update:value'],
    template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
  'a-select': {
    props: ['value', 'options'],
    emits: ['update:value'],
    template:
      '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
  },
  'a-segmented': {
    props: ['value', 'options'],
    emits: ['update:value'],
    template:
      '<div><button v-for="option in options" :key="option.value" @click="$emit(\'update:value\', option.value)">{{ option.label }}</button></div>',
  },
}
const render = () => mount(SpecialRecordReportView, { global: { stubs } })
const button = (wrapper: ReturnType<typeof render>, text: string) =>
  wrapper.findAll('button').find((node) => node.text().includes(text))!
beforeEach(() => {
  vi.resetAllMocks()
  actor.id = 'synthetic-A'
  actor.institute_id = 'H1'
  mocks.report.mockResolvedValue(report)
  mocks.records.mockResolvedValue({
    total: 1,
    page: 1,
    page_size: 20,
    items: [row],
    scope: report.scope,
    score_standard: report.score_standard,
  })
  mocks.defects.mockResolvedValue(defects)
  mocks.export.mockResolvedValue(new Blob(['synthetic']))
})
describe('特殊病历报表页面', () => {
  it('按账号机构和上海日期初始化，未知不补0，不显示未授权配置按钮', async () => {
    const wrapper = render()
    await flushPromises()
    expect(mocks.report).toHaveBeenCalledWith(
      expect.objectContaining({
        institute_id: 'H1',
        record_type: 'death',
        record_type_state: 'positive',
      }),
    )
    expect(wrapper.text()).toContain('未知')
    expect(wrapper.text()).not.toContain('机构代码配置')
    expect(wrapper.text()).toContain('历史分 / 等级')
    wrapper.unmount()
  })
  it('缺陷明细是8列原合同，按已应用条件导出而不混草稿科室', async () => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:synthetic'),
      revokeObjectURL: vi.fn(),
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const wrapper = render()
    await flushPromises()
    await wrapper.findAll('input')[1].setValue('未应用科室')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '明细')!
      .trigger('click')
    await flushPromises()
    const headers = wrapper.findAll('th').map((node) => node.text())
    expect(headers.slice(0, 8)).toEqual([
      '缺陷名称',
      '提醒等级',
      '大类',
      '类型',
      '文书',
      '单否',
      '数量',
      '占比',
    ])
    await button(wrapper, '下载缺陷明细').trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith(
      expect.objectContaining({ department: '', institute_id: 'H1' }),
      'defects',
      report,
    )
    expect(click).toHaveBeenCalledOnce()
    click.mockRestore()
    vi.unstubAllGlobals()
    wrapper.unmount()
  })
  it('科室下钻及分页保留类型，病例导出使用下钻而缺陷导出使用概览条件', async () => {
    const wrapper = render()
    await flushPromises()
    await button(wrapper, '合成科室').trigger('click')
    await flushPromises()
    expect(mocks.records).toHaveBeenLastCalledWith(
      expect.objectContaining({ department: '合成科室', record_type: 'death' }),
      1,
    )
    wrapper.unmount()
  })
  it('明细读取失败独立展示，不隐藏已读取概览', async () => {
    mocks.records.mockRejectedValue(new Error('病例来源不可用'))
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('病例来源不可用')
    expect(wrapper.text()).toContain('范围病例')
    wrapper.unmount()
  })
  it('账号切换拒绝旧病例响应且默认机构同步变化', async () => {
    let resolve!: (value: unknown) => void
    mocks.records.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const wrapper = render()
    await flushPromises()
    actor.institute_id = 'H2'
    actor.id = 'synthetic-B'
    mocks.report.mockResolvedValue({ ...report, scope: { ...report.scope, institute_id: 'H2' } })
    mocks.records.mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 20,
      items: [],
      scope: { ...report.scope, institute_id: 'H2' },
      score_standard: report.score_standard,
    })
    await flushPromises()
    resolve({ total: 1, page: 1, page_size: 20, items: [row] })
    await flushPromises()
    expect(mocks.report).toHaveBeenLastCalledWith(expect.objectContaining({ institute_id: 'H2' }))
    expect(wrapper.text()).not.toContain('合成病例')
    wrapper.unmount()
  })
  it('无账号机构必须填写，不发送无机构请求', async () => {
    actor.institute_id = ''
    const wrapper = render()
    await flushPromises()
    expect(mocks.report).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请填写授权范围内的机构')
    wrapper.unmount()
  })
  it.each(['classification', 'standard', 'binding'])('下钻%s版本漂移拒绝混显', async (change) => {
    const metadata = {
      scope: { ...report.scope, classification_version_seq: change === 'classification' ? 2 : 1 },
      score_standard: {
        ...report.score_standard,
        standard_id: change === 'standard' ? 'changed' : null,
        binding_version_seq: change === 'binding' ? 2 : null,
      },
    }
    mocks.records.mockResolvedValue({ total: 1, page: 1, page_size: 20, items: [row], ...metadata })
    mocks.defects.mockResolvedValue({ ...defects, ...metadata })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('版本已变化，请刷新报表')
    expect(wrapper.text()).not.toContain('合成病例')
    wrapper.unmount()
  })
  it('下载病例后切换下钻，旧导出不触发保存', async () => {
    let done!: (value: Blob) => void
    mocks.export.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          done = resolve
        }),
    )
    vi.stubGlobal('URL', { createObjectURL: vi.fn(), revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const wrapper = render()
    await flushPromises()
    await button(wrapper, '下载病例').trigger('click')
    await button(wrapper, '合成科室').trigger('click')
    done(new Blob(['synthetic']))
    await flushPromises()
    expect(click).not.toHaveBeenCalled()
    click.mockRestore()
    vi.unstubAllGlobals()
    wrapper.unmount()
  })
})
