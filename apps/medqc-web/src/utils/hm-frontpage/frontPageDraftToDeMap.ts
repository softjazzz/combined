import type { DeValue } from './templateRefill'

type MaybeString = string | null | undefined

function coalesce<T>(...values: Array<T | null | undefined>): T | undefined {
  for (const value of values) {
    if (value !== null && value !== undefined) return value
  }
  return undefined
}

function genderToCode(params: { gender?: MaybeString; genderText?: MaybeString }): MaybeString {
  const { gender, genderText } = params
  if (gender === '1' || gender === '2') return gender
  if (!genderText) return gender
  if (genderText.includes('男')) return '1'
  if (genderText.includes('女')) return '2'
  return gender
}

function maritalStatusToCode(params: {
  maritalStatus?: MaybeString
  maritalStatusText?: MaybeString
}): MaybeString {
  const { maritalStatus, maritalStatusText } = params
  if (maritalStatus) return maritalStatus
  const text = maritalStatusText || ''
  if (text.includes('未婚')) return '1'
  if (text.includes('已婚')) return '2'
  if (text.includes('丧偶')) return '3'
  if (text.includes('离婚')) return '4'
  if (text) return '9'
  return undefined
}

function rhToCode(params: { rh?: MaybeString; rhText?: MaybeString }): MaybeString {
  const { rh, rhText } = params
  if (rh === '1' || rh === '2' || rh === '3' || rh === '4') return rh
  const text = rhText || ''
  if (text.includes('阴')) return '1'
  if (text.includes('阳')) return '2'
  if (text.includes('不详')) return '3'
  if (text.includes('未查')) return '4'
  return rh
}

function joinList(values: unknown): string | undefined {
  if (!Array.isArray(values)) return undefined
  const texts = values
    .map((value) => (value === null || value === undefined ? '' : String(value).trim()))
    .filter(Boolean)
  if (texts.length === 0) return undefined
  return texts.join('，')
}

/**
 * 将 MedQC 的 `FrontPageDraft`（API snake_case）转换为 HM 模板回填需要的 `DE -> value` 字典。
 *
 * 注意：当前 MedQC 生成结果并不保证包含“编码系统”输出（ICD/手术编码/字典码等）。
 * - 一期优先回填可展示的文本字段
 * - 对“代码字段”尽量做最小映射（性别/婚姻/Rh），其余先填文本或留空
 */
export function frontPageDraftToDeMap(frontpageDraft: any): Record<string, DeValue> {
  const basic = frontpageDraft?.basic_info || {}
  const hosp = frontpageDraft?.hospitalization || {}
  const diag = frontpageDraft?.diagnoses || {}
  const proc = frontpageDraft?.procedures || {}
  const other = frontpageDraft?.other_medical_info || {}
  const staff = frontpageDraft?.staff || {}
  const costs = frontpageDraft?.costs || {}

  const edDiagnosisTexts: unknown = diag?.ed_diagnosis_texts
  const edDiagnosisCodes: unknown = diag?.ed_diagnosis_codes

  const drugAllergyDrugsText =
    joinList(other?.drug_allergy_drugs) ||
    joinList(other?.drug_allergy_drugs_texts) ||
    joinList(other?.drug_allergy_drug_texts)

  return {
    // 医疗机构/住院
    'DE08.10.013.00.012': hosp?.hospital_name, // 医疗机构名称
    'DE08.10.052.00': hosp?.organization_code, // 组织机构代码（MedQC 目前一般没有，留空）
    'DE01.00.004.00': hosp?.medical_record_no, // 病案号
    'DE02.10.090.00': hosp?.admission_times_in_hospital, // 住院次数
    'DE07.00.007.00': coalesce(hosp?.payment_method, hosp?.payment_method_text), // 医疗付费方式代码（一期可填文本）
    'DE06.00.339.00': coalesce(hosp?.admission_way, hosp?.admission_way_text), // 入院途径代码（一期可填文本）
    'DE08.10.026.00.022': hosp?.admission_dept, // 入院科别
    'DE01.00.019.00.003': hosp?.admission_ward, // 入院病房
    'DE06.00.092.00': hosp?.admission_datetime, // 入院时间
    'DE08.10.026.00.024': hosp?.discharge_dept, // 出院科别
    'DE01.00.019.00.004': hosp?.discharge_ward, // 出院病房
    'DE06.00.017.00': hosp?.discharge_datetime, // 预出院时间（模板缺“出院时间”，先占位）
    'DE06.00.310.00': hosp?.actual_hospital_days, // 住院天数

    // 基本信息
    'DE02.01.039.00': basic?.patient_name, // 姓名
    'DE99.09.001.79': genderToCode({ gender: basic?.gender, genderText: basic?.gender_text }), // 首页_性别
    'DE02.01.005.01': basic?.birth_date, // 出生日期
    'DE02.01.026.00': basic?.age_years, // 年龄
    'DE02.01.015.00': basic?.nationality, // 国籍代码（一期可填文本）
    'DE02.01.025.00': basic?.ethnicity, // 民族
    'DE02.01.018.00': maritalStatusToCode({
      maritalStatus: basic?.marital_status,
      maritalStatusText: basic?.marital_status_text
    }), // 婚姻状况代码
    'DE02.01.030.00': basic?.id_number, // 身份证号码
    'DE02.01.052.00': coalesce(basic?.occupation_code, basic?.occupation), // 职业类别代码（一期可填文本）
    'DE02.01.009.06.005': basic?.current_address, // 住址_门牌号码（一期直接填整段地址）
    'DE02.01.010.00.009': basic?.contact_phone, // 电话号码（MedQC 暂无患者电话字段，先复用联系人电话）
    'DE02.01.039.00.144': basic?.contact_name, // 联系人姓名
    'DE02.10.024.00.005': coalesce(basic?.contact_relation_code, basic?.contact_relation), // 联系人与患者的关系代码（一期可填文本）
    'DE02.01.010.00.017': basic?.contact_phone, // 联系人电话

    // 诊断
    'DE05.01.025.00.016': Array.isArray(edDiagnosisTexts) ? edDiagnosisTexts[0] : undefined, // 门急诊诊断名称
    'DE05.01.024.00.046': Array.isArray(edDiagnosisCodes) ? edDiagnosisCodes[0] : undefined, // 门急诊诊断编码
    'DE05.01.025.00.009': diag?.discharge_main_diagnosis_text, // 出院西医诊断名称
    'DE05.01.024.00.044': diag?.discharge_main_icd, // 出院西医诊断编码
    'DE09.00.104.00.002': diag?.admission_condition, // 入院病情代码

    // 手术/操作
    'DE99.02.002.001': proc?.main_procedure_text, // 手术及操作名称_1
    'DE99.02.001.001': proc?.main_procedure_code, // 手术及操作编码_1
    'DE99.02.003.001': proc?.main_procedure_date, // 手术及操作日期_1
    'DE99.02.004.001': coalesce(proc?.main_procedure_level, proc?.main_procedure_level_code), // 手术级别代码_1
    'DE99.02.010.001': coalesce(proc?.anesthesia_method, proc?.anesthesia_method_code), // 麻醉方式代码_1
    'DE99.02.009.001': coalesce(proc?.incision_healing_grade, proc?.incision_healing_grade_code), // 切口愈合等级代码_1

    // 其他医疗信息
    'DE01.00.005.00': other?.pathology_no, // 病理号
    'DE05.01.025.00.019': other?.pathology_text, // 病理诊断名称
    'DE02.10.023.00': coalesce(other?.drug_allergy_flag, other?.drug_allergy_flag_text), // 药物过敏标志
    'DE02.10.022.00': drugAllergyDrugsText, // 过敏药物
    'DE04.50.001.00': other?.abo_blood_type, // ABO血型代码
    'DE04.50.010.00': rhToCode({ rh: other?.rh_blood_type, rhText: other?.rh_blood_type_text }), // Rh血型代码

    // 费用
    'DE07.00.010.00': costs?.total_cost, // 住院总费用
    'DE07.00.001.00': costs?.self_paid, // 住院自付金额

    // 人员/签名（演示用：将姓名填到“签名”字段）
    'DE02.01.039.00.119': staff?.dept_director, // 科主任签名
    'DE02.01.039.00.172': staff?.attending_physician, // 主治医师签名
    'DE02.01.039.00.171': staff?.resident_physician, // 住院医师签名
    'DE02.01.039.00.145': staff?.responsible_nurse, // 责任护士签名
    'DE02.01.039.00.126': staff?.coder // 编码员签名
  }
}

