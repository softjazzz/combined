import { describe, expect, it } from 'vitest'
import { isBatchJobCancelable, isBatchJobPollingActive } from '../batchJobStatus'

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
