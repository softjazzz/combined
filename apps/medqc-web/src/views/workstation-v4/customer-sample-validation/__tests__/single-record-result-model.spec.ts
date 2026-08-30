import { describe, expect, it } from 'vitest'

import { recommendationEvidenceForSingleRecord } from '../single-record-result-model'

describe('single-record recommendation evidence', () => {
  it('exposes signed nested refs with recommendation metadata', () => {
    const result = recommendationEvidenceForSingleRecord({
      rule_id: 'LX0609-020',
      customer_display_facts: {
        recommendation_evidence: [
          {
            recommendation_index: 1,
            opinion_evidence: [
              { source_type: 'consultation_record', source_ref: 'src_aaaaaaaaaaaaaaaaaaaaaaaa' },
            ],
            execution_evidence: [
              { source_type: 'daily_course_record', source_ref: 'src_bbbbbbbbbbbbbbbbbbbbbbbb' },
            ],
          },
        ],
      },
      evidence: [],
    })

    expect(result).toMatchObject([
      {
        recommendation_index: 1,
        evidence_role: 'opinion',
        source_ref: 'src_aaaaaaaaaaaaaaaaaaaaaaaa',
      },
      {
        recommendation_index: 1,
        evidence_role: 'execution',
        source_ref: 'src_bbbbbbbbbbbbbbbbbbbbbbbb',
      },
    ])
  })

  it('ignores raw nested ids and keeps legacy evidence when no nested refs exist', () => {
    const result = recommendationEvidenceForSingleRecord({
      rule_id: 'LX0609-020',
      customer_display_facts: {
        recommendation_evidence: [
          {
            recommendation_index: 1,
            opinion_evidence: [{ source_type: 'consultation_record', source_document_id: 'raw-1' }],
            execution_evidence: [],
          },
        ],
      },
      evidence: [
        { source_type: 'consultation_record', source_ref: 'src_aaaaaaaaaaaaaaaaaaaaaaaa' },
      ],
    })

    expect(result).toHaveLength(1)
    expect(result[0].source_ref).toBe('src_aaaaaaaaaaaaaaaaaaaaaaaa')
    expect(result[0]).not.toHaveProperty('source_document_id')
  })

  it('does not duplicate a flat ref already present in nested evidence', () => {
    const result = recommendationEvidenceForSingleRecord({
      rule_id: 'LX0609-020',
      customer_display_facts: {
        recommendation_evidence: [
          {
            recommendation_index: 1,
            opinion_evidence: [
              { source_type: 'consultation_record', source_ref: 'src_aaaaaaaaaaaaaaaaaaaaaaaa' },
            ],
            execution_evidence: [],
          },
        ],
      },
      evidence: [
        { source_type: 'consultation_record', source_ref: 'src_aaaaaaaaaaaaaaaaaaaaaaaa' },
        { source_type: 'daily_course_record', source_ref: 'src_bbbbbbbbbbbbbbbbbbbbbbbb' },
      ],
    })

    expect(result.map((item) => item.source_ref)).toEqual([
      'src_aaaaaaaaaaaaaaaaaaaaaaaa',
      'src_bbbbbbbbbbbbbbbbbbbbbbbb',
    ])
  })
})
