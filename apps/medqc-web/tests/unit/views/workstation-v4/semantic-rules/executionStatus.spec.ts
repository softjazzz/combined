import { describe, expect, it, vi } from 'vitest'
import { normalizeSemanticRule } from '@/views/workstation-v4/semantic-rules/service'
import { executionStatus, executionStatusHint } from '@/views/workstation-v4/semantic-rules/executionStatus'

// 这里只测目录投影，不初始化HTTP客户端或UI消息组件。
vi.mock('@/services/apiService', () => ({ ApiService: {} }))

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
  it('工程暂停明确显示未启用，不以规则编号改写历史状态', () => {
    const rule = normalizeSemanticRule({
      rule_id: 'LX0609-08-01-04', phase_status: 'pending_definition',
      pending_reason_code: 'engineering_acceptance_pending_20261110',
      pending_definition_note: '未启用：工程验收中，新任务及补跑不执行',
    })
    expect(executionStatus(rule)).toBe('未启用')
    expect(executionStatusHint(rule)).toBe('未启用：工程验收中，新任务及补跑不执行')
    const old = normalizeSemanticRule({ rule_id: 'LX0609-08-01-04', phase_status: 'phase_1_target', release_scope: 'default' })
    expect(executionStatus(old)).toBe('默认启用')
  })
})
