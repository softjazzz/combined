import { describe, expect, it } from 'vitest'
import { toWriteItems } from '@/api/scoring'

describe('评分条目写入边界', () => {
  it('规范化机构内科室引用且不丢失适用模式', () => {
    expect(toWriteItems([{
      group_name: '病程', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: true,
      department_scope_mode: 'selected',
      department_refs: [{ institute_id: ' H1 ', department_name: ' 心内科 ' }],
    }])).toEqual([{
      group_name: '病程', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: true,
      department_scope_mode: 'selected',
      department_refs: [{ institute_id: 'H1', department_name: '心内科' }],
    }])
  })

  it('拒绝不可信运行时科室引用', () => {
    const invalid = [{
      group_name: '病程', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: true,
      department_scope_mode: 'selected', department_refs: [{ institute_id: 1, department_name: '心内科' }],
    }]
    expect(() => toWriteItems(invalid as never)).toThrow('科室引用格式无效')
  })
})
