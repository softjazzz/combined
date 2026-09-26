/* eslint-disable vue/one-component-per-file */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import QCRecordResultComparisonDrawer from '@/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue'

const {
  downloadBlob,
  exportLatestLuxian0609RecordResult,
  getLatestLuxian0609RecordResult,
  getSichuanWorkspaceBatchJob,
} = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  exportLatestLuxian0609RecordResult: vi.fn(),
  getLatestLuxian0609RecordResult: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  exportLatestLuxian0609RecordResult,
  getLatestLuxian0609RecordResult,
  getSichuanWorkspaceBatchJob,
}))

const authState = vi.hoisted(() => ({
  roles: [] as string[],
  calls: 0,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => {
    authState.calls += 1
    return {
      user: { id: 'reviewer-1' },
      hasRole: (role: string) => authState.roles.includes(role),
    }
  },
}))

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob,
  normalizeBatchExportBlob: vi.fn(async (blob: Blob) => blob),
}))

let workbenchProps: Record<string, unknown> | null = null

const QCRecordCompareWorkbenchStub = defineComponent({
  name: 'QCRecordCompareWorkbenchStub',
  props: {
    visitId: { type: String, default: '' },
    admissionTime: { type: String, default: '' },
    dischargeTime: { type: String, default: '' },
    jobId: { type: String, default: '' },
    recordRef: { type: String, default: '' },
    issues: { type: Array, default: () => [] },
    singleRecordItems: { type: Array, default: () => [] },
    debugContext: { type: Object, default: undefined },
    presentationMode: { type: String, default: 'flat' },
  },
  setup(props) {
    workbenchProps = props as unknown as Record<string, unknown>
    return () => h('div', { class: 'record-compare-workbench-stub' })
  },
})

const readyResult = {
  schema_version: 'lx0609-single-record-result-v1' as const,
  state: 'ready' as const,
  reason_code: 'ok',
  record_ref: 'rec-safe-001',
  job_id: 'job-safe-001',
  rule_set_key: 'luxian_0609_qc_v1',
  rule_set_version: '2026.08.27',
  items: [
    {
      rule_id: 'LX0609-018',
      rule_name: '主诉能导出第一诊断',
      status: 'non_compliant',
      conclusion: '主诉长度不符合要求。',
    },
  ],
  expected_rule_count: 49,
  result_rule_count: 49,
  is_complete: true,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}

let reviewPanelProps: Record<string, unknown> | null = null

const CaseRecordReviewPanelStub = defineComponent({
  name: 'CaseRecordReviewPanel',
  props: {
    instituteId: { type: String, required: true },
    patientId: { type: String, required: true },
    visitId: { type: String, required: true },
    jobId: { type: String, default: undefined },
    userId: { type: String, default: undefined },
  },
  emits: ['review-submitted', 'forbidden'],
  setup(props) {
    reviewPanelProps = props as unknown as Record<string, unknown>
    return () => h('div', { 'data-testid': 'case-review-stub' })
  },
})

let manualDefectPanelProps: Record<string, unknown> | null = null

const CaseManualDefectPanelStub = defineComponent({
  name: 'CaseManualDefectPanel',
  props: {
    instituteId: { type: String, required: true },
    patientId: { type: String, required: true },
    visitId: { type: String, required: true },
  },
  emits: ['forbidden'],
  setup(props) {
    manualDefectPanelProps = props as unknown as Record<string, unknown>
    return () => h('div', { 'data-testid': 'case-manual-defects-stub' })
  },
})

let operationTimelineProps: Record<string, unknown> | null = null

const CaseOperationTimelineStub = defineComponent({
  name: 'CaseOperationTimeline',
  props: {
    instituteId: { type: String, required: true },
    patientId: { type: String, required: true },
    visitId: { type: String, required: true },
  },
  emits: ['forbidden'],
  setup(props) {
    operationTimelineProps = props as unknown as Record<string, unknown>
    return () => h('div', { 'data-testid': 'case-operations-stub' })
  },
})

function mountDrawer(
  presentationMode?: 'flat' | 'grouped',
  extraProps: Record<string, unknown> = {},
) {
  return mount(QCRecordResultComparisonDrawer, {
    props: {
      open: true,
      focus: {
        visitId: 'V001',
        instituteId: 'H1',
        patientId: 'P001',
        patientName: '周勇书',
        recordId: 'R001',
        admissionTime: '2026-06-18 07:02:00',
        dischargeTime: '2026-06-26 08:31:00',
        label: '测试病历',
      },
      ...(presentationMode ? { presentationMode } : {}),
      ...extraProps,
    },
    global: {
      stubs: {
        ADrawer: defineComponent({
          setup:
            (_, { slots }) =>
            () =>
              h('section', [slots.title?.(), slots.default?.()]),
        }),
        ASpin: defineComponent({
          setup:
            (_, { slots }) =>
            () =>
              h('div', slots.default?.()),
        }),
        AResult: defineComponent({
          props: { title: { type: String, default: '' } },
          setup: (props) => () => h('div', { class: 'result-stub' }, props.title),
        }),
        QCRecordCompareWorkbench: QCRecordCompareWorkbenchStub,
        CaseRecordReviewPanel: CaseRecordReviewPanelStub,
        CaseManualDefectPanel: CaseManualDefectPanelStub,
        CaseOperationTimeline: CaseOperationTimelineStub,
      },
    },
  })
}

describe('QCRecordResultComparisonDrawer', () => {
  beforeEach(() => {
    getLatestLuxian0609RecordResult.mockReset()
    getSichuanWorkspaceBatchJob.mockReset()
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { status: 'completed', finished_at: '2026-09-09T13:20:00+08:00' },
    })
    exportLatestLuxian0609RecordResult.mockReset()
    downloadBlob.mockReset()
    workbenchProps = null
    reviewPanelProps = null
    manualDefectPanelProps = null
    operationTimelineProps = null
    authState.roles = []
    authState.calls = 0
  })

  it('以醒目的当前病历上下文栏展示患者与质控完成信息', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-safe-001')
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toContain('质控完成时间：')
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toContain('13:20:00')

    expect(wrapper.get('.customer-record-result-title__context-label').text()).toBe('当前病历')
    expect(workbenchProps?.admissionTime).toBe('2026-06-18 07:02:00')
    expect(workbenchProps?.dischargeTime).toBe('2026-06-26 08:31:00')
    expect(wrapper.get('.customer-record-result-title__context-value').text()).toBe('测试病历')
    expect(wrapper.get('.customer-record-result-title__context-time').text()).toBe(
      '住院时间 2026-06-18 07:02:00 → 2026-06-26 08:31:00',
    )
    expect(wrapper.get('.customer-record-result-title__context').attributes('aria-label')).toBe(
      '当前病历：测试病历，入院时间：2026-06-18 07:02:00，出院时间：2026-06-26 08:31:00',
    )
  })

  it('缺少完成时间时不使用任务创建时间代替', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { status: 'completed', created_at: '2026-09-08T10:00:00' },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toBe('质控完成时间未返回')
  })

  it('当前结果所属任务仍运行时展示进行中', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    getSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: { status: 'running' } })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toBe('质控进行中')
  })

  it('任务服务无时区UTC时间转换为北京时间', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { status: 'completed', finished_at: '2026-09-09T05:20:00' },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toContain('13:20:00')
  })

  it('ready结果可按当前三坐标导出单病历HTML', async () => {
    const blob = new Blob(['<!doctype html>'], { type: 'text/html' })
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    exportLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: blob })
    const wrapper = mountDrawer('grouped')
    await flushPromises()

    await wrapper.get('.customer-record-result-title__export').trigger('click')
    await flushPromises()

    expect(exportLatestLuxian0609RecordResult).toHaveBeenCalledWith({
      instituteId: 'H1',
      patientId: 'P001',
      visitId: 'V001',
    })
    expect(downloadBlob).toHaveBeenCalledWith(blob, '单病历质控结果.html')
  })

  it('关闭或未选择病历时不请求单病历结果接口', async () => {
    const wrapper = mount(QCRecordResultComparisonDrawer, {
      props: { open: false, focus: null },
      global: {
        stubs: {
          ADrawer: defineComponent({
            setup:
              (_, { slots }) =>
              () =>
                h('section', slots.default?.()),
          }),
          ASpin: defineComponent({
            setup:
              (_, { slots }) =>
              () =>
                h('div', slots.default?.()),
          }),
          AResult: true,
          QCRecordCompareWorkbench: QCRecordCompareWorkbenchStub,
        },
      },
    })
    await flushPromises()

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.record-compare-workbench-stub').exists()).toBe(false)
    expect(getLatestLuxian0609RecordResult).not.toHaveBeenCalled()
  })

  it('ready DTO 将 job_id、record_ref 与固定 items 直接交给对照工作台', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })

    mountDrawer()
    await flushPromises()

    // 单病历原文读取与现有工作台使用 visitId 作为受控病历标识；
    // DTO 内的 record_ref 再作为服务端授权文书引用使用。
    expect(getLatestLuxian0609RecordResult).toHaveBeenCalledWith({
      instituteId: 'H1',
      patientId: 'P001',
      visitId: 'V001',
    })
    expect(workbenchProps?.visitId).toBe('V001')
    expect(workbenchProps?.jobId).toBe('job-safe-001')
    expect(workbenchProps?.recordRef).toBe('rec-safe-001')
    expect(workbenchProps?.singleRecordItems).toEqual(readyResult.items)
    expect(workbenchProps?.debugContext).toMatchObject({
      instituteId: 'H1',
      patientId: 'P001',
      patientName: '周勇书',
      visitId: 'V001',
      recordId: 'R001',
      recordRef: 'rec-safe-001',
      jobId: 'job-safe-001',
      ruleSetKey: 'luxian_0609_qc_v1',
      ruleSetVersion: '2026.08.27',
      expectedRuleCount: 49,
      resultRuleCount: 49,
      isComplete: true,
    })
    expect(workbenchProps?.presentationMode).toBe('flat')
  })

  it('显式分组模式只透传到对照工作台，不改写单病历结果', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })

    mountDrawer('grouped')
    await flushPromises()

    expect(workbenchProps?.presentationMode).toBe('grouped')
    expect(workbenchProps?.singleRecordItems).toEqual(readyResult.items)
  })

  it('切换病历后忽略上一病历的迟到响应，禁止跨三坐标闪现旧结果', async () => {
    const first = deferred<{ success: true; data: typeof readyResult }>()
    const second = deferred<{ success: true; data: typeof readyResult }>()
    getLatestLuxian0609RecordResult
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise)

    const wrapper = mountDrawer('grouped')
    await flushPromises()
    await wrapper.setProps({
      focus: {
        visitId: 'V002',
        instituteId: 'H2',
        patientId: 'P002',
        recordId: 'R002',
        label: '第二份病历',
      },
    })
    await flushPromises()

    second.resolve({
      success: true,
      data: { ...readyResult, job_id: 'job-second', record_ref: 'record-second' },
    })
    await flushPromises()
    expect(workbenchProps?.visitId).toBe('V002')
    expect(workbenchProps?.jobId).toBe('job-second')

    first.resolve({ success: true, data: readyResult })
    await flushPromises()
    expect(workbenchProps?.visitId).toBe('V002')
    expect(workbenchProps?.jobId).toBe('job-second')
    expect(workbenchProps?.recordRef).toBe('record-second')
  })

  it('not_found 时停止展示，不回退查询批量任务或其他病历结果', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({
      success: true,
      data: {
        ...readyResult,
        state: 'not_found',
        reason_code: 'no_completed_result',
        job_id: '',
        record_ref: '',
        items: [],
        result_rule_count: 0,
        is_complete: false,
      },
    })

    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.find('.record-compare-workbench-stub').exists()).toBe(false)
    expect(wrapper.text()).toContain('暂无已保存质控结果')
    expect(getLatestLuxian0609RecordResult).toHaveBeenCalledTimes(1)
  })

  it('technical_error 使用安全错误文案停止展示，不伪装成未质控或回退旧结果', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({
      success: true,
      data: {
        ...readyResult,
        state: 'technical_error',
        reason_code: 'canonical_envelope_invalid',
        job_id: '',
        record_ref: '',
        items: [],
        result_rule_count: 0,
        is_complete: false,
      },
    })

    const wrapper = mountDrawer('grouped')
    await flushPromises()

    expect(wrapper.find('.record-compare-workbench-stub').exists()).toBe(false)
    expect(wrapper.text()).toContain('质控结果读取异常')
    expect(wrapper.text()).not.toContain('暂无已保存质控结果')
    expect(getLatestLuxian0609RecordResult).toHaveBeenCalledTimes(1)
  })

  it('未开启病例审核时不挂载审核面板且不访问登录态', async () => {
    authState.roles = ['admin']
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.find('[data-testid="case-review-stub"]').exists()).toBe(false)
    expect(authState.calls).toBe(0)
  })

  it.each([
    [['admin'], true],
    [['qc_manager'], true],
    [['qc_staff'], false],
    [['doctor'], false],
  ])('开启病例审核后按角色 %j 决定是否挂载面板', async (roles, mounted) => {
    authState.roles = roles
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-review-stub"]').exists()).toBe(mounted)
    if (mounted) {
      expect(reviewPanelProps).toMatchObject({
        instituteId: 'H1',
        patientId: 'P001',
        visitId: 'V001',
        jobId: 'job-safe-001',
        userId: 'reviewer-1',
      })
    }
  })

  it('结果未就绪时不挂载审核面板', async () => {
    authState.roles = ['admin']
    getLatestLuxian0609RecordResult.mockResolvedValue({
      success: true,
      data: { ...readyResult, state: 'technical_error' },
    })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-review-stub"]').exists()).toBe(false)
  })

  it('审核提交后向列表转发三坐标与决定；403 时隐藏面板', async () => {
    authState.roles = ['qc_manager']
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    const panel = wrapper.getComponent(CaseRecordReviewPanelStub)
    panel.vm.$emit('review-submitted', 'doubtful')
    expect(wrapper.emitted('review-submitted')).toEqual([
      [{ instituteId: 'H1', patientId: 'P001', visitId: 'V001', decision: 'doubtful' }],
    ])

    panel.vm.$emit('forbidden')
    await flushPromises()
    expect(wrapper.find('[data-testid="case-review-stub"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('权限')
  })

  it('未传入导航 props 时不显示上一个/下一个', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    expect(wrapper.find('[data-testid="record-result-nav"]').exists()).toBe(false)
  })

  it('导航按钮按 hasPrev/hasNext 禁用，显示位置并发出 navigate 事件', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', {
      hasPrev: false,
      hasNext: true,
      currentIndex: 1,
      totalCount: 3,
    })
    await flushPromises()
    const prev = wrapper.get('[data-testid="record-result-nav-prev"]')
    const next = wrapper.get('[data-testid="record-result-nav-next"]')
    expect(prev.attributes('disabled')).toBeDefined()
    expect(next.attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="record-result-nav-position"]').text()).toBe('第 1 / 3 份')

    await next.trigger('click')
    expect(wrapper.emitted('navigate-next')).toHaveLength(1)
    await prev.trigger('click')
    expect(wrapper.emitted('navigate-prev')).toBeUndefined()

    await wrapper.setProps({ hasPrev: true, currentIndex: undefined })
    await wrapper.get('[data-testid="record-result-nav-prev"]').trigger('click')
    expect(wrapper.emitted('navigate-prev')).toHaveLength(1)
    expect(wrapper.find('[data-testid="record-result-nav-position"]').exists()).toBe(false)
  })

  it('人工缺陷分区与病例审核同条件挂载，并按三坐标传入', async () => {
    authState.roles = ['qc_manager']
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-manual-defects-stub"]').exists()).toBe(true)
    expect(manualDefectPanelProps).toMatchObject({ instituteId: 'H1', patientId: 'P001', visitId: 'V001' })

    // 审核面板 403 不影响人工缺陷分区；人工缺陷 403 只隐藏自身。
    wrapper.getComponent(CaseRecordReviewPanelStub).vm.$emit('forbidden')
    await flushPromises()
    expect(wrapper.find('[data-testid="case-review-stub"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="case-manual-defects-stub"]').exists()).toBe(true)
    wrapper.getComponent(CaseManualDefectPanelStub).vm.$emit('forbidden')
    await flushPromises()
    expect(wrapper.find('[data-testid="case-manual-defects-stub"]').exists()).toBe(false)
  })

  it.each([
    [['qc_staff'], true],
    [['admin'], false],
  ])('角色 %j 或未开启审核(%s)时不挂载人工缺陷分区', async (roles, recordReview) => {
    authState.roles = roles
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', recordReview ? { recordReview: true } : {})
    await flushPromises()
    expect(wrapper.find('[data-testid="case-manual-defects-stub"]').exists()).toBe(false)
  })

  it('操作记录位于人工缺陷之后，同条件挂载并按三坐标传入；403 只隐藏自身', async () => {
    authState.roles = ['admin']
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    const html = wrapper.html()
    expect(html.indexOf('case-operations-stub')).toBeGreaterThan(html.indexOf('case-manual-defects-stub'))
    expect(operationTimelineProps).toMatchObject({ instituteId: 'H1', patientId: 'P001', visitId: 'V001' })

    // 审核面板与人工缺陷 403 不影响操作记录；操作记录 403 只隐藏自身。
    wrapper.getComponent(CaseManualDefectPanelStub).vm.$emit('forbidden')
    wrapper.getComponent(CaseRecordReviewPanelStub).vm.$emit('forbidden')
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operations-stub"]').exists()).toBe(true)
    wrapper.getComponent(CaseOperationTimelineStub).vm.$emit('forbidden')
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operations-stub"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('权限')
  })

  it.each([
    [['qc_staff'], true],
    [['admin'], false],
  ])('角色 %j 或未开启审核(%s)时不挂载操作记录', async (roles, recordReview) => {
    authState.roles = roles
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer('grouped', recordReview ? { recordReview: true } : {})
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operations-stub"]').exists()).toBe(false)
  })

  it('结果未就绪时不挂载操作记录', async () => {
    authState.roles = ['admin']
    getLatestLuxian0609RecordResult.mockResolvedValue({
      success: true,
      data: { ...readyResult, state: 'technical_error' },
    })
    const wrapper = mountDrawer('grouped', { recordReview: true })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operations-stub"]').exists()).toBe(false)
  })
})
