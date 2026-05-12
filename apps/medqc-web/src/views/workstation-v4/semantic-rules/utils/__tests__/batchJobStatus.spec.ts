import { describe, expect, it } from 'vitest'
import { isBatchJobCancelable } from '../batchJobStatus'

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
