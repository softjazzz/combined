<template>
  <a-drawer
    :open="open"
    title="招标字段生成验证"
    width="720"
    root-class-name="frontpage-validation-drawer"
    destroy-on-close
    @update:open="emit('update:open', $event)"
  >
    <div class="frontpage-validation-body space-y-4">
      <a-alert
        type="info"
        show-icon
        message="粘贴病历文本验证"
        description="该入口仅调用生成草稿接口验证招标字段抽取覆盖情况，不选择病历、不写入正式首页表或结算表。"
      />

      <section
        class="rounded border border-sky-100 bg-sky-50/60 p-3"
        data-testid="frontpage-demo-presets"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="text-sm font-semibold text-slate-900">预置病历示例</div>
            <div class="mt-1 text-xs text-slate-600">
              从本机候选 visit_id 加载演示输入，虚拟费用仅参与本次草稿生成。
            </div>
          </div>
          <a-button
            size="small"
            :disabled="!selectedPreset || validating"
            data-testid="preset-generate"
            @click="startValidation"
          >
            直接生成
          </a-button>
        </div>

        <div class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          <button
            v-for="preset in frontpageDemoPresets"
            :key="preset.id"
            type="button"
            class="rounded border bg-white p-3 text-left transition hover:border-sky-300 hover:bg-white"
            :class="
              selectedPresetId === preset.id ? 'border-sky-400 shadow-sm' : 'border-slate-200'
            "
            :data-testid="`frontpage-demo-preset-${preset.id}`"
            @click="loadPreset(preset.id)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="truncate text-sm font-semibold text-slate-900">
                  {{ preset.title }}
                </div>
                <div class="mt-1 text-xs leading-5 text-slate-600">
                  {{ preset.description }}
                </div>
              </div>
              <span class="shrink-0 rounded bg-sky-100 px-2 py-0.5 text-xs text-sky-700">
                加载示例
              </span>
            </div>
            <div class="mt-2 flex flex-wrap gap-1">
              <span
                v-for="tag in preset.tags"
                :key="tag"
                class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
              >
                {{ tag }}
              </span>
            </div>
          </button>
        </div>

        <a-alert
          v-if="selectedPreset"
          class="mt-3"
          type="warning"
          show-icon
          message="已加载本机病历示例"
          description="病历全文由后端按 visit_id 从本机读取；演示用医保费用只是补充信息，不写入正式数据表。"
        />

        <a-spin :spinning="previewLoading">
          <div v-if="selectedPreset" class="mt-3 space-y-3" data-testid="preset-source-summary">
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="mb-2 text-xs font-semibold text-slate-700">病历来源摘要</div>
              <div class="grid grid-cols-2 gap-2 text-xs text-slate-600 md:grid-cols-3">
                <div>
                  <span class="text-slate-400">visit_id</span>
                  <div class="mt-0.5 font-medium text-slate-900">
                    {{ selectedPreset.visit_id }}
                  </div>
                </div>
                <div>
                  <span class="text-slate-400">patient_id</span>
                  <div class="mt-0.5 font-medium text-slate-900">
                    {{ presetPreview?.patient_id_masked || maskPresetPatientId(selectedPreset) }}
                  </div>
                </div>
                <div>
                  <span class="text-slate-400">患者</span>
                  <div class="mt-0.5 font-medium text-slate-900">
                    {{ presetPreview?.patient_name_masked || '-' }}
                  </div>
                </div>
                <div>
                  <span class="text-slate-400">科室</span>
                  <div class="mt-0.5 font-medium text-slate-900">
                    {{ presetPreview?.department || '-' }}
                  </div>
                </div>
                <div>
                  <span class="text-slate-400">入院</span>
                  <div class="mt-0.5 font-medium text-slate-900">
                    {{ presetPreview?.admission_date || '-' }}
                  </div>
                </div>
                <div>
                  <span class="text-slate-400">出院</span>
                  <div class="mt-0.5 font-medium text-slate-900">
                    {{ presetPreview?.discharge_date || '-' }}
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="mb-2 flex items-center justify-between gap-2">
                <span class="text-xs font-semibold text-slate-700">文书类型</span>
                <span class="text-xs text-slate-500">
                  {{ presetPreview?.document_count ?? 0 }} 份
                </span>
              </div>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="docType in presetPreview?.document_types || []"
                  :key="docType"
                  class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                >
                  {{ docType }}
                </span>
                <span
                  v-if="!(presetPreview?.document_types || []).length"
                  class="text-xs text-slate-400"
                >
                  暂无可展示文书类型
                </span>
              </div>
            </div>

            <a-collapse>
              <a-collapse-panel key="preview" header="脱敏病历预览">
                <pre
                  class="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs leading-5 text-slate-700"
                  data-testid="preset-text-preview"
                  >{{ presetPreview?.text_preview || previewFallbackText }}</pre
                >
              </a-collapse-panel>
            </a-collapse>

            <div
              class="rounded border border-amber-100 bg-amber-50 p-3"
              data-testid="preset-synthetic-settlement"
            >
              <div class="mb-2 text-xs font-semibold text-amber-900">演示用医保费用补充</div>
              <pre class="m-0 whitespace-pre-wrap text-xs leading-5 text-amber-900">{{
                selectedPreset.synthetic_settlement_text
              }}</pre>
            </div>
          </div>
        </a-spin>
      </section>

      <a-form layout="vertical">
        <a-form-item label="场景选择">
          <a-radio-group v-model:value="scene" button-style="solid">
            <a-radio-button value="combined"> 联合草稿 </a-radio-button>
            <a-radio-button value="nhc_frontpage"> 病案首页 </a-radio-button>
            <a-radio-button value="insurance_settlement"> 医保结算清单 </a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="medical_text">
          <div
            v-if="selectedPreset"
            class="mb-2 rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
          >
            该示例将由后端按 visit_id 读取本机病历全文；上方仅展示脱敏预览，演示费用补充会作为
            documents 追加。
          </div>
          <a-textarea
            v-if="!selectedPreset"
            v-model:value="medicalText"
            :auto-size="{ minRows: 10, maxRows: 18 }"
            placeholder="请粘贴完整病历文本，用于验证病案首页招标字段生成能力"
          />
          <div
            v-else
            class="rounded border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600"
            data-testid="medical-text-preset-readonly"
          >
            该示例将由后端按 visit_id 读取本机病历全文；下方仅展示脱敏预览。
          </div>
        </a-form-item>

        <div class="flex items-center gap-2">
          <a-button type="primary" :loading="validating" @click="startValidation">
            开始验证
          </a-button>
          <a-button :disabled="validating" @click="clearValidation"> 清空 </a-button>
        </div>
      </a-form>

      <a-spin :spinning="validating">
        <div v-if="result" class="space-y-4">
          <a-alert
            v-if="resultUsedSynthetic"
            type="warning"
            show-icon
            message="包含演示用虚拟医保费用数据"
            description="该数据仅用于本次生成草稿验证，不写入正式首页表、结算表或业务库。"
          />

          <a-alert
            v-if="inputContext?.manual_text_too_short"
            type="warning"
            show-icon
            message="当前粘贴文本偏短"
            description="本次 medical_text 少于 500 字，可能不是完整病历。建议粘贴完整入院记录、出院记录、手术记录等文书后再验证。"
            data-testid="short-medical-text-warning"
          />

          <div
            v-if="inputContext"
            class="grid grid-cols-2 gap-2 rounded border border-slate-200 bg-white p-3 text-xs text-slate-600 md:grid-cols-4"
            data-testid="input-context-summary"
          >
            <div>
              <span class="text-slate-400">输入来源</span>
              <div class="mt-0.5 font-semibold text-slate-900">
                {{ inputModeLabel }}
              </div>
            </div>
            <div>
              <span class="text-slate-400">抽取文本长度</span>
              <div class="mt-0.5 font-semibold text-slate-900">
                {{ inputContext.text_length }} 字
              </div>
            </div>
            <div>
              <span class="text-slate-400">visit_id</span>
              <div class="mt-0.5 font-semibold text-slate-900">
                {{ inputContext.has_visit_id ? '已提供' : '未提供' }}
              </div>
            </div>
            <div>
              <span class="text-slate-400">补充 documents</span>
              <div class="mt-0.5 font-semibold text-slate-900">
                {{ inputContext.document_count ?? 0 }} 份
              </div>
            </div>
          </div>

          <div
            class="flex flex-wrap items-center justify-between gap-2 rounded border border-blue-100 bg-blue-50 px-3 py-2"
          >
            <div>
              <div class="text-sm font-semibold text-slate-900">格式化生成结果</div>
              <div class="mt-0.5 text-xs text-slate-600">
                使用现有病案首页和医保结算清单官方表格样式预览本次草稿。
              </div>
            </div>
            <a-button
              type="primary"
              ghost
              data-testid="open-formatted-preview"
              @click="openFormattedPreview"
            >
              查看格式化结果
            </a-button>
          </div>

          <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="text-xs font-medium text-slate-500">文本抽取覆盖率</div>
              <div class="mt-1 text-xl font-semibold text-slate-900">
                {{ textExtractionLabel }}
              </div>
              <div class="mt-1 text-xs text-slate-500">
                {{ textExtractionDesc }}
              </div>
            </div>
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="text-xs font-medium text-slate-500">结算草稿映射</div>
              <div class="mt-1 text-xl font-semibold text-slate-900">
                {{ settlementLabel }}
              </div>
              <div class="mt-1 text-xs text-slate-500">settlement_from_frontpage_success</div>
            </div>
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="text-xs font-medium text-slate-500">缺失字段</div>
              <div class="mt-1 text-xl font-semibold text-slate-900">
                {{ missingFields.length }}
              </div>
              <div class="mt-1 text-xs text-slate-500">coverage 字段状态为 missing</div>
            </div>
          </div>

          <a-alert v-if="warnings.length" type="warning" show-icon message="warnings">
            <template #description>
              <ul class="m-0 list-disc pl-4 text-xs leading-5">
                <li v-for="warning in warnings" :key="warning">
                  {{ warning }}
                </li>
              </ul>
            </template>
          </a-alert>

          <div class="rounded border border-slate-200 bg-white p-3">
            <div class="mb-2 text-sm font-semibold text-slate-800">失败 / 缺失字段</div>
            <a-empty v-if="!missingFields.length" description="当前 coverage 未返回缺失字段" />
            <div v-else class="space-y-2">
              <div
                v-for="field in missingFields"
                :key="field.path"
                class="rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-900"
              >
                <div class="font-semibold">{{ field.group }} / {{ field.field }}</div>
                <div class="mt-1 text-amber-800">
                  {{ field.path }}{{ field.message ? `：${field.message}` : '' }}
                </div>
              </div>
            </div>
          </div>

          <a-collapse>
            <a-collapse-panel key="frontpage" header="病案首页草稿">
              <pre class="max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{{
                stringifyJson(result.frontpage)
              }}</pre>
            </a-collapse-panel>
            <a-collapse-panel key="settlement" header="医保结算清单草稿">
              <pre class="max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{{
                stringifyJson(result.settlement)
              }}</pre>
            </a-collapse-panel>
            <a-collapse-panel key="coverage" header="coverage 明细">
              <pre class="max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{{
                stringifyJson(result.coverage)
              }}</pre>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </a-spin>
    </div>
  </a-drawer>

  <a-modal
    v-model:open="formattedPreviewOpen"
    title="格式化生成结果"
    :width="'96vw'"
    wrap-class-name="frontpage-formatted-preview-modal"
    :footer="null"
    :body-style="{
      maxHeight: 'calc(100vh - 150px)',
      overflowY: 'auto',
      background: '#f5f5f7',
      padding: '16px',
    }"
    destroy-on-close
  >
    <a-alert
      v-if="resultUsedSynthetic"
      class="mb-3"
      type="warning"
      show-icon
      message="包含演示用虚拟医保费用数据"
      description="该数据仅用于本次生成草稿验证，不写入正式首页表、结算表或业务库。"
    />
    <a-tabs v-model:active-key="formattedPreviewTab">
      <a-tab-pane key="frontpage" tab="病案首页">
        <div
          class="rounded border border-slate-200 bg-white p-3"
          data-testid="formatted-frontpage-preview"
        >
          <FrontpageSheet
            v-if="formattedFrontpageData"
            :data="formattedFrontpageData"
            :post-processing="false"
          />
          <a-empty v-else description="暂无病案首页草稿" />
        </div>
      </a-tab-pane>
      <a-tab-pane key="settlement" tab="医保结算清单">
        <div
          class="rounded border border-slate-200 bg-white p-3"
          data-testid="formatted-settlement-preview"
        >
          <SettlementSheet v-if="formattedSettlementData" :data="formattedSettlementData" />
          <a-empty v-else description="当前场景未返回医保结算清单草稿" />
        </div>
      </a-tab-pane>
      <a-tab-pane key="json" tab="原始 JSON">
        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2" data-testid="formatted-json-preview">
          <div class="rounded border border-slate-200 bg-white p-3">
            <div class="mb-2 text-sm font-semibold text-slate-800">病案首页草稿</div>
            <pre
              class="max-h-[60vh] overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700"
              >{{ stringifyJson(result?.frontpage) }}</pre
            >
          </div>
          <div class="rounded border border-slate-200 bg-white p-3">
            <div class="mb-2 text-sm font-semibold text-slate-800">医保结算清单草稿</div>
            <pre
              class="max-h-[60vh] overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700"
              >{{ stringifyJson(result?.settlement) }}</pre
            >
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import FrontpageSheet from './FrontpageSheet.vue'
import SettlementSheet from './SettlementSheet.vue'
import {
  frontpageApi,
  type FrontpageDemoVisitPreview,
  type FrontpageReportScene,
  type GenerateReportDraftRequest,
  type GenerateReportDraftResponse,
} from '@/api/frontpage'
import {
  frontpageDemoPresets,
  type FrontpageDemoPreset,
} from '@/views/workstation-v4/data/frontpageDemoPresets'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

type ReportDraftData = NonNullable<GenerateReportDraftResponse['data']>

const scene = ref<FrontpageReportScene>('combined')
const medicalText = ref('')
const validating = ref(false)
const result = ref<ReportDraftData | null>(null)
const selectedPresetId = ref('')
const resultUsedSynthetic = ref(false)
const previewLoading = ref(false)
const presetPreview = ref<FrontpageDemoVisitPreview | null>(null)
const previewError = ref('')
const formattedPreviewOpen = ref(false)
const formattedPreviewTab = ref<'frontpage' | 'settlement' | 'json'>('frontpage')

const coverage = computed(() => result.value?.coverage)
const inputContext = computed(() => result.value?.input_context)

const inputModeLabel = computed(() => {
  const mode = inputContext.value?.mode
  if (mode === 'medical_text') return '手动粘贴 medical_text'
  if (mode === 'visit_id_with_documents') return '本机 visit_id + 补充 documents'
  if (mode === 'visit_id') return '本机 visit_id'
  if (mode === 'documents') return '补充 documents'
  return mode || '-'
})

const selectedPreset = computed(() =>
  frontpageDemoPresets.find((preset) => preset.id === selectedPresetId.value),
)

const previewFallbackText = computed(
  () =>
    previewError.value ||
    '暂未获取到脱敏病历预览，请确认本机 CDM 中存在该 visit_id。直接生成仍会按 visit_id 读取后端病历上下文。',
)

const warnings = computed(() => {
  const items = result.value?.warnings || coverage.value?.warnings || []
  return items.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
})

const missingFields = computed(() => {
  const fields = coverage.value?.fields || []
  return fields.filter((field) => field.status === 'missing')
})

const textExtractionLabel = computed(() => {
  const metric = coverage.value?.text_extraction
  const success = metric?.success ?? metric?.present
  const total = metric?.total ?? coverage.value?.total
  if (typeof success === 'number' && typeof total === 'number') {
    return `${success}/${total}`
  }
  if (coverage.value) {
    return `${coverage.value.present}/${coverage.value.total}`
  }
  return '-'
})

const textExtractionDesc = computed(() => {
  const total = coverage.value?.text_extraction?.total ?? coverage.value?.total
  return typeof total === 'number' ? `text_extraction_success / tender_field_total` : '等待验证结果'
})

const settlementLabel = computed(() => {
  const metric = coverage.value?.settlement_from_frontpage
  const success = metric?.success ?? metric?.present
  const total = metric?.total
  if (typeof success === 'number' && typeof total === 'number') {
    return `${success}/${total}`
  }
  return result.value?.settlement ? '已生成' : '-'
})

const formattedFrontpageData = computed(() => {
  if (!result.value?.frontpage) return null
  return adaptFrontpageDraftToSheetData(result.value.frontpage)
})

const formattedSettlementData = computed(() => {
  if (!result.value?.settlement) return null
  return result.value.settlement
})

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object',
      )
    : []
}

function textValue(...values: unknown[]): string {
  for (const value of values) {
    if (value === undefined || value === null) continue
    const text = String(value).trim()
    if (text) return text
  }
  return ''
}

function textArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => textValue(item)).filter((item) => item.length > 0)
    : []
}

function pairRows(names: string[], codes: string[]) {
  return names.map((name, index) => ({
    name,
    code: codes[index] || '',
  }))
}

function adaptFrontpageDraftToSheetData(frontpage: ReportDraftData['frontpage']) {
  const basicInfo = asRecord(frontpage.basic_info)
  const hospitalization = asRecord(frontpage.hospitalization)
  const diagnoses = asRecord(frontpage.diagnoses)
  const procedures = asRecord(frontpage.procedures)
  const otherMedicalInfo = asRecord(frontpage.other_medical_info)
  const staff = asRecord(frontpage.staff)
  const costs = asRecord(frontpage.costs)

  const diagnosisRows = []
  const mainDiagnosis = textValue(
    diagnoses.discharge_main_diagnosis_text,
    diagnoses.discharge_main_diagnosis,
  )
  if (mainDiagnosis) {
    diagnosisRows.push({
      diagnosis_type: '主要诊断',
      diagnosis_name: mainDiagnosis,
      diagnosis_code: textValue(diagnoses.discharge_main_icd),
      admission_condition: textValue(diagnoses.admission_condition),
    })
  }
  const otherDiagnosisRows = pairRows(
    textArray(diagnoses.discharge_other_diagnoses_texts),
    textArray(diagnoses.discharge_other_icds),
  )
  otherDiagnosisRows.forEach((item) => {
    diagnosisRows.push({
      diagnosis_type: '其他诊断',
      diagnosis_name: item.name,
      diagnosis_code: item.code,
      admission_condition: '',
    })
  })

  const surgeryRows = []
  const mainProcedure = textValue(procedures.main_procedure_text)
  if (mainProcedure) {
    surgeryRows.push({
      surgery_name: mainProcedure,
      surgery_code: textValue(procedures.main_procedure_code),
      surgery_begin_datetime: textValue(procedures.main_procedure_date),
      surgical_level: textValue(procedures.main_procedure_level),
      surgeon: textValue(procedures.surgeon_name),
      surgeon_code: textValue(procedures.surgeon_code),
      first_assistant: textValue(procedures.assistant1_name),
      first_assistant_code: textValue(procedures.assistant1_code),
      second_assistant: textValue(procedures.assistant2_name),
      second_assistant_code: textValue(procedures.assistant2_code),
      surgical_incisionheal_level: textValue(procedures.incision_healing_grade),
      anesthesia_method: textValue(procedures.anesthesia_method),
      anesthesiologist: textValue(procedures.anesthetist_name),
      anesthesiologist_code: textValue(procedures.anesthetist_code),
    })
  }
  const structuredOthers = asRecords(procedures.other_procedures_structured)
  const otherProcedureNames = textArray(procedures.other_procedures_texts)
  const otherProcedureCodes = textArray(procedures.other_procedures_codes)
  const otherProcedures = structuredOthers.length
    ? structuredOthers
    : pairRows(otherProcedureNames, otherProcedureCodes)
  otherProcedures.forEach((item) => {
    const name = textValue(item.text, item.name, item.surgery_name)
    if (!name) return
    surgeryRows.push({
      surgery_name: name,
      surgery_code: textValue(item.code, item.surgery_code),
      surgery_begin_datetime: textValue(item.date, item.surgery_begin_datetime),
      surgical_level: textValue(item.level, item.surgical_level),
      surgeon: textValue(item.surgeon, item.surgeon_name),
      surgeon_code: textValue(item.surgeon_code),
      first_assistant: textValue(item.first_assistant, item.assistant1_name),
      first_assistant_code: textValue(item.first_assistant_code, item.assistant1_code),
      second_assistant: textValue(item.second_assistant, item.assistant2_name),
      second_assistant_code: textValue(item.second_assistant_code, item.assistant2_code),
      surgical_incisionheal_level: textValue(
        item.surgical_incisionheal_level,
        item.incision_healing_grade,
      ),
      anesthesia_method: textValue(item.anesthesia_method),
      anesthesiologist: textValue(item.anesthesiologist, item.anesthetist_name),
      anesthesiologist_code: textValue(item.anesthesiologist_code, item.anesthetist_code),
    })
  })

  return {
    basic: {
      institute_county_desc: textValue(hospitalization.hospital_name),
      institute_code: textValue(hospitalization.organization_code),
      medical_payment_method: textValue(
        hospitalization.payment_method_text,
        hospitalization.payment_method,
      ),
      mr_no: textValue(hospitalization.medical_record_no),
      visit_cnt: textValue(hospitalization.admission_times_in_hospital),
      name: textValue(basicInfo.patient_name),
      sex: textValue(basicInfo.gender_text, basicInfo.gender),
      birthday: textValue(basicInfo.birth_date),
      age: textValue(basicInfo.age_years),
      nationality: textValue(basicInfo.nationality),
      ethnicity: textValue(basicInfo.ethnicity),
      id_card_no: textValue(basicInfo.id_number),
      occupation_category: textValue(basicInfo.occupation),
      marital_status: textValue(basicInfo.marital_status_text, basicInfo.marital_status),
      currentaddress: textValue(basicInfo.current_address),
      work_unit: textValue(basicInfo.work_unit, basicInfo.work_unit_address),
      nativeplace: textValue(basicInfo.nativeplace, basicInfo.birthplace),
      contact_name: textValue(basicInfo.contact_name),
      contact_relationship: textValue(basicInfo.contact_relation),
      contact_address: textValue(basicInfo.contact_address),
      contact_telephone: textValue(basicInfo.contact_phone),
      admission_route: textValue(hospitalization.admission_way_text, hospitalization.admission_way),
      admission_dept_name: textValue(hospitalization.admission_dept),
      admission_ward_name: textValue(hospitalization.admission_ward),
      discharge_dept_name: textValue(hospitalization.discharge_dept),
      discharge_ward_name: textValue(hospitalization.discharge_ward),
      transfer_dept_name: textValue(hospitalization.transfer_dept),
      admission_datetime: textValue(hospitalization.admission_datetime),
      discharge_datetime: textValue(hospitalization.discharge_datetime),
      hospital_duration: textValue(hospitalization.actual_hospital_days),
      leaving_hospital_way: textValue(hospitalization.leaving_hospital_way),
      rehospital_with_month: textValue(hospitalization.rehospital_within_month),
      pathology_id: textValue(otherMedicalInfo.pathology_no),
      allergy_sign: textValue(otherMedicalInfo.drug_allergy_flag, otherMedicalInfo.drug_allergy),
      abo_blood_code: textValue(otherMedicalInfo.abo_blood_type),
      rh_blood_code: textValue(otherMedicalInfo.rh_blood_type),
      deptdirector_sign: textValue(staff.dept_director),
      chief_physician_sign: textValue(staff.chief_physician),
      attending_physician_sign: textValue(staff.attending_physician),
      resident_physician_sign: textValue(staff.resident_physician),
      responsible_nurse_sign: textValue(staff.responsible_nurse),
      coder_sign: textValue(staff.coder),
      medicalrecord_quality: textValue(staff.medical_record_quality),
    },
    diagnoses: diagnosisRows,
    surgeries: surgeryRows,
    cost: {
      total_cost: textValue(costs.total_cost, costs.total),
      self_pay: textValue(costs.self_paid, costs.self_pay),
    },
    other_medical_info: otherMedicalInfo,
    evidence: frontpage.evidence || {},
  }
}

function maskPresetPatientId(preset: FrontpageDemoPreset) {
  const text = preset.patient_id || ''
  if (!text) return '-'
  if (text.length <= 4) return '*'.repeat(text.length)
  return `${text.slice(0, 2)}${'*'.repeat(Math.max(2, text.length - 4))}${text.slice(-2)}`
}

async function loadPreset(presetId: string) {
  const preset = frontpageDemoPresets.find((item) => item.id === presetId)
  if (!preset) return
  selectedPresetId.value = preset.id
  scene.value = preset.scene
  medicalText.value = ''
  result.value = null
  resultUsedSynthetic.value = false
  presetPreview.value = null
  previewError.value = ''
  message.success('已加载预置示例')

  previewLoading.value = true
  try {
    const response = await frontpageApi.getDemoVisitPreview({
      visit_id: preset.visit_id,
      patient_id: preset.patient_id,
    })
    if (!response.success || !response.data) {
      throw new Error(response.error || response.message || '脱敏病历预览加载失败')
    }
    presetPreview.value = response.data
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    previewError.value =
      status === 404
        ? '当前后端尚未启用脱敏病历预览接口；该示例仍会按 visit_id 从后端读取本机病历全文，直接生成不受影响。'
        : error instanceof Error
          ? error.message
          : '脱敏病历预览加载失败'
    message.warning(previewError.value)
  } finally {
    previewLoading.value = false
  }
}

function buildPresetRequest(preset: FrontpageDemoPreset): GenerateReportDraftRequest {
  const request: GenerateReportDraftRequest = {
    scene: scene.value || preset.scene,
    visit_id: preset.visit_id,
  }
  if (preset.patient_id) {
    request.patient_id = preset.patient_id
  }
  request.documents = [
    {
      type: '演示用医保结算补充信息',
      content: preset.synthetic_settlement_text,
      meta: {
        source: 'demo/synthetic',
        preset_id: preset.id,
      },
    },
  ]
  return request
}

function buildManualRequest(): GenerateReportDraftRequest | null {
  const text = medicalText.value.trim()
  if (!text) {
    message.warning('请先粘贴完整病历文本')
    return null
  }
  return {
    scene: scene.value,
    medical_text: text,
  }
}

async function startValidation() {
  const preset = selectedPreset.value
  const request = preset ? buildPresetRequest(preset) : buildManualRequest()
  if (!request) {
    return
  }

  validating.value = true
  try {
    const response = await frontpageApi.generateReportDraft(request)
    if (!response.success || !response.data) {
      throw new Error(response.error || response.message || '招标字段验证失败')
    }
    result.value = response.data
    formattedPreviewOpen.value = false
    formattedPreviewTab.value = response.data.frontpage ? 'frontpage' : 'json'
    resultUsedSynthetic.value = Boolean(preset)
    message.success('招标字段验证完成')
  } catch (error) {
    const reason = error instanceof Error ? error.message : '招标字段验证失败'
    message.error(reason)
  } finally {
    validating.value = false
  }
}

function clearValidation() {
  medicalText.value = ''
  result.value = null
  scene.value = 'combined'
  selectedPresetId.value = ''
  resultUsedSynthetic.value = false
  presetPreview.value = null
  previewError.value = ''
  previewLoading.value = false
  formattedPreviewOpen.value = false
  formattedPreviewTab.value = 'frontpage'
}

function stringifyJson(value: unknown) {
  if (value === undefined || value === null) return 'null'
  return JSON.stringify(value, null, 2)
}

function openFormattedPreview() {
  formattedPreviewTab.value = result.value?.frontpage ? 'frontpage' : 'json'
  formattedPreviewOpen.value = true
}
</script>

<style scoped>
.frontpage-validation-body {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.frontpage-validation-body :deep(.ant-alert),
.frontpage-validation-body :deep(.ant-collapse),
.frontpage-validation-body .rounded {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.045);
}

.frontpage-validation-body button.rounded,
.frontpage-validation-body .grid > .rounded {
  transition:
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.frontpage-validation-body button.rounded:hover,
.frontpage-validation-body .grid > .rounded:hover {
  border-color: rgba(0, 0, 0, 0.14) !important;
  transform: translateY(-2px);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
}

.frontpage-validation-body .text-slate-900,
.frontpage-validation-body .text-slate-800,
.frontpage-validation-body .text-slate-700 {
  color: #1d1d1f !important;
}

.frontpage-validation-body .text-slate-600,
.frontpage-validation-body .text-slate-500,
.frontpage-validation-body .text-slate-400 {
  color: rgba(29, 29, 31, 0.58) !important;
}

.frontpage-validation-body .bg-slate-50,
.frontpage-validation-body .bg-slate-100,
.frontpage-validation-body .bg-sky-50\/60,
.frontpage-validation-body .bg-blue-50,
.frontpage-validation-body .bg-white {
  background: rgba(255, 255, 255, 0.78) !important;
}

.frontpage-validation-body .border-slate-200,
.frontpage-validation-body .border-sky-100,
.frontpage-validation-body .border-blue-100,
.frontpage-validation-body .border-sky-400 {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.frontpage-validation-body :deep(.ant-btn-primary) {
  background: #0066cc !important;
  border-color: #0066cc !important;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.18);
}

.frontpage-validation-body pre {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.72) !important;
  color: rgba(29, 29, 31, 0.78) !important;
  font-family: 'SF Pro Text', 'Source Han Sans SC', 'Cascadia Code', 'Roboto Mono', monospace;
}

:global(.frontpage-validation-drawer .ant-drawer-content),
:global(.frontpage-formatted-preview-modal .ant-modal-content) {
  background: rgba(255, 255, 255, 0.9) !important;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:global(.frontpage-validation-drawer .ant-drawer-body),
:global(.frontpage-formatted-preview-modal .ant-modal-body) {
  background: #f5f5f7 !important;
}

:global(.frontpage-formatted-preview-modal .ant-tabs-tab-active .ant-tabs-tab-btn),
:global(.frontpage-formatted-preview-modal .ant-tabs-tab:hover) {
  color: #0066cc !important;
}

:global(.frontpage-formatted-preview-modal .ant-tabs-ink-bar) {
  background: #0066cc !important;
}
</style>
