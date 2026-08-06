import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CustomerSampleQcTaskStatusBar from '@/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const stubs = {
  'a-button': {
    template: '<button :disabled="disabled"><slot /></button>',
    props: ['disabled', 'loading', 'danger', 'size', 'type'],
  },
  'a-spin': {
    template: '<div><slot /></div>',
    props: ['spinning'],
  },
}

function buildJob(overrides: Partial<SichuanBatchJob> = {}): SichuanBatchJob {
  return {
    id: 'job-1',
    rule_code: 'LX0609-BATCH',
    rule_name: '泸县0609质控点验证 v1',
    rule_set_key: 'luxian_0609_qc_v1',
    rule_set_name: '泸县0609质控点验证 v1',
    scope: 'final',
    status: 'running',
    customer_rule_count: 49,
    total_records: 2,
    created_at: '2026-07-31T12:00:00+08:00',
    updated_at: '2026-07-31T12:01:00+08:00',
    summary: {
      total_records: 2,
      success_count: 1,
      failed_count: 0,
      issue_records: 1,
      compliant_records: 0,
      total_tokens: 0,
      total_processing_time: 0,
      customer_rule_count: 49,
      progress_percent: 50,
      display_status_counts: {
        non_compliant: 3,
        data_gap: 1,
      },
    },
    ...overrides,
  }
}

describe('CustomerSampleQcTaskStatusBar', () => {
  it('没有任务时不渲染状态条', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: { task: null },
      global: { stubs },
    })

    expect(wrapper.find('[data-testid="customer-sample-qc-task-status"]').exists()).toBe(false)
  })

  it('运行中展示进度并发出查看、停止和历史事件', async () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: { task: buildJob() },
      global: { stubs },
    })

    const text = wrapper.text()
    expect(text).toContain('正在执行质控')
    expect(text).toContain('病历进度：已完成 1 / 2 份')
    expect(text).toContain('结果回写：4 / 98 条')
    expect(text).toContain('不合规 3')
    expect(text).toContain('数据不足 1')

    await wrapper.get('[data-testid="qc-task-view-result"]').trigger('click')
    await wrapper.get('[data-testid="qc-task-cancel"]').trigger('click')
    await wrapper.get('[data-testid="qc-task-open-history"]').trigger('click')

    expect(wrapper.emitted('view-result')).toEqual([['job-1']])
    expect(wrapper.emitted('cancel')).toEqual([['job-1']])
    expect(wrapper.emitted('open-history')).toHaveLength(1)
  })

  it('运行中尚无完成病例时使用动态等待进度而不是静态空轨道', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          summary: {
            ...buildJob().summary,
            success_count: 0,
            progress_percent: 0,
            display_status_counts: {},
          },
          items: [],
        }),
      },
      global: { stubs },
    })

    const progress = wrapper.get('[data-testid="qc-task-running-progress"]')
    expect(progress.classes()).toContain('is-running')
    expect(progress.classes()).toContain('is-indeterminate')
    expect(progress.attributes('aria-label')).toBe('质控执行中，等待首份病历完成')
  })

  it('完成后保留查看、复核、导出和历史入口', async () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({ status: 'completed', finished_at: '2026-07-31T12:02:00+08:00' }),
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.classes()).toContain('is-collapsed')
    expect(wrapper.get('[data-testid="qc-task-settled-summary"]').text()).toContain(
      '病历进度：已完成 1 / 2 份',
    )
    expect(wrapper.text()).toContain('查看结果')
    expect(wrapper.text()).toContain('复核本次结果')
    expect(wrapper.text()).toContain('导出 HTML')

    await wrapper.get('[data-testid="qc-task-review"]').trigger('click')
    await wrapper.get('[data-testid="qc-task-export"]').trigger('click')

    expect(wrapper.emitted('review')).toEqual([['job-1']])
    expect(wrapper.emitted('export')).toEqual([['job-1']])
  })

  it.each([
    ['failed', '执行失败'],
    ['canceled', '已取消'],
  ] as const)('%s 状态使用客户可读文案', (status, label) => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: { task: buildJob({ status }) },
      global: { stubs },
    })

    expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain('查看结果')
  })
})
