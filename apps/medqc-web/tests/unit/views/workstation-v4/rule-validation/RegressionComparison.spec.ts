import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { ComparisonRow } from '@/services/rule-validation-service'
import RegressionComparison from '@/views/workstation-v4/rule-validation/RegressionComparison.vue'

function row(): ComparisonRow {
  return {
    item_id: 'test', rule_id: 'LX0609-06-01-04', role: 'regression', case_title: '合成病例',
    record_ref: { institute_id: 'TEST', patient_id: 'P', visit_id: 'V' },
    source_kind: 'synthetic', evaluation_as_of_date: '2026-10-02', purpose: 'acceptance',
    human_reason: '工程测试', answer_revision: 1, expected_status: 'non_compliant',
    actual_status: 'non_compliant', comparison: 'different',
    result: { customer_display_facts: { missing_count: 2 } },
    regression_comparison: {
      baseline_run_id: 'r0', baseline_job_id: 'j0', status: 'different',
      baseline: { customer_display_facts: { missing_count: 1 } }, changed_fields: ['customer_display_facts'],
      metrics: { basis: 'whole_job', baseline: { llm_calls: 1, tokens: 50, elapsed_seconds: 2 },
        current: { llm_calls: 0, tokens: 0, elapsed_seconds: 1 }, delta: null,
        baseline_scope: { rule_ids: ['old'], record_count: 1 },
        current_scope: { rule_ids: ['old', 'new'], record_count: 1 },
        comparable: false, reason: '任务范围不同，仅并列展示' },
    },
  }
}

describe('同族保存基线对照', () => {
  it('显示事实的前后值、整任务统计与不可比范围，不吞掉零值', () => {
    const wrapper = mount(RegressionComparison, { props: { row: row() } })
    expect(wrapper.text()).toContain('判定事实')
    expect(wrapper.text()).toContain('基线：{"missing_count":1}')
    expect(wrapper.text()).toContain('本次：{"missing_count":2}')
    expect(wrapper.text()).toContain('任务范围不同')
    const tokenRow = wrapper.findAll('tbody tr')[1]
    expect(tokenRow.findAll('td').map((td) => td.text())).toEqual(['Token', '50', '0', '不可直接比较'])
  })

  it('缺基线和统计时明确显示缺口', () => {
    const input = row()
    input.regression_comparison!.baseline = null
    input.regression_comparison!.metrics.current.tokens = null
    const wrapper = mount(RegressionComparison, { props: { row: input } })
    expect(wrapper.text()).toContain('保存基线缺失或不可读取')
    expect(wrapper.text()).toContain('未记录')
  })
})
