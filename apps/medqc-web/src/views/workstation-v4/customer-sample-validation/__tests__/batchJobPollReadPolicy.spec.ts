import { describe, expect, it } from 'vitest'
import {
  MAX_CONSECUTIVE_READ_FAILURES,
  decidePollReadFailure,
  pollReadFailureMessage,
  resolveTerminalBatchJobStatus,
} from '../batchJobPollReadPolicy'

describe('batchJobPollReadPolicy', () => {
  it.each([403, 404, 410])('%s 任务不存在或无权限：立即停止', (status) => {
    expect(decidePollReadFailure(status, 1)).toBe('stop_terminal')
  })

  it.each(['completed', 'failed', 'cancelled', 'canceled'])(
    '409 且任务已结束（%s）：结果不会再变，立即停止',
    (jobStatus) => {
      expect(decidePollReadFailure(409, 1, jobStatus)).toBe('stop_terminal')
    },
  )

  it.each(['running', 'queued', 'retrying', 'RUNNING'])(
    '409 且任务仍在执行（%s）：继续重试',
    (jobStatus) => {
      expect(decidePollReadFailure(409, 1, jobStatus)).toBe('retry')
    },
  )

  it.each([
    ['completed', 'completed'],
    ['failed', 'failed'],
    ['canceled', 'canceled'],
    ['cancelled', 'canceled'],
  ] as const)('只将权威终态 %s 回写为 %s', (jobStatus, expected) => {
    expect(resolveTerminalBatchJobStatus(jobStatus)).toBe(expected)
  })

  it.each(['running', 'queued', 'retrying'])('不把执行态 %s 改写为终态', (jobStatus) => {
    expect(resolveTerminalBatchJobStatus(jobStatus)).toBeUndefined()
  })

  it('旧后端未附带任务状态的 409 视为临时失败，按上限暂停', () => {
    expect(decidePollReadFailure(409, 1)).toBe('retry')
    expect(decidePollReadFailure(409, MAX_CONSECUTIVE_READ_FAILURES)).toBe('stop_exhausted')
  })

  it('网络或 5xx 失败：未到上限继续重试，达到上限暂停', () => {
    expect(decidePollReadFailure(undefined, MAX_CONSECUTIVE_READ_FAILURES - 1)).toBe('retry')
    expect(decidePollReadFailure(502, MAX_CONSECUTIVE_READ_FAILURES)).toBe('stop_exhausted')
  })

  it('停止提示说明原因与后续操作', () => {
    expect(pollReadFailureMessage('stop_terminal', '结果不完整')).toContain('已停止自动刷新')
    expect(pollReadFailureMessage('stop_exhausted', '超时')).toContain('请稍后手动刷新')
  })
})
