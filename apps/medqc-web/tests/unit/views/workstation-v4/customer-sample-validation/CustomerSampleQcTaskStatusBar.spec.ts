import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { UserRole, type User } from '@/types/auth'
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
  'a-dropdown': {
    template: '<div><slot /><slot name="overlay" /></div>',
    props: ['placement'],
  },
  'a-menu': {
    template: '<div><slot /></div>',
  },
  'a-menu-item': {
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
    props: ['disabled'],
    emits: ['click'],
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
  // 原有完整视图用例固定为开发身份；演示和普通受限身份在专项用例中显式切换。
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
      success: true,
      data: { id: 'test-developer', roles: ['sync_admin'], is_demo_account: true },
    })
    await useAuthStore().initialize()
  })

  it('C11 结算后的任务卡显示75项有效结果及1项失败，不再显示0条回写', () => {
    const job = buildJob({
      status: 'failed',
      total_records: 1,
      customer_rule_count: 76,
      items: [],
      progress: { processed_records: 1, total_records: 1, step_key: 'failed' },
    })
    Object.assign(job.summary!, {
      total_records: 1,
      success_count: 0,
      failed_count: 1,
      progress_percent: 0,
      execution_status: 'partial_failed',
      completed_rule_count: 75,
      failed_rule_count: 1,
      display_status_counts: {},
      status_breakdown: {},
      automatic_failed_rule_retry: { status: 'not_retryable', should_retry: false },
    })
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: { task: job },
      global: { stubs },
    })
    const text = wrapper.text()
    expect(text).toContain('部分执行失败')
    expect(text).toContain('病历进度：已处理 1 / 1 份（全部成功 0 份）')
    expect(text).toContain('结果回写：75 / 76 条（75 项有效结果，1 项失败）')
    expect(text).not.toContain('结果回写：0 /')
    expect(text).not.toContain('自动补跑中')
    expect(wrapper.find('[data-testid="qc-task-cancel"]').exists()).toBe(false)
    wrapper.unmount()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

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
    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain(
      '等待首条质控结果回写',
    )
  })

  it('轮询回写首条结果后立即替换等待提示', async () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: { task: buildJob({ items: [] }) },
      global: { stubs },
    })

    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain(
      '等待首条质控结果回写',
    )

    await wrapper.setProps({
      task: buildJob({
        items: [
          {
            rule_id: 'LX0609-06-01-05',
            rule_name: 'CT/MRI阳性结果无分析',
            status: 'data_gap',
            is_compliant: null,
            conclusion: '缺少评价截止日期或有效出院时间。',
          },
        ],
      }),
    })

    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain('LX0609-06-01-05')
    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain('数据不足')
    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain(
      '缺少评价截止日期或有效出院时间。',
    )
  })

  it('单病历尚未形成Canonical结果时展示真实执行阶段，不伪造结论', () => {
    const executorStreamState = {
      enabled: true,
      kind: 'native_executor_phase',
      event: 'started',
      executor_key: 'course_quality',
      completed_batches: 4,
      total_batches: 10,
    }
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          items: [],
          summary: {
            ...buildJob().summary,
            stream_state: executorStreamState,
          },
        }),
      },
      global: { stubs },
    })

    const liveResult = wrapper.get('[data-testid="qc-task-live-result"]').text()
    expect(liveResult).toContain('执行动态')
    expect(liveResult).toContain('正在核对病程质量（4 / 10）')
    expect(liveResult).not.toContain('合规')
    expect(liveResult).not.toContain('不合规')
    expect(wrapper.text()).not.toContain('正在准备首份结果')
  })

  it('已有规则族结果但尚未完成病历时，不再提示准备首份结果', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          total_records: 20,
          success_count: 0,
          items: [],
          summary: {
            ...buildJob().summary!,
            total_records: 20,
            success_count: 0,
            progress_percent: 0,
            display_status_counts: { non_compliant: 2 },
            progress: { processed_records: 0, total_records: 20 },
            stream_state: {
              kind: 'native_executor_phase',
              event: 'published',
              executor_key: 'basic_timeliness',
              partial_item_count: 2,
            },
          },
        }),
      },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('已有 2 项有效结果')
    expect(wrapper.text()).not.toContain('正在准备首份结果')
    expect(wrapper.text()).toContain('已完成 0 / 20')
  })

  it('运行中放大进度并轮播服务端已回写的真实结果', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          items: [
            {
              rule_id: 'LX0609-03-01-01',
              rule_name: '会诊意见及执行情况',
              status: 'non_compliant',
              is_compliant: false,
              conclusion: '后续病程未记录会诊意见及执行情况。',
            },
            {
              rule_id: 'LX0609-07-02-01',
              rule_name: '输血记录',
              status: 'compliant',
              is_compliant: true,
              conclusion: '已找到输血记录。',
            },
          ],
        }),
      },
      global: { stubs },
    })

    expect(wrapper.classes()).toContain('is-expanded')
    expect(wrapper.text()).toContain('当前进度 50%')
    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain('LX0609-07-02-01')
    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain('已找到输血记录。')

    await vi.advanceTimersByTimeAsync(3600)

    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain('LX0609-03-01-01')
    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain(
      '后续病程未记录会诊意见及执行情况。',
    )
  })

  it.each<[string, User]>([
    ['演示管理员', { id: 'demo-admin', roles: [UserRole.ADMIN], is_demo_account: true }],
    ['普通非全量用户', { id: 'regular-user', roles: [UserRole.QC_STAFF] }],
  ])('%s的实时栏只展示非内部确定问题', async (_name, user) => {
    setActivePinia(createPinia())
    vi.mocked(ApiService.getCurrentUser).mockResolvedValue({ success: true, data: user })
    await useAuthStore().initialize()
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          items: [
            {
              rule_id: 'LX0609-03-01-01',
              rule_name: '会诊意见及执行情况',
              status: 'non_compliant',
              is_compliant: false,
              conclusion: '应保留的确定问题。',
            },
            ...Array.from({ length: 6 }, (_, index) => ({
              rule_id: `LX0609-09-01-0${index + 1}`,
              rule_name: '非确定结论',
              status: index % 2 === 0 ? 'compliant' : 'data_gap',
              is_compliant: index % 2 === 0 ? true : null,
              conclusion: `不应展示的最近结论${index + 1}`,
            })),
            {
              rule_id: 'LX0609-12-01-01',
              rule_name: '内部确定问题',
              status: 'non_compliant',
              is_compliant: false,
              internal_only: true,
              conclusion: '不应展示的内部问题。',
            },
          ],
        }),
      },
      global: { stubs },
    })

    const liveResult = wrapper.get('[data-testid="qc-task-live-result"]').text()
    expect(liveResult).toContain('应保留的确定问题。')
    expect(liveResult).not.toContain('不应展示的最近结论')
    expect(liveResult).not.toContain('不应展示的内部问题。')
    wrapper.unmount()
  })

  it('带演示标记的sync_admin仍保留完整实时结论', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          items: [
            {
              rule_id: 'LX0609-07-02-01',
              rule_name: '输血记录',
              status: 'compliant',
              is_compliant: true,
              conclusion: '开发权限可见的合规结论。',
            },
          ],
        }),
      },
      global: { stubs },
    })

    expect(wrapper.get('[data-testid="qc-task-live-result"]').text()).toContain(
      '开发权限可见的合规结论。',
    )
    wrapper.unmount()
  })

  it('受限账号没有确定问题时展示中性执行进度，不把隐藏项说成无问题', async () => {
    setActivePinia(createPinia())
    vi.mocked(ApiService.getCurrentUser).mockResolvedValue({
      success: true,
      data: { id: 'demo-admin', roles: [UserRole.ADMIN], is_demo_account: true },
    })
    await useAuthStore().initialize()
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          items: [
            {
              rule_id: 'LX0609-06-01-05',
              rule_name: '检查检验',
              status: 'technical_error',
              is_compliant: null,
              conclusion: '不应作为实时结论展示的技术失败。',
            },
            {
              rule_id: 'LX0609-07-02-01',
              rule_name: '输血记录',
              status: 'compliant',
              is_compliant: true,
              conclusion: '不应展示的合规结论。',
            },
          ],
          summary: {
            ...buildJob().summary!,
            completed_rule_count: 2,
            failed_rule_count: 1,
            diagnostic_rule_failure_count: 1,
            display_status_counts: { technical_error: 1, compliant: 1 },
          },
        }),
      },
      global: { stubs },
    })

    const liveResult = wrapper.get('[data-testid="qc-task-live-result"]').text()
    expect(liveResult).toContain('执行进度')
    expect(liveResult).toContain('质控执行中，已回写 2 条结果')
    expect(liveResult).not.toContain('不应作为实时结论展示的技术失败。')
    expect(liveResult).not.toContain('不应展示的合规结论。')
    expect(liveResult).not.toMatch(/无问题|全部通过/u)
    expect(wrapper.get('[data-testid="qc-task-diagnostic-warning"]').text()).toContain(
      '1 项规则未完成',
    )
    wrapper.unmount()
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
    expect(wrapper.get('[data-testid="qc-task-more-actions"]').text()).toContain('更多')
    expect(wrapper.text()).toContain('复核本次结果')
    expect(wrapper.text()).toContain('导出 HTML')

    await wrapper.get('[data-testid="qc-task-review"]').trigger('click')
    await wrapper.get('[data-testid="qc-task-export"]').trigger('click')

    expect(wrapper.emitted('review')).toEqual([['job-1']])
    expect(wrapper.emitted('export')).toEqual([['job-1']])
  })

  it('共享只读任务仅保留结果查看与质控记录入口', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({
          status: 'completed',
          read_only: true,
        }),
      },
      global: { stubs },
    })

    expect(wrapper.get('[data-testid="qc-task-view-result"]').element).toBeTruthy()
    expect(wrapper.get('[data-testid="qc-task-open-history"]').element).toBeTruthy()
    expect(wrapper.find('[data-testid="qc-task-cancel"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="qc-task-more-actions"]').exists()).toBe(false)
  })

  it('复核执行中在更多菜单内保留禁用与进行中反馈', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      props: {
        task: buildJob({ status: 'completed' }),
        reviewing: true,
      },
      global: { stubs },
    })

    const reviewAction = wrapper.get('[data-testid="qc-task-review"]')
    expect(reviewAction.text()).toBe('复核中…')
    expect(reviewAction.attributes('disabled')).toBeDefined()
  })

  it('将关注状态与其他结果分开呈现，完成态在窄屏结构中仍保留摘要和操作', () => {
    const wrapper = mount(CustomerSampleQcTaskStatusBar, {
      attachTo: document.body,
      props: {
        task: buildJob({
          status: 'completed',
          summary: {
            ...buildJob().summary,
            display_status_counts: {
              technical_error: 2,
              non_compliant: 8,
              data_gap: 13,
              data_quality_gap: 6,
              uncertain: 3,
              compliant: 28,
              not_applicable: 17,
              not_executed: 4,
            },
            diagnostic_rule_failure_count: 2,
          },
        }),
      },
      global: { stubs },
    })

    const attention = wrapper.get('[data-testid="qc-task-attention-statuses"]').text()
    const other = wrapper.get('[data-testid="qc-task-other-statuses"]').text()

    expect(attention).toContain('技术异常 2')
    expect(attention).toContain('不合规 8')
    expect(attention).toContain('数据不足 13')
    expect(attention).toContain('资料待核实 6')
    expect(attention).toContain('AI判断 3')
    expect(attention).not.toContain('合规 28')
    expect(other).toContain('其他结果')
    expect(other).toContain('合规 28')
    expect(other).toContain('不适用 17')
    expect(other).toContain('未执行 4')
    expect(wrapper.get('[data-testid="qc-task-settled-summary"]').text()).toContain('更新')
    expect(wrapper.get('[data-testid="qc-task-diagnostic-warning"]').text()).toBe(
      '2 项规则未完成，请查看技术详情',
    )
    expect(wrapper.get('[data-testid="qc-task-view-result"]').element).toBeTruthy()
    expect(wrapper.get('[data-testid="qc-task-more-actions"]').element).toBeTruthy()
    expect(wrapper.get('[data-testid="qc-task-open-history"]').element).toBeTruthy()

    wrapper.unmount()
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
