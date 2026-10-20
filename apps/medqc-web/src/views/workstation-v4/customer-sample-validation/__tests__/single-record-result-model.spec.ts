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
        statusLabel: '未执行',
      },
      {
        text: '给予调脂治疗',
        state: 'generic',
        statusLabel: '执行医嘱不具体',
      },
      {
        text: '复查血常规',
        state: 'specific',
        statusLabel: '已执行',
      },
      {
        text: '必要时完善TCD检查',
        state: 'excluded',
        statusLabel: '未纳入核对',
      },
    ])
    expect(presentation?.checkedSources).toEqual([
      '会诊记录前3天至当天开立的住院药品医嘱',
      '会诊记录前3天至当天开立的住院非药品医嘱（“继续/维持”原治疗的建议也认此前已开立的医嘱）',
    ])
  })

  it('names consultation time, measures without orders and why recommendations were not checked', () => {
    const presentation = buildConsultationRecommendationPresentation({
      rule_id: 'LX0609-03-01-04',
      customer_display_facts: {
        recommendation_evidence: [
          {
            episode_index: 1,
            recommendation_index: 1,
            recommendation_text: '完善血气分析、乳酸、心衰指标',
            execution_state: 'specific',
            opinion_time: '2026-08-24 15:07:30',
            missing_measures: ['乳酸', '心衰指标'],
          },
          {
            episode_index: 2,
            recommendation_index: 2,
            recommendation_text: '复查凝血功能',
            execution_state: 'missing',
            opinion_time: '2026-01-26',
          },
        ],
        excluded_recommendations: [
          {
            episode_index: 1,
            recommendation_text: '卧床休息',
            exclusion_reason: 'non_order_recommendation',
          },
          {
            episode_index: 1,
            recommendation_text: '继续服用原降压药',
            exclusion_reason: 'home_medication',
          },
          {
            episode_index: 2,
            recommendation_text: '若病情加重可转科',
            exclusion_reason: 'condition_not_met',
          },
        ],
      },
    })

    expect(presentation?.rows).toMatchObject([
      {
        state: 'partial',
        opinionTime: '2026-08-24 15:07',
        statusLabel: '部分措施未执行',
        detail: '会诊记录前3天至当天未开立以下措施的医嘱：乳酸、心衰指标',
      },
      {
        state: 'missing',
        opinionTime: '2026-01-26',
        detail: '会诊记录前3天至当天未开立与建议对应的医嘱',
      },
      {
        state: 'excluded',
        detail: '卧床、体位、饮食营养、护理宣教等建议不通过开立医嘱落实，不核对',
      },
      { state: 'excluded', detail: '院外自带药建议不核对' },
      { state: 'excluded', detail: '条件式建议在核对期间未开立对应医嘱，视为条件未成立，不核对' },
    ])
  })

  it('names the consultation date and the measures declined in the consultation record', () => {
    const presentation = buildConsultationRecommendationPresentation({
      rule_id: 'LX0609-03-01-04',
      customer_display_facts: {
        recommendation_evidence: [
          {
            episode_index: 1,
            recommendation_index: 1,
            recommendation_text: '诱导痰XPERT检测、真菌G/GM试验；若均阴性则行气管镜检查',
            execution_state: 'missing',
            opinion_time: '2026-10-07 20:16:04',
            window_start_date: '2026-10-05',
            declined_measures: ['纤支镜检查'],
          },
        ],
        excluded_recommendations: [
          {
            episode_index: 1,
            recommendation_text: '建议行胃镜检查',
            exclusion_reason: 'declined_in_record',
          },
        ],
      },
    })

    expect(presentation?.rows).toMatchObject([
      {
        state: 'missing',
        windowStartDate: '2026-10-05',
        opinionTime: '2026-10-07 20:16',
        declinedMeasures: ['纤支镜检查'],
        detail:
          '会诊记录前3天至当天未开立与建议对应的医嘱；会诊记录写明不执行：纤支镜检查，该项不核对',
      },
      { state: 'excluded', detail: '会诊记录写明患者或家属拒绝、或暂缓执行，不核对' },
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
