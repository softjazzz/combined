import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getSichuanWorkspaceBatchJob: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getSichuanWorkspaceBatchJob: mocks.getSichuanWorkspaceBatchJob,
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
  beforeEach(() => {
    vi.clearAllMocks()
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
            rule_code: 'LX0609-017',
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
    expect(wrapper.text()).toContain('已执行 18 / 75 个质控点')
    expect(wrapper.text()).toContain('当前：LX0609-017 不合理复制病历')

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
})
