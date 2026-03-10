import { computed, ref, type Ref } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import type { FrontpageFocusTarget, IcdApplyTarget, PatientRecord } from '../types'
import type { ICDCodeDetail } from '../components/ICDDetailPanel.vue'

function parseDownloadFilename(contentDisposition: string | null, fallback = 'frontpage_export.xlsx') {
  if (!contentDisposition) return fallback
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1])
  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  if (plainMatch?.[1]) return plainMatch[1]
  return fallback
}

export function useFrontpageDraft(
  selectedId: Ref<string | null>,
  selectedRecord: Readonly<Ref<PatientRecord | undefined>>,
  combinedMedicalText: Ref<string>,
  onDraftChanged?: () => void,
) {
  const frontpageGenerating = ref(false)
  const frontpageDraft = ref<any>(null)
  const frontpageModule = ref('')
  const frontpageFocusTarget = ref<'' | FrontpageFocusTarget>('')

  const frontpageFields = computed(() => {
    const draft = frontpageDraft.value
    if (!draft) return []

    const fields: any[] = []
    const addField = (category: string, label: string, value: any, confidence = 0.8) => {
      fields.push({ category, label, value: value ?? '', confidence })
    }

    const bi = draft.basic_info || {}
    addField('basic', '患者姓名', bi.patient_name)
    addField('basic', '性别', bi.gender_text)
    addField('basic', '年龄', bi.age_years ? `${bi.age_years}岁` : '')
    addField('basic', '出生日期', bi.birth_date)
    addField('basic', '民族', bi.ethnicity)
    addField('basic', '婚姻状况', bi.marital_status_text)
    addField('basic', '身份证号', bi.id_number)
    addField('basic', '职业', bi.occupation)
    addField('basic', '住院号', draft.hospitalization?.medical_record_no || '')

    const hosp = draft.hospitalization || {}
    addField('basic', '医疗机构名称', hosp.hospital_name)
    addField('admission', '入院日期', hosp.admission_datetime?.split(' ')[0] || '')
    addField('admission', '出院日期', hosp.discharge_datetime?.split(' ')[0] || '')
    addField('admission', '住院天数', hosp.actual_hospital_days ? String(hosp.actual_hospital_days) : '')
    addField('admission', '入院科室', hosp.admission_dept)
    addField('admission', '出院科室', hosp.discharge_dept)
    addField('admission', '床号', selectedRecord.value?.bedNo ? `${selectedRecord.value.bedNo}床` : '')

    const diag = draft.diagnoses || {}
    addField('basic', '主要诊断', diag.discharge_main_diagnosis_text)
    addField('basic', '主要诊断编码', diag.discharge_main_icd)
    addField('basic', '主要手术', draft.procedures?.main_procedure_text)
    addField('basic', '主要手术编码', draft.procedures?.main_procedure_code)

    return fields
  })

  function setDraftEmpty() {
    frontpageDraft.value = null
    frontpageModule.value = ''
    frontpageGenerating.value = false
    frontpageFocusTarget.value = ''
  }

  async function generateFrontpage() {
    if (!selectedRecord.value) return

    frontpageGenerating.value = true
    frontpageDraft.value = null
    frontpageModule.value = ''

    try {
      const response = await fetch('/api/v1/frontpage/auto-generate-draft-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: selectedId.value,
          medical_text: '',
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('无法读取响应流')

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(line.slice(6))
            if (payload.frontpage) {
              frontpageDraft.value = payload.frontpage
              onDraftChanged?.()
            }
            if (payload.module) {
              frontpageModule.value = payload.module
            }
          } catch {
            // 忽略解析错误
          }
        }
      }

      if (frontpageDraft.value) {
        message.success('首页生成完成')
      } else {
        message.warning('未能生成首页数据')
      }
    } catch (err: any) {
      console.error('首页生成失败:', err)
      message.error('首页生成失败: ' + (err.message || '未知错误'))
    } finally {
      frontpageGenerating.value = false
      frontpageModule.value = ''
    }
  }

  async function handleExportFrontpage(format: 'health' | 'insurance' | 'settlement') {
    if (!frontpageDraft.value) {
      message.warning('请先生成首页后再导出')
      return
    }

    const formatMap = {
      health: 'nhc',
      insurance: 'insurance',
      settlement: 'settlement',
    } as const

    try {
      const response = await fetch('/api/v1/frontpage/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          frontpage: frontpageDraft.value,
          format: formatMap[format],
        }),
      })

      if (!response.ok) {
        const errText = await response.text()
        throw new Error(errText || `HTTP ${response.status}`)
      }

      const blob = await response.blob()
      const filename = parseDownloadFilename(
        response.headers.get('content-disposition'),
        `frontpage_${formatMap[format]}.xlsx`,
      )
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      message.success('导出成功')
    } catch (err: any) {
      console.error('首页导出失败:', err)
      message.error(`导出失败: ${err?.message || '未知错误'}`)
    }
  }

  async function handleSaveFrontpage() {
    const draft = frontpageDraft.value
    const record = selectedRecord.value
    if (!draft || !record) {
      message.warning('请先生成首页后再保存')
      return
    }
    if (!record.instituteId || !record.patientId || !record.id) {
      message.error('缺少保存主键（机构号/患者号/就诊号），请刷新后重试')
      return
    }

    const bi = draft.basic_info || {}
    const hosp = draft.hospitalization || {}
    const staff = draft.staff || {}

    const payload = {
      institute_id: record.instituteId,
      patient_id: record.patientId,
      visit_id: record.id,
      name: bi.patient_name || record.name || '',
      sex: bi.gender_text || record.sex || '',
      age_year: bi.age_years != null ? String(bi.age_years) : (record.age != null ? String(record.age) : ''),
      birthday: bi.birth_date || null,
      ethnicity: bi.ethnicity || null,
      marital_status: bi.marital_status_text || null,
      id_card_no: bi.id_number || null,
      occupation_category: bi.occupation || null,
      inpat_no: hosp.medical_record_no || null,
      institute_county_desc: hosp.hospital_name || null,
      admission_datetime: hosp.admission_datetime || null,
      discharge_datetime: hosp.discharge_datetime || null,
      hospital_duration: hosp.actual_hospital_days != null ? String(hosp.actual_hospital_days) : null,
      admission_dept_name: hosp.admission_dept || null,
      discharge_dept_name: hosp.discharge_dept || null,
      attending_physician_sign: staff.attending_physician_name || null,
      chief_physician_sign: staff.chief_physician_name || null,
      record_content: combinedMedicalText.value || null,
    }

    try {
      await axios.put('/api/medical-records/frontpage', payload)
      message.success('首页保存成功')
    } catch (err: any) {
      console.error('首页保存失败:', err)
      message.error(`保存失败: ${err?.response?.data?.detail || err?.message || '未知错误'}`)
    }
  }

  function focusFrontpageSection(target: FrontpageFocusTarget) {
    if (frontpageFocusTarget.value === target) {
      frontpageFocusTarget.value = ''
      window.setTimeout(() => {
        frontpageFocusTarget.value = target
        window.setTimeout(() => {
          if (frontpageFocusTarget.value === target) {
            frontpageFocusTarget.value = ''
          }
        }, 1800)
      }, 0)
      return
    }
    frontpageFocusTarget.value = target
    window.setTimeout(() => {
      if (frontpageFocusTarget.value === target) {
        frontpageFocusTarget.value = ''
      }
    }, 1800)
  }

  function handleApplyICDCode(
    detail: ICDCodeDetail,
    icdApplyTarget: IcdApplyTarget,
    icdApplyIndex: number,
  ) {
    if (!frontpageDraft.value) {
      message.warning('请先生成首页后再回填编码')
      return false
    }
    const otherIdx = Math.max(1, Number(icdApplyIndex || 1)) - 1
    if (icdApplyTarget === 'mainDiagnosis') {
      if (detail.type === 'icd9cm3') {
        message.warning('当前目标是诊断编码，建议选择 ICD-10 编码')
      }
      frontpageDraft.value.diagnoses = frontpageDraft.value.diagnoses || {}
      frontpageDraft.value.diagnoses.discharge_main_icd = detail.code
      if (!frontpageDraft.value.diagnoses.discharge_main_diagnosis_text) {
        frontpageDraft.value.diagnoses.discharge_main_diagnosis_text = detail.name
      }
      message.success(`已回填主诊断编码：${detail.code}`)
      focusFrontpageSection('diagnosis')
    } else if (icdApplyTarget === 'otherDiagnosis') {
      if (detail.type === 'icd9cm3') {
        message.warning('当前目标是诊断编码，建议选择 ICD-10 编码')
      }
      frontpageDraft.value.diagnoses = frontpageDraft.value.diagnoses || {}
      const diag = frontpageDraft.value.diagnoses
      diag.discharge_other_icds = Array.isArray(diag.discharge_other_icds) ? diag.discharge_other_icds : []
      diag.discharge_other_diagnoses_texts = Array.isArray(diag.discharge_other_diagnoses_texts) ? diag.discharge_other_diagnoses_texts : []
      while (diag.discharge_other_icds.length <= otherIdx) diag.discharge_other_icds.push('')
      while (diag.discharge_other_diagnoses_texts.length <= otherIdx) diag.discharge_other_diagnoses_texts.push('')
      diag.discharge_other_icds[otherIdx] = detail.code
      if (!diag.discharge_other_diagnoses_texts[otherIdx]) {
        diag.discharge_other_diagnoses_texts[otherIdx] = detail.name
      }
      message.success(`已回填第 ${otherIdx + 1} 条其他诊断编码：${detail.code}`)
      focusFrontpageSection('diagnosis')
    } else if (icdApplyTarget === 'mainProcedure') {
      if (detail.type === 'icd10') {
        message.warning('当前目标是手术编码，建议选择 ICD-9-CM-3 编码')
      }
      frontpageDraft.value.procedures = frontpageDraft.value.procedures || {}
      frontpageDraft.value.procedures.main_procedure_code = detail.code
      if (!frontpageDraft.value.procedures.main_procedure_text) {
        frontpageDraft.value.procedures.main_procedure_text = detail.name
      }
      message.success(`已回填主手术编码：${detail.code}`)
      focusFrontpageSection('procedure')
    } else {
      if (detail.type === 'icd10') {
        message.warning('当前目标是手术编码，建议选择 ICD-9-CM-3 编码')
      }
      frontpageDraft.value.procedures = frontpageDraft.value.procedures || {}
      const proc = frontpageDraft.value.procedures
      proc.other_procedure_codes = Array.isArray(proc.other_procedure_codes) ? proc.other_procedure_codes : []
      proc.other_procedure_texts = Array.isArray(proc.other_procedure_texts) ? proc.other_procedure_texts : []
      proc.other_procedures = Array.isArray(proc.other_procedures) ? proc.other_procedures : []
      while (proc.other_procedure_codes.length <= otherIdx) proc.other_procedure_codes.push('')
      while (proc.other_procedure_texts.length <= otherIdx) proc.other_procedure_texts.push('')
      while (proc.other_procedures.length <= otherIdx) proc.other_procedures.push({})
      proc.other_procedure_codes[otherIdx] = detail.code
      if (!proc.other_procedure_texts[otherIdx]) {
        proc.other_procedure_texts[otherIdx] = detail.name
      }
      proc.other_procedures[otherIdx] = {
        ...(proc.other_procedures[otherIdx] || {}),
        code: detail.code,
        name: proc.other_procedure_texts[otherIdx] || detail.name,
      }
      message.success(`已回填第 ${otherIdx + 1} 条其他手术编码：${detail.code}`)
      focusFrontpageSection('procedure')
    }
    onDraftChanged?.()
    return true
  }

  function applyFrontPanelEdits(payload: { diagnoses?: any[]; procedures?: any[] }) {
    if (!frontpageDraft.value) return
    const diagItems = payload.diagnoses || []
    const procItems = payload.procedures || []

    frontpageDraft.value.diagnoses = frontpageDraft.value.diagnoses || {}
    frontpageDraft.value.procedures = frontpageDraft.value.procedures || {}

    if (diagItems.length > 0) {
      const [main, ...others] = diagItems
      frontpageDraft.value.diagnoses.discharge_main_diagnosis_text = main?.name || ''
      frontpageDraft.value.diagnoses.discharge_main_icd = main?.code || ''
      frontpageDraft.value.diagnoses.discharge_other_diagnoses_texts = others.map(item => item?.name || '')
      frontpageDraft.value.diagnoses.discharge_other_icds = others.map(item => item?.code || '')
    }

    if (procItems.length > 0) {
      const [main, ...others] = procItems
      frontpageDraft.value.procedures.main_procedure_text = main?.name || ''
      frontpageDraft.value.procedures.main_procedure_code = main?.code || ''
      frontpageDraft.value.procedures.other_procedure_texts = others.map(item => item?.name || '')
      frontpageDraft.value.procedures.other_procedure_codes = others.map(item => item?.code || '')
      frontpageDraft.value.procedures.other_procedures = others.map(item => ({
        code: item?.code || '',
        name: item?.name || '',
      }))
    }

    onDraftChanged?.()
  }

  return {
    frontpageGenerating,
    frontpageDraft,
    frontpageModule,
    frontpageFocusTarget,
    frontpageFields,
    setDraftEmpty,
    generateFrontpage,
    handleExportFrontpage,
    handleSaveFrontpage,
    focusFrontpageSection,
    handleApplyICDCode,
    applyFrontPanelEdits,
  }
}
