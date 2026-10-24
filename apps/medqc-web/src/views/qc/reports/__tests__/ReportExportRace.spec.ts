import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RecordQualityReportView from '../RecordQualityReportView.vue'
import FrontpageQualityReportView from '../FrontpageQualityReportView.vue'

const api = vi.hoisted(() => ({ record: vi.fn(), frontpage: vi.fn(), error: vi.fn() }))
const route = reactive({ query: { scene: 'running' } })
const auth = reactive({ user: { id: 'manager', institute_id: 'A', roles: ['qc_manager'] } })
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
  getRecordQualityReport: vi.fn(async () => ({ success: true, data: recordData })),
  getRecordQualityRecords: vi.fn(),
  exportRecordQualityReport: api.record,
}))
vi.mock('@/api/frontpageQualityReport', () => ({
  getFrontpageQualityReport: vi.fn(async () => ({ success: true, data: frontpageData })),
  getFrontpageQualityRecords: vi.fn(),
  exportFrontpageQualityReport: api.frontpage,
}))
vi.mock('ant-design-vue', () => ({ message: { error: api.error } }))

const pending = () => {
  let resolve!: (value: { success: boolean; data?: Blob; message?: string }) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<{ success: boolean; data?: Blob; message?: string }>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
const stubs = {
  'a-drawer': true,
  CoreSystemReportPanel: true,
  RecordRemediationAnalysisPanel: true,
}
const downloadedNames: string[] = []
beforeEach(() => {
  vi.clearAllMocks()
  route.query.scene = 'running'
  auth.user = { id: 'manager', institute_id: 'A', roles: ['qc_manager'] }
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
  it.each(['filter', 'identity', 'institute', 'roles', 'unmount', 'query'] as const)(
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
})
