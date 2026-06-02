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
          <a-textarea
            v-model:value="medicalText"
            :auto-size="{ minRows: 10, maxRows: 18 }"
            placeholder="请粘贴完整病历文本，用于验证病案首页招标字段生成能力"
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
  type GenerateReportDraftResponse,
} from '@/api/frontpage'

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

const coverage = computed(() => result.value?.coverage)

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

async function startValidation() {
  const text = medicalText.value.trim()
  if (!text) {
    message.warning('请先粘贴完整病历文本')
    return
  }

  validating.value = true
  try {
    const response = await frontpageApi.generateReportDraft({
      scene: scene.value,
      medical_text: text,
    })
    if (!response.success || !response.data) {
      throw new Error(response.error || response.message || '招标字段验证失败')
    }
    result.value = response.data
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
}

function stringifyJson(value: unknown) {
  if (value === undefined || value === null) return 'null'
  return JSON.stringify(value, null, 2)
}
</script>
