import { describe, expect, it } from 'vitest'
import {
  buildSyntheticCaseRunPayload,
  buildRuleDrivenCaseTitle,
  buildSyntheticCaseRuleFamiliesFromCatalog,
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

  it('完整 0609 目录进入创建页时手术麻醉族应保留 16 条质控点', () => {
    const surgeryRuleIds = [
      'LX0609-003',
      'LX0609-024',
      'LX0609-025',
      'LX0609-028',
      'LX0609-029',
      'LX0609-030',
      'LX0609-031',
      'LX0609-032',
      'LX0609-033',
      'LX0609-034',
      'LX0609-035',
      'LX0609-036',
      'LX0609-037',
      'LX0609-038',
      'LX0609-039',
      'LX0609-040',
    ]
    const families = buildSyntheticCaseRuleFamiliesFromCatalog(
      surgeryRuleIds.map((ruleId) => ({
        rule_id: ruleId,
        rule_code: ruleId,
        name: `${ruleId} 手术麻醉质控点`,
        required_documents_label: '手术麻醉文书',
      })),
    )

    const surgery = families.find((family) => family.key === 'surgery_anesthesia')
    expect(surgery?.name).toBe('手术麻醉')
    expect(surgery?.templateKey).toBe('surgery-anesthesia-defect')
    expect(surgery?.rules.map((rule) => rule.ruleId)).toEqual(surgeryRuleIds)
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

  it('按质控点生成的测试病历名称应包含规则族、质控点和创建时间', () => {
    const title = buildRuleDrivenCaseTitle(
      ['会诊质量'],
      ['LX0609-021', 'lx0609-020', 'LX0609-020'],
      new Date('2026-06-23T15:30:00'),
    )

    expect(title).toBe('会诊质量质控病历｜LX020/021｜0623-1530')
    expect(title).not.toMatch(/测试患者|测试病历/u)
  })

  it('五组演示关键模板生成真实住院病历风格多文书', () => {
    const templateByKey = new Map(
      syntheticCaseTemplates.map((template) => [template.key, template]),
    )
    const forbiddenSelfHints =
      /测试患者|模拟患者|样例患者|模拟|为了测试|本条为反例|故意缺失|备注[:：].*缺陷/u

    const timeliness = templateByKey.get('basic-timeliness-defect')
    const admissionRecord = timeliness?.documents.find(
      (document) => document.document_type === 'admission_record',
    )

    expect(admissionRecord?.content.length).toBeGreaterThan(650)
    expect(admissionRecord?.content).toContain('主诉')
    expect(admissionRecord?.content).toContain('现病史')
    expect(admissionRecord?.content).toContain('既往史')
    expect(admissionRecord?.content).toContain('体格检查')
    expect(admissionRecord?.content).toContain('专科检查')
    expect(admissionRecord?.content).toContain('辅助检查')
    expect(admissionRecord?.content).toContain('初步诊断')
    expect(admissionRecord?.content).toContain('诊疗计划')
    expect(admissionRecord?.content).not.toMatch(forbiddenSelfHints)

    const consultation = templateByKey.get('consultation-quality-defect')
    expect(consultation?.documents.map((document) => document.document_type)).toEqual(
      expect.arrayContaining(['admission_record', 'consultation_record', 'daily_course_record']),
    )
    expect(
      consultation?.documents.some(
        (document) =>
          document.title === '会诊申请单' && document.content.includes('会诊目的：请会诊'),
      ),
    ).toBe(true)
    expect(
      consultation?.documents.some(
        (document) =>
          document.title === '会诊记录单' &&
          document.content.includes('建议完善相关检查，继续目前治疗，必要时调整用药'),
      ),
    ).toBe(true)
    consultation?.documents.forEach((document) => {
      expect(document.content.length).toBeGreaterThan(180)
      expect(document.content).not.toMatch(forbiddenSelfHints)
    })

    const examLab = templateByKey.get('ct-mri-culture-defect')
    expect(examLab?.documents.map((document) => document.document_type)).toEqual(
      expect.arrayContaining([
        'admission_record',
        'exam_report',
        'lab_report',
        'daily_course_record',
      ]),
    )
    const examAdmission = examLab?.documents.find(
      (document) => document.document_type === 'admission_record',
    )
    const mriReport = examLab?.documents.find((document) => document.title === '腰椎MRI检查报告')
    const cultureReport = examLab?.documents.find((document) => document.title === '尿培养报告')
    const firstCourse = examLab?.documents.find(
      (document) => document.title === '2026-06-01 日常病程记录',
    )
    const secondCourse = examLab?.documents.find(
      (document) => document.title === '2026-06-03 日常病程记录',
    )
    expect(examAdmission?.content.length).toBeGreaterThan(650)
    expect(examAdmission?.content).toContain('主诉')
    expect(examAdmission?.content).toContain('现病史')
    expect(examAdmission?.content).toContain('专科检查')
    expect(examAdmission?.content).toContain('诊疗计划')
    expect(mriReport?.content).toContain('L4/5椎间盘突出并右侧神经根受压')
    expect(mriReport?.content).toContain('建议结合患者右下肢放射痛')
    expect(cultureReport?.content).toContain('大肠埃希菌生长')
    expect(cultureReport?.content).toContain('左氧氟沙星：耐药')
    expect(firstCourse?.content).toContain('已完善腰椎MRI检查')
    expect(firstCourse?.content).toContain('继续予塞来昔布镇痛、甲钴胺营养神经')
    expect(secondCourse?.content).toContain('偶有尿频')
    expect(secondCourse?.content).toContain('暂维持现有处理')
    examLab?.documents.forEach((document) => {
      expect(document.content.length).toBeGreaterThan(180)
      expect(document.content).not.toMatch(forbiddenSelfHints)
    })

    const surgery = templateByKey.get('surgery-anesthesia-defect')
    expect(surgery?.documents.map((document) => document.document_type)).toEqual(
      expect.arrayContaining([
        'presurg_summary',
        'presurg_discussion',
        'surgery_record',
        'anesthesia_record',
        'daily_course_record',
      ]),
    )
    const surgeryRecord = surgery?.documents.find(
      (document) => document.document_type === 'surgery_record',
    )
    const anesthesiaRecord = surgery?.documents.find(
      (document) => document.document_type === 'anesthesia_record',
    )
    expect(surgeryRecord?.content).toContain('手术结束时间：2026-06-01 11:30')
    expect(surgeryRecord?.content).toContain('记录时间：2026-06-03 12:00')
    expect(anesthesiaRecord?.content).toContain('麻醉方式：')
    expect(anesthesiaRecord?.content).toContain('麻醉医师代码：')
    expect(anesthesiaRecord?.content).toContain('出室评分：未填写')
    surgery?.documents.forEach((document) => {
      expect(document.content.length).toBeGreaterThan(180)
      expect(document.content).not.toMatch(forbiddenSelfHints)
    })

    const criticalRounds = templateByKey.get('critical-round-defect')
    expect(criticalRounds?.documents.map((document) => document.document_type)).toEqual(
      expect.arrayContaining([
        'medical_order',
        'first_course_record',
        'daily_course_record',
        'senior_course_record',
      ]),
    )
    expect(
      criticalRounds?.documents.some((document) =>
        document.content.includes('2026-06-02 09:00 患者氧合较前下降'),
      ),
    ).toBe(true)
    expect(
      criticalRounds?.documents.some((document) =>
        document.content.includes('未形成每日病危病程记录'),
      ),
    ).toBe(true)
    criticalRounds?.documents.forEach((document) => {
      expect(document.content.length).toBeGreaterThan(180)
      expect(document.content).not.toMatch(forbiddenSelfHints)
    })

    const transfusion = templateByKey.get('transfusion-defect')
    expect(transfusion?.documents.map((document) => document.document_type)).toEqual(
      expect.arrayContaining([
        'admission_record',
        'medical_order',
        'blood_application',
        'daily_course_record',
        'bloodtrans_record',
      ]),
    )
    expect(transfusion?.documents.length).toBeGreaterThanOrEqual(6)
    const transfusionAdmission = transfusion?.documents.find(
      (document) => document.document_type === 'admission_record',
    )
    const bloodApplication = transfusion?.documents.find(
      (document) => document.document_type === 'blood_application',
    )
    const transfusionOrder = transfusion?.documents.find(
      (document) => document.document_type === 'medical_order',
    )
    const transfusionRecord = transfusion?.documents.find(
      (document) => document.document_type === 'bloodtrans_record',
    )
    const beforeTransfusionCourse = transfusion?.documents.find(
      (document) => document.title === '输血前病程记录',
    )
    const afterTransfusionCourse = transfusion?.documents.find(
      (document) => document.title === '输血后病程记录',
    )
    expect(transfusionAdmission?.content.length).toBeGreaterThan(650)
    expect(transfusionAdmission?.content).toContain('主诉')
    expect(transfusionAdmission?.content).toContain('现病史')
    expect(transfusionAdmission?.content).toContain('输血相关风险')
    expect(bloodApplication?.content).toContain('输血前检查摘要')
    expect(bloodApplication?.content).toContain('未见丙肝抗体、HIV抗体、梅毒抗体完整报告')
    expect(bloodApplication?.content).toContain('未检索到本次输血治疗知情同意书')
    expect(beforeTransfusionCourse?.content).toContain('未见本次输血知情同意书')
    expect(beforeTransfusionCourse?.content).toContain('完整输血风险告知记录')
    expect(transfusionOrder?.content).toContain('费用明细摘要')
    expect(transfusionOrder?.content).toContain('去白悬浮红细胞4U')
    expect(transfusionRecord?.content).toContain('血袋号')
    expect(transfusionRecord?.content).toContain('输血前核对')
    expect(afterTransfusionCourse?.content).toContain('未记录输血后血红蛋白复查结果')
    transfusion?.documents.forEach((document) => {
      expect(document.content.length).toBeGreaterThan(180)
      expect(document.content).not.toMatch(forbiddenSelfHints)
    })

    const tumor = templateByKey.get('tumor-pathology-chemo-defect')
    expect(tumor?.documents.map((document) => document.document_type)).toEqual(
      expect.arrayContaining([
        'admission_record',
        'surgery_record',
        'lab_report',
        'daily_course_record',
        'medical_order',
      ]),
    )
    expect(tumor?.documents.length).toBeGreaterThanOrEqual(6)
    const tumorAdmission = tumor?.documents.find(
      (document) => document.document_type === 'admission_record',
    )
    const tumorSurgery = tumor?.documents.find(
      (document) => document.document_type === 'surgery_record',
    )
    const tumorPathology = tumor?.documents.find((document) => document.title === '病理检查报告')
    const tumorChemoCourse = tumor?.documents.find(
      (document) => document.title === '化疗前病程记录',
    )
    expect(tumorAdmission?.content.length).toBeGreaterThan(650)
    expect(tumorAdmission?.content).toContain('主诉')
    expect(tumorAdmission?.content).toContain('现病史')
    expect(tumorAdmission?.content).toContain('体格检查')
    expect(tumorAdmission?.content).toContain('诊疗计划')
    expect(tumorSurgery?.content).toContain('标本处理')
    expect(tumorSurgery?.content).toContain('未逐项标明近端切缘、远端切缘、肿瘤部位')
    expect(tumorPathology?.content).toContain('中分化腺癌')
    expect(tumorChemoCourse?.content).toContain('今日准备开始辅助化疗')
    expect(tumorChemoCourse?.content).not.toContain('奥沙利铂 130mg')
    tumor?.documents.forEach((document) => {
      expect(document.content.length).toBeGreaterThan(180)
      expect(document.content).not.toMatch(forbiddenSelfHints)
    })
  })
})
