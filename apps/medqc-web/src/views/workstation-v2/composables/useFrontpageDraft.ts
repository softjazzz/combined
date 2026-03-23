import { computed, ref, type Ref } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import type { FrontpageFocusTarget, IcdApplyTarget, PatientRecord } from '../types'
import type { ICDCodeDetail } from '../components/ICDDetailPanel.vue'
import { frontpageApi, type FrontpageExtractionSettings } from '@/api/frontpage'

/** 模块中文名映射 */
export const MODULE_LABELS: Record<string, string> = {
  basic_info: '基本信息',
  hospitalization: '住院信息',
  diagnoses: '诊断信息',
  procedures: '手术/操作',
  other_medical_info: '其他医疗信息',
  staff: '医护人员',
  costs: '费用信息',
  confidence: 'ICD 编码校验',
}

export interface CompletedModule {
  name: string
  label: string
  /** 从抽取结果里整理关键字段预览（用于界面展示） */
  preview: string[]
  timestamp: number
}

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
  const frontpagePostProcessing = ref(false)
  const frontpageDraft = ref<any>(null)
  const frontpageModule = ref('')
  const frontpageFocusTarget = ref<'' | FrontpageFocusTarget>('')
  const completedModules = ref<CompletedModule[]>([])
  const generateStartTime = ref(0)
  const extractionSettings = ref<FrontpageExtractionSettings | null>(null)
  const defaultPreviewTab = ref<'fields' | 'preview'>('fields')

  async function ensureExtractionSettingsLoaded() {
    if (extractionSettings.value) return extractionSettings.value
    try {
      const resp = await frontpageApi.getExtractionSettings()
      extractionSettings.value = resp.settings
      defaultPreviewTab.value = resp.settings.default_preview_tab
    } catch (error) {
      console.warn('读取首页抽取设置失败，使用默认策略', error)
      extractionSettings.value = null
      defaultPreviewTab.value = 'fields'
    }
    return extractionSettings.value
  }

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
    addField('basic', '病案号', draft.hospitalization?.medical_record_no || '')

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

  /** 从 frontpage 数据中提取模块关键字段的预览文本 */
  function getModulePreview(moduleName: string, fp: any): string[] {
    if (!fp) return []
    const previews: string[] = []
    const add = (v: any) => { if (v && String(v).trim()) previews.push(String(v).trim()) }
    switch (moduleName) {
      case 'basic_info': {
        const bi = fp.basic_info || {}
        add(bi.patient_name ? `姓名: ${bi.patient_name}` : '')
        add(bi.gender_text ? `性别: ${bi.gender_text}` : '')
        add(bi.age_years ? `年龄: ${bi.age_years}岁` : '')
        add(bi.birth_date ? `出生日期: ${bi.birth_date}` : '')
        add(bi.ethnicity ? `民族: ${bi.ethnicity}` : '')
        add(bi.marital_status_text ? `婚姻状况: ${bi.marital_status_text}` : '')
        add(bi.id_number ? `证件号: ${bi.id_number.replace(/^(.{6}).+(.{4})$/, '$1****$2')}` : '')
        add(bi.occupation ? `职业: ${bi.occupation}` : '')
        add(bi.contact_name ? `联系人: ${bi.contact_name}` : '')
        break
      }
      case 'hospitalization': {
        const h = fp.hospitalization || {}
        add(h.hospital_name ? `医疗机构名称: ${h.hospital_name}` : '')
        add(h.admission_datetime ? `入院日期: ${h.admission_datetime.split(' ')[0]}` : '')
        add(h.discharge_datetime ? `出院日期: ${h.discharge_datetime.split(' ')[0]}` : '')
        add(h.actual_hospital_days ? `住院天数: ${h.actual_hospital_days}天` : '')
        add(h.admission_dept ? `入院科室: ${h.admission_dept}` : '')
        add(h.discharge_dept ? `出院科室: ${h.discharge_dept}` : '')
        add(h.payment_method_text ? `医疗付费方式: ${h.payment_method_text}` : '')
        add(h.admission_way_text ? `入院途径: ${h.admission_way_text}` : '')
        add(h.medical_record_no ? `病案号: ${h.medical_record_no}` : '')
        break
      }
      case 'diagnoses': {
        const d = fp.diagnoses || {}
        add(d.discharge_main_diagnosis_text ? `主诊断: ${d.discharge_main_diagnosis_text}` : '')
        add(d.discharge_main_icd ? `主诊断编码: ${d.discharge_main_icd}` : '')
        add(d.discharge_main_outcome ? `转归: ${d.discharge_main_outcome}` : '')
        const others = d.discharge_other_diagnoses_texts || []
        if (others.length) {
          others.forEach((t: string, i: number) => {
            const code = d.discharge_other_icds?.[i] || ''
            add(`其他${i + 1}: ${t}${code ? ' (' + code + ')' : ''}`)
          })
        }
        const eds = d.ed_diagnosis_texts || []
        if (eds.length) add(`门诊诊断: ${eds.join('、')}`)
        break
      }
      case 'procedures': {
        const p = fp.procedures || {}
        if (!p.main_procedure_text) {
          add('无手术记录')
          break
        }
        add(p.main_procedure_text ? `主手术: ${p.main_procedure_text}` : '')
        add(p.main_procedure_code ? `手术编码: ${p.main_procedure_code}` : '')
        add(p.main_procedure_date ? `手术日期: ${p.main_procedure_date}` : '')
        add(p.surgeon_name ? `术者: ${p.surgeon_name}` : '')
        add(p.anesthesia_method ? `麻醉方式: ${p.anesthesia_method}` : '')
        add(p.anesthetist_name ? `麻醉医师: ${p.anesthetist_name}` : '')
        add(p.incision_grade ? `切口等级: ${p.incision_grade}` : '')
        const otherProcs = p.other_procedures_texts || p.other_procedure_texts || []
        if (otherProcs.length) add(`其他手术: ${otherProcs.length}项`)
        break
      }
      case 'other_medical_info': {
        const o = fp.other_medical_info || {}
        add(o.abo_blood_type ? `ABO血型: ${o.abo_blood_type}` : '')
        add(o.rh_blood_type_text ? `Rh血型: ${o.rh_blood_type_text}` : '')
        add(o.drug_allergy_flag === '2' ? '药物过敏: 有' : o.drug_allergy_flag === '1' ? '药物过敏: 无' : '')
        add(o.drug_allergy_drugs?.length ? `过敏药物: ${o.drug_allergy_drugs.join('、')}` : '')
        add(o.pathology_text ? `病理诊断: ${o.pathology_text}` : '')
        add(o.pathology_no ? `病理号: ${o.pathology_no}` : '')
        add(o.ventilation_hours ? `机械通气时长: ${o.ventilation_hours}小时` : '')
        break
      }
      case 'staff': {
        const s = fp.staff || {}
        add(s.dept_director ? `科主任: ${s.dept_director}` : '')
        add(s.chief_physician ? `主任医师: ${s.chief_physician}` : '')
        add(s.attending_physician ? `主治医师: ${s.attending_physician}` : '')
        add(s.resident_physician ? `住院医师: ${s.resident_physician}` : '')
        add(s.responsible_nurse ? `责任护士: ${s.responsible_nurse}` : '')
        add(s.coder ? `编码员: ${s.coder}` : '')
        add(s.medical_record_quality ? `病案质量等级: ${s.medical_record_quality}` : '')
        break
      }
      case 'costs': {
        const c = fp.costs || {}
        add(c.total_cost ? `住院总费用: ¥${c.total_cost}` : '')
        add(c.self_paid ? `自付金额: ¥${c.self_paid}` : '')
        const cats = c.categories || {}
        if (cats.western_medicine) add(`西药费: ¥${cats.western_medicine}`)
        if (cats.surgery_treatment) add(`手术费: ¥${cats.surgery_treatment}`)
        if (cats.laboratory_diagnostic) add(`检验费: ¥${cats.laboratory_diagnostic}`)
        if (cats.nursing_care) add(`护理费: ¥${cats.nursing_care}`)
        break
      }
      case 'confidence':
        add('编码匹配校验完成')
        break
    }
    return previews
  }

  function setDraftEmpty() {
    frontpageDraft.value = null
    frontpageModule.value = ''
    frontpageGenerating.value = false
    frontpageFocusTarget.value = ''
    completedModules.value = []
  }

  async function generateFrontpage() {
    if (!selectedRecord.value) return

    // 如果已有草稿，说明是“重新生成”，需强制走 LLM
    const isRegenerate = !!frontpageDraft.value
    const settings = await ensureExtractionSettingsLoaded()
    const allowForceRegenerate = settings?.allow_force_llm_regenerate !== false
    const effectiveForceLlm = isRegenerate && allowForceRegenerate

    if (isRegenerate && !allowForceRegenerate) {
      message.warning('当前配置已禁用强制重抽，本次将按普通重抽执行')
    }

    frontpageGenerating.value = true
    frontpagePostProcessing.value = true
    frontpageDraft.value = null
    frontpageModule.value = ''
    completedModules.value = []
    generateStartTime.value = Date.now()
    let releasedForPreview = false
    const seenModules = new Set<string>()

    const tryReleaseForPreview = () => {
      if (releasedForPreview || !frontpageDraft.value) return
      const hasDiagnoses = seenModules.has('diagnoses')
      const hasProcedures = seenModules.has('procedures')
      if (hasDiagnoses && hasProcedures) {
        releasedForPreview = true
        // 关键模块完成后先放行，剩余后处理继续流式更新
        frontpageGenerating.value = false
        frontpageModule.value = ''
      }
    }

    try {
      const response = await fetch('/api/v1/frontpage/auto-generate-draft-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: selectedId.value,
          medical_text: '',
          force_llm: effectiveForceLlm,
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
              seenModules.add(payload.module)
              // 记录已完成的模块（去重，同一模块可能多次更新）
              const existing = completedModules.value.findIndex(m => m.name === payload.module)
              const entry: CompletedModule = {
                name: payload.module,
                label: MODULE_LABELS[payload.module] || payload.module,
                preview: getModulePreview(payload.module, payload.frontpage),
                timestamp: Date.now() - generateStartTime.value,
              }
              if (existing >= 0) {
                completedModules.value[existing] = entry
              } else {
                completedModules.value.push(entry)
              }
              tryReleaseForPreview()
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
      frontpagePostProcessing.value = false
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
    if (!record.patientId || !record.id) {
      message.error('缺少保存主键（患者号/就诊号），请刷新后重试')
      return
    }

    try {
      // 注意：AI 草稿保存到独立副表 ai_frontpage_draft，不覆盖原始 HIS 首页数据（mr 表）
      await axios.post('/api/medical-records/ai-frontpage-draft', {
        institute_id: record.instituteId || null,
        patient_id: record.patientId,
        visit_id: record.id,
        draft_json: JSON.stringify(draft),
      })
      message.success('AI 首页草稿已保存')
    } catch (err: any) {
      console.error('AI 草稿保存失败:', err)
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
    frontpagePostProcessing,
    frontpageDraft,
    frontpageModule,
    frontpageFocusTarget,
    frontpageFields,
    defaultPreviewTab,
    completedModules,
    setDraftEmpty,
    ensureExtractionSettingsLoaded,
    generateFrontpage,
    handleExportFrontpage,
    handleSaveFrontpage,
    focusFrontpageSection,
    handleApplyICDCode,
    applyFrontPanelEdits,
  }
}
