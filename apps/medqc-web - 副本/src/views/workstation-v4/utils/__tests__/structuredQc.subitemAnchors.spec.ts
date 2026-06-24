import { describe, expect, it } from 'vitest'

import {
  getSubitemAnchorDisplayLabel,
  mapBatchJobToStructuredQC,
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

  it('正式质控在线任务优先使用后处理统计和展示字段', () => {
    const result = mapBatchJobToStructuredQC(
      {
        id: 'job-1',
        status: 'completed',
        rule_code: 'FORMAL-FAST-SCREEN-FULL',
        rule_name: '正式质控 84 条',
        scene: 'final',
        scope: 'final',
        created_at: '',
        updated_at: '',
        total_records: 1,
        success_count: 1,
        failed_count: 0,
        issue_records: 0,
        compliant_records: 1,
        total_tokens: 0,
        total_processing_time: 0,
        summary: {
          total_records: 1,
          success_count: 1,
          failed_count: 0,
          issue_records: 0,
          compliant_records: 1,
          total_tokens: 0,
          total_processing_time: 0,
          rule_count: 84,
          rule_set_key: 'sc_content_full_v1',
          confirmed_defect_count: 0,
          qc_review_candidate_count: 0,
          needs_review_count: 0,
          data_quality_gap_count: 4,
          rejected_by_system_count: 5,
          technical_error_internal_count: 0,
          postprocess_summary: {
            confirmed_defect_count: 0,
            qc_review_candidate_count: 0,
            needs_review_count: 0,
            data_quality_gap_count: 4,
            rejected_by_system_count: 5,
            technical_error_internal_count: 0,
          },
        },
        rule_results: [
          {
            rule_code: 'SC-036',
            rule_name: '病程记录异常结果处理',
            status: 'completed',
            items: [
              {
                rule_id: 'SC-036',
                rule_code: 'SC-036',
                rule_name: '病程记录异常结果处理',
                record_id: '2207717',
                status: 'non_compliant',
                is_compliant: false,
                findings: '病程记录了ALT异常及甲肝抗体阳性，并给出处理意见，合规。',
                evidence: '病程记录已有处理意见。',
                suggestion: '无需整改。',
                confidence: 0.72,
                display_status: 'rejected_by_system',
                display_bucket: '系统驳回',
                postprocess_label: 'evidence_insufficient',
                postprocess_reason: '状态和结论自相矛盾，系统驳回。',
                can_show_as_defect: false,
                can_show_to_doctor: false,
                internal_only: true,
                postprocess_mode: 'formal_final_online',
              },
            ],
          },
        ],
      },
      null,
    )

    expect(result.overview.issueCount).toBe(0)
    expect(result.overview.uncertainCount).toBe(0)
    expect(result.issues[0].status).toBe('non_compliant')
    expect(result.issues[0].displayStatus).toBe('rejected_by_system')
    expect(result.issues[0].canShowAsDefect).toBe(false)
    expect(result.issues[0].postprocessMode).toBe('formal_final_online')
  })
})
