import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({ confirmedResultsOnly: ref(false) }),
}))

import RecordPoolQcTaskHistory from '@/views/workstation-v4/components/workbench/RecordPoolQcTaskHistory.vue'

const listJobs = vi.fn()
const getJob = vi.fn()
const getDebug = vi.fn()
const reviewJob = vi.fn()
const cancelJob = vi.fn()

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  listSichuanWorkspaceBatchJobs: (...args: unknown[]) => listJobs(...args),
  getSichuanWorkspaceBatchJob: (...args: unknown[]) => getJob(...args),
  getSichuanWorkspaceBatchJobDebugSnapshot: (...args: unknown[]) => getDebug(...args),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  reviewSichuanWorkspaceBatchJob: (...args: unknown[]) => reviewJob(...args),
  cancelSichuanWorkspaceBatchJob: (...args: unknown[]) => cancelJob(...args),
}))

const passthrough = (name: string, tag = 'div') =>
  defineComponent({
    name,
    setup(_props, { attrs, slots }) {
      return () => h(tag, attrs, [slots.title?.(), slots.default?.()])
    },
  })

describe('RecordPoolQcTaskHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listJobs.mockResolvedValue({
      success: true,
      data: {
        total: 2,
        page: 1,
        page_size: 30,
        items: [
          {
            id: 'record-pool-job',
            rule_code: 'LX0609',
            rule_name: '泸县0609质控',
            rule_set_key: 'luxian_0609_qc_v1',
            rule_set_name: '泸县0609质控点验证 v1',
            scope: 'all',
            status: 'completed',
            total_records: 20,
            created_at: '2026-09-16T06:18:52Z',
            wall_clock_time: 311,
            summary: { total_records: 20 },
          },
          {
            id: 'other-job',
            rule_code: 'SC',
            rule_name: '其他规则任务',
            rule_set_key: 'sc_content_full_v1',
            scope: 'all',
            status: 'completed',
            total_records: 3,
          },
        ],
      },
    })
    getJob.mockResolvedValue({
      success: true,
      data: {
        id: 'record-pool-job',
        rule_code: 'LX0609',
        rule_name: '泸县0609质控',
        rule_set_key: 'luxian_0609_qc_v1',
        scope: 'all',
        status: 'completed',
      },
    })
    getDebug.mockResolvedValue({
      success: true,
      data: {
        job_id: 'record-pool-job',
        status: 'completed',
        scope: 'all',
        rules: [],
        recent_items: [],
        recent_failed_records: [],
      },
    })
  })

  it('loads only record-pool QC jobs and opens their existing detail drawer', async () => {
    const wrapper = mount(RecordPoolQcTaskHistory, {
      global: {
        stubs: {
          AButton: passthrough('AButton', 'button'),
          ADrawer: passthrough('ADrawer'),
          ASpin: passthrough('ASpin'),
          AEmpty: passthrough('AEmpty'),
          SemanticRulesBatchResultDrawer: defineComponent({
            name: 'SemanticRulesBatchResultDrawer',
            props: {
              open: Boolean,
              batchJobDetail: Object,
              backLabel: String,
            },
            setup(props) {
              return () =>
                h('div', {
                  'data-testid': 'batch-job-detail-drawer',
                  'data-open': String(props.open),
                  'data-job-id': String((props.batchJobDetail as { id?: string } | null)?.id || ''),
                  'data-back-label': String(props.backLabel || ''),
                })
            },
          }),
        },
      },
    })

    await wrapper.get('[data-testid="record-pool-qc-task-history-entry"]').trigger('click')
    await flushPromises()

    expect(listJobs).toHaveBeenCalledWith({
      page: 1,
      page_size: 30,
      exclude_validation: true,
    })
    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).not.toContain('其他规则任务')

    await wrapper.get('.record-pool-task-history__item').trigger('click')
    await flushPromises()

    expect(getJob).toHaveBeenCalledWith('record-pool-job')
    expect(getDebug).toHaveBeenCalledWith('record-pool-job', {
      rule_job_id: undefined,
      item_limit: undefined,
    })
    expect(wrapper.get('[data-testid="batch-job-detail-drawer"]').attributes('data-open')).toBe(
      'true',
    )
    expect(wrapper.get('[data-testid="batch-job-detail-drawer"]').attributes('data-job-id')).toBe(
      'record-pool-job',
    )
    expect(
      wrapper.get('[data-testid="batch-job-detail-drawer"]').attributes('data-back-label'),
    ).toBe('返回病历池')
  })

  it('wires review-batch-job-result and cancel-batch-job to SemanticRulesBatchResultDrawer', async () => {
    reviewJob.mockResolvedValue({
      success: true,
      data: {
        job: {
          id: 'record-pool-job',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控',
          rule_set_key: 'luxian_0609_qc_v1',
          scope: 'all',
          status: 'completed',
          summary: {
            review_report: {
              scope: 'luxian_0609_qc_v1',
              summary: { total_findings: 1 },
              findings: [],
            },
          },
        },
        review_report: {
          scope: 'luxian_0609_qc_v1',
          summary: { total_findings: 1 },
          findings: [],
        },
      },
    })
    cancelJob.mockResolvedValue({
      success: true,
      data: {
        id: 'record-pool-job',
        rule_code: 'LX0609',
        rule_name: '泸县0609质控',
        rule_set_key: 'luxian_0609_qc_v1',
        scope: 'all',
        status: 'canceled',
      },
    })

    let capturedReview: (() => Promise<void> | void) | undefined
    let capturedCancel: ((jobId: string) => Promise<void> | void) | undefined
    const wrapper = mount(RecordPoolQcTaskHistory, {
      global: {
        stubs: {
          AButton: passthrough('AButton', 'button'),
          ADrawer: passthrough('ADrawer'),
          ASpin: passthrough('ASpin'),
          AEmpty: passthrough('AEmpty'),
          SemanticRulesBatchResultDrawer: defineComponent({
            name: 'SemanticRulesBatchResultDrawer',
            props: {
              open: Boolean,
              batchJobDetail: Object,
              reviewBatchJobResult: Function,
              cancelBatchJob: Function,
            },
            setup(props) {
              return () => {
                capturedReview = props.reviewBatchJobResult as typeof capturedReview
                capturedCancel = props.cancelBatchJob as typeof capturedCancel
                return h('div', {
                  'data-testid': 'batch-job-detail-drawer',
                  'data-status': String(
                    (props.batchJobDetail as { status?: string } | null)?.status || '',
                  ),
                })
              }
            },
          }),
        },
      },
    })

    await wrapper.get('[data-testid="record-pool-qc-task-history-entry"]').trigger('click')
    await flushPromises()
    await wrapper.get('.record-pool-task-history__item').trigger('click')
    await flushPromises()

    expect(typeof capturedReview).toBe('function')
    expect(typeof capturedCancel).toBe('function')

    await capturedReview?.()
    await flushPromises()
    expect(reviewJob).toHaveBeenCalledWith('record-pool-job')

    getJob.mockResolvedValueOnce({
      success: true,
      data: {
        id: 'record-pool-job',
        rule_code: 'LX0609',
        rule_name: '泸县0609质控',
        rule_set_key: 'luxian_0609_qc_v1',
        scope: 'all',
        status: 'canceled',
      },
    })
    await capturedCancel?.('record-pool-job')
    await flushPromises()
    expect(cancelJob).toHaveBeenCalledWith('record-pool-job')
    expect(wrapper.get('[data-testid="batch-job-detail-drawer"]').attributes('data-status')).toBe(
      'canceled',
    )
  })
})
