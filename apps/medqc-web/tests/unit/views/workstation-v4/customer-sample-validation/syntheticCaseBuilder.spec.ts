import { describe, expect, it } from 'vitest'
import {
  buildSyntheticCaseRuleFamiliesFromCatalog,
  createDefaultSyntheticCaseForm,
  createSyntheticDocument,
  findForbiddenSelfHints,
  resolveSyntheticCaseRuleFamilyKey,
} from '@/views/workstation-v4/customer-sample-validation/syntheticCaseBuilder'

describe('syntheticCaseBuilder (P1-12)', () => {
  it('将 course_quality / exam_lab 规则族键与后端目录对齐，并双向兼容别名', () => {
    const families = buildSyntheticCaseRuleFamiliesFromCatalog([
      {
        rule_id: 'LX0609-02-01-04',
        name: '病重患者2天内无查房病程记录',
        required_documents_label: '病程记录',
      },
      {
        rule_id: 'LX0609-06-01-05',
        name: 'CT/MRI 阳性结果未分析',
        required_documents_label: '检查报告',
      },
    ])

    expect(families.map((family) => family.key)).toEqual(['course_quality', 'exam_lab'])
    expect(resolveSyntheticCaseRuleFamilyKey('course_quality', families)).toBe('course_quality')
    expect(resolveSyntheticCaseRuleFamilyKey('critical_rounds', families)).toBe('course_quality')
    expect(resolveSyntheticCaseRuleFamilyKey('exam_lab', families)).toBe('exam_lab')
    expect(resolveSyntheticCaseRuleFamilyKey('ct_mri_culture', families)).toBe('exam_lab')
  })

  it('保留后端目录中超出内置列表的新增 LX0609 规则到“其他”族', () => {
    const families = buildSyntheticCaseRuleFamiliesFromCatalog([
      {
        rule_id: 'LX0609-01-01-01',
        name: '入院记录24小时时限',
        required_documents_label: '入院记录',
      },
      {
        rule_id: 'LX0609-15-01-01',
        name: '新增扩展质控点',
        required_documents_label: '护理记录',
      },
    ])

    const otherFamily = families.find((family) => family.key === 'other')
    expect(otherFamily).toBeDefined()
    expect(otherFamily?.name).toBe('其他')
    expect(otherFamily?.templateKey).toBeTruthy()
    expect(otherFamily?.rules).toEqual([
      {
        ruleId: 'LX0609-15-01-01',
        name: '新增扩展质控点',
        requiredDocumentsLabel: '护理记录',
      },
    ])
  })

  it('findForbiddenSelfHints 跳过已停用文书，仅检查已启用文书', () => {
    const form = createDefaultSyntheticCaseForm()
    form.documents = [
      createSyntheticDocument('admission_record', {
        title: '启用入院记录',
        content: '正常病历内容。',
        enabled: true,
      }),
      createSyntheticDocument('daily_course_record', {
        title: '已停用病程',
        content: '这里缺失诊断依据（停用文书不应拦保存）。',
        enabled: false,
      }),
    ]
    expect(findForbiddenSelfHints(form)).toEqual([])

    form.documents[0].content = '故意缺失检查结果'
    expect(findForbiddenSelfHints(form)).toEqual(['启用入院记录'])
  })
})
