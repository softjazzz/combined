import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Panel from '../RecordRemediationAnalysisPanel.vue'
import type { RecordRemediationAnalysis, RemediationRow } from '@/api/qualityReports'
const mocks = vi.hoisted(() => ({ read: vi.fn(), export: vi.fn(), download: vi.fn() }))
const actor = reactive({ id: 'manager' })
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return { id: actor.id }
    },
  }),
}))
vi.mock('@/api/qualityReports', () => ({
  getRecordRemediationAnalysis: mocks.read,
  exportRecordRemediationAnalysis: mocks.export,
}))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: mocks.download,
}))
const row: RemediationRow = {
  institute_id: 'H',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'running',
  target_kind: 'canonical_defect',
  target_id: 'R1',
  target_label: '合成保存缺陷',
  root_job_id: 'J',
  envelope_id: 'E',
  source_known: true,
  patient_name: '合成患者',
  department: '内科',
  doctor: '甲医生',
  labels: ['urged_rectified', 'clinical_appeal'],
  rectification_state: 'approved',
  rectification_id: 'rect1',
  assignee_name: '合成医生',
  submission_event_id: 'submit1',
  submission_urge_ids: ['urge1'],
  current_urge_ids: [],
  appeals: [{ id: 'appeal1', status: 'pending' }],
  events: [
    {
      id: 'submit1',
      version: 3,
      action: 'submit',
      new_status: 'submitted',
      comment: '合成医生提交说明',
      created_at: '2026-10-01',
      related_event_id: null,
    },
  ],
}
const payload: RecordRemediationAnalysis = {
  scope: { scene: 'running', defect_source: 'all' },
  contract_status: 'confirmed',
  assumptions: ['催办按提交当时有效提醒，申诉独立'],
  labels: [
    { key: 'urged_rectified', label: '催办已整改', defect_total: 1, case_total: 1 },
    { key: 'clinical_appeal', label: '临床申诉', defect_total: 1, case_total: 1 },
  ],
  state_counts: { not_dispatched: 2, source_unknown: 1, pending_acceptance: 1 },
  total: 21,
  page: 1,
  page_size: 20,
  filter_label: null,
  items: [row],
}
function make() {
  return mount(Panel, {
    props: {
      filters: { scene: 'running', department: '内科', doctor: '甲医生', defect_source: 'all' },
    },
    global: {
      stubs: {
        'a-button': {
          props: ['disabled'],
          template: '<button :disabled="disabled"><slot/></button>',
        },
        'a-alert': { props: ['message'], template: '<p>{{message}}</p>' },
        'a-spin': { template: '<div><slot/></div>' },
        'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot/></aside>' },
        'a-pagination': {
          emits: ['change'],
          template: '<button class="next" @click="$emit(\'change\', 2)">下一页</button>',
        },
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  actor.id = 'manager'
  mocks.read.mockImplementation(async (filters) => ({
    success: true,
    data: { ...payload, scope: filters, filter_label: filters.label || null, page: filters.page },
  }))
  mocks.export.mockResolvedValue({ success: true, data: new Blob(['合成CSV']) })
})
describe('整改分析', () => {
  it('七标签明确已确认且可重叠，历史带冻结来源和提交提醒证据', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('七标签统计口径已确认')
    expect(wrapper.text()).toContain('尚未派发：2')
    await wrapper
      .findAll('button')
      .find((item) => item.text() === '查看历史')!
      .trigger('click')
    expect(wrapper.get('aside').text()).toContain('H / P / V')
    expect(wrapper.get('aside').text()).toContain('J / E')
    expect(wrapper.get('aside').text()).toContain('submit1')
    expect(wrapper.get('aside').text()).toContain('urge1')
    expect(wrapper.get('aside').text()).toContain('合成医生提交说明')
    expect(wrapper.get('aside').text()).toContain('独立申诉')
    wrapper.unmount()
  })
  it('标签筛选、分页和受认证导出保持同一scope，标签改变复位页码', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((item) => item.text().startsWith('临床申诉'))!
      .trigger('click')
    await flushPromises()
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scene: 'running',
        department: '内科',
        doctor: '甲医生',
        label: 'clinical_appeal',
        page: 1,
        page_size: 20,
      }),
    )
    await wrapper.get('.next').trigger('click')
    await flushPromises()
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: 'clinical_appeal', page: 2 }),
    )
    await wrapper
      .findAll('button')
      .find((item) => item.text().includes('导出 CSV'))!
      .trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith({
      scene: 'running',
      department: '内科',
      doctor: '甲医生',
      defect_source: 'all',
      label: 'clinical_appeal',
    })
    expect(mocks.download).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('owner故障清空旧统计，不伪称零整改或空匹配', async () => {
    const wrapper = make()
    await flushPromises()
    mocks.read.mockResolvedValue({ success: false, status: 503, message: '整改来源不可用' })
    await wrapper
      .findAll('button')
      .find((item) => item.text().startsWith('临床申诉'))!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('整改来源不可用')
    expect(wrapper.text()).not.toContain('暂无匹配')
    expect(wrapper.find('table').exists()).toBe(false)
    wrapper.unmount()
  })
  it('缺失分页计数的畸形成功不展示统计', async () => {
    mocks.read.mockResolvedValue({ success: true, data: { ...payload, total: undefined } })
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('响应无法确认')
    expect(wrapper.find('table').exists()).toBe(false)
    wrapper.unmount()
  })
  it('换场景丢弃迟到结果和导出，不将运行数据挂终末', async () => {
    let resolve!: (value: unknown) => void
    mocks.read.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const wrapper = make()
    await wrapper.setProps({ filters: { scene: 'final', defect_source: 'manual' } })
    await flushPromises()
    resolve({ success: true, data: payload })
    await flushPromises()
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ scene: 'final', defect_source: 'manual' }),
    )
    expect(wrapper.findAll('tr')).toHaveLength(2)
    wrapper.unmount()
  })
  it('换账号关闭历史并隔离迟到导出', async () => {
    let resolve!: (value: unknown) => void
    mocks.export.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const wrapper = make()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((item) => item.text() === '查看历史')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((item) => item.text().includes('导出 CSV'))!
      .trigger('click')
    mocks.read.mockResolvedValue({ success: false, status: 403, message: '无权访问' })
    actor.id = 'other'
    await flushPromises()
    resolve({ success: true, data: new Blob(['旧账号']) })
    await flushPromises()
    expect(wrapper.find('aside').exists()).toBe(false)
    expect(mocks.download).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('无权访问')
    wrapper.unmount()
  })
})
