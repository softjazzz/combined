import { describe, expect, it } from 'vitest'

import {
  buildRecordComparisonIssues,
  buildRecommendationEvidence,
} from '../record-comparison-model'

const safeRef = (source_type: string, source_ref: string) => ({ source_type, source_ref })

describe('record comparison consultation evidence', () => {
  it('flattens safe per-recommendation references with role and index', () => {
    const item = {
      rule_id: 'LX0609-03-01-01',
      status: 'compliant',
      is_compliant: true,
      customer_display_facts: {
        recommendation_evidence: [
          {
            recommendation_index: 2,
            opinion_evidence: [safeRef('consultation_record', 'src_aaaaaaaaaaaaaaaaaaaaaaaa')],
            execution_evidence: [safeRef('daily_course_record', 'src_bbbbbbbbbbbbbbbbbbbbbbbb')],
          },
        ],
      },
    }

    expect(buildRecommendationEvidence(item, 'issue')).toMatchObject([
      {
        source_ref: 'src_aaaaaaaaaaaaaaaaaaaaaaaa',
        recommendation_index: 2,
        evidence_role: 'opinion',
      },
      {
        source_ref: 'src_bbbbbbbbbbbbbbbbbbbbbbbb',
        recommendation_index: 2,
        evidence_role: 'execution',
      },
    ])
  })

  it('ignores raw document ids and deduplicates identical safe references', () => {
    const item = {
      rule_id: 'LX0609-03-01-01',
      status: 'non_compliant',
      is_compliant: false,
      customer_display_facts: {
        recommendation_evidence: [
          {
            recommendation_index: 1,
            opinion_evidence: [
              { source_type: 'consultation_record', source_document_id: 'raw-1' },
              safeRef('consultation_record', 'src_aaaaaaaaaaaaaaaaaaaaaaaa'),
              safeRef('consultation_record', 'src_aaaaaaaaaaaaaaaaaaaaaaaa'),
            ],
            execution_evidence: [],
          },
        ],
      },
    }

    const result = buildRecommendationEvidence(item, 'issue')
    expect(result).toHaveLength(1)
    expect(result[0].source_ref).toBe('src_aaaaaaaaaaaaaaaaaaaaaaaa')
    expect(result[0]).not.toHaveProperty('source_document_id')
  })

  it('keeps the existing six-item UI cap after flattening', () => {
    const item = {
      rule_id: 'LX0609-03-01-01',
      status: 'non_compliant',
      record_id: 'visit-1',
      customer_display_facts: {
        recommendation_evidence: Array.from({ length: 4 }, (_, index) => ({
          recommendation_index: index + 1,
          opinion_evidence: [
            safeRef('consultation_record', `src_${String(index + 1).padStart(24, 'a')}`),
          ],
          execution_evidence: [
            safeRef('daily_course_record', `src_${String(index + 1).padStart(24, 'b')}`),
          ],
        })),
      },
    }

    const [issue] = buildRecordComparisonIssues({ items: [item] } as never, { recordId: 'visit-1' })
    expect(issue.evidences).toHaveLength(6)
    expect(issue.evidences.every((evidence) => evidence.source_ref?.startsWith('src_'))).toBe(true)
  })

  it('keeps legacy top-level evidence when no nested recommendation facts exist', () => {
    const [issue] = buildRecordComparisonIssues(
      {
        items: [
          {
            rule_id: 'LX0609-03-01-01',
            status: 'non_compliant',
            record_id: 'visit-1',
            evidence: [safeRef('consultation_record', 'src_aaaaaaaaaaaaaaaaaaaaaaaa')],
          },
        ],
      } as never,
      { recordId: 'visit-1' },
    )
    expect(issue.evidences).toHaveLength(1)
    expect(issue.evidences[0].evidence_role).toBeUndefined()
  })
})
