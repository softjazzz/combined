import { describe, expect, it } from 'vitest'

import {
  getSubitemAnchorDisplayLabel,
  mapSichuanEvaluationToStructuredQC,
  shouldCountSubitemAnchorAsDefect,
} from '../structuredQc'

describe('formal qc subitem anchors mapping', () => {
  it('保留顶层 subitem_anchor_results 字段且不计入问题数', () => {
    const result = mapSichuanEvaluationToStructuredQC({
      evaluation_summary: {
        total_rules: 84,
        issues_found: 1,
        uncertain_count: 1,
      },
      evaluation_results: [
        {
          rule_id: 'SC-070',
          rule_name: '会诊记录质量',
          status: 'uncertain',
          findings: '会诊意见落实需复核。',
          metadata: {
            subitem_anchors: [
              {
                anchor_id: 'SC-070-consultation-not-implemented',
                subitem_name: '会诊意见落实与医嘱/执行闭环',
                display_status: 'needs_review',
                display_bucket: '待复核',
                can_show_as_defect: false,
              },
            ],
          },
        },
      ],
      subitem_anchor_results: [
        {
          parent_rule_id: 'SC-070',
          anchor_id: 'SC-070-consultation-not-implemented',
          subitem_id: 'SC-070-consultation-not-implemented',
          subitem_name: '会诊意见落实与医嘱/执行闭环',
          anchor_evidence_status: 'consultation_and_execution_evidence_needs_review',
          anchor_evidence: '会诊意见建议康复治疗；医嘱/执行闭环待人工复核。',
          anchor_decision_reason: '找到会诊意见及执行/病程相关片段，是否未落实需人工核对。',
          display_status: 'needs_review',
          display_bucket: '待复核',
          can_show_as_defect: false,
          internal_only: false,
        },
      ],
    })

    expect(result.overview.totalRules).toBe(84)
    expect(result.overview.issueCount).toBe(1)
    expect(result.subitemAnchors).toHaveLength(1)
    expect(result.subitemAnchors[0].anchorId).toBe('SC-070-consultation-not-implemented')
    expect(result.issues[0].metadata.subitemAnchors).toHaveLength(1)
    expect(result.issues[0].metadata.subitemAnchors[0].subitemName).toBe(
      '会诊意见落实与医嘱/执行闭环',
    )
  })

  it('子锚点显示为待复核或数据缺口，且不作为确认缺陷计数', () => {
    const result = mapSichuanEvaluationToStructuredQC({
      evaluation_results: [],
      subitem_anchor_results: [
        {
          parent_rule_id: 'SC-036',
          anchor_id: 'SC-036-abnormal-result-unaddressed',
          subitem_name: '异常检查检验结果后续病程分析处理',
          display_status: 'data_quality_gap',
          can_show_as_defect: true,
        },
      ],
    })

    expect(result.subitemAnchors).toHaveLength(1)
    expect(getSubitemAnchorDisplayLabel(result.subitemAnchors[0])).toBe('数据缺口')
    expect(shouldCountSubitemAnchorAsDefect(result.subitemAnchors[0])).toBe(false)
  })

  it('子锚点字段缺失时保持兼容默认值', () => {
    const result = mapSichuanEvaluationToStructuredQC({
      evaluation_results: [
        {
          rule_id: 'SC-009',
          rule_name: '现病史记录',
          status: 'uncertain',
          metadata: {
            subitem_anchors: [{}],
          },
        },
      ],
    })

    expect(result.subitemAnchors).toHaveLength(0)
    expect(result.issues[0].metadata.subitemAnchors).toHaveLength(0)
  })
})
