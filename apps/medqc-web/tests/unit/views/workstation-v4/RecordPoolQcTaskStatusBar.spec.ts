import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  exportSichuanWorkspaceBatchJob: mocks.exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob: mocks.getSichuanWorkspaceBatchJob,
}))

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: mocks.downloadBlob,
  normalizeBatchExportBlob: vi.fn(async (blob: Blob) => blob),
}))

import RecordPoolQcTaskStatusBar from '@/views/workstation-v4/components/workbench/RecordPoolQcTaskStatusBar.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

function job(overrides: Partial<SichuanBatchJob> = {}): SichuanBatchJob {
  return {
    id: 'job-1',
    rule_code: 'LX0609',
    rule_name: '泸县0609质控',
    scope: 'all',
    status: 'queued',
    total_records: 4,
    ...overrides,
  }
}

describe('RecordPoolQcTaskStatusBar', () => {
  it('执行态展示状态标签和阶段说明，完成态不保留执行标识', async () => {
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: { job: job({ status: 'running' }), autoPoll: false },
    })
    expect(wrapper.classes()).toContain('is-active')
    expect(wrapper.find('.record-pool-qc-status__live-dot').exists()).toBe(true)
    expect(wrapper.get('.record-pool-qc-status__heading').text()).toContain('执行中')
    expect(wrapper.get('.record-pool-qc-status__phase').text()).not.toBe('')
    await wrapper.setProps({ job: job({ status: 'completed' }) })
    expect(wrapper.find('.record-pool-qc-status__live-dot').exists()).toBe(false)
    expect(wrapper.find('.record-pool-qc-status__phase').exists()).toBe(false)
    wrapper.unmount()
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('completed task downloads the exact batch HTML instead of current filters', async () => {
    const blob = new Blob(['<!doctype html>'], { type: 'text/html' })
    mocks.exportSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: blob })
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: { job: job({ status: 'completed', success_count: 4, failed_count: 0 }) },
      global: { stubs: { AProgress: true } },
    })

    await wrapper.get('.record-pool-qc-status__export').trigger('click')
    await flushPromises()

    expect(mocks.exportSichuanWorkspaceBatchJob).toHaveBeenCalledWith({
      job_id: 'job-1',
      format: 'html',
    })
    expect(mocks.downloadBlob).toHaveBeenCalledWith(blob, '本次批量质控结果.html')
  })

  it('polls the created task and shows record, rule and current-stage progress', async () => {
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: job({
        status: 'running',
        success_count: 1,
        failed_count: 0,
        summary: {
          total_records: 4,
          success_count: 1,
          failed_count: 0,
          issue_records: 1,
          compliant_records: 0,
          total_tokens: 120,
          total_processing_time: 5,
          customer_rule_count: 75,
          processed_rule_count: 18,
          current_rule: {
            rule_code: 'LX0609-12-01-02',
            rule_name: '不合理复制病历',
          },
        },
      }),
    })

    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: { job: job() },
      global: {
        stubs: {
          AProgress: true,
        },
      },
    })
    await flushPromises()

    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-1')
    expect(wrapper.get('[role="status"]').text()).toContain('正在执行质控')
    expect(wrapper.text()).toContain('已处理 1 / 4 份病历')
    expect(wrapper.text()).toContain('当前单份规则进度 18 / 75 个质控点')
    expect(wrapper.text()).toContain('当前：LX0609-12-01-02 不合理复制病历')

    wrapper.unmount()
  })

  it('shows a completed summary without starting another poll', async () => {
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: {
        job: job({
          status: 'completed',
          success_count: 3,
          failed_count: 1,
        }),
      },
      global: {
        stubs: {
          AProgress: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('质控任务已完成')
    expect(wrapper.text()).toContain('成功 3 份')
    expect(wrapper.text()).toContain('失败 1 份')
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
  })

  it('continues polling through the transient failed state used by automatic retry', async () => {
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: job({ status: 'completed', success_count: 20, failed_count: 0 }),
    })
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: {
        job: job({
          status: 'failed',
          summary: {
            total_records: 20,
            success_count: 19,
            failed_count: 1,
            issue_records: 0,
            compliant_records: 19,
            total_tokens: 0,
            total_processing_time: 0,
            execution_status: 'partial_failed',
            automatic_failed_rule_retry: { status: 'queued', should_retry: true },
          },
        }),
      },
      global: { stubs: { AProgress: true } },
    })

    expect(wrapper.text()).toContain('正在自动补跑失败项')
    await flushPromises()

    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-1')
    expect(wrapper.text()).toContain('质控任务已完成')
    expect(wrapper.emitted('completed')).toHaveLength(1)
    expect(wrapper.emitted('results-updated')).toHaveLength(1)
    wrapper.unmount()
  })

  it('轮询确认部分失败时通知刷新已保存结果，只发一次终态事件', async () => {
    const terminal = job({
      status: 'failed',
      summary: {
        total_records: 2,
        success_count: 1,
        failed_count: 1,
        issue_records: 0,
        compliant_records: 1,
        total_tokens: 0,
        total_processing_time: 0,
        execution_status: 'partial_failed',
        completed_rule_count: 151,
        failed_rule_count: 1,
        automatic_failed_rule_retry: { status: 'not_retryable', should_retry: false },
      },
    })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: terminal })
    const wrapper = mount(RecordPoolQcTaskStatusBar, { props: { job: job({ status: 'running' }) } })
    await flushPromises()
    expect(wrapper.emitted('results-updated')).toHaveLength(1)
    expect(wrapper.emitted('completed')).toBeUndefined()
    expect(wrapper.text()).toContain('不适合自动补跑')
    expect(wrapper.text()).toContain('质控任务部分执行失败')
    expect(wrapper.text()).toContain('已保留 151 项有效结果')
    expect(wrapper.text()).toContain('1 项未完成')
    expect(wrapper.classes()).not.toContain('is-active')
    wrapper.unmount()
  })

  it('stops polling and leaves the running presentation when completed results fail contract validation', async () => {
    vi.useFakeTimers()
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: false,
      message: '历史质控结果交付合同不完整，无法安全展示',
    })
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: {
        job: job({
          status: 'running',
          total_records: 11,
          summary: {
            total_records: 11,
            success_count: 11,
            failed_count: 0,
            issue_records: 0,
            compliant_records: 11,
            total_tokens: 0,
            total_processing_time: 0,
            progress_percent: 100,
            progress: {
              processed_records: 11,
              total_records: 11,
              active_record_count: 0,
              queued_record_count: 0,
              max_parallel_records: 11,
            },
          },
        }),
        pollIntervalMs: 500,
      },
      global: { stubs: { AProgress: true } },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('质控结果暂不可查看')
    expect(wrapper.text()).toContain('历史质控结果交付合同不完整，无法安全展示')
    expect(wrapper.text()).not.toContain('正在执行质控')

    await vi.advanceTimersByTimeAsync(2000)
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('持续读取失败达到上限后暂停轮询', async () => {
    vi.useFakeTimers()
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: false,
      status: 502,
      message: '上游服务暂不可用',
    })
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: {
        job: job({ status: 'running' }),
        pollIntervalMs: 500,
      },
      global: { stubs: { AProgress: true } },
    })

    await flushPromises()
    await vi.advanceTimersByTimeAsync(500 * 11)
    await flushPromises()
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(12)
    expect(wrapper.text()).toContain('已暂停自动刷新')

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(12)

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('shows the real four-stage workflow and projected in-flight rule progress', async () => {
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: job({
        status: 'running',
        total_records: 1,
        summary: {
          total_records: 1,
          success_count: 0,
          failed_count: 0,
          issue_records: 0,
          compliant_records: 0,
          total_tokens: 0,
          total_processing_time: 0,
          rule_count: 49,
          progress: {
            step_key: 'run',
            processed_rule_count: 18,
            rule_count: 49,
            processed_records: 0,
            total_records: 1,
          },
        },
      }),
    })

    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: { job: job({ total_records: 1 }) },
      global: {
        stubs: {
          AProgress: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('已执行 18 / 49 个质控点')
    const stages = wrapper.get('[data-testid="record-pool-qc-task-stages"]')
    expect(stages.text()).toContain('确认质控范围')
    expect(stages.text()).toContain('准备病历资料')
    expect(stages.text()).toContain('执行质控规则')
    expect(stages.text()).toContain('汇总并保存结果')
    expect(stages.find('[data-stage-key="scope"]').classes()).toContain('is-complete')
    expect(stages.find('[data-stage-key="records"]').classes()).toContain('is-complete')
    expect(stages.find('[data-stage-key="rules"]').classes()).toContain('is-active')
    expect(stages.find('[data-stage-key="result"]').classes()).toContain('is-pending')

    wrapper.unmount()
  })

  it('shows honest multi-record concurrency, completed and queued counts', async () => {
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: job({
        status: 'running',
        total_records: 14,
        summary: {
          total_records: 14,
          success_count: 1,
          failed_count: 0,
          issue_records: 0,
          compliant_records: 1,
          total_tokens: 0,
          total_processing_time: 0,
          rule_count: 49,
          progress: {
            step_key: 'run',
            processed_rule_count: 18,
            rule_count: 49,
            processed_records: 1,
            total_records: 14,
            max_parallel_records: 4,
            active_record_count: 4,
            queued_record_count: 9,
          },
        },
      }),
    })

    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: { job: job({ total_records: 14 }) },
      global: {
        stubs: {
          AProgress: true,
        },
      },
    })
    await flushPromises()

    const concurrency = wrapper.get('[data-testid="record-pool-qc-concurrency"]')
    expect(concurrency.text()).toContain('并发 4 份')
    expect(concurrency.text()).toContain('执行中 4 份')
    expect(concurrency.text()).toContain('已完成 1 份')
    expect(concurrency.text()).toContain('排队 9 份')
    expect(wrapper.text()).toContain('当前单份规则进度 18 / 49 个质控点')

    wrapper.unmount()
  })
})

it('材料准备失败显示根因与零执行，不显示76条已执行', () => {
  const wrapper = mount(RecordPoolQcTaskStatusBar, {
    props: { autoPoll:false, job:job({status:'failed',total_records:1, summary:{total_records:1,success_count:0,failed_count:1,issue_records:0,compliant_records:0,total_tokens:0,total_processing_time:0,rule_count:76, processed_rule_count:0,failed_rule_count:0, material_failed_record_count:1,
      material_failure:{code:'cdm_publication_window_unconfirmed',stage:'material_capture',message:'CDM发布范围与取材窗口尚未确认，未开始执行该病历的质控规则。'},
      progress:{step_key:'failed',processed_rule_count:0,rule_count:76,processed_records:1,total_records:1}}})},
    global:{stubs:{AProgress:true}},
  })
  expect(wrapper.text()).toContain('取材窗口')
  expect(wrapper.text()).toContain('0 / 76')
  expect(wrapper.text()).not.toContain('已执行 76')
  expect(wrapper.text()).not.toContain('补跑未确认')
  wrapper.unmount()
})

it('失败任务提供明确任务ID入口，不依赖通知ID', () => {
  const wrapper = mount(RecordPoolQcTaskStatusBar, {
    props: { job: job({ id: 'failed-job', status: 'failed' }), autoPoll: false },
  })
  expect(wrapper.get('[data-testid="qc-task-detail-link"]').attributes('href')).toBe(
    '/workstation-v5/qc-task?job_id=failed-job',
  )
  wrapper.unmount()
})
