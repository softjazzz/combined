import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RecordQualityReportView from '../RecordQualityReportView.vue'
import FrontpageQualityReportView from '../FrontpageQualityReportView.vue'

const api = vi.hoisted(() => ({
  record: vi.fn(),
  frontpage: vi.fn(),
  error: vi.fn(),
  recordReport: vi.fn(),
  frontpageReport: vi.fn(),
  recordRows: vi.fn(),
  frontpageRows: vi.fn(),
}))
const route = reactive({ query: { scene: 'running' } })
const auth = reactive({
  user: { id: 'manager', institute_id: 'A', department: '内科', roles: ['qc_manager'] },
})
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
const recordData = {
  scope: { scene: 'running' },
  score_standard: { status: 'no_standard' },
  source_status: { review: 'unavailable', manual_defect: 'unavailable' },
  kpis: {},
  department_rows: [],
  doctor_rows: [],
  unavailable_dimensions: [],
}
const frontpageData = { scope: {}, kpis: {}, sources: [], department_rows: [] }
vi.mock('@/api/qualityReports', () => ({
  getRecordQualityReport: api.recordReport,
  getRecordQualityRecords: api.recordRows,
  exportRecordQualityReport: api.record,
}))
vi.mock('@/api/frontpageQualityReport', () => ({
  getFrontpageQualityReport: api.frontpageReport,
  getFrontpageQualityRecords: api.frontpageRows,
  exportFrontpageQualityReport: api.frontpage,
}))
vi.mock('ant-design-vue', () => ({ message: { error: api.error } }))

const pending = () => {
  let resolve!: (value: { success: boolean; data?: unknown; message?: string }) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<{ success: boolean; data?: unknown; message?: string }>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
const stubs = {
  'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
  CoreSystemReportPanel: true,
  RecordRemediationAnalysisPanel: true,
}
const downloadedNames: string[] = []
beforeEach(() => {
  vi.clearAllMocks()
  route.query.scene = 'running'
  auth.user = { id: 'manager', institute_id: 'A', department: '内科', roles: ['qc_manager'] }
  api.recordReport.mockResolvedValue({ success: true, data: recordData })
  api.frontpageReport.mockResolvedValue({ success: true, data: frontpageData })
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: vi.fn(() => 'blob:synthetic'),
  })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  downloadedNames.length = 0
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloadedNames.push(this.download)
  })
})
afterEach(() => vi.restoreAllMocks())

describe.each([
  ['record', RecordQualityReportView, '#report-department'],
  ['frontpage', FrontpageQualityReportView, '#fp-department'],
] as const)('%s export lifecycle', (kind, Component, department) => {
  it.each(['filter', 'identity', 'institute', 'department', 'roles', 'unmount', 'query'] as const)(
    'discards a delayed export after %s changes',
    async (change) => {
      const deferred = pending()
      api[kind].mockReturnValueOnce(deferred.promise)
      const wrapper = mount(Component, { global: { stubs } })
      await flushPromises()
      await wrapper
        .findAll('button')
        .find((button) => button.text().includes('科室 CSV'))!
        .trigger('click')
      if (change === 'filter') await wrapper.get(department).setValue('外科')
      if (change === 'identity') auth.user.id = 'other'
      if (change === 'institute') auth.user.institute_id = 'B'
      if (change === 'department') auth.user.department = '外科'
      if (change === 'roles') auth.user.roles = ['doctor']
      if (change === 'query') {
        if (kind === 'record') route.query.scene = 'final'
        else await wrapper.get('.filters .primary').trigger('click')
      }
      if (change === 'unmount') wrapper.unmount()
      await flushPromises()
      deferred.resolve({ success: true, data: new Blob(['synthetic']) })
      await flushPromises()
      expect(URL.createObjectURL).not.toHaveBeenCalled()
      expect(api.error).not.toHaveBeenCalled()
      if (change !== 'unmount') wrapper.unmount()
    },
  )

  it('ignores stale rejection without clearing the new export loading state', async () => {
    const old = pending()
    const current = pending()
    api[kind].mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const wrapper = mount(Component, { global: { stubs } })
    await flushPromises()
    const button = () => wrapper.findAll('button').find((item) => item.text().includes('科室 CSV'))!
    await button().trigger('click')
    await wrapper.get(department).setValue('外科')
    await wrapper.get('.filters .primary').trigger('click')
    await flushPromises()
    await button().trigger('click')
    old.reject(new Error('stale synthetic failure'))
    await flushPromises()
    expect(api.error).not.toHaveBeenCalled()
    expect(button().attributes('disabled')).toBeDefined()
    current.resolve({ success: false, message: '当前导出失败' })
    await flushPromises()
    expect(api.error).toHaveBeenCalledWith('当前导出失败')
    expect(button().attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('downloads a current response with its captured filename and releases loading', async () => {
    api[kind].mockResolvedValueOnce({ success: true, data: new Blob(['synthetic']) })
    const wrapper = mount(Component, { global: { stubs } })
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text().includes('科室 CSV'))!
    await button.trigger('click')
    await flushPromises()
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(downloadedNames).toEqual([
      kind === 'record' ? '病历质量分析-running-departments.csv' : '病案首页统计-departments.csv',
    ])
    expect(button.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('shows current Promise rejection and releases only its loading state', async () => {
    api[kind].mockRejectedValueOnce(new Error('synthetic current rejection'))
    const wrapper = mount(Component, { global: { stubs } })
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text().includes('科室 CSV'))!
    await button.trigger('click')
    await flushPromises()
    expect(api.error).toHaveBeenCalledWith('导出失败')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('rejects delayed summary and drilldown writes after identity switch', async () => {
    const summary = pending()
    const rows = pending()
    const getReport = kind === 'record' ? api.recordReport : api.frontpageReport
    const getRows = kind === 'record' ? api.recordRows : api.frontpageRows
    const data = kind === 'record' ? recordData : frontpageData
    const report = (name: string) => ({
      success: true,
      data: { ...data, department_rows: [kind === 'record' ? { name } : { department: name }] },
    })
    getReport.mockResolvedValueOnce(report('当前科室')).mockReturnValueOnce(summary.promise)
    getRows.mockReturnValueOnce(rows.promise)
    const wrapper = mount(Component, { global: { stubs } })
    await flushPromises()
    await wrapper
      .findAll('button.link')
      .find((b) => b.text() === '当前科室')!
      .trigger('click')
    auth.user.id = 'next-account'
    await flushPromises()
    expect(wrapper.text()).not.toContain('当前科室')
    expect(wrapper.text()).not.toContain('共 777 份')
    // 第二次身份切换使第一份新汇总也过期；不用被 loading 禁用的刷新按钮。
    getReport.mockResolvedValueOnce(report('最终科室'))
    auth.user.id = 'final-account'
    await flushPromises()
    summary.resolve(report('过期科室'))
    rows.resolve({ success: true, data: { total: 777, page: 1, page_size: 20, items: [] } })
    await flushPromises()
    expect(wrapper.text()).toContain('最终科室')
    expect(wrapper.text()).not.toContain('过期科室')
    expect(wrapper.text()).not.toContain('共 777 份')
    wrapper.unmount()
  })

  it('does not render a delayed summary from the previous account', async () => {
    const old = pending()
    const getReport = kind === 'record' ? api.recordReport : api.frontpageReport
    const data = kind === 'record' ? recordData : frontpageData
    getReport.mockReturnValueOnce(old.promise)
    const wrapper = mount(Component, { global: { stubs } })
    await flushPromises()
    auth.user.id = 'next-account'
    await flushPromises()
    old.resolve({
      success: true,
      data: {
        ...data,
        department_rows: [
          kind === 'record' ? { name: '旧账号科室' } : { department: '旧账号科室' },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain('旧账号科室')
    wrapper.unmount()
  })
})

it('discards a record CSV when its visible column selection changes', async () => {
  const old = pending()
  api.record.mockReturnValueOnce(old.promise)
  const wrapper = mount(RecordQualityReportView, { global: { stubs } })
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text().includes('科室 CSV'))!
    .trigger('click')
  await wrapper.get('.column-options input[type="checkbox"]').setValue(false)
  old.resolve({ success: true, data: new Blob(['synthetic']) })
  await flushPromises()
  expect(URL.createObjectURL).not.toHaveBeenCalled()
  wrapper.unmount()
})
