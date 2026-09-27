import { describe, expect, it } from 'vitest'

import {
  hasActionableCustomerExplanation,
  normalizeCustomerQcResult,
} from '@/domain/customer-qc/result-normalizer'

describe('normalizeCustomerQcResult', () => {
  it.each([
    ['LX0609-001', 'LX0609-01-01-01'],
    ['LX0609-01-01-01', 'LX0609-001'],
    ['LX0609-01-01-01', 'LX0609-01-02-01'],
    ['LX0609-01-00-01', 'LX0609-01-00-01'],
  ])('不把冲突身份归到任一规则：%s / %s', (rule_id, rule_code) => {
    expect(normalizeCustomerQcResult({ rule_id, rule_code, status: 'compliant' }).ruleId).toBe('UNKNOWN')
  })

  it('旧三位泸县编号被拒绝，不在结果主链中静默保留', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-001',
      rule_code: 'LX0609-001',
      status: 'non_compliant',
      reason_code: 'requirement_violated',
    })

    expect(result.ruleId).toBe('UNKNOWN')
  })

  it('安全 DTO 直接复用后端受控解释，页面不再维护第二套质控结论', () => {
    const result = normalizeCustomerQcResult({
      schema_version: 'customer-qc-result-v1',
      explanation_contract_version: 'lx0609-customer-explanation-v1',
      rule_id: 'LX0609-01-01-01',
      status: 'non_compliant',
      reason_code: 'deadline_exceeded',
      conclusion: 'LX0609-01-01-01：入院记录完成时间超过24小时。',
      detail: '入院记录未在规定时限内完成。',
      requirement: 'LX0609-01-01-01：入院记录应在入院后24小时内完成。',
      suggestion: '请及时完成入院记录并核对记录时间。',
      findings: 'PRIVATE_RAW_FINDING_MUST_NOT_WIN',
    })

    expect(result.display).toMatchObject({
      summary: 'LX0609-01-01-01：入院记录完成时间超过24小时。',
      detail: '入院记录未在规定时限内完成。',
      requirement: 'LX0609-01-01-01：入院记录应在入院后24小时内完成。',
      suggestion: '请及时完成入院记录并核对记录时间。',
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_RAW_FINDING_MUST_NOT_WIN')
  })

  it('缺少解释合同版本时保留执行器状态并隐藏伪造文案', () => {
    const result = normalizeCustomerQcResult({
      schema_version: 'customer-qc-result-v1',
      rule_id: 'LX0609-01-01-01',
      status: 'non_compliant',
      reason_code: 'threshold_exceeded',
      conclusion: 'PRIVATE_UNTRUSTED_CONCLUSION',
      detail: 'PRIVATE_UNTRUSTED_DETAIL',
      requirement: 'PRIVATE_UNTRUSTED_REQUIREMENT',
      suggestion: 'PRIVATE_UNTRUSTED_SUGGESTION',
    })

    expect(result.decisionStatus).toBe('non_compliant')
    expect(result.display.summary).not.toBe('PRIVATE_UNTRUSTED_CONCLUSION')
    expect(JSON.stringify(result)).not.toContain('PRIVATE_UNTRUSTED')
    expect(result.display.summary).toBe('执行器已判定发现质控问题，但当前客户解释资料不完整。')
    expect(result.display.detail).toContain('未提供可展示的具体原因')
    expect(result.display.detail).toContain('结果状态保持为不合规')
  })

  it('通用不合规占位文案不能通过客户可解释质量门', () => {
    const raw = {
      rule_id: 'LX0609-04-01-03',
      status: 'non_compliant',
      reason_code: 'requirement_violated',
      conclusion: '发现该质控点对应的明确问题。',
      suggestion: '请按质控要求补充或修正。',
    }

    expect(hasActionableCustomerExplanation(raw)).toBe(false)
    const result = normalizeCustomerQcResult(raw)
    expect(result.decisionStatus).toBe('non_compliant')
    expect(result.display).toMatchObject({
      summary: '执行器已判定发现质控问题，但当前客户解释资料不完整。',
      requirement: '不合规结果应同时提供规则专属原因、核对标准、实际情况及可定位证据。',
    })
    expect(JSON.stringify(result)).not.toContain('发现该质控点对应的明确问题')
  })

  it('75 条 LX0609 规则缺少可核对事实时均保留状态且不回退泛化文案', () => {
    const results = Array.from({ length: 75 }, (_, index) =>
      normalizeCustomerQcResult({
        rule_id: `LX0609-${String(index + 1).padStart(2, '0')}-01-01`,
        status: 'non_compliant',
        reason_code: 'requirement_violated',
      }),
    )

    for (const result of results) {
      expect(result.decisionStatus).toBe('non_compliant')
      expect(result.display.summary).toBe('执行器已判定发现质控问题，但当前客户解释资料不完整。')
      expect(JSON.stringify(result)).not.toContain('发现该质控点对应的明确问题')
    }
  })

  it('将 LX0609-01-01-02 的受控事实转换为客户可读明细，而不携带主诉正文', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-01-01-02',
      status: 'non_compliant',
      reason_code: 'complaint_too_long',
      criterion_results: [
        {
          criterion_id: 'chief_complaint_length',
          kind: 'text_length',
          status: 'failed',
          reason_code: 'complaint_too_long',
          actual_value: 28,
          expected_value: 20,
          operator: 'lte',
          unit: 'character',
          source_fact: 'admission_record.chief_complaint',
        },
        {
          criterion_id: 'diagnostic_direction',
          kind: 'semantic_relation',
          status: 'passed',
          reason_code: 'requirement_satisfied',
          actual_value: 'supported',
          left_fact: 'admission_record.chief_complaint',
          right_fact: 'admission_record.first_diagnosis',
          dimensions: ['anatomic_site', 'symptom_pattern'],
          medical_analysis: '主诉中的症状与第一诊断方向一致。',
        },
      ],
      metadata: {
        medical_text: '主诉：腹痛2天。',
        raw_response: '{"is_compliant":false}',
      },
      evidence_payload: { primary_document_text: '主诉：腹痛2天。' },
    })

    expect(result).toMatchObject({
      ruleId: 'LX0609-01-01-02',
      decisionStatus: 'non_compliant',
      evidenceAvailability: 'available',
      display: {
        summary: '主诉超过20字上限；诊断指向子项通过。',
        detail:
          '1. 主诉书写规范性：主诉共28字，超过20字上限。\n2. 诊断指向性：主诉与第一诊断的解剖部位、症状特征能够对应，诊断指向子项通过。\n\nAI医学分析：主诉中的症状与第一诊断方向一致。',
        actualValue: '实际值：28字；标准：不超过20字；诊断指向：诊断指向子项通过。',
        evidenceSources: [
          {
            label: '入院记录—主诉',
            kind: 'admission_record',
            fieldPath: 'chief_complaint',
          },
        ],
      },
    })
    expect(JSON.stringify(result)).not.toContain('腹痛2天')
    expect(JSON.stringify(result)).not.toContain('raw_response')
    expect(JSON.stringify(result)).not.toContain('medical_text')
    expect(JSON.stringify(result)).not.toContain('evidence_payload')
  })

  it('完整展示后端 018 双子结论、实际字数和核对标准', () => {
    const result = normalizeCustomerQcResult({
      schema_version: 'customer-qc-result-v1',
      explanation_contract_version: 'lx0609-customer-explanation-v1',
      rule_id: 'LX0609-01-01-02',
      status: 'non_compliant',
      reason_code: 'complaint_too_long',
      conclusion:
        '入院记录“主诉”字段共28字，超过20字上限。主诉与第一诊断的对应关系判断通过，本次仅因主诉过长判定不合规。',
      detail:
        '本项按两个独立子项完成核对：\n1. 主诉书写规范性：主诉长度为28字，超过20字上限。\n2. 诊断指向性：基于本次可用的主诉材料与第一诊断完成对应关系判断；两者诊断方向一致，诊断指向子项通过。\n综合判定：诊断指向子项通过，本次仅因主诉过长判定不合规。',
      requirement: 'LX0609-01-01-02：主诉应能导出第一诊断，且主诉长度应不超过20字。',
      suggestion: '请精简主诉并保留诊断指向信息，确保与第一诊断一致。',
      criterion_results: [
        {
          criterion_id: 'chief_complaint_length',
          kind: 'text_length',
          status: 'failed',
          reason_code: 'complaint_too_long',
          actual_value: 28,
          expected_value: 20,
          operator: 'lte',
          unit: 'character',
          source_fact: 'admission_record.chief_complaint',
        },
        {
          criterion_id: 'diagnostic_direction',
          kind: 'semantic_relation',
          status: 'passed',
          reason_code: 'requirement_satisfied',
          actual_value: 'supported',
          left_fact: 'admission_record.chief_complaint',
          right_fact: 'admission_record.first_diagnosis',
          dimensions: ['anatomic_site', 'symptom_pattern'],
          medical_analysis: '主诉中的症状与第一诊断方向一致。',
        },
      ],
    })

    expect(result.display).toMatchObject({
      summary: '主诉超过20字上限；诊断指向子项通过。',
      detail:
        '1. 主诉书写规范性：主诉共28字，超过20字上限。\n2. 诊断指向性：主诉与第一诊断的解剖部位、症状特征能够对应，诊断指向子项通过。\n\nAI医学分析：主诉中的症状与第一诊断方向一致。',
      actualValue: '实际值：28字；标准：不超过20字；诊断指向：诊断指向子项通过。',
      evidenceSources: [
        {
          label: '入院记录—主诉',
          kind: 'admission_record',
          fieldPath: 'chief_complaint',
        },
      ],
    })
  })

  it('缺少字段级事实时，不把 LX0609-04-02-04 旧结果展示为确定问题', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-02-04',
      status: 'non_compliant',
      reason_code: 'implant_information_incomplete',
      findings: '手术记录中存在原文片段，不得返回给客户展示模型。',
    })

    expect(result).toMatchObject({
      ruleId: 'LX0609-04-02-04',
      decisionStatus: 'non_compliant',
      display: {
        summary: '执行器已判定发现质控问题，但当前客户解释资料不完整。',
      },
    })
    expect(result.display.actualValue).toBeUndefined()
    expect(JSON.stringify(result)).not.toContain('原文片段')
  })

  it('为 LX0609-04-02-04 展示受控字段级缺项，不回显手术原文', () => {
    const raw = {
      rule_id: 'LX0609-04-02-04',
      status: 'non_compliant',
      reason_code: 'requirement_violated',
      customer_display_facts: {
        failure_kind: 'implant_information_incomplete',
        performed_surgery_confirmed: true,
        missing_fields: ['implant_material', 'implant_quantity'],
        implant_event_details: [
          {
            event_position: 1,
            missing_fields: ['implant_material'],
            implant_names: ['人工硬脑膜'],
          },
          {
            event_position: 2,
            missing_fields: ['implant_quantity'],
            implant_names: ['钛网'],
          },
        ],
        source_label: '手术记录',
        source_document_type: 'surgery_record',
      },
      findings: 'PRIVATE_SURGERY_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary:
        '已确认使用永久性植入物；第1台手术（人工硬脑膜）缺少材质；第2台手术（钛网）缺少数量。',
      detail:
        '逐台核对结果：第1台手术（人工硬脑膜）缺少材质；第2台手术（钛网）缺少数量。本次共缺少材质、数量。',
      actualValue: '第1台手术（人工硬脑膜）缺失：材质；第2台手术（钛网）缺失：数量。',
      evidenceSources: [{ kind: 'surgery_record', label: '手术记录' }],
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_SURGERY_TEXT')
    expect(JSON.stringify(result)).not.toContain('barcode')
    expect(JSON.stringify(result)).not.toContain('条码')
  })

  it('规则专属事实优先于通用受控解释，避免明确缺项被泛化文案覆盖', () => {
    const result = normalizeCustomerQcResult({
      schema_version: 'customer-qc-result-v1',
      explanation_contract_version: 'lx0609-customer-explanation-v1',
      rule_id: 'LX0609-04-02-04',
      status: 'non_compliant',
      conclusion: '发现该质控点对应的明确问题。',
      detail: '受控证据表明本次记录未满足质控要求。',
      requirement: '请核对。',
      suggestion: '请按质控要求补充或修正。',
      customer_display_facts: {
        failure_kind: 'implant_information_incomplete',
        performed_surgery_confirmed: true,
        missing_fields: ['implant_material'],
        implant_event_details: [
          {
            event_position: 1,
            missing_fields: ['implant_material'],
            implant_names: ['人工硬脑膜'],
          },
        ],
        source_label: '手术记录',
        source_document_type: 'surgery_record',
      },
    })

    expect(result.display.summary).toBe('已确认使用永久性植入物；第1台手术（人工硬脑膜）缺少材质。')
    expect(result.display.detail).toContain('逐台核对结果')
  })

  it('025拒绝混入条码的旧字段清单，不对其余字段做部分交付', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-02-04',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'implant_information_incomplete',
        performed_surgery_confirmed: true,
        missing_fields: ['implant_material', 'implant_barcode'],
        implant_event_details: [
          {
            event_position: 1,
            missing_fields: ['implant_material'],
            implant_names: ['人工硬脑膜'],
          },
        ],
        source_label: '手术记录',
        source_document_type: 'surgery_record',
      },
    })

    expect(result.decisionStatus).toBe('non_compliant')
    expect(JSON.stringify(result)).not.toContain('条码')
  })

  it.each([
    {
      status: 'non_compliant',
      facts: {
        failure_kind: 'implant_information_incomplete',
        performed_surgery_confirmed: true,
        missing_fields: ['implant_material'],
        implant_event_details: [
          {
            event_position: 1,
            missing_fields: ['implant_material'],
            implant_names: ['人工硬脑膜'],
          },
        ],
        source_label: '病程记录',
        source_document_type: 'surgery_record',
      },
      forbidden: '第1台手术',
    },
    {
      status: 'non_compliant',
      facts: {
        failure_kind: 'implant_information_incomplete',
        performed_surgery_confirmed: true,
        missing_fields: ['implant_material'],
        implant_event_details: [
          {
            event_position: 1,
            missing_fields: ['implant_material'],
            implant_names: ['人工硬脑膜'],
          },
        ],
        source_label: '手术记录',
      },
      forbidden: '第1台手术',
    },
    {
      status: 'compliant',
      facts: {
        verification_kind: 'implant_information_complete',
        performed_surgery_confirmed: false,
        checked_fields: [
          'implant_name',
          'implant_type',
          'implant_specification',
          'implant_material',
          'implant_quantity',
        ],
        source_label: '手术记录',
        source_document_type: 'surgery_record',
      },
      forbidden: '名称、种类、规格/型号、材质、数量均已记录',
    },
    {
      status: 'compliant',
      facts: {
        verification_kind: 'implant_information_complete',
        checked_fields: [
          'implant_name',
          'implant_type',
          'implant_specification',
          'implant_material',
          'implant_quantity',
        ],
        source_label: '手术记录',
        source_document_type: 'surgery_record',
      },
      forbidden: '名称、种类、规格/型号、材质、数量均已记录',
    },
    {
      status: 'not_applicable',
      facts: {
        verification_kind: 'implant_not_used',
        performed_surgery_confirmed: true,
        source_label: '病程记录',
      },
      forbidden: '本次手术未使用植入物',
    },
    {
      status: 'not_applicable',
      facts: {
        verification_kind: 'implant_not_used',
        source_label: '手术记录',
      },
      forbidden: '本次手术未使用植入物',
    },
  ])('025不从不可信来源或未确认手术事实生成专属描述', ({ status, facts, forbidden }) => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-02-04',
      status,
      customer_display_facts: facts,
    })

    expect(JSON.stringify(result.display)).not.toContain(forbidden)
  })

  it('为已实施手术缺失目标文书展示确定性原因，不把来源不可用伪装为缺文书', () => {
    const raw = {
      rule_id: 'LX0609-04-02-02',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'surgery_document_missing',
        target_document: 'surgery_record',
        performed_surgery_confirmed: true,
      },
      findings: 'PRIVATE_SURGERY_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '已确认本次住院存在已实施手术；未找到手术记录。',
      detail:
        '本项仅核对手术记录是否存在且具有可用正文。未找到手术记录，因此不能满足本质控点的文书要求。',
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_SURGERY_TEXT')

    const unavailable = normalizeCustomerQcResult({
      ...raw,
      customer_display_facts: {
        failure_kind: 'source_unavailable',
        target_document: 'surgery_record',
        performed_surgery_confirmed: true,
      },
    })
    expect(unavailable.display.summary).not.toContain('未找到手术记录')
  })

  it('为 LX0609-12-01-02 展示两份被比较文书、记录时间和相似度，不透传正文', () => {
    const raw = {
      rule_id: 'LX0609-12-01-02',
      status: 'non_compliant',
      reason_code: 'threshold_exceeded',
      customer_display_facts: {
        failure_kind: 'copy_similarity_threshold_exceeded',
        copy_similarity: 0.83,
        copy_similarity_threshold: 0.7,
        copy_document_sources: ['daily_course_record', 'senior_course_record'],
        copy_document_record_times: ['2026-06-01 09:20:00', '2026-06-02 10:30:00'],
      },
      findings: 'PRIVATE_COURSE_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '以下两份病程文书相似度为83%，超过70%阈值。',
      detail:
        '对比文书：\n1. 日常病程记录（2026-06-01 09:20:00）\n2. 上级医师查房记录（2026-06-02 10:30:00）\n\n系统按相邻、不同日期的病程/查房记录进行全文相似度比较，本次命中阈值。',
      requirement: '相邻不同日期的病程/查房记录相似度不得超过70%。',
      suggestion: '请分别补充两次记录当日的病情变化、诊疗措施或疗效，避免机械复制。',
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_COURSE_TEXT')
  })

  it('为 LX0609-12-01-01 明确展示相似度、阈值和超出幅度', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-12-01-01',
      status: 'non_compliant',
      reason_code: 'requirement_violated',
      customer_display_facts: {
        failure_kind: 'admission_first_course_copy_detected',
        copy_similarity: 1,
        copy_similarity_threshold: 0.7,
        compared_sections: ['入院记录现病史', '首次病程记录病例特点'],
      },
    })

    expect(
      hasActionableCustomerExplanation({
        rule_id: 'LX0609-12-01-01',
        status: 'non_compliant',
        customer_display_facts: {
          copy_similarity: 1,
          copy_similarity_threshold: 0.7,
        },
      }),
    ).toBe(true)
    expect(result.display).toMatchObject({
      summary: '入院记录现病史与首次病程记录病例特点相似度为100%，超过70%判定阈值。',
      requirement: '上述两部分相似度超过70%时，判定为不合理复制病历。',
      actualValue: '相似度：100%；判定阈值：70%；超出阈值：30个百分点。',
    })
  })

  it('为 LX0609-02-01-03 展示权威时间区间，不透传病程正文', () => {
    const raw = {
      rule_id: 'LX0609-02-01-03',
      status: 'non_compliant',
      reason_code: 'threshold_exceeded',
      customer_display_facts: {
        failure_kind: 'course_record_interval_over_72h',
        interval_start_source: 'daily_course_record',
        interval_end_source: 'senior_course_record',
        interval_start_time: '2026-06-01 09:00:00',
        interval_end_time: '2026-06-04 10:00:00',
        interval_hours: 73,
        threshold_hours: 72,
      },
      findings: 'PRIVATE_COURSE_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '从2026-06-01 09:00:00至2026-06-04 10:00:00间隔73小时，超过72小时要求。',
      detail:
        '在已纳入核对的日常病程记录（2026-06-01 09:00:00）与上级医师查房记录（2026-06-04 10:00:00）之间，未见可计入本项的日常病程记录或上级医师查房记录。',
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_COURSE_TEXT')
  })

  it('为 LX0609-02-01-03 展示首尾边界，不把边界伪装成查房文书', () => {
    const startBoundary = normalizeCustomerQcResult({
      rule_id: 'LX0609-02-01-03',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'course_record_interval_over_72h',
        interval_start_source: 'inpat_registration',
        interval_end_source: 'senior_course_record',
        interval_start_time: '2026-08-14 08:00:00',
        interval_end_time: '2026-08-17 10:02:00',
        interval_hours: 74.03,
        threshold_hours: 72,
      },
    })
    const dateBoundary = normalizeCustomerQcResult({
      rule_id: 'LX0609-02-01-03',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'course_record_interval_over_72h',
        interval_start_source: 'daily_course_record',
        interval_end_source: 'evaluation_context.horizon',
        interval_start_time: '2026-08-14 09:30:00',
        interval_end_date: '2026-08-18',
        interval_end_precision: 'date',
        threshold_hours: 72,
      },
    })
    const preciseTailBoundary = normalizeCustomerQcResult({
      rule_id: 'LX0609-02-01-03',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'course_record_interval_over_72h',
        interval_start_source: 'daily_course_record',
        interval_end_source: 'evaluation_context.horizon',
        interval_start_time: '2026-08-14 09:30:00',
        interval_end_time: '2026-08-17 10:00:00',
        interval_hours: 72.5,
        threshold_hours: 72,
      },
    })
    const zeroRoundsDateBoundary = normalizeCustomerQcResult({
      rule_id: 'LX0609-02-01-03',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'course_record_interval_over_72h',
        interval_start_source: 'inpat_registration',
        interval_end_source: 'evaluation_context.horizon',
        interval_start_time: '2026-08-14 08:00:00',
        interval_end_date: '2026-08-18',
        interval_end_precision: 'date',
        threshold_hours: 72,
      },
    })

    expect(startBoundary.display).toMatchObject({
      summary:
        '权威入院时间（2026-08-14 08:00:00）至首次查房（2026-08-17 10:02:00）间隔74.03小时，超过72小时要求。',
      detail: '以权威入院时间为起点，首次查房前未见可计入本项的日常病程记录或上级医师查房记录。',
    })
    expect(dateBoundary.display).toMatchObject({
      summary:
        '最后一次查房（2026-08-14 09:30:00）至评价截止日期（2026-08-18）已确认超过72小时要求。',
      detail:
        '评价截止日期仅精确到日期；该日期已能确定最后一次查房后超过72小时仍未见可计入本项的后续记录。',
    })
    expect(preciseTailBoundary.display).toMatchObject({
      summary:
        '最后一次查房（2026-08-14 09:30:00）至评价截止时间（2026-08-17 10:00:00）间隔72.50小时，超过72小时要求。',
      detail: '以最后一次查房为起点，评价截止时间前未见可计入本项的后续记录。',
    })
    expect(zeroRoundsDateBoundary.display).toMatchObject({
      summary:
        '权威入院时间（2026-08-14 08:00:00）至评价截止日期（2026-08-18）已确认超过72小时要求；期间未见有效查房。',
      detail:
        '评价截止日期仅精确到日期；该日期已能确定入院后超过72小时仍未见可计入本项的查房记录。',
    })
  })

  it('为基础时限规则展示锚点、首个可计入记录和超时原因', () => {
    const raw = {
      rule_id: 'LX0609-02-01-02',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'timeliness_requirement_not_met',
        target_document: 'senior_course_record',
        timeliness_state: 'late',
        source_label: '副主任医师或主任医师首次查房记录',
        threshold_hours: 72,
        anchor_time: '2026-06-01 08:00:00',
        observed_time: '2026-06-04 10:00:00',
        elapsed_hours: 74,
      },
      findings: 'PRIVATE_COURSE_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary:
        '入院时间为2026-06-01 08:00:00；首次可计入的副主任医师或主任医师首次查房记录时间为2026-06-04 10:00:00，间隔74小时，超过72小时要求。',
      requirement: '入院后72小时内应完成副主任医师或主任医师首次查房记录。',
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_COURSE_TEXT')
  })

  it('为缺失的基础时限目标文书说明缺失边界，不伪造时间', () => {
    const raw = {
      rule_id: 'LX0609-01-02-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'timeliness_requirement_not_met',
        target_document: 'first_course_record',
        timeliness_state: 'missing',
        source_label: '首次病程记录',
        threshold_hours: 8,
      },
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display.summary).toBe('以入院时间为锚点核对后，未找到可计入本项的首次病程记录。')
    expect(result.display.detail).toContain('未找到满足文书类型与角色要求的记录')
  })

  it('为抢救记录展示抢救结束到记录形成的实际超时区间', () => {
    const raw = {
      rule_id: 'LX0609-09-01-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'timeliness_requirement_not_met',
        target_document: 'rescue_record',
        timeliness_state: 'late',
        source_label: '抢救记录',
        threshold_hours: 6,
        anchor_time: '2026-06-01 09:00:00',
        observed_time: '2026-06-01 16:15:00',
        elapsed_hours: 7.25,
      },
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary:
        '抢救结束时间为2026-06-01 09:00:00；抢救记录形成于2026-06-01 16:15:00，间隔7.25小时，超过6小时要求。',
      requirement: '抢救结束后6小时内应完成抢救记录。',
    })
  })

  it('为 LX0609-04-02-01 展示权威手术结束时间、文书时间和超时区间', () => {
    const raw = {
      rule_id: 'LX0609-04-02-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'surgery_record_late',
        performed_surgery_confirmed: true,
        surgery_end_time: '2026-06-01 08:00:00',
        record_time: '2026-06-02 10:30:00',
        elapsed_hours: 26.5,
        threshold_hours: 24,
      },
      findings: 'PRIVATE_SURGERY_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary:
        '本次手术于2026-06-01 08:00:00结束；手术记录形成于2026-06-02 10:30:00，间隔26.50小时，超过术后24小时要求。',
      requirement: '手术记录应在手术结束后24小时内完成。',
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_SURGERY_TEXT')
  })

  it('为 LX0609-11-01-01 区分同意书缺失与来源未证明，避免将资料不足报成缺陷', () => {
    const missing = {
      rule_id: 'LX0609-11-01-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'surgery_consent_document_missing',
        consent_state: 'missing',
        performed_surgery_confirmed: true,
      },
    }
    const unproven = {
      rule_id: 'LX0609-11-01-01',
      status: 'data_gap',
      customer_display_facts: {
        failure_kind: 'surgery_consent_source_unproven',
        consent_state: 'source_unproven',
        performed_surgery_confirmed: true,
      },
    }

    expect(hasActionableCustomerExplanation(missing)).toBe(true)
    expect(normalizeCustomerQcResult(missing).display.summary).toContain('未找到对应文书')
    expect(hasActionableCustomerExplanation(unproven)).toBe(true)
    expect(normalizeCustomerQcResult(unproven).display.summary).toContain('来源完整性未获证明')
  })

  it('为 008/009 展示超期区间或缺失日期，而不透传病程正文', () => {
    const seriousGap = {
      rule_id: 'LX0609-02-01-04',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'severity_course_gap_exceeded',
        severity: 'serious',
        anchor_date: '2026-06-01',
        horizon_date: '2026-06-04',
        gap_start_date: '2026-06-01',
        gap_end_date: '2026-06-04',
        gap_days: 3,
        threshold_days: 2,
      },
      findings: 'PRIVATE_COURSE_TEXT',
    }
    const criticalGap = {
      rule_id: 'LX0609-02-01-05',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'critical_daily_record_missing',
        severity: 'critical',
        anchor_date: '2026-06-01',
        horizon_date: '2026-06-03',
        missing_dates: ['2026-06-02'],
        missing_count: 1,
        missing_first_date: '2026-06-02',
        missing_last_date: '2026-06-02',
      },
      findings: 'PRIVATE_COURSE_TEXT',
    }

    expect(hasActionableCustomerExplanation(seriousGap)).toBe(true)
    expect(normalizeCustomerQcResult(seriousGap).display.summary).toContain(
      '2026-06-01至2026-06-04间隔3个自然日',
    )
    expect(hasActionableCustomerExplanation(criticalGap)).toBe(true)
    expect(normalizeCustomerQcResult(criticalGap).display.detail).toContain('缺失日期：2026-06-02')
    expect(JSON.stringify(normalizeCustomerQcResult(criticalGap))).not.toContain(
      'PRIVATE_COURSE_TEXT',
    )
  })

  it('为 LX0609-06-02-02 展示已核对来源与取材记录缺口，不透传原文', () => {
    const raw = {
      rule_id: 'LX0609-06-02-02',
      status: 'non_compliant',
      reason_code: 'pathology_sampling_not_documented',
      customer_display_facts: {
        failure_kind: 'pathology_sampling_not_documented',
        pathology_trigger_sources: ['pathology_exam_master'],
        checked_target_sources: [
          { source: 'surgery_record', state: 'present' },
          { source: 'daily_course_record', state: 'empty' },
        ],
      },
      findings: 'PRIVATE_PATHOLOGY_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '病理相关来源已触发本项核对；在目标文书中未检出取材、送检或标本处理的已实施记录。',
      detail: expect.stringContaining(
        '触发来源：病理检查主表。已核对：手术记录（已核对）、日常病程记录（无可用文书）。',
      ),
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_PATHOLOGY_TEXT')
  })

  it('为 LX0609-04-02-03 展示恶性手术门控与已核对的淋巴结清扫来源', () => {
    const raw = {
      rule_id: 'LX0609-04-02-03',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'lymph_node_dissection_not_documented',
        performed_surgery_confirmed: true,
        malignant_surgery_confirmed: true,
        checked_sources: ['surgery_record', 'pathology_exam_report'],
      },
      findings: 'PRIVATE_LYMPH_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '已确认本次为恶性肿瘤手术；已核对的手术相关文书未记录淋巴结清扫情况。',
      detail: expect.stringContaining('已核对：手术记录、病理检查报告'),
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_LYMPH_TEXT')
  })

  it('为 LX0609-05-01-01 展示实际预防用药时长与缺少延长理由', () => {
    const raw = {
      rule_id: 'LX0609-05-01-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'prophylaxis_extension_reason_missing',
        incision_class: 'I',
        start_time: '2026-01-01 08:00:00',
        end_time: '2026-01-02 14:00:00',
        duration_hours: 30,
        threshold_hours: 24,
      },
      findings: 'PRIVATE_PROPHYLAXIS_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary:
        'Ⅰ/Ⅱ类切口预防用药2026-01-01 08:00:00至2026-01-02 14:00:00，共30小时，超过24小时；未记录延长用药理由。',
      detail: expect.stringContaining('实际给药与实际停药'),
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_PROPHYLAXIS_TEXT')
  })

  it('为麻醉/术前文书缺失展示已确认事件与具体缺失文书', () => {
    const consent = normalizeCustomerQcResult({
      rule_id: 'LX0609-11-02-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'anesthesia_consent_missing',
        performed_anesthesia_confirmed: true,
        consent_state: 'missing',
        checked_sources: ['consent_form'],
      },
    })
    const visits = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-04-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'anesthesia_visit_missing',
        performed_anesthesia_confirmed: true,
        missing_visit_sources: ['preane_surveil_record', 'postane_surveil_record'],
      },
    })
    const discussion = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-01-02',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'preop_discussion_missing',
        performed_surgery_confirmed: true,
        emergency_rescue_exception_absent: true,
        checked_sources: ['presurg_discussion'],
      },
    })

    expect(consent.display.summary).toBe('已确认本次实施麻醉；未检出麻醉知情同意书。')
    expect(visits.display.summary).toContain('麻醉术前访视记录、麻醉术后访视记录')
    expect(discussion.display.summary).toContain('未检出术前讨论记录')
  })

  it('为检查检验原生不合规展示触发事件、缺少记录与已核对来源', () => {
    const raw = {
      rule_id: 'LX0609-06-01-04',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'exam_lab_requirement_not_documented',
        subject: 'ct_mri',
        requirement: 'result_recording_within_24h',
        event_phase: 'report',
        checked_sources: ['exam_lab_report', 'course_record'],
      },
      findings: 'PRIVATE_EXAM_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '已确认本次住院存在CT/MRI检查报告；未在报告后24小时内检出结果记录。',
      detail: expect.stringContaining(
        '已核对来源：检查/检验报告、日常病程记录及上级医师查房记录。',
      ),
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_EXAM_TEXT')
  })

  it('为输血原生不合规展示具体缺口与已核对来源', () => {
    const raw = {
      rule_id: 'LX0609-07-04-01',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'transfusion_requirement_not_documented',
        requirement: 'postop_first_course_transfusion',
        checked_sources: ['surgery_record', 'postsurg_firstcourse_record'],
      },
      findings: 'PRIVATE_TRANSFUSION_TEXT',
    }
    const result = normalizeCustomerQcResult(raw)

    expect(hasActionableCustomerExplanation(raw)).toBe(true)
    expect(result.display).toMatchObject({
      summary: '手术记录已明确术中输血；术后首次病程记录未提及输血事实。',
      detail: expect.stringContaining('已核对来源：手术记录、术后首次病程记录。'),
    })
    expect(JSON.stringify(result)).not.toContain('PRIVATE_TRANSFUSION_TEXT')
  })

  it('缺少细分原因码时保留 LX0609-04-02-04 状态并使用安全提示', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-02-04',
      status: 'non_compliant',
      reason_code: 'reason_unavailable',
    })

    expect(result.decisionStatus).toBe('non_compliant')
    expect(result.display.summary).toContain('执行器已判定发现质控问题')
  })

  it('将通用 data_gap 与临床结论分离，并给出安全的补充资料说明', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-11-01-01',
      status: 'data_gap',
      evidence_problem_type: 'source_unavailable',
      suggestion: '不要透传这条内部建议。',
    })

    expect(result).toMatchObject({
      decisionStatus: 'data_gap',
      evidenceAvailability: 'unavailable',
      display: {
        summary: '现有受控数据不足以形成确定结论。',
        suggestion: '请补充或同步所需数据后重新评估。',
      },
    })
    expect(JSON.stringify(result)).not.toContain('不要透传')
  })

  it('将 AI 建议态保留为 evaluation_unknown，不能混入最终不合规', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-03-01-02',
      status: 'ai_suggested_non_compliant',
    })

    expect(result.decisionStatus).toBe('evaluation_unknown')
    expect(result.display.summary).toBe('该结果需要人工复核后确认。')
  })

  it('忽略空 result_status 并原样保留后续状态；无事实时使用安全提示', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-01-01-02',
      result_status: '',
      status: 'non_compliant',
      reason_code: 'complaint_too_short',
    })

    expect(result.decisionStatus).toBe('non_compliant')
  })

  it('展示手术记录24小时内完成的实际时间事实', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-02-01',
      status: 'compliant',
      customer_display_facts: {
        failure_kind: 'surgery_record_within_threshold',
        performed_surgery_confirmed: true,
        surgery_end_time: '2026-07-30 10:00:00',
        record_time: '2026-07-30 12:30:00',
        elapsed_hours: 2.5,
        threshold_hours: 24,
        source_label: '手术记录',
      },
    })

    expect(result.display.summary).toContain('间隔2.50小时，未超过术后24小时要求')
  })

  it('为手术安全核查表合规结果说明已找到目标文书', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-03-01',
      status: 'compliant',
      customer_display_facts: {
        verification_kind: 'surgery_document_present',
        target_document: 'surgery_safecheck_record',
        performed_surgery_confirmed: true,
      },
    })

    expect(result.display.summary).toContain('已找到可用的手术安全核查记录')
  })

  it('为麻醉同意书列出具体缺失签名和分钟级时间', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-11-02-02',
      status: 'non_compliant',
      customer_display_facts: {
        failure_kind: 'anesthesia_consent_incomplete',
        performed_anesthesia_confirmed: true,
        missing_fields: ['physician_signature', 'physician_signature_time'],
      },
    })

    expect(result.display.summary).toContain('医师签名、医师签署时间（精确到分钟）')
  })

  it('说明第一助手书写但术者签名的031例外', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-02-05',
      status: 'compliant',
      customer_display_facts: {
        verification_kind: 'surgery_signature_confirmed',
        performed_surgery_confirmed: true,
        surgeon_signature_matches: true,
        first_assistant_exception_used: true,
      },
    })

    expect(result.display.summary).toBe('手术记录由第一助手书写，且已由本次手术术者签名确认。')
  })

  it('展示040的手术编码、院内优先分级和MDT结论', () => {
    const result = normalizeCustomerQcResult({
      rule_id: 'LX0609-04-01-03',
      status: 'compliant',
      customer_display_facts: {
        performed_surgery_confirmed: true,
        procedure_kind: 'surgery',
        procedure_code: '01.2408',
        procedure_name: '颅内血肿清除术',
        effective_surgery_level: '四级',
        surgery_level_source: 'hospital_performance',
        mdt_discussion_state: 'completed',
      },
    })

    expect(result.display.summary).toContain('01.2408 颅内血肿清除术')
    expect(result.display.summary).toContain('院内绩效分配目录')
    expect(result.display.summary).toContain('术前多学科讨论已完成')
  })
})
