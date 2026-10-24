import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import ManualQualityReportPanel from '../ManualQualityReportPanel.vue'
const mocks = vi.hoisted(() => ({
  report: vi.fn(),
  export: vi.fn(),
  auth: { user: { id: 'synthetic-user', roles: ['qc_manager'] } },
}))
vi.mock('@/api/manualQualityReport', () => ({
  getManualQualityReport: mocks.report,
  exportManualQualityReport: mocks.export,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
const data = {
  assumption: '已确认统计口径',
  summary: {
    entered: 1,
    review: { pending: 1, approved: 0, rejected: 0, unknown: 0 },
    rectification: {
      pending: 0,
      submitted: 1,
      approved: 0,
      rejected: 0,
      unassigned: 0,
      unknown: 0,
    },
  },
  filter_options: {
    institutes: ['H1', 'H2'],
    departments: [
      { institute_id: 'H1', department: '内科' },
      { institute_id: 'H2', department: '内科' },
    ],
    creators: [{ id: 'u1', name: '合成人员' }],
    tasks: [{ id: 'T1', name: '合成任务' }],
  },
  items: [
    {
      id: 'd1',
      institute_id: 'H1',
      department: '内科',
      creator_name: '合成人员',
      review_status: 'pending',
      rectification_status: 'submitted',
    },
  ],
  total: 21,
}
function make() {
  return mount(ManualQualityReportPanel, {
    global: {
      stubs: {
        'a-alert': {
          props: ['message', 'type'],
          template: '<p :data-type="type">{{ message }}</p>',
        },
        'a-button': { template: '<button><slot/></button>' },
        'a-spin': { template: '<div><slot/></div>' },
        'a-table': {
          props: ['dataSource'],
          template: `<div class="rows"><div v-for="row in dataSource" :key="row.id">
            <slot name="bodyCell" :column="{dataIndex: 'creator_name'}" :record="row" :text="row.creator_name" />
            <slot name="bodyCell" :column="{key: 'detail'}" :record="{id: row.id}" />
          </div></div>`,
        },
        'a-pagination': {
          emits: ['change'],
          template: '<button class="next" @click="$emit(\'change\', 2)">下一页</button>',
        },
        'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot/></aside>' },
        'a-descriptions': { template: '<dl><slot/></dl>' },
        'a-descriptions-item': { template: '<dd><slot/></dd>' },
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth = reactive({ user: { id: 'synthetic-user', roles: ['qc_manager'] } })
  mocks.report.mockResolvedValue(data)
  mocks.export.mockResolvedValue(new Blob(['synthetic csv']))
})
describe('人工质控报表', () => {
  it('表格显示单元格文本，明细从已校验行读取，翻页清理旧明细', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.get('.rows').text()).toContain('合成人员')
    await wrapper.get('.rows button').trigger('click')
    expect(wrapper.get('aside').text()).toContain('合成人员')
    expect(wrapper.get('aside').text()).toContain('待验收')
    await wrapper.get('.next').trigger('click')
    await flushPromises()
    expect(wrapper.find('aside').exists()).toBe(false)
    wrapper.unmount()
  })
  it('账户改变后丢弃迟到查询，不能显示前账户病例', async () => {
    let resolve!: (value: unknown) => void
    mocks.report.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const wrapper = make()
    mocks.auth.user.id = 'other-user'
    await flushPromises()
    resolve({ ...data, summary: { ...data.summary, entered: 999 } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('录入 999 条')
    expect(wrapper.text()).toContain('录入 1 条')
    wrapper.unmount()
  })
  it('审核整改分列、完整院科人员任务场景筛选及分页', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('已确认统计口径')
    expect(wrapper.text()).not.toContain('待确认')
    expect(wrapper.get('[data-type="info"]').attributes('data-type')).toBe('info')
    expect(wrapper.text()).toContain('待审核 1')
    expect(wrapper.text()).toContain('待验收 1')
    const selects = wrapper.findAll('select')
    await selects[0].setValue('H1')
    await selects[1].setValue('内科')
    await selects[2].setValue('u1')
    await selects[3].setValue('T1')
    await selects[4].setValue('final')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.report).toHaveBeenLastCalledWith(
      expect.objectContaining({
        institute_id: 'H1',
        department: '内科',
        creator_id: 'u1',
        task_id: 'T1',
        scene: 'final',
      }),
      1,
    )
    await wrapper.get('.next').trigger('click')
    await flushPromises()
    expect(mocks.report).toHaveBeenLastCalledWith(expect.objectContaining({ task_id: 'T1' }), 2)
    wrapper.unmount()
  })
  it('新查询失败清掉旧统计，不伪造零；导出使用已应用筛选', async () => {
    const create = vi.fn(() => 'blob:synthetic'),
      revoke = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = make()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '导出 CSV')!
      .trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith(expect.objectContaining({ scene: 'all' }))
    expect(create).toHaveBeenCalledTimes(1)
    mocks.report.mockRejectedValue(new Error('来源读取失败'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('来源读取失败')
    expect(wrapper.text()).not.toContain('录入 1 条')
    wrapper.unmount()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })
})
