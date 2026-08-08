/* eslint-disable vue/one-component-per-file */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import QCRecordResultComparisonDrawer from '@/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue'

const { getLatestLuxian0609RecordResult } = vi.hoisted(() => ({
  getLatestLuxian0609RecordResult: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getLatestLuxian0609RecordResult,
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

function mountDrawer() {
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
    },
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
    workbenchProps = null
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
})
