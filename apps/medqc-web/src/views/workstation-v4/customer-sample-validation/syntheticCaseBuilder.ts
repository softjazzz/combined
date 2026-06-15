import type {
  ManualTestRecordCreateRequest,
  SyntheticCaseGoldenAnswer,
  TestRecordDocumentForm,
  TestRecordForm,
} from './types'

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
  { label: '不合规', value: 'non_compliant' },
  { label: '合规', value: 'compliant' },
  { label: '不适用', value: 'not_applicable' },
  { label: '数据不足', value: 'data_gap' },
  { label: '需人工复核', value: 'uncertain' },
]

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
  return {
    key: buildDocumentKey(),
    document_type: type,
    title: label,
    record_time: nowText,
    submit_time: nowText,
    content: '',
    doctor_name: '测试医师',
    doctor_code: '',
    enabled: true,
    ...overrides,
  }
}

export function createDefaultSyntheticCaseForm(): TestRecordForm {
  const now = new Date()
  const admission = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000)
  const firstCourse = new Date(admission.getTime() + 4 * 60 * 60 * 1000)
  return {
    caseTitle: '客户自建质控测试病历',
    patientName: '测试患者',
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
