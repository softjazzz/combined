import { describe, expect, it } from 'vitest'
import { normalizeRecord, normalizeRecordPoolQcSummary } from '@/views/workstation-v4/normalize'
import { resolveResultPresentation } from '@/views/workstation-v4/components/qc/latestQcSummaryPresentation'

describe('病历池失败语义传到最终展示', () => {
  it.each([0, 1])('保留%s项有效结果及失败提示，不伪装已完成', (delivered) => {
    const summary = {
      status: delivered ? 'ready' : 'failed',
      execution_status: delivered ? 'partial_failed' : 'failed',
      total_rule_count: delivered,
      completed_rule_count: delivered,
      failed_rule_count: 2 - delivered,
      failed_rule_ids: delivered ? ['LX0609-06-01-05'] : ['LX0609-06-01-04', 'LX0609-06-01-05'],
      status_counts: delivered ? { non_compliant: 1 } : {},
      completed_at: '2026-10-28T00:00:00Z',
    }
    const record = normalizeRecord({ latest_qc_summary: summary })
    expect(record.latestQcSummary?.executionStatus).toBe(summary.execution_status)
    expect(record.latestQcSummary?.failedRuleCount).toBe(2 - delivered)
    expect(record.latestQcSummary?.failedRuleIds).toEqual(summary.failed_rule_ids)
    const shown = resolveResultPresentation(record.latestQcSummary)
    expect(shown.resultLabel).toBe(delivered ? '部分执行失败' : '执行失败')
    expect(shown.issueSummary).toContain(`${2 - delivered} 项失败`)
    if (delivered) expect(shown.issueSummary).toContain('确定问题 1')
    expect(shown.issueSummary).not.toContain('未发现确定问题')
    expect(shown.resultStatus).not.toBe('completed')
  })

  it.each(['material_capture', 'material_preparation'])('以 %s 识别本轮资料准备失败', (stage) => {
    const record = normalizeRecord({ latest_qc_summary: {
      status: 'technical_error',
      failure_stage: stage,
      reason_code: 'material_source_contract_incomplete',
      completed_at: '2026-10-28T00:00:00Z',
    } })
    expect(record.latestQcSummary?.failureStage).toBe(stage)
    expect(resolveResultPresentation(record.latestQcSummary)).toMatchObject({
      resultStatus: 'technical-error', resultLabel: '病历资料准备失败',
      issueSummary: '最近一次病历资料准备失败，未生成质控结果。',
      latestQcTime: '2026-10-28 08:00',
    })
  })

  it('没有资料准备失败标记时仍提示结果校验异常', () => {
    const record = normalizeRecord({ latest_qc_summary: {
      status: 'technical_error', reason_code: 'saved_partial_result_invalid',
    } })
    expect(resolveResultPresentation(record.latestQcSummary)).toMatchObject({
      resultLabel: '结果校验异常', issueSummary: '请复核结果交付',
    })
  })

  it('汇总保留部分失败和全部失败的独立计数', () => {
    const counts = normalizeRecordPoolQcSummary({
      total_records: 3, ready_records: 1, partial_failed_records: 1, failed_records: 1,
    })
    expect(counts.readyRecords).toBe(1)
    expect(counts.partialFailedRecords).toBe(1)
    expect(counts.failedRecords).toBe(1)
  })
})
