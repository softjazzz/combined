import { describe, expect, it } from 'vitest'
import type { BusinessAgentTurn } from '@/api/businessAgent'
import {
  followupIntents,
  statusTone,
  turnSummary,
} from '@/views/workstation-v4/components/businessAgentPresentation'

function turn(partial: Partial<BusinessAgentTurn>): BusinessAgentTurn {
  return {
    run_id: 'r',
    question: 'q',
    answer: 'a',
    status: 'completed',
    references: [],
    tool_calls: 2,
    elapsed_ms: 3200,
    ...partial,
  }
}

describe('业务助手展示派生', () => {
  it('步骤摘要只来自本轮实际来源类型，停止与失败如实标注', () => {
    expect(
      turnSummary(
        turn({
          references: [
            { id: '1', kind: 'saved_result', title: 'a' },
            { id: '2', kind: 'saved_result', title: 'b' },
            { id: '3', kind: 'rule', title: 'c' },
          ],
        }),
      ),
    ).toBe('已完成 2 次查询 · 读取保存结果、核对规则目录 · 3.2 秒')
    expect(turnSummary(turn({ references: [] }))).toBe('已完成 2 次查询 · 3.2 秒')
    expect(turnSummary(turn({ status: 'stopped' }))).toContain('已停止')
    expect(turnSummary(turn({ status: 'failed' }))).toContain('部分步骤失败')
  })

  it('状态色调仅用于数据状态', () => {
    expect(statusTone('non_compliant')).toBe('mq-status--danger')
    expect(statusTone('data_gap')).toBe('mq-status--warning')
    expect(statusTone('compliant')).toBe('mq-status--success')
    expect(statusTone('not_applicable')).toBe('')
  })

  it('追问建议按来源模板生成，医生才有草稿，未完成轮次不给建议', () => {
    const references = [
      {
        id: 'n',
        kind: 'saved_result' as const,
        title: 'a',
        status: 'non_compliant',
        rule_id: 'R',
        position: 2,
      },
      { id: 'g', kind: 'saved_result' as const, title: 'b', status: 'data_gap' },
    ]
    expect(followupIntents(turn({ references }), 'doctor').map((item) => item.label)).toEqual([
      '第 2 条要求从哪里来？',
      '资料不足是漏写还是没同步？',
      '帮我写第 2 条的补充',
    ])
    expect(followupIntents(turn({ references }), 'manager').map((item) => item.kind)).not.toContain(
      'draft',
    )
    expect(followupIntents(turn({ references, status: 'stopped' }), 'doctor')).toEqual([])
    const stats = followupIntents(
      turn({ references: [{ id: 's', kind: 'statistics', title: '统计' }] }),
      'manager',
    )
    expect(stats.map((item) => item.label)).toEqual([
      '列出这些问题对应的病例',
      '生成质量会议报告草稿',
    ])
  })
})
