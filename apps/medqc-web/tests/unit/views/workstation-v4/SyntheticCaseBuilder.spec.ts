import { describe, expect, it } from 'vitest'
import {
  buildSyntheticCaseRunPayload,
  createDefaultSyntheticCaseForm,
  createGoldenAnswer,
  createSyntheticDocument,
  normalizeSyntheticCasePayload,
} from '@/views/workstation-v4/customer-sample-validation/syntheticCaseBuilder'
import {
  syntheticCaseRuleFamilies,
  syntheticCaseTemplates,
} from '@/views/workstation-v4/customer-sample-validation/syntheticCaseTemplates'

describe('SyntheticCaseBuilder 按质控点创建', () => {
  it('覆盖泸县0609主要规则族并为每个规则族提供模板', () => {
    const familyNames = syntheticCaseRuleFamilies.map((family) => family.name)

    expect(familyNames).toEqual(
      expect.arrayContaining([
        '基础时限',
        '查房病程',
        '检查检验',
        '会诊质量',
        '手术麻醉',
        '输血',
        '肿瘤病理',
      ]),
    )

    const templateKeys = new Set(syntheticCaseTemplates.map((template) => template.key))
    syntheticCaseRuleFamilies.forEach((family) => {
      expect(templateKeys.has(family.templateKey)).toBe(true)
      expect(family.rules.length).toBeGreaterThan(0)
    })
  })

  it('每条可选 LX0609 规则都能找到对应模板和 golden answer', () => {
    const templateByKey = new Map(
      syntheticCaseTemplates.map((template) => [template.key, template]),
    )

    syntheticCaseRuleFamilies.forEach((family) => {
      const template = templateByKey.get(family.templateKey)
      expect(template?.documents.length).toBeGreaterThan(0)

      family.rules.forEach((rule) => {
        expect(rule.ruleId).toMatch(/^LX0609-\d{3}$/u)
        expect(template?.suggestedRuleIds).toContain(rule.ruleId)
        expect(template?.goldenAnswers.some((answer) => answer.qc_point_id === rule.ruleId)).toBe(
          true,
        )
      })
    })
  })

  it('保存 payload 保留所选质控点和 golden answer，且过滤停用文书', () => {
    const form = createDefaultSyntheticCaseForm()
    form.caseTitle = '会诊质量测试'
    form.selectedRuleIds = ['LX0609-020', 'LX0609-021']
    form.goldenAnswers = [
      createGoldenAnswer({
        qc_point_id: 'lx0609-020',
        expected_status: 'non_compliant',
        trigger_facts: ['会诊意见已出具', '病程未记录执行情况'],
        evidence_keywords: ['会诊记录单', '未记录执行情况'],
      }),
    ]
    form.documents = [
      createSyntheticDocument('consultation_record', {
        title: '会诊记录单',
        content: '会诊意见：建议完善相关检查，必要时调整用药。',
        enabled: true,
      }),
      createSyntheticDocument('daily_course_record', {
        title: '停用病程',
        content: '这份文书不应写入 payload。',
        enabled: false,
      }),
    ]

    const payload = normalizeSyntheticCasePayload(form)

    expect(payload.selected_rule_ids).toEqual(['LX0609-020', 'LX0609-021'])
    expect(payload.golden_answers).toHaveLength(1)
    expect(payload.golden_answers?.[0]?.qc_point_id).toBe('LX0609-020')
    expect(payload.documents).toHaveLength(1)
    expect(payload.documents[0]?.document_type).toBe('consultation_record')
  })

  it('保存并验证 payload 只请求选中的 LX0609 质控点', () => {
    const form = createDefaultSyntheticCaseForm()
    form.selectedRuleIds = ['lx0609-020', 'LX0609-021', 'LX0609-020']

    const payload = buildSyntheticCaseRunPayload(form, 'VISIT-SCOPE-001')

    expect(payload).toMatchObject({
      rule_set_key: 'luxian_0609_qc_v1',
      validation_mode: 'customer',
      record_ids: ['VISIT-SCOPE-001'],
      max_parallel_records: 1,
    })
    expect(payload.selected_rule_ids).toEqual(['LX0609-020', 'LX0609-021'])
  })
})
