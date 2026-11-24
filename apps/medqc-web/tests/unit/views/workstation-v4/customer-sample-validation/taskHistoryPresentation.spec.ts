import { describe, expect, it } from 'vitest'
import {
  buildTaskHistoryRow,
  cleanTaskTitle,
  formatDuration,
  groupTaskHistoryRows,
} from '@/views/workstation-v4/customer-sample-validation/taskHistoryPresentation'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

function job(extra: Record<string, unknown> = {}): SichuanBatchJob {
  return {
    id: 'job-1',
    rule_name: '1023样本验证任务(68条规则)',
    status: 'completed',
    created_at: '2026-10-23T08:27:00',
    customer_rule_count: 68,
    summary: {
      total_records: 18,
      success_count: 18,
      display_status_counts: {
        non_compliant: 5,
        ai_suggested_non_compliant: 2,
        data_gap: 3,
        data_quality_gap: 1,
        compliant: 20,
        ai_suggested_compliant: 4,
        not_applicable: 9,
        technical_error: 1,
        uncertain: 2,
      },
    },
    ...extra,
  } as unknown as SichuanBatchJob
}

describe('质控记录列表展示模型', () => {
  it('任务名去掉末尾规则数，范围写成一句话', () => {
    expect(cleanTaskTitle('1023样本验证任务(68条规则)')).toBe('1023样本验证任务')
    expect(cleanTaskTitle('1023样本验证任务（12 条规则）')).toBe('1023样本验证任务')
    expect(cleanTaskTitle('')).toBe('质控任务')
    const row = buildTaskHistoryRow(job())
    expect(row.title).toBe('1023样本验证任务')
    expect(row.metaText).toBe('16:27 发起 · 18 份病历 · 全量 68 个质控点')
  })

  it('列表不携带结果摘要与计数，完成任务只显示完成时间与用时', () => {
    const row = buildTaskHistoryRow(
      job({
        started_at: '2026-10-23T08:27:00',
        finished_at: '2026-10-23T08:29:05',
      }),
    )
    expect(row).not.toHaveProperty('counts')
    expect(row).not.toHaveProperty('countTotal')
    expect(row.detailText).toBe('16:29 完成 · 执行 2 分 5 秒')
    expect(row.statusLabel).toBe('已完成')
    expect(row.statusTone).toBe('success')
    expect(row.canExport).toBe(true)
  })

  it('部分失败写明已完成结果可查看，仍可导出', () => {
    const row = buildTaskHistoryRow(
      job({
        status: 'failed',
        summary: {
          total_records: 20,
          execution_status: 'partial_failed',
          failed_rule_count: 2,
          completed_rule_count: 318,
          display_status_counts: { non_compliant: 3 },
        },
      }),
    )
    expect(row.statusLabel).toBe('未全部完成')
    expect(row.statusTone).toBe('warning')
    expect(row.detailText).toBe('查看原因及已有结果')
    expect(row.canExport).toBe(true)
    expect(row.isCompleted).toBe(false)
  })

  it('完全失败任务渲染 danger 语气和执行失败标签，不误判为未全部完成', () => {
    const row = buildTaskHistoryRow(job({ status: 'failed', summary: null, has_results: false }))
    expect(row.statusLabel).toBe('执行失败')
    expect(row.statusTone).toBe('danger')
    expect(row.detailText).toBe('查看失败原因')
    expect(row.detailTone).toBe('danger')
    expect(row.canExport).toBe(false)
    expect(row.isCompleted).toBe(false)
  })

  it('失败但 has_results=true 时归类为部分失败，保持 warning 语气并允许导出', () => {
    const row = buildTaskHistoryRow(job({ status: 'failed', summary: null, has_results: true }))
    expect(row.statusLabel).toBe('未全部完成')
    expect(row.statusTone).toBe('warning')
    expect(row.detailText).toBe('查看原因及已有结果')
    expect(row.canExport).toBe(true)
  })

  it('轻量列表的进度只取病历计数', () => {
    const row = buildTaskHistoryRow(
      job({ status: 'running', summary: null, total_records: 27, success_count: 9 }),
    )
    expect(row.progressText).toBe('已完成 9 / 27 份 · 33%')
  })

  it('完成时间缺失不虚构用时', () => {
    expect(buildTaskHistoryRow(job({ summary: null })).detailText).toBe('已完成')
    expect(formatDuration(0)).toBe('0 秒')
    expect(formatDuration(3600)).toBe('1 小时')
  })

  it('有排队等待时与实际执行时长分别显示', () => {
    const row = buildTaskHistoryRow(job({
      created_at: '2026-10-23T05:24:24', started_at: '2026-10-23T05:29:28',
      finished_at: '2026-10-23T05:33:09',
    }))
    expect(row.detailText).toBe('13:33 完成 · 等待 5 分 4 秒 · 执行 3 分 41 秒')
  })

  it('执行中显示病历进度', () => {
    const row = buildTaskHistoryRow(
      job({
        status: 'running',
        summary: { total_records: 18, success_count: 8, progress_percent: 46 },
      }),
    )
    expect(row.isRunning).toBe(true)
    expect(row.statusTone).toBe('info')
    expect(row.progressText).toBe('已完成 8 / 18 份 · 46%')
  })

  it('按发起日期分组为今天、昨天和具体日期', () => {
    const now = new Date('2026-10-22T16:15:00Z')
    const rows = [
      buildTaskHistoryRow(job({ id: 'a', created_at: '2026-10-22 16:00:00' })),
      buildTaskHistoryRow(job({ id: 'b', created_at: '2026-10-22T23:59:00+08:00' })),
      buildTaskHistoryRow(job({ id: 'c', created_at: '2026-10-20T09:00:00' })),
      buildTaskHistoryRow(job({ id: 'd', created_at: '2026-10-20T07:00:00' })),
    ]
    const groups = groupTaskHistoryRows(rows, now)
    expect(groups.map((group) => group.label)).toEqual([
      '今天 · 10月23日',
      '昨天 · 10月22日',
      '10月20日',
    ])
    expect(groups[0].rows[0].timeText).toBe('00:00')
    expect(groups[1].rows[0].timeText).toBe('23:59')
    expect(groups[2].rows.map((row) => row.id)).toEqual(['c', 'd'])
  })
})
