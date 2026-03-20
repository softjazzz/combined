<template>
  <div class="frontpage-workspace-panel">
    <div v-if="generating" class="py-4">
      <div class="mb-3 rounded-[18px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(255,255,255,0.98)_100%)] px-4 py-3.5 shadow-[0_8px_20px_rgba(15,23,42,0.035)]">
        <div class="flex items-start gap-2.5">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-blue-500 to-blue-700 shadow-[0_8px_16px_rgba(37,99,235,0.16)]">
            <ThunderboltOutlined class="text-base text-white" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2.5">
              <div class="text-[14px] font-bold tracking-tight text-slate-900">正在从病历中提取病案首页</div>
              <div class="rounded-full border border-blue-100/80 bg-blue-50/70 px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                {{ progressPercent }}%
              </div>
            </div>
            <div class="mt-1 text-[12px] leading-5 text-slate-500">
              已完成 {{ completedCount }} / {{ totalCount }} 个模块，正在逐段整理结构化字段与编码结果
            </div>
          </div>
          <a-spin class="mt-1" />
        </div>

        <div class="mt-3">
          <div class="mb-1.5 flex items-center justify-between text-[11px] font-medium text-slate-400">
            <span>提取进度</span>
            <span class="tabular-nums">{{ completedCount }}/{{ totalCount }}</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-slate-100/90">
            <div
              class="h-full rounded-full bg-gradient-to-r from-blue-500 via-blue-600 to-blue-400 transition-all duration-500"
              :style="{ width: `${progressPercent}%` }"
            ></div>
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
            <div class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[10px]" :class="moduleIconClass(module.status)">
              <CheckCircleOutlined v-if="module.status === 'done'" class="text-[12px] text-white" />
              <span v-else-if="module.status === 'active'" class="h-2.5 w-2.5 rounded-full bg-white animate-pulse"></span>
              <span v-else class="h-2 w-2 rounded-full bg-slate-400"></span>
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="text-[13px] font-semibold" :class="moduleTitleClass(module.status)">{{ module.label }}</span>
                <span v-if="module.entry?.timestamp" class="text-[10px] tabular-nums text-slate-400">
                  {{ (module.entry.timestamp / 1000).toFixed(1) }}s
                </span>
                <span
                  v-if="module.status === 'active'"
                  class="rounded-full border border-blue-100/80 bg-blue-50/70 px-2 py-0.5 text-[10px] font-semibold text-blue-600"
                >提取中</span>
                <span
                  v-else-if="module.status === 'done'"
                  class="rounded-full border border-slate-200/80 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold text-slate-500"
                >已完成</span>
              </div>

              <div v-if="module.entry?.preview?.length" class="mt-1.5 flex flex-wrap gap-1.5">
                <span
                  v-for="(preview, pi) in module.entry.preview"
                  :key="pi"
                  class="max-w-[220px] truncate rounded-full border border-slate-200/80 bg-white px-2.5 py-0.5 text-[11px] leading-5 text-slate-600"
                >{{ preview }}</span>
              </div>
              <div v-else class="mt-1.5 text-[11px] text-slate-400">
                {{ module.status === 'active' ? '正在解析当前模块字段...' : '等待提取' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="draft">
      <div class="frontpage-workspace-panel__tabs-shell">
      <a-tabs class="frontpage-workspace-panel__tabs" :activeKey="frontpageTab" size="small" @update:activeKey="onTabChange">
        <a-tab-pane key="fields" tab="提取结果">
          <div class="mb-3 flex flex-wrap items-center gap-2.5 rounded-[16px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(255,255,255,0.98)_100%)] px-4 py-2.5 shadow-[0_6px_16px_rgba(15,23,42,0.03)]">
            <div class="flex h-7 w-7 items-center justify-center rounded-[10px] bg-blue-500/95 shadow-[0_6px_14px_rgba(37,99,235,0.1)]">
              <CheckCircleOutlined class="text-sm text-white" />
            </div>
            <div class="flex-1">
              <div class="text-[13px] font-bold text-slate-800">病案首页提取完成</div>
              <div class="mt-0.5 text-xs text-slate-400">已从病历中提取 {{ completedCount }} 个模块的结构化字段信息</div>
            </div>
            <div class="flex flex-wrap gap-2">
              <a-button size="small" class="!rounded-full !border-slate-200/80 !bg-white !shadow-none" @click="$emit('export-frontpage', 'health')">
                <template #icon><DownloadOutlined /></template>
                导出
              </a-button>
              <a-button size="small" type="primary" class="!rounded-full !shadow-[0_6px_14px_rgba(37,99,235,0.14)]" @click="$emit('save-frontpage')">
                <template #icon><SaveOutlined /></template>
                保存到数据库
              </a-button>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-2 xl:grid-cols-2">
            <div
              v-for="module in moduleCards"
              :key="module.key"
              class="rounded-[14px] border border-slate-200/80 bg-white/86 px-3 py-2.5 shadow-[0_4px_12px_rgba(15,23,42,0.02)]"
            >
              <div class="mb-1.5 flex items-center gap-2">
                <div class="flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full bg-blue-500/95">
                  <CheckCircleOutlined class="text-[10px] text-white" />
                </div>
                <span class="text-[13px] font-medium text-slate-700">{{ module.label }}</span>
                <span v-if="module.entry?.timestamp" class="text-[10px] tabular-nums text-slate-400">
                  {{ (module.entry.timestamp / 1000).toFixed(1) }}s
                </span>
                <span v-if="!module.entry?.preview?.length" class="text-[10px] italic text-slate-400">未提取到数据</span>
              </div>
              <div v-if="module.entry?.preview?.length" class="flex flex-wrap gap-1.5 pl-6">
                <span
                  v-for="(preview, pi) in module.entry.preview"
                  :key="pi"
                  class="max-w-[260px] truncate rounded-md border border-slate-200/80 bg-white px-2 py-0.5 text-[11px] leading-5 text-slate-600"
                >{{ preview }}</span>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <a-tab-pane key="preview" tab="首页预览/打印">
          <FrontpageSheet v-if="draftSheetData" :data="draftSheetData" :post-processing="postProcessing" />
          <div v-else class="py-12 text-center text-slate-400">尚未生成病案首页，请点击右上角"AI 生成首页"</div>
        </a-tab-pane>

        <a-tab-pane key="official" tab="系统首页">
          <div v-if="sheetLoading" class="flex items-center justify-center py-12">
            <a-spin />
          </div>
          <FrontpageSheet v-else-if="sheetData" :data="sheetData" :post-processing="false" />
          <div v-else class="py-12 text-center text-slate-400">暂无数据库首页数据</div>
        </a-tab-pane>
      </a-tabs>
      </div>
    </div>

    <div v-else>
      <div v-if="sheetLoading" class="flex flex-col items-center py-20">
        <a-spin size="large" />
        <div class="mt-4 text-sm text-slate-400">加载病案首页数据中...</div>
      </div>
      <div v-else-if="sheetData">
        <FrontpageSheet :data="sheetData" :post-processing="false" />
      </div>
      <div v-else class="flex flex-col items-center justify-center rounded-[20px] border border-dashed border-slate-200 bg-slate-50/65 py-20 text-slate-300">
        <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-full border-2 border-dashed border-slate-200 bg-white">
          <FileTextOutlined class="text-3xl" />
        </div>
        <div class="mb-1 text-sm font-medium text-slate-500">暂无病案首页数据</div>
        <div class="text-xs text-slate-400">可点击右上角“AI 生成首页”按钮，从病历中自动提取生成</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircleOutlined,
  DownloadOutlined,
  FileTextOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

import FrontpageSheet from './FrontpageSheet.vue'

type ModuleStatus = 'done' | 'active' | 'pending'

interface ModuleEntry {
  preview?: string[]
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
  frontpageTab: string
  moduleCards: ModuleCard[]
  completedCount: number
  totalCount: number
  sheetLoading: boolean
  sheetData: any
}>()

const emit = defineEmits<{
  'update:frontpageTab': [value: string]
  'export-frontpage': [format: 'health' | 'insurance' | 'settlement']
  'save-frontpage': []
}>()

const progressPercent = computed(() => {
  if (!props.totalCount) return 0
  return Math.round((props.completedCount / props.totalCount) * 100)
})

/** 将 AI 抽取的 draft 转换为 FrontpageSheet 所需的格式 */
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
  // 诊断列表
  const diagnoses: any[] = []
  if (diag.discharge_main_diagnosis_text) {
    diagnoses.push({ diagnosis_type: '主要诊断', diagnosis_name: diag.discharge_main_diagnosis_text, diagnosis_code: diag.discharge_main_icd || '', admission_condition: diag.admission_condition || '' })
  }
  const others: string[] = diag.discharge_other_diagnoses_texts || []
  const otherIcds: string[] = diag.discharge_other_icds || []
  others.forEach((name: string, i: number) => {
    diagnoses.push({ diagnosis_type: '其他诊断', diagnosis_name: name, diagnosis_code: otherIcds[i] || '', admission_condition: '' })
  })
  // 手术列表
  const surgeries: any[] = []
  if (proc.main_procedure_text) {
    surgeries.push({ surgery_code: proc.main_procedure_code || '', surgery_name: proc.main_procedure_text, surgery_begin_datetime: proc.main_procedure_date || '', surgical_level: proc.main_procedure_level || '', surgeon: proc.surgeon_name || '', first_assistant: proc.assistant1_name || '', second_assistant: proc.assistant2_name || '', anesthesia_method: proc.anesthesia_method || '', anesthesiologist: proc.anesthetist_name || '', surgial_incision_level: proc.incision_grade || '', surgical_incisionheal_level: proc.incision_healing_grade || '' })
  }
  ;(proc.other_procedures || []).forEach((p: any) => {
    surgeries.push({ surgery_code: p.code || '', surgery_name: p.text || p.name || '', surgery_begin_datetime: p.date || '', surgical_level: '', surgeon: '', first_assistant: '', second_assistant: '', anesthesia_method: '', anesthesiologist: '' })
  })
  // 费用
  const cats = co.categories || {}
  const cost: Record<string, any> = { total_cost: co.total_cost ?? '', self_pay: co.self_paid ?? '', general_medical_service_fee: cats.general_medical_service ?? '', general_treatment_fee: cats.general_treatment ?? '', nursing_care_fee: cats.nursing_care ?? '', other_service_fee: cats.other_service ?? '', pathological_diagnostic_fee: cats.pathological_diagnostic ?? '', laboratory_diagnostic_fee: cats.laboratory_diagnostic ?? '', imaging_diagnostic_fee: cats.imaging_diagnostic ?? '', clinical_diagnostic_fee: cats.clinical_diagnostic ?? '', nonsurgical_treatment_fee: cats.nonsurgical_treatment ?? '', clinical_physical_therapy_fee: cats.clinical_physical_therapy ?? '', surgery_treatment_fee: cats.surgery_treatment ?? '', anesthesia_fee: cats.anesthesia ?? '', surgery_fee: cats.surgery ?? '', rehabilitation_fee: cats.rehabilitation ?? '', western_medicine_fee: cats.western_medicine ?? '', antibacterial_drug_fee: cats.antibacterial_drug ?? '', chinese_patent_medcine_fee: cats.chinese_patent_medicine ?? '', chinese_herbal_medicine_fee: cats.chinese_herbal_medicine ?? '', blood_fee: cats.blood ?? '', exam_disposable_mat_fee: cats.exam_disposable_material ?? '', treat_disposable_mat_fee: cats.treat_disposable_material ?? '', surgery_disposable_mat_fee: cats.surgery_disposable_material ?? '', other_fee: cats.other ?? '' }
  // 基本信息
  const basic: Record<string, any> = { name: bi.patient_name || '', sex: bi.gender || '', birthday: bi.birth_date || '', id_card_no: bi.id_number || '', marital_status: bi.marital_status || '', nationality: bi.nationality || '中国', ethnicity: bi.ethnicity || '', occupation_category: bi.occupation || '', nativeplace: bi.nativeplace || '', currentaddress: bi.current_address || '', contact_name: bi.contact_name || '', contact_relationship: bi.contact_relation || '', contact_telephone: bi.contact_phone || '', contact_address: bi.contact_address || '', work_unit: bi.work_unit || '', admission_datetime: ho.admission_datetime || '', discharge_datetime: ho.discharge_datetime || '', admission_dept_name: ho.admission_dept || '', discharge_dept_name: ho.discharge_dept || '', admission_ward_name: ho.admission_ward || '', discharge_ward_name: ho.discharge_ward || '', hospital_duration: ho.actual_hospital_days ?? '', medical_payment_method: ho.payment_method_text || '', admission_route: ho.admission_way_text || '', leaving_hospital_way: ho.leaving_hospital_way || '', transfer_dept_name: ho.transfer_dept || '', document_id: ho.medical_record_no || '', visit_cnt: ho.admission_times_in_hospital || '', rehospital_with_month: ho.rehospital_within_month || '', allergy_sign: omi.drug_allergy_flag || '', abo_blood_code: omi.abo_blood_type || '', rh_blood_code: omi.rh_blood_type || '', deptdirector_sign: st.dept_director || '', chief_physician_sign: st.chief_physician || '', attending_physician_sign: st.attending_physician || '', resident_physician_sign: st.resident_physician || '', responsible_nurse_sign: st.responsible_nurse || '', coder_sign: st.coder || '', medicalrecord_quality: st.medical_record_quality || '' }
  const evidence = d.evidence || {}
  return { basic, diagnoses, surgeries, cost, evidence }
})

function onTabChange(tab: string) {
  emit('update:frontpageTab', tab)
}

function moduleCardClass(status: ModuleStatus) {
  if (status === 'done') {
    return 'border-slate-200/85 bg-[linear-gradient(180deg,rgba(252,253,255,0.96)_0%,rgba(255,255,255,0.98)_100%)] shadow-[0_8px_18px_rgba(15,23,42,0.03)]'
  }
  if (status === 'active') {
    return 'border-blue-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.96)_0%,rgba(255,255,255,0.98)_100%)] shadow-[0_10px_22px_rgba(37,99,235,0.08)]'
  }
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

<style scoped>
.frontpage-workspace-panel__tabs-shell {
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: linear-gradient(180deg, rgba(250, 252, 255, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.03);
  padding: 10px 10px 8px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav) {
  margin: 0 0 12px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav::before) {
  display: none;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav-wrap) {
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.88);
  border-radius: 999px;
  padding: 4px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav-list) {
  gap: 4px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab) {
  margin: 0 !important;
  border-radius: 999px;
  padding: 8px 14px;
  color: #64748b;
  transition: all 0.18s ease;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab:hover) {
  color: #1e293b;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab.ant-tabs-tab-active) {
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #0f172a;
  font-weight: 700;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-ink-bar) {
  display: none;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-content-holder) {
  padding: 0 2px 2px;
}
</style>
