import { describe, expect, it } from 'vitest'
import { buildRecordComparisonIssues } from '@/views/workstation-v4/semantic-rules/record-comparison-model'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

describe('buildRecordComparisonIssues', () => {
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
          rule_id: 'LX0609-018',
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
