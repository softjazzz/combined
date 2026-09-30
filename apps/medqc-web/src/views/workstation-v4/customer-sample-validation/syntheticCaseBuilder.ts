import type {
  ManualLuxian0609RuleCatalogItem,
  ManualTestRecordCreateRequest,
  SyntheticCaseBuilderMode,
  SyntheticCaseGoldenAnswer,
  SyntheticCaseRuleFamily,
  TestRecordDocumentForm,
  TestRecordForm,
} from './types'

export const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'

export const sexOptions = [
  { label: '男', value: '男' },
  { label: '女', value: '女' },
]

export const testRecordDocumentTypeOptions = [
  { label: '入院记录', value: 'admission_record' },
  { label: '首次病程记录', value: 'first_course_record' },
  { label: '日常病程记录', value: 'daily_course_record' },
  { label: '上级医师查房记录', value: 'senior_course_record' },
  { label: '抢救记录', value: 'rescue_record' },
  { label: '会诊记录', value: 'consultation_record' },
  { label: '出院记录', value: 'discharge_record' },
  { label: '术前小结', value: 'presurg_summary' },
  { label: '术前讨论', value: 'presurg_discussion' },
  { label: '手术记录', value: 'surgery_record' },
  { label: '手术安全核查', value: 'surgery_safecheck_record' },
  { label: '手术知情同意', value: 'surgery_inform_consent' },
  { label: '麻醉记录', value: 'anesthesia_record' },
  { label: '检查报告', value: 'exam_report' },
  { label: '检验报告', value: 'lab_report' },
  { label: '医嘱记录', value: 'medical_order' },
  { label: '输血申请', value: 'blood_application' },
  { label: '输血记录', value: 'bloodtrans_record' },
  { label: '其他文书', value: 'other' },
]

export const expectedStatusOptions = [
  { label: '有缺陷', value: 'non_compliant' },
  { label: '无缺陷', value: 'compliant' },
  { label: '不适用', value: 'not_applicable' },
  { label: '数据不足', value: 'data_gap' },
  { label: '需质控确认', value: 'uncertain' },
]

export const syntheticCaseBuilderModeOptions: Array<{
  label: string
  value: SyntheticCaseBuilderMode
}> = [
  { label: '按病历创建', value: 'case' },
  { label: '按质控点创建', value: 'rule' },
]

const LUXIAN_0609_SYNTHETIC_RULE_FAMILY_DEFINITIONS = [
  {
    key: 'basic_timeliness',
    name: '基础时限',
    description: '覆盖入院记录、首次病程、抢救记录和上级医师首次查房时限。',
    templateKey: 'basic-timeliness-defect',
    ruleIds: ['LX0609-01-01-01', 'LX0609-01-02-01', 'LX0609-09-01-01', 'LX0609-02-01-01', 'LX0609-02-01-02'],
  },
  {
    key: 'critical_rounds',
    name: '查房病程',
    description: '覆盖查房频次、病程复制、主诉和诊断依据等病程质量问题。',
    templateKey: 'critical-round-defect',
    ruleIds: ['LX0609-02-01-03', 'LX0609-02-01-04', 'LX0609-02-01-05', 'LX0609-12-01-01', 'LX0609-12-01-02', 'LX0609-01-01-02'],
  },
  {
    key: 'ct_mri_culture',
    name: '检查检验',
    description: '覆盖 CT/MRI、细菌培养结果记录与阳性结果分析。',
    templateKey: 'ct-mri-culture-defect',
    ruleIds: ['LX0609-06-01-02', 'LX0609-06-01-04', 'LX0609-06-01-05', 'LX0609-06-03-03', 'LX0609-06-03-04'],
  },
  {
    key: 'consultation_quality',
    name: '会诊质量',
    description: '覆盖会诊目的、会诊意见和会诊执行记录。',
    templateKey: 'consultation-quality-defect',
    ruleIds: ['LX0609-03-01-01', 'LX0609-03-01-02', 'LX0609-03-01-03', 'LX0609-03-01-04'],
  },
  {
    key: 'surgery_anesthesia',
    name: '手术麻醉',
    description: '覆盖手术记录、术前小结、知情同意、核查表、麻醉记录和术前讨论。',
    templateKey: 'surgery-anesthesia-defect',
    ruleIds: [
      'LX0609-04-02-01',
      'LX0609-04-02-03',
      'LX0609-04-02-04',
      'LX0609-05-01-01',
      'LX0609-04-01-01',
      'LX0609-04-02-02',
      'LX0609-04-02-05',
      'LX0609-04-03-01',
      'LX0609-11-01-01',
      'LX0609-11-02-01',
      'LX0609-11-02-02',
      'LX0609-04-04-01',
      'LX0609-04-04-02',
      'LX0609-04-04-03',
      'LX0609-04-01-02',
      'LX0609-04-01-03',
    ],
  },
  {
    key: 'transfusion',
    name: '输血',
    description: '覆盖输血知情同意、输血前检查、输血前后评价和医嘱收费一致性。',
    templateKey: 'transfusion-defect',
    ruleIds: [
      'LX0609-11-03-01',
      'LX0609-11-03-02',
      'LX0609-07-01-01',
      'LX0609-07-01-02',
      'LX0609-07-02-01',
      'LX0609-07-02-02',
      'LX0609-07-03-01',
      'LX0609-07-04-01',
      'LX0609-07-04-02',
    ],
  },
  {
    key: 'tumor_pathology',
    name: '肿瘤病理',
    description: '覆盖病理结果、取材情况、化疗记录和肿瘤出院治疗计划。',
    templateKey: 'tumor-pathology-chemo-defect',
    ruleIds: ['LX0609-06-02-03', 'LX0609-06-02-02', 'LX0609-05-02-01', 'LX0609-08-01-04'],
  },
] as const

export function buildSyntheticCaseRuleFamiliesFromCatalog(
  rules: ManualLuxian0609RuleCatalogItem[],
): SyntheticCaseRuleFamily[] {
  const ruleById = new Map<string, ManualLuxian0609RuleCatalogItem>()
  rules.forEach((rule) => {
    const ruleId = String(rule.rule_id || rule.rule_code || '')
      .trim()
      .toUpperCase()
    if (/^LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}$/u.test(ruleId)) {
      ruleById.set(ruleId, rule)
    }
  })
  return LUXIAN_0609_SYNTHETIC_RULE_FAMILY_DEFINITIONS.map((family) => ({
    key: family.key,
    name: family.name,
    description: family.description,
    templateKey: family.templateKey,
    rules: family.ruleIds
      .map((ruleId) => {
        const rule = ruleById.get(ruleId)
        if (!rule) return null
        const requiredDocumentsLabel =
          rule.required_documents_label ||
          (Array.isArray(rule.applicable_document_labels)
            ? rule.applicable_document_labels.join('、')
            : '')
        return {
          ruleId,
          name: String(rule.name || rule.description || ruleId).trim() || ruleId,
          requiredDocumentsLabel: String(requiredDocumentsLabel || '病历文书').trim(),
        }
      })
      .filter((rule): rule is SyntheticCaseRuleFamily['rules'][number] => Boolean(rule)),
  })).filter((family) => family.rules.length > 0)
}

export function toDateTimeLocal(value: Date): string {
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`
}

export function normalizeDateTimeLocal(value: string): string | undefined {
  const text = String(value || '').trim()
  if (!text) return undefined
  return text.length === 16 ? `${text}:00` : text
}

export function documentTypeLabel(value: string): string {
  return testRecordDocumentTypeOptions.find((item) => item.value === value)?.label || '其他文书'
}

export function buildDocumentKey(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function createSyntheticDocument(
  type = 'daily_course_record',
  overrides: Partial<TestRecordDocumentForm> = {},
): TestRecordDocumentForm {
  const label = documentTypeLabel(type)
  const nowText = toDateTimeLocal(new Date())
  const content = String(overrides.content ?? '')
  return {
    key: buildDocumentKey(),
    document_type: type,
    title: label,
    record_time: nowText,
    submit_time: nowText,
    content,
    doctor_name: '测试医师',
    doctor_code: '',
    enabled: true,
    ...overrides,
    originalContent: String(overrides.originalContent ?? content),
    appliedContent: String(overrides.appliedContent ?? content),
  }
}

export function createDefaultSyntheticCaseForm(): TestRecordForm {
  const now = new Date()
  const admission = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000)
  const firstCourse = new Date(admission.getTime() + 4 * 60 * 60 * 1000)
  return {
    builderMode: 'rule',
    caseTitle: '客户自建质控测试病历',
    patientName: '李某某',
    sex: '男',
    age: 56,
    mrNo: '',
    department: '普通外科',
    admissionTime: toDateTimeLocal(admission),
    dischargeTime: toDateTimeLocal(now),
    mainDiagnosis: '',
    otherDiagnosesText: '',
    manualIssueText: '',
    templateKey: '',
    selectedRuleFamilyKey: '',
    selectedRuleIds: [],
    goldenAnswers: [],
    documents: [
      createSyntheticDocument('admission_record', {
        record_time: toDateTimeLocal(admission),
        submit_time: toDateTimeLocal(admission),
        content:
          '入院记录\n主诉：腹痛3小时。\n现病史：患者入院前无明显诱因出现腹痛，伴恶心，无呕血黑便。\n初步诊断：腹痛待查。',
      }),
      createSyntheticDocument('first_course_record', {
        record_time: toDateTimeLocal(firstCourse),
        submit_time: toDateTimeLocal(firstCourse),
        content:
          '首次病程记录\n病例特点：患者因腹痛入院，查体腹软，上腹压痛。\n诊疗计划：完善血常规、腹部影像检查，予对症处理。',
      }),
      createSyntheticDocument('daily_course_record', {
        content: '日常病程记录\n患者腹痛较前缓解，生命体征平稳，继续当前治疗方案。',
      }),
      createSyntheticDocument('discharge_record', {
        content:
          '出院记录\n诊疗经过：患者入院后完善检查并对症治疗，症状好转。\n出院医嘱：门诊随访，不适随诊。',
      }),
    ],
  }
}

export function buildRuleDrivenCaseTitle(
  ruleFamilyNames: string[],
  ruleIds: string[],
  now = new Date(),
): string {
  const families = ruleFamilyNames.map((item) => String(item || '').trim()).filter(Boolean)
  const normalizedRuleIds = normalizeRuleIds(ruleIds)
  const familyText = families.length ? families.join('、') : '泸县0609'
  const ruleText = normalizedRuleIds.map((ruleId) => ruleId.replace(/^LX0609-/u, '')).join('/')
  const pad = (input: number) => String(input).padStart(2, '0')
  const timeText = `${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
  return `${familyText}质控病历｜LX${ruleText || '全量'}｜${timeText}`
}

export function createGoldenAnswer(
  overrides: Partial<SyntheticCaseGoldenAnswer> = {},
): SyntheticCaseGoldenAnswer {
  return {
    id: buildDocumentKey(),
    qc_point_id: '',
    expected_status: 'non_compliant',
    trigger_facts: [],
    evidence_keywords: [],
    human_reason: '',
    ...overrides,
  }
}

export function splitLines(value: string): string[] {
  return String(value || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function normalizeSyntheticCasePayload(form: TestRecordForm): ManualTestRecordCreateRequest {
  const documents = form.documents
    .filter((document) => document.enabled && String(document.content || '').trim())
    .map((document) => ({
      document_type: document.document_type,
      title: String(document.title || documentTypeLabel(document.document_type)).trim(),
      record_time: normalizeDateTimeLocal(document.record_time || ''),
      submit_time: normalizeDateTimeLocal(document.submit_time || ''),
      content: String(document.content || '').trim(),
      doctor_name: String(document.doctor_name || '').trim() || undefined,
      doctor_code: String(document.doctor_code || '').trim() || undefined,
      enabled: true,
    }))
  return {
    case_title: form.caseTitle.trim(),
    basic_info: {
      patient_name: form.patientName.trim(),
      sex: form.sex,
      age: Number(form.age || 0),
      mr_no: form.mrNo.trim() || undefined,
      department: form.department.trim(),
      admission_time: normalizeDateTimeLocal(form.admissionTime) || form.admissionTime,
      discharge_time: normalizeDateTimeLocal(form.dischargeTime),
      main_diagnosis: form.mainDiagnosis.trim() || undefined,
      other_diagnoses: splitLines(form.otherDiagnosesText),
    },
    documents,
    evaluation_as_of_date: String(form.evaluationAsOfDate || '').trim() || undefined,
    selected_rule_ids: form.selectedRuleIds,
    manual_issue_text: form.manualIssueText.trim() || undefined,
    template_key: form.templateKey || undefined,
    golden_answers: form.goldenAnswers
      .filter((answer) => String(answer.qc_point_id || '').trim())
      .map((answer) => ({
        ...answer,
        qc_point_id: String(answer.qc_point_id || '')
          .trim()
          .toUpperCase(),
        trigger_facts: answer.trigger_facts
          .map((item) => String(item || '').trim())
          .filter(Boolean),
        evidence_keywords: answer.evidence_keywords
          .map((item) => String(item || '').trim())
          .filter(Boolean),
      })),
  }
}

export function normalizeRuleIds(ruleIds: string[]): string[] {
  return Array.from(
    new Set(
      ruleIds
        .map((ruleId) =>
          String(ruleId || '')
            .trim()
            .toUpperCase(),
        )
        .filter((ruleId) => /^LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}$/u.test(ruleId))
        .filter(Boolean),
    ),
  ).sort()
}

export function hasSameRuleScope(left: string[], right: string[]): boolean {
  const normalizedLeft = normalizeRuleIds(left)
  const normalizedRight = normalizeRuleIds(right)
  if (normalizedLeft.length !== normalizedRight.length) return false
  return normalizedLeft.every((ruleId, index) => ruleId === normalizedRight[index])
}

export type SyntheticCaseRunIdentity = {
  sampleItemId: string
  instituteId: string
  patientId: string
  visitId: string
}

export function buildSyntheticCaseRunPayload(
  form: TestRecordForm,
  identity: SyntheticCaseRunIdentity,
) {
  const sampleItemId = String(identity.sampleItemId || '').trim()
  const instituteId = String(identity.instituteId || '').trim()
  const patientId = String(identity.patientId || '').trim()
  const visitId = String(identity.visitId || '').trim()
  if (!sampleItemId || !instituteId || !patientId || !visitId) {
    throw new Error('测试病历缺少完整的样本标识或病例三坐标')
  }
  return {
    rule_set_key: LUXIAN_0609_RULE_SET_KEY,
    validation_mode: 'customer',
    sample_item_ids: [sampleItemId],
    record_refs: [{ institute_id: instituteId, patient_id: patientId, visit_id: visitId }],
    selected_rule_ids: normalizeRuleIds(form.selectedRuleIds),
    max_parallel_records: 1,
  }
}

export function findForbiddenSelfHints(form: TestRecordForm): string[] {
  const forbiddenPatterns = [/备注[:：].*未分析/u, /这里缺失/u, /本条为反例/u, /故意缺失/u]
  const hits: string[] = []
  form.documents.forEach((document) => {
    const content = String(document.content || '')
    if (forbiddenPatterns.some((pattern) => pattern.test(content))) {
      hits.push(document.title || documentTypeLabel(document.document_type))
    }
  })
  return hits
}
