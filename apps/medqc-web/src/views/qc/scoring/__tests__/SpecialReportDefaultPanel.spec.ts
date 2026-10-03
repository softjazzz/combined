import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SpecialReportDefaultPanel from '../SpecialReportDefaultPanel.vue'

const mocks = vi.hoisted(() => ({ get: vi.fn(), list: vi.fn(), put: vi.fn() }))
vi.mock('@/api/scoring', () => ({
  getSpecialReportDefault: mocks.get, listScoringStandards: mocks.list, setSpecialReportDefault: mocks.put,
}))
const actor = reactive({ id: 'synthetic-user' })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: actor }) }))
const candidate = { id: 'S1', name: '合成专用标准', scene: 'final', status: 'active', is_default: false, version_seq: 3 }
const binding = { purpose: 'special_report', execution_scene: 'final', version_seq: 2, standard_id: null, standard_version_seq: null, status: 'no_standard', standard: null }
const response = { success: true, data: binding }
const render = (canWrite = true) => mount(SpecialReportDefaultPanel, {
  props: { canWrite },
  global: { stubs: {
    'a-button': { props: ['htmlType', 'disabled'], template: '<button :type="htmlType || \'button\'" :disabled="disabled"><slot /></button>' },
    'a-select': { props: ['value', 'options', 'disabled'], emits: ['update:value'], template: '<select :value="value" :disabled="disabled" @change="$emit(\'update:value\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value" :disabled="option.disabled">{{ option.label }}</option></select>' },
  } },
})
beforeEach(() => {
  vi.resetAllMocks()
  actor.id = 'synthetic-user'
  mocks.get.mockResolvedValue(response)
  mocks.list.mockResolvedValue({ success: true, data: { items: [candidate, { ...candidate, id: 'R', scene: 'running' }, { ...candidate, id: 'D', status: 'draft' }] } })
  mocks.put.mockResolvedValue(response)
})
describe('特殊报表专用默认标准', () => {
  it('可选非默认active final标准，保存绑定和标准CAS而不修改执行场景默认', async () => {
    const wrapper = render()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith({ scene: 'final', status: 'active' })
    expect(wrapper.findAll('option')).toHaveLength(2)
    await wrapper.get('select').setValue('S1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.put).toHaveBeenCalledOnce()
    expect(mocks.put).toHaveBeenCalledWith({ version_seq: 2, standard_id: 'S1', standard_version_seq: 3 })
    wrapper.unmount()
  })
  it('绑定失效显示不可用，不能自动套用候选默认；可以显式解除', async () => {
    mocks.get.mockResolvedValue({ success: true, data: { ...binding, standard_id: 'gone', standard_version_seq: 1, status: 'unavailable' } })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('已绑定标准不可用')
    expect(mocks.put).not.toHaveBeenCalled()
    await wrapper.get('select').setValue('')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.put).toHaveBeenCalledWith({ version_seq: 2, standard_id: null, standard_version_seq: null })
    wrapper.unmount()
  })
  it('CAS冲突刷新并重置选择，必须重新确认不会自动重写', async () => {
    mocks.put.mockResolvedValue({ success: false, status: 409, code: 'version_conflict' })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('select').setValue('S1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(2)
    expect(mocks.put).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('请重新选择标准并确认保存')
    expect(wrapper.get('[data-testid="special-default-save"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('读取失败独立提示，不借用候选标准，只读用户不显示写控件', async () => {
    mocks.get.mockResolvedValue({ success: false, message: '来源不可用' })
    const wrapper = render(false)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('来源不可用')
    expect(wrapper.find('form').exists()).toBe(false)
    wrapper.unmount()
  })
  it('账号切换隔离晚到读取', async () => {
    let resolve!: (value: unknown) => void
    mocks.get.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    const wrapper = render()
    actor.id = 'new-user'
    await flushPromises()
    resolve({ success: true, data: { ...binding, status: 'configured', standard_id: 'S1', standard: candidate } })
    await flushPromises()
    expect(wrapper.get('[data-testid="special-binding-status"]').text()).toBe('未配置专用默认标准')
    wrapper.unmount()
  })
  it('未知写入结果先回读，不重复PUT；回读503禁止再写', async () => {
    const wrapper = render()
    await flushPromises()
    mocks.put.mockResolvedValue({ success: false, status: 503 })
    mocks.get.mockResolvedValue({ success: false, status: 503, message: '配置不可用' })
    await wrapper.get('select').setValue('S1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(2)
    expect(mocks.put).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('配置不可用')
    expect(wrapper.text()).toContain('回读失败')
    expect(wrapper.text()).not.toContain('已回读配置')
    expect(wrapper.find('form').exists()).toBe(false)
    wrapper.unmount()
  })
  it('同标准版本变化失效可显式确认新版本，未点击前不自动恢复', async () => {
    mocks.get.mockResolvedValue({ success: true, data: { ...binding, standard_id: 'S1', standard_version_seq: 2, status: 'unavailable' } })
    const wrapper = render()
    await flushPromises()
    expect(mocks.put).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="special-default-save"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.put).toHaveBeenCalledWith({ version_seq: 2, standard_id: 'S1', standard_version_seq: 3 })
    wrapper.unmount()
  })
  it('200损坏写回执先GET核对不重PUT，回读替换不显示保存成功', async () => {
    mocks.put.mockResolvedValue({ success: false, status: 200, message: '回执不完整' })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('select').setValue('S1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(2)
    expect(mocks.put).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('保存结果未确认，已回读配置')
    expect(wrapper.text()).not.toContain('专用默认标准已保存')
    wrapper.unmount()
  })
  it('PUT确认后回读已被替换时显示变化', async () => {
    mocks.put.mockResolvedValue({ success: true, data: { ...binding, version_seq: 3, standard_id: 'S1', standard_version_seq: 3, status: 'configured', standard: candidate } })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('select').setValue('S1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('保存后配置已被更新')
    expect(wrapper.text()).not.toContain('专用默认标准已保存')
    wrapper.unmount()
  })
  it('未知写嵌套回读期间账号A-B-A切换隔离旧通知', async () => {
    const wrapper = render()
    await flushPromises()
    let old!: (value: unknown) => void
    mocks.put.mockResolvedValue({ success: false, status: 503 })
    mocks.get.mockImplementationOnce(() => new Promise((resolve) => { old = resolve }))
    await wrapper.get('select').setValue('S1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    actor.id = 'account-B'
    await flushPromises()
    actor.id = 'synthetic-user'
    await flushPromises()
    old(response)
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存结果未确认')
    expect(wrapper.get('[data-testid="special-binding-status"]').text()).toBe('未配置专用默认标准')
    wrapper.unmount()
  })
})
