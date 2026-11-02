import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

import type { FrontpageQcRun } from '@/services/frontpage-qc-v2-service'

const createRun = vi.fn()
const getRun = vi.fn()
const cancelRun = vi.fn()
const listActive = vi.fn()
vi.mock('@/services/frontpage-qc-v2-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/frontpage-qc-v2-service')>()
  return {
    ...actual,
    createFrontpageQcRun: (...args: unknown[]) => createRun(...args),
    getFrontpageQcRun: (...args: unknown[]) => getRun(...args),
    cancelFrontpageQcRun: (...args: unknown[]) => cancelRun(...args),
    listActiveFrontpageQcRuns: (...args: unknown[]) => listActive(...args),
  }
})

import { FrontpageQcRequestError } from '@/services/frontpage-qc-v2-service'

import {
  formatPercent,
  formatScore,
  groupFindings,
  runProgressPercent,
  summarizeDataGaps,
} from '../presentation'
import { MAX_POLL_FAILURES, POLL_INTERVAL_MS, useFrontpageQcRun } from '../useFrontpageQcRun'

function makeRun(overrides: Partial<FrontpageQcRun> = {}): FrontpageQcRun {
  return {
    id: 'run-1',
    status: 'running',
    ruleset_version: '2026.10.13',
    filters: { mode: 'selected' },
    total_records: 2,
    processed_records: 0,
    success_count: 0,
    failed_count: 0,
    issue_records: 0,
    data_gap_records: 0,
    failed_records: [],
    error_message: null,
    cancel_requested: false,
    created_by: 'qc',
    created_at: null,
    started_at: null,
    finished_at: null,
    updated_at: null,
    ...overrides,
  }
}

function setup() {
  const onFinished = vi.fn()
  let api!: ReturnType<typeof useFrontpageQcRun>
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useFrontpageQcRun(onFinished)
        return () => null
      },
    }),
  )
  return { api, onFinished, wrapper }
}

describe('useFrontpageQcRun', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('创建后轮询到结束并回调一次', async () => {
    const { api, onFinished } = setup()
    createRun.mockResolvedValueOnce(makeRun())
    getRun
      .mockResolvedValueOnce(makeRun({ processed_records: 1 }))
      .mockResolvedValueOnce(makeRun({ status: 'completed', processed_records: 2, success_count: 2 }))

    await api.start({ record_refs: [{ institute_id: 'H', patient_id: 'P-C01', visit_id: 'C01' }] })
    expect(api.run.value?.status).toBe('running')

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(api.run.value?.processed_records).toBe(1)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

    expect(api.run.value?.status).toBe('completed')
    expect(onFinished).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
    expect(getRun).toHaveBeenCalledTimes(2)
  })

  it('409 时接管已有任务并提示', async () => {
    const { api } = setup()
    const existing = makeRun({ id: 'run-old' })
    createRun.mockRejectedValueOnce(
      new FrontpageQcRequestError('已有进行中的首页质控任务', 409, { message: 'x', run: existing }),
    )

    await api.start({ department: '内科' })

    expect(api.run.value?.id).toBe('run-old')
    expect(api.error.value).toContain('已切换到该任务的进度')
  })

  it('连续读取失败达到上限后停止轮询', async () => {
    const { api } = setup()
    createRun.mockResolvedValueOnce(makeRun())
    getRun.mockRejectedValue(new FrontpageQcRequestError('网络异常', 0))

    await api.start({ department: '' })
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * (MAX_POLL_FAILURES + 3))

    expect(getRun).toHaveBeenCalledTimes(MAX_POLL_FAILURES)
    expect(api.error.value).toContain('已停止自动刷新')
  })

  it('进入页面时恢复自己进行中的任务，卸载后不再轮询', async () => {
    const { api, wrapper } = setup()
    listActive.mockResolvedValueOnce({ items: [makeRun({ id: 'run-resume' })] })
    getRun.mockResolvedValue(makeRun({ id: 'run-resume' }))

    await api.resume()
    await flushPromises()
    expect(api.run.value?.id).toBe('run-resume')

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
    expect(getRun).not.toHaveBeenCalled()
  })

  it('进行中的任务不能关闭，结束后可以', async () => {
    const { api } = setup()
    createRun.mockResolvedValueOnce(makeRun())
    await api.start({ department: '' })

    api.dismiss()
    expect(api.run.value).not.toBeNull()

    cancelRun.mockResolvedValueOnce(makeRun({ status: 'cancelled' }))
    await api.cancel()
    api.dismiss()
    expect(api.run.value).toBeNull()
  })
})

describe('presentation', () => {
  it('数值格式', () => {
    expect(formatScore(92)).toBe('92')
    expect(formatScore(87.25)).toBe('87.3')
    expect(formatScore(null)).toBe('—')
    expect(formatPercent(0.9123)).toBe('91.2%')
    expect(formatPercent(null)).toBe('—')
    expect(runProgressPercent({ processed_records: 3, total_records: 0 })).toBe(0)
    expect(runProgressPercent({ processed_records: 1, total_records: 3 })).toBe(33)
  })

  it('问题按首页四部分分组，提示与资料不足单独列出', () => {
    const base = {
      group: 'completeness' as const,
      score_item: null,
      reason: '',
      details: [],
      review_status: 'pending' as const,
      review_note: '',
      reviewed_by: '',
      reviewed_at: null,
    }
    const groups = groupFindings([
      { ...base, id: '1', rule_id: 'C-D01', rule_name: '主要诊断', section: 'diagnosis', severity: 'required', verdict: 'fail', problem: '', deduction: 4 },
      { ...base, id: '2', rule_id: 'C-P01', rule_name: '姓名', section: 'patient', severity: 'deduct', verdict: 'fail', problem: '', deduction: 1 },
      { ...base, id: '3', rule_id: 'C-D12', rule_name: '损伤外部原因', section: 'diagnosis', severity: 'hint', verdict: 'fail', problem: '', deduction: 0 },
      { ...base, id: '4', rule_id: 'C-H30', rule_name: '编码员', section: 'hospitalization', severity: 'deduct', verdict: 'data_gap', problem: '', deduction: 0, reason: '首页同步未带入该字段' },
    ])

    expect(groups.sections.map((g) => g.section)).toEqual(['patient', 'diagnosis'])
    expect(groups.hints.map((f) => f.rule_id)).toEqual(['C-D12'])
    expect(summarizeDataGaps(groups.dataGaps)).toEqual([{ reason: '首页同步未带入该字段', rules: ['编码员'] }])
  })
})
