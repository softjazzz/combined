<template>
  <a-drawer
    :open="open"
    title="招标字段生成验证"
    width="720"
    destroy-on-close
    @update:open="emit('update:open', $event)"
  >
    <div class="space-y-4">
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
            <div class="text-sm font-semibold text-slate-900">
              预置病历示例
            </div>
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
          message="已加载预置示例"
          description="该示例包含用于演示的虚拟费用/医保字段，不写入正式数据表。"
        />
      </section>

      <a-form layout="vertical">
        <a-form-item label="场景选择">
          <a-radio-group
            v-model:value="scene"
            button-style="solid"
          >
            <a-radio-button value="combined">
              联合草稿
            </a-radio-button>
            <a-radio-button value="nhc_frontpage">
              病案首页
            </a-radio-button>
            <a-radio-button value="insurance_settlement">
              医保结算清单
            </a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="medical_text">
          <div
            v-if="selectedPreset"
            class="mb-2 rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
          >
            当前文本框为预置示例的演示补充信息，将以 documents 方式追加到 visit_id
            病历上下文后参与抽取。
          </div>
          <a-textarea
            v-model:value="medicalText"
            :auto-size="{ minRows: 10, maxRows: 18 }"
            placeholder="请粘贴完整病历文本，或选择上方预置示例后直接生成"
          />
        </a-form-item>

        <div class="flex items-center gap-2">
          <a-button
            type="primary"
            :loading="validating"
            @click="startValidation"
          >
            开始验证
          </a-button>
          <a-button
            :disabled="validating"
            @click="clearValidation"
          >
            清空
          </a-button>
        </div>
      </a-form>

      <a-spin :spinning="validating">
        <div
          v-if="result"
          class="space-y-4"
        >
          <a-alert
            v-if="resultUsedSynthetic"
            type="warning"
            show-icon
            message="包含演示用虚拟医保费用数据"
            description="该数据仅用于本次生成草稿验证，不写入正式首页表、结算表或业务库。"
          />

          <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="text-xs font-medium text-slate-500">
                文本抽取覆盖率
              </div>
              <div class="mt-1 text-xl font-semibold text-slate-900">
                {{ textExtractionLabel }}
              </div>
              <div class="mt-1 text-xs text-slate-500">
                {{ textExtractionDesc }}
              </div>
            </div>
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="text-xs font-medium text-slate-500">
                结算草稿映射
              </div>
              <div class="mt-1 text-xl font-semibold text-slate-900">
                {{ settlementLabel }}
              </div>
              <div class="mt-1 text-xs text-slate-500">
                settlement_from_frontpage_success
              </div>
            </div>
            <div class="rounded border border-slate-200 bg-white p-3">
              <div class="text-xs font-medium text-slate-500">
                缺失字段
              </div>
              <div class="mt-1 text-xl font-semibold text-slate-900">
                {{ missingFields.length }}
              </div>
              <div class="mt-1 text-xs text-slate-500">
                coverage 字段状态为 missing
              </div>
            </div>
          </div>

          <a-alert
            v-if="warnings.length"
            type="warning"
            show-icon
            message="warnings"
          >
            <template #description>
              <ul class="m-0 list-disc pl-4 text-xs leading-5">
                <li
                  v-for="warning in warnings"
                  :key="warning"
                >
                  {{ warning }}
                </li>
              </ul>
            </template>
          </a-alert>

          <div class="rounded border border-slate-200 bg-white p-3">
            <div class="mb-2 text-sm font-semibold text-slate-800">
              失败 / 缺失字段
            </div>
            <a-empty
              v-if="!missingFields.length"
              description="当前 coverage 未返回缺失字段"
            />
            <div
              v-else
              class="space-y-2"
            >
              <div
                v-for="field in missingFields"
                :key="field.path"
                class="rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-900"
              >
                <div class="font-semibold">
                  {{ field.group }} / {{ field.field }}
                </div>
                <div class="mt-1 text-amber-800">
                  {{ field.path }}{{ field.message ? `：${field.message}` : '' }}
                </div>
              </div>
            </div>
          </div>

          <a-collapse>
            <a-collapse-panel
              key="frontpage"
              header="病案首页草稿"
            >
              <pre class="max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{{
                stringifyJson(result.frontpage)
              }}</pre>
            </a-collapse-panel>
            <a-collapse-panel
              key="settlement"
              header="医保结算清单草稿"
            >
              <pre class="max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{{
                stringifyJson(result.settlement)
              }}</pre>
            </a-collapse-panel>
            <a-collapse-panel
              key="coverage"
              header="coverage 明细"
            >
              <pre class="max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">{{
                stringifyJson(result.coverage)
              }}</pre>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </a-spin>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  frontpageApi,
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

const coverage = computed(() => result.value?.coverage)

const selectedPreset = computed(() =>
  frontpageDemoPresets.find((preset) => preset.id === selectedPresetId.value),
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

function loadPreset(presetId: string) {
  const preset = frontpageDemoPresets.find((item) => item.id === presetId)
  if (!preset) return
  selectedPresetId.value = preset.id
  scene.value = preset.scene
  medicalText.value = preset.synthetic_settlement_text
  result.value = null
  resultUsedSynthetic.value = false
  message.success('已加载预置示例')
}

function buildPresetRequest(preset: FrontpageDemoPreset): GenerateReportDraftRequest {
  const request: GenerateReportDraftRequest = {
    scene: scene.value || preset.scene,
    visit_id: preset.visit_id,
  }
  if (preset.patient_id) {
    request.patient_id = preset.patient_id
  }
  const supplementalText = medicalText.value.trim() || preset.synthetic_settlement_text
  request.documents = [
    {
      type: '演示用医保结算补充信息',
      content: supplementalText,
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
}

function stringifyJson(value: unknown) {
  if (value === undefined || value === null) return 'null'
  return JSON.stringify(value, null, 2)
}
</script>
