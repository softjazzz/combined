/**
 * 医疗文书结构化字段的统一中文展示名称。
 * 仅用于前端展示，不参与质控规则、同步或数据转换。
 */
const MEDICAL_FIELD_LABELS: Record<string, string> = {
  record_time: '记录时间',
  submit_time: '提交时间',
  department: '科室',
  dept_name: '科室',
  ward_name: '病房',
  ward_no: '病房',
  name: '患者姓名',
  sex: '性别',
  age_year: '年龄',
  doctor_name: '医生',
  physician_name: '申请医师',
  recorder_name: '记录者',
  submitter: '记录者',
  chief_complaint: '主诉',
  history_of_present_illness: '现病史',
  present_illness_history: '现病史',
  present_history: '现病史',
  current_medical_history: '现病史',
  past_history: '既往史',
  previous_history: '既往史',
  personal_history: '个人史',
  marital_delivery_history: '婚育史',
  menstrual_history: '月经史',
  marital_history: '婚育史',
  family_history: '家族史',
  allergy_history: '过敏史',
  drug_allergy_history: '药物过敏史',
  food_allergy_history: '食物过敏史',
  physical_examination: '体格检查',
  physical_exam: '体格检查',
  checkup: '体格检查',
  checkup_special: '专科情况',
  specialist_examination: '专科检查',
  auxiliary_examination: '辅助检查',
  assist_exam: '辅助检查',
  case_characteristic: '病例特点',
  diagnose_based_on: '诊断依据',
  differential_diagnosis: '鉴别诊断',
  diagnosis: '诊断',
  admission_diagnosis: '入院诊断',
  treatment_plan: '诊疗计划',
  treatment_course: '诊疗经过',
  admission_condition: '入院情况',
  current_situation: '目前情况',
  discharge_condition: '出院情况',
  discharge_order: '出院医嘱',
  record_content: '记录内容',
  other_content: '其他内容',
  transfer_purpose: '转科目的',
  transfer_treatment_plan: '转入诊疗计划',
  note: '注意事项',
  request_dept: '申请科室',
  request_physician: '申请医生',
  request_datetime: '申请时间',
  request_time: '申请时间',
  request_surgery_datetime: '申请手术时间',
  surgery_name: '手术项目',
  surgery_code: '手术编码',
  surgery_level: '手术等级',
  anesthesia_method: '麻醉方式',
  surgeon: '手术医师',
  anesthesiologist: '麻醉医师',
  surgery_process: '手术经过',
  surgery_begin_time: '手术开始时间',
  surgery_end_time: '手术结束时间',
  preoperative_diagnosis: '术前诊断',
  intraoperative_diagnosis: '术中诊断',
  postoperative_diagnosis: '术后诊断',
  reason_for_blood: '输血申请理由',
  patient_bloodtype_abo: 'ABO血型',
  patient_bloodtype_rhd: 'Rh血型',
  transfuse_variety: '输血品种',
  transfuse_volume: '输血剂量',
  transfuse_volume_unit: '剂量单位',
  hemoglobin: '血红蛋白',
  hematocrit: '红细胞压积',
  rbc: '红细胞计数',
  prothrombin_time: '凝血酶原时间',
  partial_thromboplastin_time: '部分凝血活酶时间',
  fibrinogen: '纤维蛋白原',
  albumin: '白蛋白',
  platelet_antibody: '血小板抗体',
  rbc_antibody: '红细胞抗体',
  exam_id: '检查编号',
  exam_type: '检查类型',
  exam_reason: '检查原因',
  exam_time: '检查时间',
  report_time: '报告时间',
  report_datetime: '报告时间',
  report_status: '报告状态',
  reporter: '报告者',
  reviewer: '审核者',
  review_datetime: '审核时间',
  test_id: '检验编号',
  labtest_subject: '检验项目',
  labtest_cause: '检验原因',
  labtest_result_status: '报告状态',
  specimen: '标本',
  specimen_name: '标本名称',
  order_name: '医嘱名称',
  order_status: '医嘱状态',
  order_dept_name: '开单科室',
  executive_dept_name: '执行科室',
  prescribed_datetime: '下达时间',
  prescribed_doctor: '下达医生',
  generic_name: '药品名称',
  brand_name: '商品名',
  drug_specification: '规格',
  drug_frequency: '频次',
  drug_apply_method: '给药途径',
  single_dose: '单次剂量',
  single_dose_unit: '剂量单位',
  quantity: '数量',
  quantity_unit: '数量单位',
  application_id: '申请号',
  inpat_no: '住院号',
}

function normalizeMedicalFieldKey(value: unknown): string {
  return String(value || '')
    .trim()
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

const NORMALIZED_LABELS = new Map(
  Object.entries(MEDICAL_FIELD_LABELS).map(([key, label]) => [
    normalizeMedicalFieldKey(key),
    label,
  ]),
)

export function resolveMedicalFieldLabel(value: unknown): string {
  const raw = String(value || '').trim()
  if (!raw) return ''
  return MEDICAL_FIELD_LABELS[raw] || NORMALIZED_LABELS.get(normalizeMedicalFieldKey(raw)) || ''
}

export function resolveSafeMedicalSectionLabel(value: unknown, fallback = '正文'): string {
  const raw = String(value || '').trim()
  return resolveMedicalFieldLabel(raw) || (/[㐀-鿿]/u.test(raw) ? raw : fallback)
}
