import { describe, expect, it } from 'vitest'
import { buildCustomerQcDisplayModel } from '@/views/workstation-v4/semantic-rules/customer-qc-display-model'

describe('customerQcDisplayModel', () => {
  it('读取客户安全 DTO 顶层受控事实，不再退回通用占位文案', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-018',
      status: 'non_compliant',
      reason_code: 'requirement_violated',
      customer_display_facts: {
        complaint_length: 24,
        length_state: 'violated',
        diagnostic_relation_state: 'supported',
        diagnostic_reason_dimensions: ['anatomic_site', 'symptom_pattern'],
        diagnostic_rationale_code: 'supported',
        primary_diagnosis_available: true,
        source_label: '入院记录—主诉',
      },
    })

    expect(model).toMatchObject({
      isEnhanced: true,
      conclusion: '主诉超过20字上限；诊断指向子项通过。',
      actualValue: expect.stringContaining('实际值：24字'),
      evidenceSource: '入院记录—主诉',
    })
    expect(model.detail).toContain('诊断指向子项通过')
    expect(model.detail).toContain('医学判断：主诉中的部位、症状特征或病程信息能够支持第一诊断')
    expect(model.conclusion).not.toBe('发现该质控点对应的明确问题。')
  })

  it('将 LX0609-018 的长度缺陷转换为可直接给质控员阅读的明细', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-018',
      status: 'non_compliant',
      reason_code: 'threshold_exceeded',
      findings: '规则要求未满足。',
      metadata: {
        customer_display_facts: {
          complaint_length: 28,
          primary_diagnosis_available: true,
          source_label: '入院记录—主诉',
        },
      },
    })

    expect(model.conclusion).toBe('主诉超过20字上限；诊断指向子项待确认。')
    expect(model.isEnhanced).toBe(true)
    expect(model.detail).toContain('主诉共28字，超过20字上限')
    expect(model.detail).toContain('诊断指向性：本次语义核对未形成可靠子结论')
    expect(model.requirement).toBe(
      '主诉应不超过20字；同时应能从主诉的部位、症状特征、病程等信息导出第一诊断。',
    )
    expect(model.actualValue).toContain('实际值：28字')
    expect(model.actualValue).toContain('第一诊断：已找到')
    expect(model.evidenceSource).toBe('入院记录—主诉')
    expect(model.suggestion).toContain('针对未通过的子项精简或修正主诉')
  })

  it('在来源不足时不伪造实际值，并给出可理解的缺口说明', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-018',
      status: 'data_gap',
      reason_code: 'complaint_or_primary_diagnosis_unavailable',
    })

    expect(model.conclusion).toBe('现有资料不足，暂不能判断主诉是否可导出第一诊断。')
    expect(model.isEnhanced).toBe(true)
    expect(model.detail).toBe('未取得可用于核对的主诉或第一诊断。')
    expect(model.actualValue).toBe('')
    expect(model.evidenceSource).toBe('')
  })

  it('将 018 受控语义原因映射为客户可理解的结论，不展示模型原文', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-018',
      status: 'non_compliant',
      reason_code: 'course_customer_prompt',
      metadata: {
        customer_display_facts: {
          complaint_length: 28,
          primary_diagnosis_available: true,
          source_label: '入院记录—主诉',
          failure_kind: 'complaint_primary_diagnosis_mismatch',
        },
      },
    })

    expect(model.isEnhanced).toBe(true)
    expect(model.conclusion).toBe('主诉超过20字上限；诊断指向子项未通过。')
    expect(model.detail).toContain('主诉与第一诊断在部位、侧别或症状特征上不一致')
    expect(model.actualValue).toContain('实际值：28字')
    expect(model.actualValue).toContain('诊断指向：与第一诊断不一致')
  })

  it('对未建设专用展示合同的规则保留安全的原始客户结论', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-029',
      status: 'non_compliant',
      findings: '术前小结未记录。',
      suggestion: '请补充术前小结。',
    })

    expect(model.conclusion).toBe('术前小结未记录。')
    expect(model.isEnhanced).toBe(false)
    expect(model.suggestion).toBe('请补充术前小结。')
  })

  it('将 025 的缺失字段直接说明为本次手术记录未记录的内容', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-025',
      status: 'non_compliant',
      customer_display_facts: {
        missing_fields: ['implant_barcode', 'implant_quantity'],
        source_label: '手术记录',
      },
    })

    expect(model.conclusion).toBe(
      '已确认本次手术使用植入物；手术记录未记录：条码/批号、数量（共2项）。',
    )
    expect(model.detail).toContain('本次不合规的直接原因')
    expect(model.suggestion).toBe('请在本次手术记录中补录植入物条码/批号、数量。')
  })

  it('将 016 的复制判定显示为客户可复核的百分比', () => {
    const model = buildCustomerQcDisplayModel({
      rule_id: 'LX0609-016',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'admission_first_course_copy_detected',
        copy_similarity: 1,
        copy_similarity_threshold: 0.7,
      },
    })

    expect(model).toMatchObject({
      isEnhanced: true,
      conclusion: '入院记录现病史与首次病程记录病例特点相似度为100%，超过70%判定阈值。',
      actualValue: '相似度：100%；判定阈值：70%；超出阈值：30个百分点。',
    })
  })
})
