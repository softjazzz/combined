import { ApiService } from '@/services/apiService'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { UserRole } from '@/types/auth'
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

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob,
  normalizeBatchExportBlob: vi.fn(async (blob: Blob) => blob),
}))

let workbenchProps: Record<string, unknown> | null = null

const QCRecordCompareWorkbenchStub = defineComponent({
  name: 'QCRecordCompareWorkbenchStub',
  props: {
    visitId: { type: String, default: '' },
    sourceView: { type: String, default: 'saved' },
    lazyResultDocuments: { type: Boolean, default: false },
    admissionTime: { type: String, default: '' },
    dischargeTime: { type: String, default: '' },
    jobId: { type: String, default: '' },
    recordRef: { type: String, default: '' },
    issues: { type: Array, default: () => [] },
    singleRecordItems: { type: Array, default: () => [] },
    debugContext: { type: Object, default: undefined },
    presentationMode: { type: String, default: 'flat' },
    feedbackAvailable: { type: Boolean, default: true },
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
      rule_id: 'LX0609-01-01-02',
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

function mountDrawer(presentationMode?: 'flat' | 'grouped', loadJobMetadata = true) {
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
      loadJobMetadata,
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
      },
    },
  })
}

// 原有完整视图用例固定为开发身份；演示身份在专项用例中显式切换。
beforeEach(async () => {
  setActivePinia(createPinia())
  vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
  vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
    success: true, data: { id: 'test-developer', roles: ['sync_admin'], is_demo_account: true },
  })
  await useAuthStore().initialize()
})

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
  })

  it.each(['sync_admin', UserRole.ADMIN] as const)('部分失败时保留已完成结果并隐藏失败横幅（%s）', async (role) => {
    vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
      success: true, data: { id: 'test-viewer', roles: [role], is_demo_account: true },
    })
    await useAuthStore().initialize()
    const partial = {
      ...readyResult,
      job_id: 'latest-partial-full',
      expected_rule_count: 76,
      result_rule_count: 75,
      is_complete: false,
      execution_status: 'partial_failed',
      failed_rule_count: 1,
      failed_rule_ids: ['LX0609-01-02-02'],
    }
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: partial })
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true, data: { status: 'failed', finished_at: '2026-10-25T09:16:48' },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(workbenchProps?.jobId).toBe('latest-partial-full')
    expect(workbenchProps?.singleRecordItems).toEqual(partial.items)
    expect(workbenchProps?.feedbackAvailable).toBe(false)
    expect(wrapper.text()).not.toContain('本次质控未全部完成')
    expect(wrapper.text()).not.toContain('自动重试')
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toContain('质控结束时间：')
  })

  it('只有定向结果时明确说明检查范围', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: {
      ...readyResult, result_scope: 'targeted', expected_rule_count: 13,
    } })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.text()).toContain('当前为定向质控结果，仅覆盖本次选择的 13 项')
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
    expect(workbenchProps?.sourceView).toBe('saved')
    expect(workbenchProps?.lazyResultDocuments).toBe(true)
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

  it('V5关闭冗余任务元数据请求，仍以三坐标读取原保存结果', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    getSichuanWorkspaceBatchJob.mockResolvedValue({ success: false, status: 404 })
    const wrapper = mountDrawer('grouped', false)
    await flushPromises()
    expect(getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(getLatestLuxian0609RecordResult).toHaveBeenCalledWith({
      instituteId: 'H1',
      patientId: 'P001',
      visitId: 'V001',
    })
    expect(workbenchProps?.singleRecordItems).toEqual(readyResult.items)
    expect(workbenchProps?.recordRef).toBe(readyResult.record_ref)
    expect(wrapper.find('.customer-record-result-title__qc-time').exists()).toBe(false)
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
})
