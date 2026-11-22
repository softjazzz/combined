import { setDatePickerValue } from '../../../../../utils/setDatePickerValue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getDepartments: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getStatus: vi.fn(),
  triggerSync: vi.fn(),
}))
const authState = vi.hoisted(() => ({
  user: { id: 'qc-user-a', email: 'qc-a@example.com' } as { id: string; email?: string } | null,
}))
const PERSISTED_WORKFLOW_TOKEN = '7a8b9c0d-1e2f-4a3b-8c4d-5e6f7081920a'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function expectedWorkflowPayload(payload: Record<string, unknown>) {
  return expect.objectContaining({
    ...payload,
    auto_qc_workflow_token: expect.stringMatching(UUID_PATTERN),
  })
}

vi.mock('@/api/sync', () => ({
  syncApi: {
    getDepartments: mocks.getDepartments,
    getStatus: mocks.getStatus,
    triggerSync: mocks.triggerSync,
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getSichuanWorkspaceBatchJob: mocks.getSichuanWorkspaceBatchJob,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

import QcSyncAndRunControl from '@/views/workstation-v4/components/qc/QcSyncAndRunControl.vue'

describe('QcSyncAndRunControl', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.sessionStorage.clear()
    authState.user = { id: 'qc-user-a', email: 'qc-a@example.com' }
    mocks.triggerSync.mockResolvedValue({
      success: true,
      auto_qc: {
        status: 'queued',
        scene: 'running',
        eligible_records: 1,
        queued_records: 1,
        job_id: 'batch-job-001',
      },
    })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        id: 'batch-job-001',
        rule_code: 'LX0609',
        rule_name: '泸县0609病历质控',
        scope: 'running',
        status: 'completed',
      },
    })
    mocks.getStatus.mockResolvedValue({ pg_sync: { is_running: false } })
    mocks.getDepartments.mockResolvedValue(['重症医学科', '康复科'])
  })

  it('默认使用当前科室，并允许在确认前追加多个科室', async () => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await flushPromises()

    expect(mocks.getDepartments).toHaveBeenCalledTimes(1)
    expect(
      (wrapper.get('input[aria-label="重症医学科"]').element as HTMLInputElement).checked,
    ).toBe(true)
    await wrapper.get('input[aria-label="康复科"]').setValue(true)
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.triggerSync).toHaveBeenCalledWith(
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'running',
        target_departments: ['重症医学科', '康复科'],
        auto_qc_after_sync: true,
      }),
    )
  })

  it('读取可选科室失败时保留当前科室，且不扩大为全部科室', async () => {
    mocks.getDepartments.mockRejectedValueOnce(new Error('network unavailable'))
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('科室列表加载失败，已保留当前筛选范围。')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.triggerSync).toHaveBeenCalledWith(
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'running',
        target_departments: ['重症医学科'],
        auto_qc_after_sync: true,
      }),
    )
  })

  it.each(['not_applicable', 'not_needed'] as const)(
    '自动质控状态为 %s 时清晰结束同步，不误报质控完成',
    async (status) => {
      mocks.triggerSync.mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status,
          scene: 'running',
          eligible_records: 0,
          queued_records: 0,
          job_id: '',
          reason_code: 'no_deliverable_records',
        },
      })
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('同步已完成，本次未形成可质控病历。')
      expect(wrapper.text()).not.toContain('质控已完成，结果已刷新')
      expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
      expect(wrapper.emitted('completed')).toBeUndefined()
    },
  )

  it.each(['not_created'] as const)(
    '自动质控状态为 %s 时不把失败误写成无可质控病历',
    async (status) => {
      mocks.triggerSync.mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status,
          scene: 'running',
          eligible_records: 0,
          queued_records: 0,
          job_id: '',
        },
      })
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('同步已完成，但未能启动质控')
      expect(wrapper.text()).not.toContain('本次未形成可质控病历')
      expect(wrapper.emitted('completed')).toBeUndefined()
    },
  )

  it('自动质控创建失败时保留原工作流，并用同一令牌重试创建质控', async () => {
    mocks.triggerSync
      .mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status: 'enqueue_failed',
          scene: 'running',
          eligible_records: 1,
          queued_records: 0,
          job_id: '',
          reason_code: 'queue_unavailable',
        },
      })
      .mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status: 'queued',
          scene: 'running',
          eligible_records: 1,
          queued_records: 1,
          job_id: 'batch-job-retried-enqueue',
        },
      })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: true,
      data: {
        id: 'batch-job-retried-enqueue',
        rule_code: 'LX0609',
        rule_name: '泸县0609病历质控',
        scope: 'running',
        status: 'completed',
      },
    })
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    const firstPayload = mocks.triggerSync.mock.calls[0]?.[0] as Record<string, unknown>
    const persistedWorkflow = JSON.parse(
      window.sessionStorage.getItem('medqc:sync-and-qc:running') || '{}',
    ) as Record<string, unknown>
    expect(wrapper.text()).toContain('请重试创建质控')
    expect(wrapper.get('[data-testid="retry-qc-creation"]').text()).toBe('重试创建质控')
    expect(wrapper.get('[data-testid="sync-and-qc-trigger"]').text()).toBe('重试创建质控')
    expect(persistedWorkflow).toMatchObject({
      stage: 'syncing',
      owner: 'qc-user-a',
      payload: {
        auto_qc_workflow_token: firstPayload.auto_qc_workflow_token,
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await flushPromises()

    const retryPayload = mocks.triggerSync.mock.calls[1]?.[0] as Record<string, unknown>
    expect(retryPayload).toEqual(firstPayload)
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-retried-enqueue')
    expect(wrapper.emitted('completed')).toHaveLength(1)
    expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).toBeNull()
  })

  it('同步失败时不显示质控成功，也不刷新结果页', async () => {
    mocks.triggerSync.mockResolvedValueOnce({
      success: false,
      error: '同步服务暂不可用',
    })
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('同步未完成，未启动质控：同步服务暂不可用')
    expect(wrapper.text()).not.toContain('质控已完成，结果已刷新')
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('确认后以当前运行病历场景和科室发起自动同步质控，并在完成后通知结果页刷新', async () => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    expect(wrapper.get('[data-testid="sync-and-qc-trigger"]').text()).toBe('同步并质控')

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')

    const dialog = wrapper.get('[role="dialog"]')
    expect(dialog.text()).toContain('运行病历')
    expect(dialog.text()).toContain('重症医学科')
    expect(dialog.text()).toContain('系统将自动同步新病历并刷新已有病历资料')

    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.triggerSync).toHaveBeenCalledWith(
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'running',
        target_departments: ['重症医学科'],
        auto_qc_after_sync: true,
      }),
    )
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-001')
    expect(wrapper.emitted('completed')).toHaveLength(1)
    expect(wrapper.text()).toContain('检查同步条件')
    expect(wrapper.text()).toContain('同步病历')
    expect(wrapper.text()).toContain('确认可质控病历')
    expect(wrapper.text()).toContain('执行质控')
    expect(wrapper.text()).toContain('汇总并保存结果')
    expect(wrapper.text()).toContain('质控已完成，结果已刷新')
  })

  it('运行病历即使父页带有日期筛选也绝不发送 date_window', async () => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
        startDate: '2026-08-01',
        endDate: '2026-08-18',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    const payload = mocks.triggerSync.mock.calls[0]?.[0] as Record<string, unknown>
    expect(payload).not.toHaveProperty('date_window')
  })

  it('终末病历确认框沿用父页完整日期范围，并将其传给同步请求', async () => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'discharged',
        department: '重症医学科',
        startDate: '2026-08-01',
        endDate: '2026-08-18',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await flushPromises()

    expect(
      (wrapper.get('[data-testid="sync-and-qc-start-date"] input').element as HTMLInputElement).value,
    ).toBe('2026-08-01')
    expect(
      (wrapper.get('[data-testid="sync-and-qc-end-date"] input').element as HTMLInputElement).value,
    ).toBe('2026-08-18')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.triggerSync).toHaveBeenCalledWith(
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'final',
        target_departments: ['重症医学科'],
        auto_qc_after_sync: true,
        date_window: {
          start_date: '2026-08-01',
          end_date: '2026-08-18',
        },
      }),
    )
  })

  it('终末病历日期差为30天时允许同步（共31个自然日）', async () => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'discharged',
        department: '重症医学科',
        startDate: '2026-01-01',
        endDate: '2026-01-31',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.triggerSync).toHaveBeenCalledWith(
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'final',
        target_departments: ['重症医学科'],
        auto_qc_after_sync: true,
        date_window: {
          start_date: '2026-01-01',
          end_date: '2026-01-31',
        },
      }),
    )
  })

  it('终末病历未收到完整父页日期时默认最近7天，并允许在确认框修改', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-19T04:00:00.000Z'))
    try {
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'discharged',
          department: '重症医学科',
          startDate: '2026-08-01',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await flushPromises()

      const startInput = wrapper.get('[data-testid="sync-and-qc-start-date"] input')
      const endInput = wrapper.get('[data-testid="sync-and-qc-end-date"] input')
      expect((startInput.element as HTMLInputElement).value).toBe('2026-08-13')
      expect((endInput.element as HTMLInputElement).value).toBe('2026-08-19')
      expect(wrapper.text()).toContain('默认最近7天（含今日）')

      await setDatePickerValue(startInput, '2026-08-05')
      await setDatePickerValue(endInput, '2026-08-17')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()

      expect(mocks.triggerSync).toHaveBeenCalledWith(
        expectedWorkflowPayload({
          source: 'pg',
          scene: 'final',
          target_departments: ['重症医学科'],
          auto_qc_after_sync: true,
          date_window: {
            start_date: '2026-08-05',
            end_date: '2026-08-17',
          },
        }),
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it.each([
    {
      title: '开始日期晚于结束日期',
      startDate: '2026-08-18',
      endDate: '2026-08-17',
      message: '开始日期不能晚于结束日期。',
    },
    {
      title: '日期跨度超过31天',
      startDate: '2026-01-01',
      endDate: '2026-02-01',
      message: '终末病历同步日期范围最多31天。',
    },
  ])('终末病历 $title 时在前端阻止同步', async ({ startDate, endDate, message }) => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'discharged',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await setDatePickerValue(wrapper.get('[data-testid="sync-and-qc-start-date"] input'), startDate)
    await setDatePickerValue(wrapper.get('[data-testid="sync-and-qc-end-date"] input'), endDate)
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(message)
    expect(wrapper.find('[data-testid="sync-and-qc-confirm"]').exists()).toBe(true)
    expect(mocks.triggerSync).not.toHaveBeenCalled()
  })

  it('质控完成后再次主动点击会生成新的工作流令牌', async () => {
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()
    await wrapper.get('[aria-label="关闭同步并质控进度"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    const firstPayload = mocks.triggerSync.mock.calls[0]?.[0] as Record<string, unknown>
    const secondPayload = mocks.triggerSync.mock.calls[1]?.[0] as Record<string, unknown>
    expect(firstPayload.auto_qc_workflow_token).toMatch(UUID_PATTERN)
    expect(secondPayload.auto_qc_workflow_token).toMatch(UUID_PATTERN)
    expect(secondPayload.auto_qc_workflow_token).not.toBe(firstPayload.auto_qc_workflow_token)
  })

  it('幂等重提返回等待中时继续等待后台同步，不误报同步失败', async () => {
    mocks.triggerSync.mockResolvedValueOnce({
      success: false,
      status: 'pending',
    })
    mocks.getStatus.mockResolvedValueOnce({ pg_sync: { is_running: true } })

    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('同步仍在后台执行')
    expect(wrapper.text()).not.toContain('同步未完成，未启动质控')
    wrapper.unmount()
  })

  it.each([
    { status: 'pending', progressMessage: '同步仍在后台执行' },
    { status: 'enqueueing', progressMessage: '质控任务正在创建或恢复' },
  ] as const)(
    '自动质控摘要为 $status 时继续等待，不误判为无可质控病历',
    async ({ status, progressMessage }) => {
      mocks.triggerSync.mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status,
          scene: 'running',
          eligible_records: 0,
          queued_records: 0,
          job_id: '',
        },
      })
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain(progressMessage)
      expect(wrapper.text()).not.toContain('本次未形成可质控病历')
      expect(wrapper.emitted('completed')).toBeUndefined()
      wrapper.unmount()
    },
  )

  it('自动质控持续处于 enqueueing 时覆盖恢复租约后才结束等待，不无限重放请求', async () => {
    vi.useFakeTimers()
    try {
      mocks.triggerSync.mockResolvedValue({
        success: true,
        auto_qc: {
          status: 'enqueueing',
          scene: 'running',
          eligible_records: 0,
          queued_records: 0,
          job_id: '',
        },
      })
      mocks.getStatus.mockResolvedValue({ pg_sync: { is_running: false } })
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(2 * 3000)
      await flushPromises()

      expect(mocks.triggerSync).toHaveBeenCalledTimes(3)
      expect(wrapper.text()).toContain('质控任务正在创建或恢复')
      expect(wrapper.text()).not.toContain('质控任务创建或恢复超时')
      expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).not.toBeNull()

      await vi.advanceTimersByTimeAsync(47 * 3000)
      await flushPromises()

      expect(mocks.triggerSync).toHaveBeenCalledTimes(50)
      expect(wrapper.text()).toContain('质控任务创建或恢复超时，请稍后重试。')
      expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).toBeNull()

      await vi.advanceTimersByTimeAsync(30000)
      await flushPromises()
      expect(mocks.triggerSync).toHaveBeenCalledTimes(50)
    } finally {
      vi.useRealTimers()
    }
  })

  it('复用已有质控任务时轮询该任务并刷新结果页', async () => {
    mocks.triggerSync.mockResolvedValueOnce({
      success: true,
      auto_qc: {
        status: 'reused',
        scene: 'running',
        eligible_records: 1,
        queued_records: 1,
        job_id: 'batch-job-reused',
      },
    })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: true,
      data: {
        id: 'batch-job-reused',
        rule_code: 'LX0609',
        rule_name: '泸县0609病历质控',
        scope: 'running',
        status: 'completed',
      },
    })
    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-reused')
    expect(wrapper.emitted('completed')).toHaveLength(1)
  })

  it('质控任务状态连续获取失败三次后停止轮询，并清理恢复状态', async () => {
    vi.useFakeTimers()
    try {
      mocks.triggerSync.mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status: 'queued',
          scene: 'running',
          eligible_records: 1,
          queued_records: 1,
          job_id: 'batch-job-status-unavailable',
        },
      })
      mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({ success: false })
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(2 * 3000)
      await flushPromises()

      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(3)
      expect(wrapper.text()).toContain('质控任务状态连续获取失败，请稍后刷新结果页查看。')
      expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).toBeNull()

      await vi.advanceTimersByTimeAsync(30000)
      await flushPromises()
      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('获取到有效任务状态后重置连续失败计数', async () => {
    vi.useFakeTimers()
    try {
      mocks.triggerSync.mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status: 'queued',
          scene: 'running',
          eligible_records: 1,
          queued_records: 1,
          job_id: 'batch-job-status-recovered',
        },
      })
      mocks.getSichuanWorkspaceBatchJob
        .mockResolvedValueOnce({ success: false })
        .mockResolvedValueOnce({ success: false })
        .mockResolvedValueOnce({
          success: true,
          data: {
            id: 'batch-job-status-recovered',
            rule_code: 'LX0609',
            rule_name: '泸县0609病历质控',
            scope: 'running',
            status: 'running',
          },
        })
        .mockResolvedValueOnce({ success: false })
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(3 * 3000)
      await flushPromises()

      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(4)
      expect(wrapper.text()).toContain('正在等待质控任务状态更新。')
      expect(wrapper.text()).not.toContain('质控任务状态连续获取失败')
      expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).not.toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('质控任务状态请求异常连续三次后停止轮询，并清理恢复状态', async () => {
    vi.useFakeTimers()
    try {
      mocks.triggerSync.mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status: 'queued',
          scene: 'running',
          eligible_records: 1,
          queued_records: 1,
          job_id: 'batch-job-status-error',
        },
      })
      mocks.getSichuanWorkspaceBatchJob.mockRejectedValue(new Error('network unavailable'))
      const wrapper = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })

      await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(2 * 3000)
      await flushPromises()

      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(3)
      expect(wrapper.text()).toContain('质控任务状态连续获取失败，请稍后刷新结果页查看。')
      expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).toBeNull()

      await vi.advanceTimersByTimeAsync(30000)
      await flushPromises()
      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it.each([
    {
      title: '当前登录人与持久化所有者不一致',
      owner: 'qc-user-a',
      user: { id: 'qc-user-b', email: 'qc-b@example.com' },
    },
    {
      title: '旧持久化记录缺少所有者',
      owner: '',
      user: { id: 'qc-user-a', email: 'qc-a@example.com' },
    },
    {
      title: '当前登录身份不可用',
      owner: 'qc-user-a',
      user: null,
    },
  ])('$title 时不重放同步并清理持久化记录', async ({ owner, user }) => {
    authState.user = user
    window.sessionStorage.setItem(
      'medqc:sync-and-qc:running',
      JSON.stringify({
        stage: 'syncing',
        owner,
        payload: {
          source: 'pg',
          scene: 'running',
          target_departments: ['重症医学科'],
          auto_qc_after_sync: true,
          auto_qc_workflow_token: PERSISTED_WORKFLOW_TOKEN,
        },
      }),
    )

    mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })
    await flushPromises()

    expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).toBeNull()
    expect(mocks.getStatus).not.toHaveBeenCalled()
    expect(mocks.triggerSync).not.toHaveBeenCalled()
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
  })

  it.each([
    { title: '缺失', workflowToken: undefined },
    { title: '格式不合法', workflowToken: 'not-a-workflow-token' },
  ])('持久化工作流令牌$title 时不重放并清理记录', async ({ workflowToken }) => {
    const payload: Record<string, unknown> = {
      source: 'pg',
      scene: 'running',
      target_departments: ['重症医学科'],
      auto_qc_after_sync: true,
    }
    if (workflowToken !== undefined) {
      payload.auto_qc_workflow_token = workflowToken
    }
    window.sessionStorage.setItem(
      'medqc:sync-and-qc:running',
      JSON.stringify({
        stage: 'syncing',
        owner: 'qc-user-a',
        payload,
      }),
    )

    mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })
    await flushPromises()

    expect(window.sessionStorage.getItem('medqc:sync-and-qc:running')).toBeNull()
    expect(mocks.getStatus).not.toHaveBeenCalled()
    expect(mocks.triggerSync).not.toHaveBeenCalled()
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
  })

  it.each([
    { title: '缺少日期范围', dateWindow: undefined },
    { title: '仅有开始日期', dateWindow: { start_date: '2026-08-01' } },
    {
      title: '跨度超过31天',
      dateWindow: { start_date: '2026-01-01', end_date: '2026-02-01' },
    },
  ])('历史终末同步记录$title 时不自动补日期重放', async ({ dateWindow }) => {
    const payload: Record<string, unknown> = {
      source: 'pg',
      scene: 'final',
      target_departments: ['重症医学科'],
      auto_qc_after_sync: true,
      auto_qc_workflow_token: PERSISTED_WORKFLOW_TOKEN,
    }
    if (dateWindow !== undefined) {
      payload.date_window = dateWindow
    }
    window.sessionStorage.setItem(
      'medqc:sync-and-qc:final',
      JSON.stringify({
        stage: 'syncing',
        owner: 'qc-user-a',
        payload,
      }),
    )

    mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'discharged',
        department: '重症医学科',
      },
    })
    await flushPromises()

    expect(window.sessionStorage.getItem('medqc:sync-and-qc:final')).toBeNull()
    expect(mocks.getStatus).not.toHaveBeenCalled()
    expect(mocks.triggerSync).not.toHaveBeenCalled()
    expect(mocks.getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
  })

  it.each([
    {
      title: '稳定用户 ID',
      owner: 'qc-user-a',
      user: { id: 'qc-user-a', email: 'qc-a@example.com' },
    },
    {
      title: '用户 ID 缺失时的邮箱',
      owner: 'qc-email-only@example.com',
      user: { id: '', email: 'qc-email-only@example.com' },
    },
  ])('同一登录身份通过 $title 恢复持久化同步范围并继续自动质控', async ({ owner, user }) => {
    authState.user = user
    window.sessionStorage.setItem(
      'medqc:sync-and-qc:running',
      JSON.stringify({
        stage: 'syncing',
        owner,
        payload: {
          source: 'pg',
          scene: 'running',
          target_departments: ['重症医学科', '康复科'],
          auto_qc_after_sync: true,
          auto_qc_workflow_token: PERSISTED_WORKFLOW_TOKEN,
        },
      }),
    )

    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'inpatient',
        department: '重症医学科',
      },
    })
    await flushPromises()

    expect(mocks.getStatus).toHaveBeenCalledTimes(1)
    expect(mocks.triggerSync).toHaveBeenCalledWith({
      source: 'pg',
      scene: 'running',
      target_departments: ['重症医学科', '康复科'],
      auto_qc_after_sync: true,
      auto_qc_workflow_token: PERSISTED_WORKFLOW_TOKEN,
    })
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-001')
    expect(wrapper.emitted('completed')).toHaveLength(1)
  })

  it('页面在后台同步期间重新打开时，用原多科室范围恢复并等待自动质控任务', async () => {
    vi.useFakeTimers()
    try {
      mocks.triggerSync
        .mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
        .mockResolvedValueOnce({
          success: true,
          auto_qc: {
            status: 'queued',
            scene: 'running',
            eligible_records: 2,
            queued_records: 2,
            job_id: 'batch-job-resumed',
          },
        })
      mocks.getStatus
        .mockResolvedValueOnce({ pg_sync: { is_running: true } })
        .mockResolvedValueOnce({ pg_sync: { is_running: false } })
      mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
        success: true,
        data: {
          id: 'batch-job-resumed',
          rule_code: 'LX0609',
          rule_name: '泸县0609病历质控',
          scope: 'running',
          status: 'completed',
        },
      })

      const firstView = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })
      await firstView.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await flushPromises()
      await firstView.get('input[aria-label="康复科"]').setValue(true)
      await firstView.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()
      expect(firstView.text()).toContain('同步仍在后台执行')
      expect(
        JSON.parse(window.sessionStorage.getItem('medqc:sync-and-qc:running') || '{}'),
      ).toMatchObject({
        stage: 'syncing',
        owner: 'qc-user-a',
        payload: {
          source: 'pg',
          scene: 'running',
          target_departments: ['重症医学科', '康复科'],
          auto_qc_workflow_token: expect.stringMatching(UUID_PATTERN),
        },
      })

      firstView.unmount()

      const resumedView = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })
      await flushPromises()

      expect(mocks.getStatus).toHaveBeenCalledTimes(2)
      expect(mocks.triggerSync).toHaveBeenNthCalledWith(
        2,
        expectedWorkflowPayload({
          source: 'pg',
          scene: 'running',
          target_departments: ['重症医学科', '康复科'],
          auto_qc_after_sync: true,
        }),
      )
      const firstPayload = mocks.triggerSync.mock.calls[0]?.[0] as Record<string, unknown>
      const resumedPayload = mocks.triggerSync.mock.calls[1]?.[0] as Record<string, unknown>
      expect(resumedPayload.auto_qc_workflow_token).toBe(firstPayload.auto_qc_workflow_token)
      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-resumed')
      expect(resumedView.emitted('completed')).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('页面在后台同步期间重新打开时，用原全部科室范围恢复并等待自动质控任务', async () => {
    vi.useFakeTimers()
    try {
      mocks.triggerSync
        .mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
        .mockResolvedValueOnce({
          success: true,
          auto_qc: {
            status: 'queued',
            scene: 'running',
            eligible_records: 2,
            queued_records: 2,
            job_id: 'batch-job-all-departments',
          },
        })
      mocks.getStatus
        .mockResolvedValueOnce({ pg_sync: { is_running: true } })
        .mockResolvedValueOnce({ pg_sync: { is_running: false } })
      mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
        success: true,
        data: {
          id: 'batch-job-all-departments',
          rule_code: 'LX0609',
          rule_name: '泸县0609病历质控',
          scope: 'running',
          status: 'completed',
        },
      })

      const firstView = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })
      await firstView.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
      await flushPromises()
      await firstView.get('input[aria-label="全部科室"]').setValue(true)
      await firstView.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
      await flushPromises()
      firstView.unmount()

      const resumedView = mount(QcSyncAndRunControl, {
        props: {
          carePhase: 'inpatient',
          department: '重症医学科',
        },
      })
      await flushPromises()

      expect(mocks.triggerSync).toHaveBeenNthCalledWith(
        1,
        expectedWorkflowPayload({
          source: 'pg',
          scene: 'running',
          target_departments: ['*'],
          auto_qc_after_sync: true,
        }),
      )
      expect(mocks.triggerSync).toHaveBeenNthCalledWith(
        2,
        expectedWorkflowPayload({
          source: 'pg',
          scene: 'running',
          target_departments: ['*'],
          auto_qc_after_sync: true,
        }),
      )
      const firstPayload = mocks.triggerSync.mock.calls[0]?.[0] as Record<string, unknown>
      const resumedPayload = mocks.triggerSync.mock.calls[1]?.[0] as Record<string, unknown>
      expect(resumedPayload.auto_qc_workflow_token).toBe(firstPayload.auto_qc_workflow_token)
      expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-all-departments')
      expect(resumedView.emitted('completed')).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('同步请求超时后等待后台同步结束，再以同一范围取得自动质控任务', async () => {
    vi.useFakeTimers()
    mocks.triggerSync
      .mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
      .mockResolvedValueOnce({
        success: true,
        auto_qc: {
          status: 'queued',
          scene: 'final',
          eligible_records: 4,
          queued_records: 4,
          job_id: 'batch-job-timeout',
        },
      })
    mocks.getStatus
      .mockResolvedValueOnce({ pg_sync: { is_running: true } })
      .mockResolvedValueOnce({ pg_sync: { is_running: false } })
    mocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        id: 'batch-job-timeout',
        rule_code: 'LX0609',
        rule_name: '泸县0609病历质控',
        scope: 'final',
        status: 'completed',
      },
    })

    const wrapper = mount(QcSyncAndRunControl, {
      props: {
        carePhase: 'discharged',
        department: '全部科室',
        startDate: '2026-08-01',
        endDate: '2026-08-18',
      },
    })

    await wrapper.get('[data-testid="sync-and-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="sync-and-qc-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('同步仍在后台执行')
    expect(mocks.getStatus).toHaveBeenCalledTimes(1)

    await vi.runOnlyPendingTimersAsync()
    await flushPromises()

    expect(mocks.getStatus).toHaveBeenCalledTimes(2)
    expect(mocks.triggerSync).toHaveBeenNthCalledWith(
      1,
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'final',
        target_departments: ['*'],
        auto_qc_after_sync: true,
        date_window: {
          start_date: '2026-08-01',
          end_date: '2026-08-18',
        },
      }),
    )
    expect(mocks.triggerSync).toHaveBeenNthCalledWith(
      2,
      expectedWorkflowPayload({
        source: 'pg',
        scene: 'final',
        target_departments: ['*'],
        auto_qc_after_sync: true,
        date_window: {
          start_date: '2026-08-01',
          end_date: '2026-08-18',
        },
      }),
    )
    const firstPayload = mocks.triggerSync.mock.calls[0]?.[0] as Record<string, unknown>
    const retryPayload = mocks.triggerSync.mock.calls[1]?.[0] as Record<string, unknown>
    expect(retryPayload.auto_qc_workflow_token).toBe(firstPayload.auto_qc_workflow_token)
    expect(mocks.getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('batch-job-timeout')
    expect(wrapper.emitted('completed')).toHaveLength(1)

    vi.useRealTimers()
  })
})
