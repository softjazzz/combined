import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import SpecialReportConfigDrawer from '../SpecialReportConfigDrawer.vue'
const mocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }))
vi.mock('@/api/specialRecordReports', () => ({
  getSpecialSourceConfig: mocks.get,
  saveSpecialSourceConfig: mocks.put,
}))
const config = {
  critical: { positive_codes: [], negative_codes: [] },
  difficult: { positive_codes: [], negative_codes: [] },
  surgery_level_codes: { '1': [], '2': [], '3': [], '4': [] },
}
const data = { institute_id: 'H1', version_seq: 0, config, sources: [] }
const render = () =>
  mount(SpecialReportConfigDrawer, {
    props: { open: true, instituteId: 'H1' },
    global: {
      stubs: {
        'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
        'a-select': true,
        'a-button': {
          props: ['htmlType', 'disabled'],
          template: '<button :type="htmlType || \'button\'" :disabled="disabled"><slot /></button>',
        },
      },
    },
  })
beforeEach(() => {
  vi.resetAllMocks()
  mocks.get.mockResolvedValue(data)
  mocks.put.mockResolvedValue({ ...data, version_seq: 1 })
})
describe('机构代码配置抽屉', () => {
  it('不添默认代码，按读取CAS保存并回读确认', async () => {
    const wrapper = render()
    await flushPromises()
    mocks.get.mockResolvedValue({ ...data, version_seq: 1 })
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.put).toHaveBeenCalledWith('H1', 0, config)
    expect(wrapper.emitted('saved')).toHaveLength(1)
    wrapper.unmount()
  })
  it('未知写入回读失败禁止重写，不误报已保存', async () => {
    const wrapper = render()
    await flushPromises()
    mocks.put.mockRejectedValue(new Error('network'))
    mocks.get.mockRejectedValue(new Error('unavailable'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('保存结果未知且回读失败')
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.emitted('saved')).toBeUndefined()
    expect(mocks.put).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
  it('关闭/切机构废弃迟到配置', async () => {
    let done!: (value: unknown) => void
    mocks.get.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          done = resolve
        }),
    )
    const wrapper = render()
    await wrapper.setProps({ open: false })
    done(data)
    await flushPromises()
    await wrapper.setProps({ instituteId: 'H2', open: true })
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith('H2')
    wrapper.unmount()
  })
  it('CAS冲突回读当前代码，需要人工重新确认而不自动PUT', async () => {
    const wrapper = render(); await flushPromises()
    mocks.put.mockRejectedValue(new AxiosError('conflict', '409', undefined, undefined, {
      status: 409, statusText: '', data: {}, headers: {}, config: { headers: new AxiosHeaders() },
    }))
    mocks.get.mockResolvedValue({ ...data, version_seq: 2 })
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('配置已被修改，请核对并重新确认保存')
    expect(mocks.put).toHaveBeenCalledOnce()
    expect(wrapper.emitted('saved')).toBeUndefined()
    wrapper.unmount()
  })
})
