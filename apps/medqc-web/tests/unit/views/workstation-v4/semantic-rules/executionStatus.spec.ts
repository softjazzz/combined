import { describe, expect, it } from 'vitest'
import { normalizeSemanticRule } from '@/views/workstation-v4/semantic-rules/service'
import { executionStatus, executionStatusHint } from '@/views/workstation-v4/semantic-rules/executionStatus'

describe('规则目录执行状态', () => {
  it.each([
    ['phase_1_target', 'default', '默认启用'],
    ['pending_definition', 'default', '暂停'],
    ['phase_1_target', 'acceptance_only', '仅供验证'],
    ['phase_1_partial', 'default', '部分启用'],
    [undefined, undefined, '状态未提供'],
  ])('透传并展示 %s / %s', (phase_status, release_scope, label) => {
    const rule = normalizeSemanticRule({ rule_id: 'LX0609-08-01-05', phase_status, release_scope })
    expect(executionStatus(rule)).toBe(label)
  })
  it('暂停提示保留后端原因', () => {
    const rule = normalizeSemanticRule({ rule_id: 'LX0609-03-01-01', phase_status: 'pending_definition', pending_definition_note: '缺少会诊申请数据' })
    expect(executionStatusHint(rule)).toBe('缺少会诊申请数据')
  })
})
