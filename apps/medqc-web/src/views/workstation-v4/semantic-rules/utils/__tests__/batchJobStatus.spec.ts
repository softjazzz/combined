import { describe, expect, it } from 'vitest'
import {
  getBatchJobRetryMessage,
  isBatchJobCancelable,
  isBatchJobFinished,
  isBatchJobPollingActive,
} from '../batchJobStatus'

describe('isBatchJobCancelable', () => {
  it('running-like statuses can be cancelled', () => {
    expect(isBatchJobCancelable('running')).toBe(true)
    expect(isBatchJobCancelable('queued')).toBe(true)
    expect(isBatchJobCancelable('pending')).toBe(true)
    expect(isBatchJobCancelable('processing')).toBe(true)
  })

  it('finished statuses cannot be cancelled', () => {
    expect(isBatchJobCancelable('completed')).toBe(false)
    expect(isBatchJobCancelable('failed')).toBe(false)
    expect(isBatchJobCancelable('canceled')).toBe(false)
    expect(isBatchJobCancelable()).toBe(false)
  })
})

describe('isBatchJobPollingActive', () => {
  it('keeps polling while a failed pass is queued for automatic retry', () => {
    expect(
      isBatchJobPollingActive({
        status: 'failed',
        summary: {
          automatic_failed_rule_retry: { status: 'queued', should_retry: true },
        },
      }),
    ).toBe(true)
  })

  it('keeps ordinary running jobs active', () => {
    expect(isBatchJobPollingActive({ status: 'running' })).toBe(true)
    expect(isBatchJobPollingActive({ status: 'queued' })).toBe(true)
  })

  it('treats exhausted and ordinary failures as terminal', () => {
    expect(
      isBatchJobPollingActive({
        status: 'failed',
        summary: {
          automatic_failed_rule_retry: { status: 'exhausted', should_retry: false },
        },
      }),
    ).toBe(false)
    expect(isBatchJobPollingActive({ status: 'failed' })).toBe(false)
    expect(isBatchJobPollingActive({ status: 'completed' })).toBe(false)
  })
})

describe('后台终态与自动补跑说明', () => {
  it.each(['queued', 'running'])('%s 且允许补跑时不视为终态', (status) => {
    const job = {
      status: 'failed',
      summary: { automatic_failed_rule_retry: { status, should_retry: true } },
    }
    expect(isBatchJobFinished(job)).toBe(false)
    expect(getBatchJobRetryMessage(job)).toContain(
      status === 'queued' ? '已排队等待' : '正在自动补跑',
    )
  })

  it.each([
    ['not_retryable', '不适合自动补跑'],
    ['exhausted', '次数已用尽'],
    ['completed', '自动补跑已结束'],
    ['not_applicable', '后台未确认自动补跑计划'],
    ['unexpected', '后台未确认自动补跑计划'],
  ])('%s 按后台状态说明，不承诺重试', (status, expected) => {
    const job = {
      status: 'failed',
      summary: { automatic_failed_rule_retry: { status, should_retry: false } },
    }
    expect(isBatchJobFinished(job)).toBe(true)
    expect(getBatchJobRetryMessage(job)).toContain(expected)
  })

  it('缺失、未知或相互矛盾的元数据不会推断自动补跑', () => {
    for (const retry of [
      undefined,
      { status: 'running' },
      { status: 'queued', should_retry: false },
      { status: 'unexpected', should_retry: true },
    ]) {
      const job = { status: 'failed', summary: { automatic_failed_rule_retry: retry } }
      expect(isBatchJobFinished(job)).toBe(true)
      expect(getBatchJobRetryMessage(job)).toContain('后台未确认自动补跑计划')
    }
  })

  it('成功或取消不受遗留重试字段影响，未知任务状态不冒充终态', () => {
    for (const status of ['completed', 'canceled', 'cancelled']) {
      const job = {
        status,
        summary: { automatic_failed_rule_retry: { status: 'running', should_retry: true } },
      }
      expect(isBatchJobFinished(job)).toBe(true)
      expect(getBatchJobRetryMessage(job)).toBe('')
    }
    expect(isBatchJobFinished({ status: 'unknown' })).toBe(false)
  })
})
