/* eslint-disable vue/one-component-per-file */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import QCRecordResultComparisonDrawer from '@/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue'

const { downloadBlob, exportLatestLuxian0609RecordResult, getLatestLuxian0609RecordResult } =
  vi.hoisted(() => ({
    downloadBlob: vi.fn(),
    exportLatestLuxian0609RecordResult: vi.fn(),
    getLatestLuxian0609RecordResult: vi.fn(),
  }))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  exportLatestLuxian0609RecordResult,
  getLatestLuxian0609RecordResult,
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
    jobId: { type: String, default: '' },
    recordRef: { type: String, default: '' },
    issues: { type: Array, default: () => [] },
    singleRecordItems: { type: Array, default: () => [] },
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

function mountDrawer(presentationMode?: 'flat' | 'grouped') {
  return mount(QCRecordResultComparisonDrawer, {
    props: {
      open: true,
      focus: {
        visitId: 'V001',
        instituteId: 'H1',
        patientId: 'P001',
        recordId: 'R001',
        label: '测试病历',
      },
      ...(presentationMode ? { presentationMode } : {}),
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

describe('QCRecordResultComparisonDrawer', () => {
  beforeEach(() => {
    getLatestLuxian0609RecordResult.mockReset()
    exportLatestLuxian0609RecordResult.mockReset()
    downloadBlob.mockReset()
    workbenchProps = null
  })

  it('以醒目的当前病历上下文栏展示患者与质控完成信息', async () => {
    getLatestLuxian0609RecordResult.mockResolvedValue({ success: true, data: readyResult })
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.get('.customer-record-result-title__context-label').text()).toBe('当前病历')
    expect(wrapper.get('.customer-record-result-title__context-value').text()).toBe('测试病历')
    expect(wrapper.get('.customer-record-result-title__context').attributes('aria-label')).toBe(
      '当前病历：测试病历',
    )
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
