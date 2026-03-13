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
 * 将 MedQC 的 `FrontPageDraft`（API snake_case）转换为 HM 模板回填需要的数据。
 *
 * 返回值包括：
 * - deMap: DE -> value 字典，用于回填有 data-hm-code 属性的元素
 * - diagnosisRows: 其他诊断行数据，用于填充诊断表格空白单元格
 * - procedureRows: 其他手术行数据，用于填充手术表格空白单元格
 */
export function frontPageDraftToDeMap(frontpageDraft: any): {
  deMap: Record<string, DeValue>
  diagnosisRows: Array<{ name?: string; code?: string }>
  procedureRows: Array<{ name?: string; code?: string }>
} {
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

  const deMap: Record<string, DeValue> = {
    // 医疗机构/住院
    'DE08.10.013.00.012': hosp?.hospital_name, // 医疗机构名称
    'DE08.10.052.00': hosp?.organization_code, // 组织机构代码
    'DE01.00.004.00': hosp?.medical_record_no, // 病案号
    'DE02.10.090.00': hosp?.admission_times_in_hospital, // 住院次数
    'DE07.00.007.00': coalesce(hosp?.payment_method, hosp?.payment_method_text), // 医疗付费方式代码
    'DE06.00.339.00': coalesce(hosp?.admission_way, hosp?.admission_way_text), // 入院途径代码
    'DE08.10.026.00.022': hosp?.admission_dept, // 入院科别
    'DE01.00.019.00.003': hosp?.admission_ward, // 入院病房
    'DE06.00.092.00': hosp?.admission_datetime, // 入院时间
    'DE08.10.026.00.023': hosp?.transfer_dept, // 转科科别
    'DE08.10.026.00.024': hosp?.discharge_dept, // 出院科别
    'DE01.00.019.00.004': hosp?.discharge_ward, // 出院病房
    'DE06.00.017.00': hosp?.discharge_datetime, // 出院时间
    'DE06.00.310.00': hosp?.actual_hospital_days, // 住院天数
    'DE06.00.223.00': hosp?.leaving_hospital_way, // 离院方式
    'DE06.00.195.00': hosp?.rehospital_within_month, // 31天内再住院计划
    // 日常生活能力评定量表得分
    'DE05.10.148.00': hosp?.daily_ability_admission, // Barthel 指数（入院）
    'DE05.10.152.00': hosp?.daily_ability_discharge, // Barthel 指数（出院）

    // 基本信息
    'DE02.01.039.00': basic?.patient_name, // 姓名
    'DE99.09.001.79': genderToCode({ gender: basic?.gender, genderText: basic?.gender_text }), // 性别
    'DE02.01.005.01': basic?.birth_date, // 出生日期
    'DE02.01.026.00': basic?.age_years, // 年龄
    'DE02.01.015.00': basic?.nationality, // 国籍代码
    'DE02.01.025.00': basic?.ethnicity, // 民族
    'DE02.01.018.00': maritalStatusToCode({
      maritalStatus: basic?.marital_status,
      maritalStatusText: basic?.marital_status_text
    }), // 婚姻状况代码
    'DE02.01.030.00': basic?.id_number, // 身份证号码
    'DE02.01.052.00': coalesce(basic?.occupation_code, basic?.occupation), // 职业类别代码
    // 出生地（省/市/县）
    'DE02.01.009.01': basic?.birthplace, // 出生地-省
    'DE02.01.009.01.007': basic?.birthplace, // 出生地-市
    'DE02.01.009.01.008': basic?.birthplace, // 出生地-县
    // 籍贯（省/市/县）
    'DE02.01.009.02': basic?.nativeplace, // 籍贯-省
    'DE02.01.009.02.006': basic?.nativeplace, // 籍贯-市
    'DE02.01.009.02.007': basic?.nativeplace, // 籍贯-县
    // 现住址
    'DE02.01.009.06.005': basic?.current_address, // 现住址
    'DE02.01.010.00.009': coalesce(basic?.current_address_phone, basic?.contact_phone), // 现住址电话
    'DE02.01.047.00': basic?.current_address_zip, // 现住址邮编
    // 户口地址（省/市/县）
    'DE02.01.009.03': basic?.household_address, // 户口地址-省
    'DE02.01.009.03.006': basic?.household_address, // 户口地址-市
    'DE02.01.009.06.006': basic?.household_address, // 户口地址-号码
    'DE02.01.047.00.004': basic?.household_address_zip, // 户口地址邮编
    // 工作单位
    'DE02.01.032.00': basic?.work_unit, // 工作单位名称
    'DE02.01.009.06.007': coalesce(basic?.workplace_address, basic?.work_unit), // 工作单位地址
    'DE02.01.010.00.016': basic?.work_unit_phone, // 工作单位电话
    'DE02.01.047.00.005': basic?.work_unit_zip, // 工作单位邮编
    // 联系人
    'DE02.01.039.00.144': basic?.contact_name, // 联系人姓名
    'DE02.10.024.00.005': coalesce(basic?.contact_relation_code, basic?.contact_relation), // 联系人关系
    'DE02.01.010.00.017': basic?.contact_phone, // 联系人电话
    'DE02.01.009.06.008': basic?.contact_address, // 联系人地址

    // 诊断 — 门急诊诊断（有 data-hm-code 元素）
    'DE05.01.025.00.016': Array.isArray(edDiagnosisTexts) ? edDiagnosisTexts[0] : undefined, // 门急诊诊断名称
    'DE05.01.024.00.046': Array.isArray(edDiagnosisCodes) ? edDiagnosisCodes[0] : undefined, // 门急诊诊断编码
    // 主要诊断（有 data-hm-code 元素）
    'DE05.01.025.00.009': diag?.discharge_main_diagnosis_text, // 出院西医诊断名称
    'DE05.01.024.00.044': diag?.discharge_main_icd, // 出院西医诊断编码
    'DE09.00.104.00.002': diag?.admission_condition, // 入院病情代码

    // 手术/操作 — 主手术（有 data-hm-code 元素）
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
    // 颅脑损伤昏迷时间（入院前）
    'DE05.10.138.01': other?.brain_injury_before_admission_hours, // 入院前-天
    'DE05.10.138.02': other?.brain_injury_before_admission_hours, // 入院前-小时
    'DE05.10.138.03': other?.brain_injury_before_admission_minutes, // 入院前-分钟
    // 颅脑损伤昏迷时间（入院后）
    'DE05.10.138.01.002': other?.brain_injury_after_admission_hours, // 入院后-天
    'DE05.10.138.02.002': other?.brain_injury_after_admission_hours, // 入院后-小时
    'DE05.10.138.03.002': other?.brain_injury_after_admission_minutes, // 入院后-分钟

    // 费用
    'DE07.00.010.00': costs?.total_cost, // 住院总费用
    'DE07.00.001.00': costs?.self_paid, // 住院自付金额

    // 人员/签名
    'DE02.01.039.00.119': staff?.dept_director, // 科主任签名
    'DE02.01.039.00.120': staff?.chief_physician, // 主（副主任）医师签名
    'DE02.01.039.00.172': staff?.attending_physician, // 主治医师签名
    'DE02.01.039.00.171': staff?.resident_physician, // 住院医师签名
    'DE02.01.039.00.145': staff?.responsible_nurse, // 责任护士签名
    'DE02.01.039.00.126': staff?.coder // 编码员签名
  }

  // 构建其他诊断行数据（用于按行索引填充表格空白单元格）
  const diagnosisRows: Array<{ name?: string; code?: string }> = []
  const otherDiagTexts = diag?.discharge_other_diagnoses_texts
  const otherDiagCodes = diag?.discharge_other_icds
  if (Array.isArray(otherDiagTexts)) {
    for (let i = 0; i < otherDiagTexts.length; i++) {
      diagnosisRows.push({
        name: otherDiagTexts[i] || undefined,
        code: Array.isArray(otherDiagCodes) ? otherDiagCodes[i] || undefined : undefined
      })
    }
  }

  // 构建其他手术行数据
  const procedureRows: Array<{ name?: string; code?: string }> = []
  const otherProcs = proc?.other_procedures
  if (Array.isArray(otherProcs)) {
    for (const p of otherProcs) {
      if (!p) continue
      procedureRows.push({
        name: p.name || p.text || undefined,
        code: p.code || undefined
      })
    }
  }

  return { deMap, diagnosisRows, procedureRows }
}
