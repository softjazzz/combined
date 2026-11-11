import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CDMDataView from '@/views/workstation-v4/CDMDataView.vue'

const { options } = vi.hoisted(() => ({ options: vi.fn() }))
vi.mock('@/api/clinicalSources', () => ({ clinicalSourcesApi: { options } }))
vi.mock('@/utils/auth-token', () => ({ getAccessToken: () => '' }))
const row = { id: 'V', instituteId: 'H', patientId: 'P', name: '合成病例' }
function render() {
  return mount(CDMDataView, { global: { stubs: {
    'a-button': { template: '<button><slot /></button>' },
    'a-alert': { props: ['message'], template: '<div role="alert">{{ message }}</div>' },
    'a-tag': { template: '<span><slot /></span>' }, 'a-modal': true,
    'a-spin': true, 'a-badge': true, 'a-tabs': true, 'a-tab-pane': true,
  } } })
}
function mockReads(items: unknown[] = [row], detailStatus = 200) {
  vi.mocked(fetch).mockImplementation(async input => {
    const url = String(input)
    let data: unknown
    if (url.endsWith('/stats')) data = { total_records: 871 }
    else if (url.endsWith('/list')) data = { items }
    else if (url.endsWith('/departments')) data = ['合成科室']
    else if (url.includes('/frontpage/')) data = { name: '合成详情', diagnoses: [] }
    else throw new Error(`Unexpected request: ${url}`)
    const status = url.includes('/frontpage/') ? detailStatus : 200
    return { ok: status === 200, status, json: async () => data } as Response
  })
}
beforeEach(() => {
  vi.mocked(fetch).mockReset()
  options.mockResolvedValue({ default_source: 'independent_cdm', sources: [
    { id: 'independent_cdm', enabled: true, name: '东华' },
  ] })
})
describe('数据管理东华读取', () => {
  it('使用真实三坐标，不调用整表接口、不展示估算数或SQLite', async () => {
    mockReads()
    const wrapper = render()
    await flushPromises()
    expect(fetch).toHaveBeenCalledWith('/api/medical-records/frontpage/H/P/V', expect.anything())
    expect(wrapper.text()).toContain('合成详情')
    expect(wrapper.text()).toContain('东华CDM（PostgreSQL）')
    expect(wrapper.text()).toContain('未统计')
    expect(wrapper.text()).toContain('不开放整表')
    expect(wrapper.text()).not.toContain('SQLite')
    expect(wrapper.text()).not.toContain('40+')
    expect(vi.mocked(fetch).mock.calls.every(([url]) => !/schema|table-data|undefined/.test(String(url)))).toBe(true)
    wrapper.unmount()
  })
  it('缺身份不发详情请求并明确提示', async () => {
    mockReads([{ name: '无身份合成病例' }])
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('病例身份不完整')
    expect(vi.mocked(fetch).mock.calls.every(([url]) => !String(url).includes('/frontpage/'))).toBe(true)
    wrapper.unmount()
  })
  it('详情HTTP失败不能渲染成诊断零条', async () => {
    mockReads([row], 403)
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('病案详情读取失败')
    expect(wrapper.find('.detail-panel').exists()).toBe(false)
    wrapper.unmount()
  })
  it('来源失败时不回退旧库、不显示连接成功', async () => {
    options.mockRejectedValue(new Error('来源不可用'))
    const wrapper = render()
    await flushPromises()
    expect(fetch).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('来源不可用')
    expect(wrapper.text()).not.toContain('读取成功')
    wrapper.unmount()
  })
})
