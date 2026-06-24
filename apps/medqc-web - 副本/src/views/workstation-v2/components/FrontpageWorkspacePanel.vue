<template>
  <div class="frontpage-workspace-panel">
    <div
      v-if="generating"
      class="py-4"
    >
      <div
        class="mb-3 rounded-[18px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(255,255,255,0.98)_100%)] px-4 py-3.5 shadow-[0_8px_20px_rgba(15,23,42,0.035)]"
      >
        <div class="flex items-start gap-2.5">
          <div
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-blue-500 to-blue-700 shadow-[0_8px_16px_rgba(37,99,235,0.16)]"
          >
            <ThunderboltOutlined class="text-base text-white" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2.5">
              <div class="text-[14px] font-bold tracking-tight text-slate-900">
                正在从病历中提取病案首页
              </div>
              <div
                class="rounded-full border border-blue-100/80 bg-blue-50/70 px-2.5 py-1 text-[11px] font-semibold text-blue-700"
              >
                {{ progressPercent }}%
              </div>
            </div>
            <div class="mt-1 text-[12px] leading-5 text-slate-500">
              已完成 {{ completedCount }} /
              {{ totalCount }} 个模块，正在逐段整理结构化字段与编码结果
            </div>
          </div>
          <a-spin class="mt-1" />
        </div>

        <div class="mt-3">
          <div
            class="mb-1.5 flex items-center justify-between text-[11px] font-medium text-slate-400"
          >
            <span>提取进度</span>
            <span class="tabular-nums">{{ completedCount }}/{{ totalCount }}</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-slate-100/90">
            <div
              class="h-full rounded-full bg-gradient-to-r from-blue-500 via-blue-600 to-blue-400 transition-all duration-500"
              :style="{ width: `${progressPercent}%` }"
            />
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-2 px-0.5 xl:grid-cols-2">
        <div
          v-for="module in moduleCards"
          :key="module.key"
          class="rounded-[14px] border px-3 py-2.5 transition-all duration-300"
          :class="moduleCardClass(module.status)"
        >
          <div class="flex items-start gap-2.5">
            <div
              class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[10px]"
              :class="moduleIconClass(module.status)"
            >
              <CheckCircleOutlined
                v-if="module.status === 'done'"
                class="text-[12px] text-white"
              />
              <span
                v-else-if="module.status === 'active'"
                class="h-2.5 w-2.5 rounded-full bg-white animate-pulse"
              />
              <span
                v-else
                class="h-2 w-2 rounded-full bg-slate-400"
              />
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span
                  class="text-[13px] font-semibold"
                  :class="moduleTitleClass(module.status)"
                >{{
                  module.label
                }}</span>
                <span
                  v-if="module.entry?.timestamp"
                  class="text-[10px] tabular-nums text-slate-400"
                >{{ (module.entry.timestamp / 1000).toFixed(1) }}s</span>
                <span
                  v-if="module.status === 'active'"
                  class="rounded-full border border-blue-100/80 bg-blue-50/70 px-2 py-0.5 text-[10px] font-semibold text-blue-600"
                >提取中</span>
                <span
                  v-else-if="module.status === 'done'"
                  class="rounded-full border border-slate-200/80 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold text-slate-500"
                >已完成</span>
              </div>

              <div
                v-if="module.entry?.preview?.length"
                class="mt-1.5 flex flex-wrap gap-1.5"
              >
                <span
                  v-for="(preview, pi) in module.entry.preview"
                  :key="pi"
                  class="max-w-[220px] truncate rounded-full border border-slate-200/80 bg-white px-2.5 py-0.5 text-[11px] leading-5 text-slate-600"
                >{{ preview.label }}: {{ preview.value }}</span>
              </div>
              <div
                v-else
                class="mt-1.5 text-[11px] text-slate-400"
              >
                {{ module.status === 'active' ? '正在解析当前模块字段...' : '等待提取' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else>
      <FrontpagePreviewTabs
        :frontpage-tab="frontpageTab"
        @update:frontpage-tab="emit('update:frontpageTab', $event)"
      >
        <template #fields>
          <template v-if="draft">
            <FrontpageFieldsPanel
              :module-cards="moduleCards"
              :completed-count="completedCount"
              @export-frontpage="emit('export-frontpage', $event)"
              @save-frontpage="emit('save-frontpage')"
            />
          </template>
          <div
            v-else
            class="flex flex-col items-center justify-center rounded-[18px] border border-dashed border-slate-200 bg-slate-50/65 py-14 text-slate-300"
          >
            <div
              class="mb-3 flex h-14 w-14 items-center justify-center rounded-full border-2 border-dashed border-slate-200 bg-white"
            >
              <FileTextOutlined class="text-2xl" />
            </div>
            <div class="mb-1 text-sm font-medium text-slate-500">
              尚未生成 AI 首页草稿
            </div>
            <div class="text-xs text-slate-400">
              可点击右上角“AI 生成首页”生成草稿；系统首页请查看“系统首页”标签。
            </div>
          </div>
        </template>

        <template #preview>
          <FrontpagePreviewSheet
            :draft-sheet-data="draftSheetData"
            :post-processing="postProcessing"
          />
        </template>

        <template #official>
          <FrontpageOfficialSheet
            :sheet-loading="sheetLoading"
            :sheet-data="sheetData"
          />
        </template>
      </FrontpagePreviewTabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircleOutlined, FileTextOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'

import FrontpageFieldsPanel from './frontpage/FrontpageFieldsPanel.vue'
import FrontpageOfficialSheet from './frontpage/FrontpageOfficialSheet.vue'
import FrontpagePreviewSheet from './frontpage/FrontpagePreviewSheet.vue'
import FrontpagePreviewTabs from './frontpage/FrontpagePreviewTabs.vue'

type ModuleStatus = 'done' | 'active' | 'pending'

interface ModuleEntry {
  preview?: { label: string; value: string; isLongText?: boolean }[]
  timestamp?: number
}

interface ModuleCard {
  key: string
  label: string
  status: ModuleStatus
  entry?: ModuleEntry
}

const props = defineProps<{
  generating: boolean
  postProcessing: boolean
  draft: any
  frontpageTab: 'fields' | 'preview' | 'official'
  moduleCards: ModuleCard[]
  completedCount: number
  totalCount: number
  sheetLoading: boolean
  sheetData: any
}>()

const emit = defineEmits<{
  'update:frontpageTab': [value: 'fields' | 'preview' | 'official']
  'export-frontpage': [format: 'health' | 'insurance' | 'settlement']
  'save-frontpage': []
}>()

const progressPercent = computed(() => {
  if (!props.totalCount) return 0
  return Math.round((props.completedCount / props.totalCount) * 100)
})

const draftSheetData = computed(() => {
  const d = props.draft
  if (!d) return null
  const bi = d.basic_info || {}
  const ho = d.hospitalization || {}
  const diag = d.diagnoses || {}
  const proc = d.procedures || {}
  const omi = d.other_medical_info || {}
  const st = d.staff || {}
  const co = d.costs || {}

  const diagnoses: any[] = []
  if (diag.discharge_main_diagnosis_text) {
    diagnoses.push({
      diagnosis_type: '主要诊断',
      diagnosis_name: diag.discharge_main_diagnosis_text,
      diagnosis_code: diag.discharge_main_icd || '',
      admission_condition: diag.admission_condition || '',
    })
  }
  const others: string[] = diag.discharge_other_diagnoses_texts || []
  const otherIcds: string[] = diag.discharge_other_icds || []
  others.forEach((name: string, i: number) => {
    diagnoses.push({
      diagnosis_type: '其他诊断',
      diagnosis_name: name,
      diagnosis_code: otherIcds[i] || '',
      admission_condition: '',
    })
  })

  const surgeries: any[] = []
  if (proc.main_procedure_text) {
    surgeries.push({
      surgery_code: proc.main_procedure_code || '',
      surgery_name: proc.main_procedure_text,
      surgery_begin_datetime: proc.main_procedure_date || '',
      surgical_level: proc.main_procedure_level || '',
      surgeon: proc.surgeon_name || '',
      surgeon_code: proc.surgeon_code || '',
      first_assistant: proc.assistant1_name || '',
      first_assistant_code: proc.assistant1_code || '',
      second_assistant: proc.assistant2_name || '',
      second_assistant_code: proc.assistant2_code || '',
      anesthesia_method: proc.anesthesia_method || '',
      anesthesiologist: proc.anesthetist_name || '',
      anesthesiologist_code: proc.anesthetist_code || '',
      surgial_incision_level: proc.incision_grade || '',
      surgical_incisionheal_level: proc.incision_healing_grade || '',
    })
  }
  ;(proc.other_procedures || []).forEach((p: any) => {
    surgeries.push({
      surgery_code: p.code || '',
      surgery_name: p.text || p.name || '',
      surgery_begin_datetime: p.date || '',
      surgical_level: '',
      surgeon: '',
      first_assistant: '',
      second_assistant: '',
      anesthesia_method: '',
      anesthesiologist: '',
    })
  })

  const cats = co.categories || {}
  const catValue = (...keys: string[]) => {
    for (const key of keys) {
      const value = cats?.[key]
      if (value !== undefined && value !== null && value !== '') return value
    }
    return ''
  }
  const cost: Record<string, any> = {
    total_cost: co.total_cost ?? '',
    self_pay: co.self_paid ?? '',
    general_medical_service_fee: catValue('general_medical_service', '1'),
    general_treatment_fee: catValue('general_treatment', '2'),
    nursing_care_fee: catValue('nursing_care', '3'),
    other_service_fee: catValue('other_service', '4'),
    pathological_diagnostic_fee: catValue('pathological_diagnostic', '5'),
    laboratory_diagnostic_fee: catValue('laboratory_diagnostic', '6'),
    imaging_diagnostic_fee: catValue('imaging_diagnostic', '7'),
    clinical_diagnostic_fee: catValue('clinical_diagnostic', '8'),
    nonsurgical_treatment_fee: catValue('nonsurgical_treatment', '9'),
    clinical_physical_therapy_fee: catValue('clinical_physical_therapy', '10'),
    surgery_treatment_fee: catValue('surgery_treatment', '11'),
    anesthesia_fee: catValue('anesthesia', '12'),
    surgery_fee: catValue('surgery', '13'),
    rehabilitation_fee: catValue('rehabilitation', '14'),
    western_medicine_fee: catValue('western_medicine', '15'),
    antibacterial_drug_fee: catValue('antibacterial_drug', '16'),
    chinese_patent_medcine_fee: catValue('chinese_patent_medicine', '17'),
    chinese_herbal_medicine_fee: catValue('chinese_herbal_medicine', '18'),
    blood_fee: catValue('blood', '19'),
    exam_disposable_mat_fee: catValue('exam_disposable_material', '24'),
    treat_disposable_mat_fee: catValue('treat_disposable_material', '25'),
    surgery_disposable_mat_fee: catValue('surgery_disposable_material', '26'),
    other_fee: catValue('other'),
  }
  const basic: Record<string, any> = {
    name: bi.patient_name || '',
    sex: bi.gender_text || bi.gender || '',
    birthday: bi.birth_date || '',
    id_card_no: bi.id_number || '',
    marital_status: bi.marital_status_text || bi.marital_status || '',
    nationality: bi.nationality || '中国',
    ethnicity: bi.ethnicity || '',
    occupation_category: bi.occupation || '',
    nativeplace: bi.nativeplace || '',
    currentaddress: bi.current_address || '',
    age: bi.age || bi.age_years || '',
    age_year: bi.age_years || bi.age || '',
    contact_name: bi.contact_name || '',
    contact_relationship: bi.contact_relation || '',
    contact_telephone: bi.contact_phone || '',
    contact_address: bi.contact_address || '',
    work_unit: bi.work_unit || '',
    admission_datetime: ho.admission_datetime || '',
    discharge_datetime: ho.discharge_datetime || '',
    admission_dept_name: ho.admission_dept || '',
    discharge_dept_name: ho.discharge_dept || '',
    admission_ward_name: ho.admission_ward || '',
    discharge_ward_name: ho.discharge_ward || '',
    hospital_duration: ho.actual_hospital_days ?? '',
    medical_payment_method: ho.payment_method_text || '',
    admission_route: ho.admission_way_text || '',
    leaving_hospital_way: ho.leaving_hospital_way || '',
    transfer_dept_name: ho.transfer_dept || '',
    document_id: ho.medical_record_no || '',
    visit_cnt: ho.admission_times_in_hospital || '',
    rehospital_with_month: ho.rehospital_within_month || '',
    allergy_sign: omi.drug_allergy_flag || '',
    abo_blood_code: omi.abo_blood_type || '',
    rh_blood_code: omi.rh_blood_type || '',
    deptdirector_sign: st.dept_director || '',
    chief_physician_sign: st.chief_physician || '',
    attending_physician_sign: st.attending_physician || '',
    resident_physician_sign: st.resident_physician || '',
    responsible_nurse_sign: st.responsible_nurse || '',
    coder_sign: st.coder || '',
    medicalrecord_quality: st.medical_record_quality || '',
  }
  const evidence = d.evidence || {}
  const otherMedicalInfo: Record<string, any> = {
    pathology_text: omi.pathology_text ?? '',
    pathology_icd: omi.pathology_icd ?? '',
    pathology_no: omi.pathology_no ?? '',
    injury_poison_cause_text: omi.injury_poison_cause_text ?? '',
    injury_poison_cause_icd: omi.injury_poison_cause_icd ?? '',
    drug_allergy_flag: omi.drug_allergy_flag ?? '',
    abo_blood_type: omi.abo_blood_type ?? '',
    rh_blood_type: omi.rh_blood_type ?? '',
  }
  return { basic, diagnoses, surgeries, cost, evidence, other_medical_info: otherMedicalInfo }
})

function moduleCardClass(status: ModuleStatus) {
  if (status === 'done')
    return 'border-slate-200/85 bg-[linear-gradient(180deg,rgba(252,253,255,0.96)_0%,rgba(255,255,255,0.98)_100%)] shadow-[0_8px_18px_rgba(15,23,42,0.03)]'
  if (status === 'active')
    return 'border-blue-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.96)_0%,rgba(255,255,255,0.98)_100%)] shadow-[0_10px_22px_rgba(37,99,235,0.08)]'
  return 'border-slate-200/80 bg-white/88'
}

function moduleIconClass(status: ModuleStatus) {
  if (status === 'done') return 'bg-blue-500/95'
  if (status === 'active') return 'bg-blue-500/95'
  return 'bg-slate-200'
}

function moduleTitleClass(status: ModuleStatus) {
  if (status === 'done') return 'text-slate-700'
  if (status === 'active') return 'text-blue-700'
  return 'text-slate-500'
}
</script>
