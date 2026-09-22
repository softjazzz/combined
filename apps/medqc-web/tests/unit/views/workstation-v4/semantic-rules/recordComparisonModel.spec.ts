import { describe, expect, it } from 'vitest'
import { buildRecordComparisonIssues } from '@/views/workstation-v4/semantic-rules/record-comparison-model'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

describe('buildRecordComparisonIssues', () => {
  it('旧三位泸县编号不会作为展示和反馈身份回退输出', () => {
    const job = {
      id: 'job-legacy-rule-id',
      items: [
        {
          record_ref: 'record-1',
          rule_id: 'LX0609-001',
          rule_code: 'LX0609-001',
          status: 'non_compliant',
        },
      ],
    } as unknown as SichuanBatchJob

    const [issue] = buildRecordComparisonIssues(job, { recordRef: 'record-1' })

    expect(issue?.rule_code).toBe('未知规则')
  })

  it('未执行质控点不应被解释为需要人工复核', () => {
    const job = {
      id: 'job-not-executed',
      items: [
        {
          record_id: 'visit-1',
          rule_id: 'LX0609-04-02-04',
          rule_name: '植入物信息',
          status: 'not_executed',
        },
      ],
    } as unknown as SichuanBatchJob

    const [issue] = buildRecordComparisonIssues(job, { recordId: 'visit-1' })

    expect(issue).toMatchObject({
      status: 'not_executed',
      status_text: '未执行',
      result_kind_text: '未执行',
      summary: '当前阶段未执行，不纳入正式结论。',
      suggestion: expect.stringContaining('无需按缺陷处理'),
    })
    expect(issue?.detail).not.toContain('人工复核')
  })

  it('合并同一受控文书引用，保留不同文书引用', () => {
    const job = {
      id: 'job-1',
      rule_code: 'LX0609',
      rule_name: '泸县0609',
      scope: 'running',
      status: 'completed',
      items: [
        {
          record_id: 'visit-1',
          rule_id: 'LX0609-01-01-02',
          rule_name: '主诉与第一诊断',
          status: 'non_compliant',
          findings: '主诉字数不足。',
          suggestion: '补充主诉。',
          evidence: [
            { source_type: 'admission_record', source_ref: 'src_same_document_001' },
            { source_type: 'admission_record', source_ref: 'src_same_document_001' },
            { source_type: 'admission_record', source_ref: 'src_another_document_002' },
          ],
        },
      ],
    } as unknown as SichuanBatchJob

    const [issue] = buildRecordComparisonIssues(job, { recordId: 'visit-1' })

    expect(issue?.evidences).toHaveLength(2)
    expect(issue?.evidences.map((item) => item.source_ref)).toEqual([
      'src_same_document_001',
      'src_another_document_002',
    ])
    expect(issue?.evidences.map((item) => item.quote)).toEqual(['', ''])
    expect(issue?.evidences.map((item) => item.section_field_path)).toEqual([
      'chief_complaint',
      'chief_complaint',
    ])
  })
})
