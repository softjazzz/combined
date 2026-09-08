import { describe, expect, it } from 'vitest'

import { buildQcResultDebugText } from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'
import type { SingleRecordQcResultItem } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

interface DiagnosticDocument {
  schema_version: string
  capture_completeness: string
  replay_capability: string
  missing_components: string[]
  context: Record<string, unknown>
  results: SingleRecordQcResultItem[]
  summary: {
    exported_result_count: number
    unique_rule_count: number
    scope: string
    duplicate_rule_ids: string[]
    status_counts: Record<string, number>
    reason_groups: { status: string; reason_code: string; rule_ids: string[] }[]
    evidence_sources: {
      source_type: string
      evidence_count: number
      unique_reference_count: number
      rule_ids: string[]
    }[]
  }
}

function appendix(markdown: string): DiagnosticDocument {
  const match = markdown.match(/```json\s*\n([\s\S]*?)\n```\s*$/)
  expect(match, '诊断包末尾必须提供可解析机器数据').not.toBeNull()
  return JSON.parse(match![1]) as DiagnosticDocument
}

function result(index: number): SingleRecordQcResultItem {
  return {
    rule_id: `LX0609-${String(index).padStart(3, '0')}`,
    rule_name: '合成规则',
    status: index <= 24 ? 'data_gap' : 'compliant',
    reason_code: index <= 24 ? 'association_failed' : 'requirement_satisfied',
  }
}

const fullContext = { expectedRuleCount: 72, resultRuleCount: 72, isComplete: true }

describe('质控诊断包机器附录', () => {
  it('汇总全部 72 项并明确仅支持人工核查、未采集执行输入', () => {
    const doc = appendix(
      buildQcResultDebugText(
        Array.from({ length: 72 }, (_, index) => result(index + 1)),
        fullContext,
        { diagnosticPackage: true },
      ),
    )
    expect(doc.schema_version).toBe('medqc-qc-diagnostic-v1')
    expect(doc.summary).toMatchObject({
      exported_result_count: 72,
      unique_rule_count: 72,
      scope: 'full_loaded_result',
      duplicate_rule_ids: [],
      status_counts: { data_gap: 24, compliant: 48 },
    })
    expect(doc.summary.reason_groups).toContainEqual({
      status: 'data_gap',
      reason_code: 'association_failed',
      rule_ids: Array.from({ length: 24 }, (_, index) => result(index + 1).rule_id),
    })
    expect(doc.results).toHaveLength(72)
    expect(doc.capture_completeness).toBe('partial')
    expect(doc.replay_capability).toBe('manual_review')
    expect(doc.missing_components).toEqual(
      expect.arrayContaining([
        'execution_inputs',
        'source_read_states',
        'model_requests_and_responses',
        'execution_build_version',
      ]),
    )
  })

  it('即使原任务完整，单条筛选导出也不能标为完整结果范围', () => {
    const doc = appendix(
      buildQcResultDebugText([result(1)], fullContext, { diagnosticPackage: true }),
    )
    expect(doc.summary.scope).toBe('partial_or_unknown')
    expect(doc.summary.exported_result_count).toBe(1)
  })

  it('重复规则不能仅凭条数充足判为完整范围', () => {
    const doc = appendix(
      buildQcResultDebugText(
        Array.from({ length: 72 }, () => result(1)),
        fullContext,
        { diagnosticPackage: true },
      ),
    )
    expect(doc.summary.duplicate_rule_ids).toEqual(['LX0609-001'])
    expect(doc.summary.unique_rule_count).toBe(1)
    expect(doc.summary.scope).toBe('partial_or_unknown')
  })

  it('同一引用跨来源分别统计，来源内重复证据不重复计算引用', () => {
    const item = {
      ...result(10),
      evidence: [
        { source_type: 'exam_master', source_ref: 'shared-reference' },
        { source_type: 'exam_master', source_ref: 'shared-reference' },
        { source_type: 'inpat_nondrug_order', source_ref: 'shared-reference' },
      ],
    }
    const doc = appendix(buildQcResultDebugText([item], undefined, { diagnosticPackage: true }))
    expect(doc.summary.evidence_sources).toEqual(
      expect.arrayContaining([
        {
          source_type: 'exam_master',
          evidence_count: 2,
          unique_reference_count: 1,
          rule_ids: ['LX0609-010'],
        },
        {
          source_type: 'inpat_nondrug_order',
          evidence_count: 1,
          unique_reference_count: 1,
          rule_ids: ['LX0609-010'],
        },
      ]),
    )
  })

  it('正文与 JSON 共用别名及日期平移，保留时间间隔且排除原身份和未白名单字段', () => {
    const item = {
      ...result(1),
      extra: 'DO_NOT_EXPORT_TOP_LEVEL',
      evidence: [
        {
          source_type: 'admission_record',
          source_ref: 'raw-document-reference',
          record_time: '2025-08-12 17:24:13',
        },
        {
          source_type: 'admission_record',
          source_ref: 'raw-document-reference',
          record_time: '2025-08-14 17:24:13',
        },
      ],
      customer_display_facts: { api_key: 'secret-credential-123' },
    }
    const markdown = buildQcResultDebugText(
      [item],
      {
        ...fullContext,
        instituteId: 'RAW-HOSPITAL',
        patientId: 'RAW-PATIENT',
        visitId: 'RAW-VISIT',
      },
      { diagnosticPackage: true },
    )
    const doc = appendix(markdown)
    const prose = markdown.slice(0, markdown.lastIndexOf('```json'))
    for (const secret of [
      'DO_NOT_EXPORT_TOP_LEVEL',
      'secret-credential-123',
      'RAW-HOSPITAL',
      'RAW-PATIENT',
      'RAW-VISIT',
      'raw-document-reference',
    ]) {
      expect(markdown).not.toContain(secret)
    }
    expect(doc.context.patientId).toBe('患者-001')
    expect(prose).toContain(`患者ID：${doc.context.patientId}`)
    const evidence = doc.results[0].evidence!
    expect(evidence[0].source_ref).toBe(evidence[1].source_ref)
    expect(prose).toContain(`安全引用：${evidence[0].source_ref}`)
    expect(prose).toContain(`记录时间：${evidence[0].record_time}`)
    expect(prose).toContain(`记录时间：${evidence[1].record_time}`)
    expect(evidence[0].record_time).not.toBe('2025-08-12 17:24:13')
    expect(
      Date.parse(String(evidence[1].record_time)) - Date.parse(String(evidence[0].record_time)),
    ).toBe(48 * 3600 * 1000)
    expect(doc.results[0]).not.toHaveProperty('extra')
  })

  it('默认复制仍然输出原有最小调试格式', () => {
    const markdown = buildQcResultDebugText([result(1)], fullContext)
    expect(markdown).toContain('medqc-qc-debug-v4-redacted-minimal')
    expect(markdown).not.toContain('medqc-qc-diagnostic-v1')
    expect(markdown).not.toContain('```json')
  })
})
