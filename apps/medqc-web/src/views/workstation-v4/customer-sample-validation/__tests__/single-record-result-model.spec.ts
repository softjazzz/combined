import { describe, expect, it } from 'vitest'

import {
  buildConsultationRecommendationPresentation,
  buildSingleRecordQcPresentation,
  recommendationEvidenceForSingleRecord,
} from '../single-record-result-model'

describe('consultation recommendation presentation', () => {
  it('separates compared recommendations from undefined conditional recommendations', () => {
    const presentation = buildConsultationRecommendationPresentation({
      rule_id: 'LX0609-03-01-04',
      customer_display_facts: {
        recommendation_evidence: [
          {
            episode_index: 1,
            recommendation_index: 1,
            recommendation_text: '完善血脂检查',
            execution_state: 'missing',
          },
          {
            episode_index: 1,
            recommendation_index: 2,
            recommendation_text: '给予调脂治疗',
            execution_state: 'generic',
          },
          {
            episode_index: 2,
            recommendation_index: 1,
            recommendation_text: '复查血常规',
            execution_state: 'specific',
          },
        ],
        excluded_recommendations: [
          {
            episode_index: 1,
            recommendation_text: '必要时完善TCD检查',
            exclusion_reason: 'execution_condition_not_defined',
          },
        ],
      },
    })

    expect(presentation).not.toBeNull()
    expect(presentation?.comparedCount).toBe(3)
    expect(presentation?.excludedCount).toBe(1)
    expect(presentation?.rows).toMatchObject([
      {
        text: '完善血脂检查',
        state: 'missing',
        statusLabel: '未找到执行证据',
      },
      {
        text: '给予调脂治疗',
        state: 'generic',
        statusLabel: '执行记录不具体',
      },
      {
        text: '复查血常规',
        state: 'specific',
        statusLabel: '已找到具体执行证据',
      },
      {
        text: '必要时完善TCD检查',
        state: 'excluded',
        statusLabel: '未纳入核对',
      },
    ])
    expect(presentation?.checkedSources).toEqual([
      '后续病程记录',
      '上级医师查房记录',
      '住院医嘱',
      '相关检查、检验及手术记录',
    ])
  })

  it('does not create the structured block for unrelated or incomplete facts', () => {
    expect(
      buildConsultationRecommendationPresentation({
        rule_id: 'LX0609-03-01-03',
        customer_display_facts: {},
      }),
    ).toBeNull()
    expect(
      buildConsultationRecommendationPresentation({
        rule_id: 'LX0609-03-01-04',
        customer_display_facts: {
          excluded_recommendations: [
            {
              episode_index: 1,
              recommendation_text: '必要时完善TCD检查',
              exclusion_reason: 'uncontrolled_reason',
            },
          ],
        },
      }),
    ).toBeNull()
  })
})

describe('single-record recommendation evidence', () => {
  it('exposes signed nested refs with recommendation metadata', () => {
    const result = recommendationEvidenceForSingleRecord({
      rule_id: 'LX0609-03-01-01',
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
      rule_id: 'LX0609-03-01-01',
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
      rule_id: 'LX0609-03-01-01',
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

describe('grouped result presentation tabs', () => {
  it('keeps compliant and not-applicable rules in separate report sections', () => {
    const presentation = buildSingleRecordQcPresentation([
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录规则',
        status: 'compliant',
        source_document: '入院记录',
      },
      {
        rule_id: 'LX0609-01-02-01',
        rule_name: '手术记录规则',
        status: 'not_applicable',
        source_document: '手术记录',
      },
      {
        rule_id: 'LX0609-04-02-01',
        rule_name: '会诊记录规则',
        status: 'data_gap',
        source_document: '会诊记录',
      },
    ])

    expect(presentation.counts.compliant).toBe(1)
    expect(presentation.counts.notApplicable).toBe(1)
    expect(presentation.sectionsByTab.compliant).toHaveLength(1)
    expect(presentation.sectionsByTab.not_applicable).toHaveLength(1)
    expect(presentation.sectionsByTab.compliant[0].items[0].rule_id).toBe('LX0609-01-01-01')
    expect(presentation.sectionsByTab.not_applicable[0].items[0].rule_id).toBe('LX0609-01-02-01')
  })
})
