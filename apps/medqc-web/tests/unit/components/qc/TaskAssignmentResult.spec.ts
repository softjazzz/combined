import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TaskAssignmentResult from '@/components/qc/TaskAssignmentResult.vue'
import { assignReasonParts, describeTaskAssignError } from '@/utils/taskAssignment'

describe('TaskAssignmentResult 分配结果', () => {
  it('每人显示数量与来源分布，缺失字段不补 0', () => {
    const wrapper = mount(TaskAssignmentResult, {
      props: {
        taskName: '任务A',
        result: {
          total_assigned: 5,
          assignment_details: [
            { user_id: 'a', user_name: '质控员甲', count: 3, reason_counts: { original_reviewer: 2, ratio_fallback: 1 } },
            { user_id: 'b', user_name: '质控员乙', count: 2, reason_counts: { department: 2 } },
            { user_id: 'c', user_name: '质控员丙', count: 0 },
          ],
        },
      },
    })
    const rows = wrapper.findAll('[data-testid="assign-result-row"]')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('质控员甲')
    expect(rows[0].text()).toContain('3 条')
    expect(rows[0].get('[data-testid="assign-result-parts"]').text()).toBe('原质控员 2 / 按比例补充 1')
    expect(rows[1].get('[data-testid="assign-result-parts"]').text()).toBe('科室 2')
    expect(rows[2].find('[data-testid="assign-result-parts"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('共分配 5 条病历')
  })

  it('无明细时回退到汇总且不显示来源；关闭事件上抛', async () => {
    const wrapper = mount(TaskAssignmentResult, {
      props: { result: { total_assigned: 2, assignment_summary: { 质控员甲: 2 } } },
    })
    expect(wrapper.get('[data-testid="assign-result-row"]').text()).toContain('质控员甲')
    expect(wrapper.find('[data-testid="assign-result-parts"]').exists()).toBe(false)
    await wrapper.get('[data-testid="assign-result-close"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})

describe('taskAssignment 辅助', () => {
  it('来源分布只取合法非负整数', () => {
    expect(assignReasonParts({ original_reviewer: 1, department: -1, ratio_fallback: 1.5 })).toEqual([
      { key: 'original_reviewer', label: '原质控员', count: 1 },
    ])
    expect(assignReasonParts(undefined)).toEqual([])
  })

  it('业务码与状态码匹配才给出专用文案', () => {
    expect(describeTaskAssignError({ code: 'method_unavailable' }, 422)).toBe('该分配方式当前不可用')
    expect(describeTaskAssignError({ code: 'method_unavailable', message: '不可用', reason: '无权威事实' }, 422)).toBe('该分配方式当前不可用（无权威事实）')
    expect(describeTaskAssignError({ code: 'method_unavailable' }, 409)).toBeUndefined()
    expect(describeTaskAssignError({ code: 'department_missing' }, 409)).toContain('缺少科室')
    expect(describeTaskAssignError({ code: 'original_reviewer_unmatched' }, 409)).toContain('部分病历无原质控员')
    expect(describeTaskAssignError({ code: 'department_unassigned' }, 409)).toContain('部分科室')
    expect(describeTaskAssignError({ code: 'other' }, 409)).toBeUndefined()
    expect(describeTaskAssignError(undefined, 409)).toBeUndefined()
  })
})
