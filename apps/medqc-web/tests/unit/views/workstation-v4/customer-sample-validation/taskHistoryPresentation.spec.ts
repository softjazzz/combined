import { describe, expect, it } from 'vitest'
import {
  buildTaskHistoryRow,
  cleanTaskTitle,
  countSegments,
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
    expect(row.metaText).toBe('08:27 发起 · 18 份病历 · 全量 68 个质控点')
  })

  it('结果计数归并为客户口径，内部状态归入未完成判定', () => {
    const row = buildTaskHistoryRow(job())
    expect(row.counts).toEqual({
      issue: 7,
      dataGap: 4,
      compliant: 24,
      notApplicable: 9,
      pending: 3,
    })
    expect(row.countTotal).toBe(47)
    expect(row.statusLabel).toBe('已完成')
    expect(row.statusTone).toBe('success')
    expect(row.canExport).toBe(true)
    expect(countSegments(row).map((segment) => segment.key)).toEqual([
      'issue',
      'dataGap',
      'compliant',
      'notApplicable',
      'pending',
    ])
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
    expect(row.statusLabel).toBe('部分未完成')
    expect(row.statusTone).toBe('warning')
    expect(row.noticeText).toBe('2 项质控未执行完，已完成结果可查看')
    expect(row.canExport).toBe(true)
    expect(row.isCompleted).toBe(false)
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
    const now = new Date('2026-10-23T12:00:00')
    const rows = [
      buildTaskHistoryRow(job({ id: 'a', created_at: '2026-10-23T08:00:00' })),
      buildTaskHistoryRow(job({ id: 'b', created_at: '2026-10-22T18:00:00' })),
      buildTaskHistoryRow(job({ id: 'c', created_at: '2026-10-20T09:00:00' })),
      buildTaskHistoryRow(job({ id: 'd', created_at: '2026-10-20T07:00:00' })),
    ]
    const groups = groupTaskHistoryRows(rows, now)
    expect(groups.map((group) => group.label)).toEqual([
      '今天 · 10月23日',
      '昨天 · 10月22日',
      '10月20日',
    ])
    expect(groups[2].rows.map((row) => row.id)).toEqual(['c', 'd'])
  })
})
