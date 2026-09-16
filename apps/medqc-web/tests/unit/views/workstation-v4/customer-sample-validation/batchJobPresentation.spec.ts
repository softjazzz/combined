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
  it('自动补跑排队期间保持运行态，不展示最终失败', () => {
    const job = buildJob({ status: 'failed' })
    job.summary = {
      ...job.summary!,
      execution_status: 'partial_failed',
      completed_rule_count: 1297,
      failed_rule_count: 3,
      automatic_failed_rule_retry: {
        status: 'queued',
        should_retry: true,
        next_attempt: 1,
      },
    }

    const model = buildBatchJobPresentation(job)

    expect(model.isRunning).toBe(true)
    expect(model.statusLabel).toBe('自动补跑中')
    expect(model.statusClass).toBe('is-running')
    expect(model.phaseText).toContain('系统正在自动补跑失败项')
    expect(model.overviewText).toContain('已有有效结果会继续保留')
  })

  it('部分执行失败保留有效结果并明确未完成项数', () => {
    const job = buildJob({ status: 'failed' })
    job.summary = {
      ...job.summary!,
      execution_status: 'partial_failed',
      completed_rule_count: 1,
      failed_rule_count: 1,
      status_breakdown: { compliant: 1 },
    }
    const model = buildBatchJobPresentation(job)
    expect(model.isRunning).toBe(false)
    expect(model.statusLabel).toBe('部分执行失败')
    expect(model.phaseText).toBe('1 项质控执行未完成，已完成的 1 条结果仍可查看。')
    expect(model.overviewText).toBe(model.phaseText)
    expect(model.resultCount).toBe(1)
    expect(model.phaseText).not.toContain('无问题')
  })

  it('全部执行失败不承诺存在临床结果', () => {
    const job = buildJob({ status: 'failed' })
    job.summary = {
      ...job.summary!,
      execution_status: 'failed',
      completed_rule_count: 0,
      failed_rule_count: 2,
    }
    const model = buildBatchJobPresentation(job)
    expect(model.isRunning).toBe(false)
    expect(model.phaseText).toBe('2 项质控执行未完成，本次未形成可交付的判定。')
    expect(model.overviewText).toBe(model.phaseText)
  })

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

  it('保留0916规则范围与 data_quality_gap 的精确展示口径', () => {
    const ruleIds = Array.from(
      { length: 32 },
      (_, index) => `LX0916-${String(index + 1).padStart(3, '0')}`,
    )
    const model = buildBatchJobPresentation(
      buildJob({
        rule_code: 'LX0916',
        rule_name: '泸县0916质控点验证',
        rule_set_key: 'luxian_0916_qc_v1',
        rule_set_name: '泸县0916质控点验证 v1',
        customer_rule_count: 32,
        filters: { selected_rule_ids: ruleIds },
        summary: {
          total_records: 1,
          success_count: 1,
          failed_count: 0,
          issue_records: 1,
          compliant_records: 0,
          total_tokens: 0,
          total_processing_time: 0,
          diagnostic_rule_failure_count: 2,
          display_status_counts: {
            data_quality_gap: 4,
            compliant: 28,
          },
        },
        items: [
          {
            rule_id: 'LX0916-001',
            rule_name: '入院记录内容完整性',
            status: 'data_quality_gap',
            is_compliant: null,
            conclusion: '入院记录来源不可用，暂无法核对。',
          },
        ],
      }),
    )

    expect(model.scopeText).toBe('选定 32 个质控点')
    expect(model.compactRuleIdsText).toBe(
      '32 个 LX0916 质控点：LX0916-001、LX0916-002、LX0916-003 +29',
    )
    expect(model.statusChips.map((chip) => [chip.key, chip.label, chip.value])).toEqual([
      ['data_quality_gap', '资料待核实', 4],
      ['compliant', '合规', 28],
    ])
    expect(model.overviewText).toBe('发现需关注结果：资料待核实 4')
    expect(model.diagnosticRuleFailureCount).toBe(2)
    expect(model.issueSummaryText).toBe('问题点：LX0916-001 入院记录内容完整性')
    expect(model.liveResultLines).toEqual([
      expect.objectContaining({
        ruleId: 'LX0916-001',
        statusLabel: '资料待核实',
      }),
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

  it('只把服务端已回写的安全结果整理为实时展示行', () => {
    const model = buildBatchJobPresentation(
      buildJob({
        status: 'running',
        items: [
          {
            rule_id: 'LX0609-020',
            rule_name: '会诊意见及执行情况',
            status: 'non_compliant',
            is_compliant: false,
            conclusion: '后续病程未记录会诊意见及执行情况。',
          },
          {
            rule_id: 'LX0609-045',
            rule_name: '输血记录',
            status: 'compliant',
            is_compliant: true,
            conclusion: '已找到输血记录。',
          },
        ],
      }),
    )

    expect(model.liveResultLines).toEqual([
      expect.objectContaining({
        ruleId: 'LX0609-045',
        statusLabel: '合规',
        text: '已找到输血记录。',
      }),
      expect.objectContaining({
        ruleId: 'LX0609-020',
        statusLabel: '不合规',
        text: '后续病程未记录会诊意见及执行情况。',
      }),
    ])
  })

  it('无最终结果时只展示安全的规则族执行阶段', () => {
    const executorStreamState = {
      enabled: true,
      kind: 'native_executor_phase',
      event: 'started',
      executor_key: 'exam_lab',
      completed_batches: 2,
      total_batches: 10,
    }
    const model = buildBatchJobPresentation(
      buildJob({
        status: 'running',
        summary: {
          ...buildJob().summary,
          stream_state: executorStreamState,
        },
        items: [],
      }),
    )

    expect(model.liveResultLines).toEqual([])
    expect(model.liveExecutionPhase).toEqual({
      label: '执行动态',
      text: '正在核对检查检验（2 / 10）',
    })
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
