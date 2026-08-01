import { describe, expect, it } from 'vitest'

import {
  buildBatchJobPresentation,
  formatBatchJobDateTime,
  getBatchJobStatusClass,
  getBatchJobStatusText,
} from '@/views/workstation-v4/customer-sample-validation/batchJobPresentation'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

function buildJob(overrides: Partial<SichuanBatchJob> = {}): SichuanBatchJob {
  return {
    id: 'job-1',
    rule_code: 'LX0609',
    rule_name: '泸县0609质控点验证',
    scope: 'running',
    status: 'completed',
    record_ids: ['208790'],
    customer_rule_count: 6,
    created_at: '2026-07-31T08:30:00Z',
    updated_at: '2026-07-31T08:35:00Z',
    summary: {
      total_records: 1,
      success_count: 1,
      failed_count: 0,
      issue_records: 0,
      compliant_records: 1,
      total_tokens: 0,
      total_processing_time: 0,
    },
    ...overrides,
  }
}

describe('batchJobPresentation', () => {
  it('归一对象型状态分布、规则范围、病历和结果进度', () => {
    const model = buildBatchJobPresentation(
      buildJob({
        rule_set_name: '泸县0609质控点验证 v1',
        filters: {
          selected_rule_ids: [
            'LX0609-001',
            'LX0609-002',
            'LX0609-003',
            'LX0609-004',
            'LX0609-005',
            'LX0609-006',
          ],
        },
        summary: {
          total_records: 1,
          success_count: 1,
          failed_count: 0,
          issue_records: 1,
          compliant_records: 0,
          total_tokens: 0,
          total_processing_time: 0,
          display_status_counts: {
            technical_error: 1,
            non_compliant: 1,
            data_gap: 1,
            uncertain: 1,
            compliant: 1,
            not_applicable: 1,
          },
        },
      }),
    )

    expect(model.statusLabel).toBe('已完成')
    expect(model.ruleSetText).toBe('泸县0609质控点验证 v1')
    expect(model.scopeText).toBe('选定 6 个质控点')
    expect(model.compactRuleIdsText).toContain('LX0609-001、LX0609-002、LX0609-003 +3')
    expect(model.recordText).toBe('1 份病历')
    expect(model.recordProgressText).toBe('病历进度：已完成 1 / 1 份')
    expect(model.resultCount).toBe(6)
    expect(model.resultProgressText).toBe('结果回写：6 / 6 条')
    expect(model.statusChips.map((chip) => [chip.key, chip.label, chip.value])).toEqual([
      ['technical_error', '技术异常', 1],
      ['non_compliant', '不合规', 1],
      ['data_gap', '数据不足', 1],
      ['uncertain', 'AI判断', 1],
      ['compliant', '合规', 1],
      ['not_applicable', '不适用', 1],
    ])
  })

  it('同时识别数组型 status_breakdown 和 AI 建议状态', () => {
    const model = buildBatchJobPresentation(
      buildJob({
        summary: {
          total_records: 1,
          success_count: 1,
          failed_count: 0,
          issue_records: 1,
          compliant_records: 0,
          total_tokens: 0,
          total_processing_time: 0,
          result_aggregation: {
            cluster_count: 0,
            duplicate_hits: 0,
            clusters: [],
            status_breakdown: [
              { key: 'ai_suggested_non_compliant', count: 1 },
              { key: 'ai_suggested_compliant', count: 1 },
              { key: 'not_executed', count: 1 },
            ],
          },
        },
      }),
    )

    expect(model.statusCounts).toMatchObject({
      ai_suggested_non_compliant: 1,
      ai_suggested_compliant: 1,
      not_executed: 1,
    })
    expect(model.statusChips.map((chip) => chip.label)).toEqual([
      'AI建议复核',
      '未执行',
      'AI未见问题',
    ])
    expect(model.resultCountText).toBe('3 条结果')
    expect(model.overviewText).toBe('发现需关注结果：AI建议复核 1，未执行 1')
  })

  it('缺少状态和统计字段时使用中性回退，不伪造排队中或合规结论', () => {
    const model = buildBatchJobPresentation(
      buildJob({
        status: '' as SichuanBatchJob['status'],
        rule_name: '',
        rule_set_name: '',
        customer_rule_count: 0,
        record_ids: [],
        created_at: undefined,
        updated_at: undefined,
        summary: undefined,
      }),
    )

    expect(model.statusLabel).toBe('状态待返回')
    expect(model.statusClass).toBe('is-muted')
    expect(model.ruleSetText).toBe('质控任务')
    expect(model.scopeText).toBe('质控范围未返回')
    expect(model.recordText).toBe('病历数未返回')
    expect(model.resultCountText).toBe('结果数待返回')
    expect(model.updatedText).toBe('未返回时间')
    expect(model.overviewText).toBe('暂无结果摘要')
    expect(model.statusChips).toEqual([])
  })

  it('集中提供状态和时间格式化合同', () => {
    expect(getBatchJobStatusText('running')).toBe('执行中')
    expect(getBatchJobStatusText(undefined)).toBe('状态待返回')
    expect(getBatchJobStatusClass('completed')).toBe('is-success')
    expect(getBatchJobStatusClass(undefined)).toBe('is-muted')
    expect(formatBatchJobDateTime(undefined)).toBe('未返回时间')
    expect(formatBatchJobDateTime('not-a-date')).toBe('not-a-date')
  })
})
