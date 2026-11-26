import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Panel from '../RecordRemediationAnalysisPanel.vue'
import CaseRectificationCreate from '@/components/qc/CaseRectificationCreate.vue'
import type { RecordRemediationAnalysis, RemediationRow } from '@/api/qualityReports'
const mocks = vi.hoisted(() => ({ read: vi.fn(), export: vi.fn(), download: vi.fn() }))
const actor = reactive({ id: 'manager' })
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return { id: actor.id, is_demo_account: false }
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
        CaseRectificationCreate: {
          props: ['jobId', 'initialTarget'],
          emits: ['created', 'changed'],
          template: '<div />',
        },
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
  vi.resetAllMocks()
  actor.id = 'manager'
  mocks.read.mockImplementation(async (filters) => ({
    success: true,
    data: { ...payload, scope: filters, filter_label: filters.label || null, page: filters.page },
  }))
  mocks.export.mockResolvedValue({ success: true, data: new Blob(['合成CSV']) })
})
describe('整改分析', () => {
  it('V7.1口径可展开且不丢失，统计筛选保留按压状态', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.get('details').attributes('open')).toBeUndefined()
    expect(wrapper.get('details').text()).toContain(payload.assumptions[0])
    expect(wrapper.get('.label-counts button').attributes('aria-pressed')).toBe('true')
    const metric = wrapper.get('.remediation-metric')
    expect(metric.classes()).not.toContain('mq-card')
    expect(wrapper.get('[aria-label="整改跟踪"]').findAll('.remediation-metric')).toHaveLength(1)
    expect(wrapper.get('[aria-label="申诉复核"]').findAll('.remediation-metric')).toHaveLength(1)
    await metric.trigger('click')
    await flushPromises()
    expect(metric.attributes('aria-pressed')).toBe('true')
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: 'urged_rectified', page: 1 }),
      expect.any(AbortSignal),
    )
    wrapper.unmount()
  })
  it.each(['created', 'changed'] as const)('冻结缺陷派发或处理后重读报表：%s', async (event) => {
    const wrapper = make()
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text().includes('查看历史'))!
    await button.trigger('click')
    const form = wrapper.findComponent(CaseRectificationCreate)
    expect(form.props('jobId')).toBe('J')
    const calls = mocks.read.mock.calls.length
    form.vm.$emit(event)
    await flushPromises()
    expect(mocks.read.mock.calls.length).toBe(calls + 1)
    expect(wrapper.find('aside').exists()).toBe(false)
  })
  it.each(
    ['标签', '分页', '场景', '账号'].flatMap((change) =>
      ['成功', '失败'].map((outcome) => ({ change, outcome })),
    ),
  )(
    '导出在途切$change后可再次导出，旧请求$outcome不清除新请求状态',
    async ({ change, outcome }) => {
      let resolveOld!: (value: { success: boolean; data: Blob }) => void
      let rejectOld!: (reason: Error) => void
      let resolveNew!: (value: { success: boolean; data: Blob }) => void
      mocks.export
        .mockImplementationOnce(
          () =>
            new Promise((resolve, reject) => {
              resolveOld = resolve
              rejectOld = reject
            }),
        )
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveNew = resolve
            }),
        )
      const wrapper = make()
      try {
        await flushPromises()
        const button = wrapper.get('header button')
        await button.trigger('click')
        expect(button.attributes('disabled')).toBeDefined()
        if (change === '标签') {
          await wrapper.findAll('.label-counts button')[2].trigger('click')
        } else if (change === '分页') {
          await wrapper.get('.next').trigger('click')
        } else if (change === '场景') {
          await wrapper.setProps({ filters: { scene: 'final', defect_source: 'manual' } })
        } else {
          actor.id = 'other'
        }
        await flushPromises()
        expect(button.attributes('disabled')).toBeUndefined()
        await button.trigger('click')
        expect(mocks.export).toHaveBeenCalledTimes(2)
        expect(mocks.export).toHaveBeenLastCalledWith(
          expect.objectContaining({
            scene: change === '场景' ? 'final' : 'running',
            label: change === '标签' ? 'clinical_appeal' : undefined,
          }),
          expect.any(AbortSignal),
        )
        if (outcome === '成功') resolveOld({ success: true, data: new Blob(['旧导出']) })
        else rejectOld(new Error('旧导出失败'))
        await flushPromises()
        expect(mocks.download).not.toHaveBeenCalled()
        expect(wrapper.text()).not.toContain('旧导出失败')
        expect(button.attributes('disabled')).toBeDefined()
        const current = new Blob(['新导出'])
        resolveNew({ success: true, data: current })
        await flushPromises()
        expect(mocks.download).toHaveBeenCalledTimes(1)
        expect(mocks.download).toHaveBeenLastCalledWith(
          current,
          `整改分析_${change === '场景' ? 'final' : 'running'}.csv`,
        )
        expect(button.attributes('disabled')).toBeUndefined()
        await button.trigger('click')
        await flushPromises()
        expect(mocks.download).toHaveBeenCalledTimes(2)
        expect(button.attributes('disabled')).toBeUndefined()
      } finally {
        wrapper.unmount()
      }
    },
  )
  it('七标签明确已确认且可重叠，历史带冻结来源和提交提醒证据', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('七标签统计口径已确认')
    const unassigned = wrapper
      .findAll('.other-counts button')
      .find((item) => item.text().startsWith('尚未派发'))!
    expect(unassigned.get('strong').text()).toBe('2')
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
  it('七标签分组仅搬运owner计数，零值仍可筛选且不把可重叠计数相加', async () => {
    const labels = [
      { key: 'clinical_appeal', label: '临床申诉', defect_total: 3, case_total: 2 },
      { key: 'appeal_rejected', label: '申诉驳回', defect_total: 0, case_total: 0 },
      { key: 'appeal_approved', label: '申诉通过', defect_total: 2, case_total: 1 },
      { key: 'urged_pending', label: '催办待整改', defect_total: 0, case_total: 0 },
      { key: 'self_rectified', label: '医生自行整改', defect_total: 1, case_total: 1 },
      { key: 'not_urged_pending', label: '未催办待整改', defect_total: 0, case_total: 0 },
      { key: 'urged_rectified', label: '催办已整改', defect_total: 1, case_total: 1 },
    ]
    mocks.read.mockImplementation(async (filters) => ({
      success: true,
      data: {
        ...payload,
        labels,
        scope: filters,
        filter_label: filters.label || null,
        page: filters.page,
      },
    }))
    const wrapper = make()
    await flushPromises()
    expect(wrapper.get('[aria-label="整改跟踪"]').findAll('.remediation-metric')).toHaveLength(4)
    expect(wrapper.get('[aria-label="申诉复核"]').findAll('.remediation-metric')).toHaveLength(3)
    expect(
      wrapper
        .get('[aria-label="整改跟踪"]')
        .findAll('.remediation-metric')
        .map((item) => item.attributes('data-label')),
    ).toEqual(['urged_pending', 'not_urged_pending', 'self_rectified', 'urged_rectified'])
    for (const item of labels) {
      const metric = wrapper.get(`[data-label="${item.key}"]`)
      expect(metric.get('strong').text()).toBe(String(item.defect_total))
      expect(metric.get('small').text()).toBe(`${item.case_total} 份病历`)
      expect(metric.classes().includes('has-value')).toBe(item.defect_total > 0)
    }
    await wrapper.get('[data-label="appeal_rejected"]').trigger('click')
    await flushPromises()
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: 'appeal_rejected', page: 1 }),
      expect.any(AbortSignal),
    )
    expect(wrapper.get('[data-label="appeal_rejected"]').attributes('aria-pressed')).toBe('true')
    wrapper.unmount()
  })
  it('次级状态筛选、导出和全部重置仍使用原始label键', async () => {
    const wrapper = make()
    await flushPromises()
    const pending = wrapper
      .findAll('.other-counts button')
      .find((item) => item.text().startsWith('待质控验收'))!
    await pending.trigger('click')
    await flushPromises()
    expect(pending.attributes('aria-pressed')).toBe('true')
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: 'pending_acceptance', page: 1 }),
      expect.any(AbortSignal),
    )
    await wrapper.get('header button').trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: 'pending_acceptance' }),
      expect.any(AbortSignal),
    )
    await wrapper.get('.remediation-toolbar button').trigger('click')
    await flushPromises()
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: undefined, page: 1 }),
      expect.any(AbortSignal),
    )
    expect(wrapper.get('.remediation-toolbar button').attributes('aria-pressed')).toBe('true')
    wrapper.unmount()
  })
  it('未识别的owner标签仍原样展示，不因分组丢失计数', async () => {
    mocks.read.mockResolvedValue({
      success: true,
      data: {
        ...payload,
        labels: [{ key: 'future_label', label: '新增统计标签', defect_total: 4, case_total: 2 }],
      },
    })
    const wrapper = make()
    await flushPromises()
    expect(wrapper.get('[data-label="future_label"]').get('strong').text()).toBe('4')
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
      expect.any(AbortSignal),
    )
    await wrapper.get('.next').trigger('click')
    await flushPromises()
    expect(mocks.read).toHaveBeenLastCalledWith(
      expect.objectContaining({ label: 'clinical_appeal', page: 2 }),
      expect.any(AbortSignal),
    )
    await wrapper
      .findAll('button')
      .find((item) => item.text().includes('导出 CSV'))!
      .trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith(
      {
        scene: 'running',
        department: '内科',
        doctor: '甲医生',
        defect_source: 'all',
        label: 'clinical_appeal',
      },
      expect.any(AbortSignal),
    )
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
      expect.any(AbortSignal),
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
