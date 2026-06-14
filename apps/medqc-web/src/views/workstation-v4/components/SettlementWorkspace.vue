<template>
  <div class="settlement-apple-workspace min-h-[400px] px-4 pb-5 pt-3 lg:px-5">
    <div
      class="mx-auto w-full max-w-[1480px] rounded-[18px] border border-slate-200/55 bg-white/86 p-3 shadow-[0_2px_12px_rgba(0,0,0,0.055)]"
    >
      <div
        class="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-slate-200/80 bg-white/82 px-4 py-3"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <div class="text-[17px] font-semibold text-slate-950">结算清单工作区</div>
            <span
              class="rounded-full border border-blue-100 bg-blue-50/85 px-2.5 py-0.5 text-[11px] font-bold text-[#0057b8]"
            >
              {{ settlementStatusLabel }}
            </span>
            <span
              v-if="settlementData?.medinsur_serial_no"
              class="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11px] font-bold text-slate-600"
            >
              流水号 {{ settlementData.medinsur_serial_no }}
            </span>
            <span
              v-if="settlementQcReport"
              class="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11px] font-bold text-slate-600"
            >
              通过率 {{ settlementQcReport.summary.pass_rate }}
            </span>
          </div>
          <div class="mt-1 text-[12px] font-medium text-slate-500">
            清单预览、结算草稿生成和控费质控集中在当前工作区完成。
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <a-button
            v-if="!settlementData"
            type="primary"
            class="!h-9 !rounded-full !border-0 !px-4 !text-sm !font-bold !shadow-[0_8px_18px_rgba(37,99,235,0.16)]"
            :disabled="
              settlementLoading ||
              !canGenerateSettlement ||
              !selectedRecord?.patientId ||
              !selectedRecord?.visitId
            "
            @click="emit('generate-settlement-draft')"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            生成结算草稿
          </a-button>
          <a-button
            v-if="settlementData"
            type="primary"
            class="!h-9 !rounded-full !border-0 !px-4 !text-sm !font-bold !shadow-[0_8px_18px_rgba(37,99,235,0.16)]"
            :loading="settlementQcLoading"
            @click="emit('run-settlement-qc')"
          >
            <template #icon>
              <CheckOutlined />
            </template>
            执行质控
          </a-button>
          <a-button
            class="!h-9 !rounded-full !border-slate-200/90 !bg-white/85 !px-4 !text-sm !font-semibold !text-slate-600"
            :disabled="settlementLoading || settlementQcLoading"
            @click="emit('reload-settlement')"
          >
            <template #icon>
              <SyncOutlined />
            </template>
            重新加载
          </a-button>
        </div>
      </div>

      <div v-if="settlementLoading" class="flex flex-col items-center py-20">
        <a-spin size="large" />
        <div class="text-sm text-slate-400 mt-4">加载结算清单...</div>
      </div>
      <div v-else-if="settlementData">
        <div
          v-if="settlementData?.data_source === 'generated_from_frontpage'"
          class="mx-1 mb-3 flex items-center gap-3 rounded-[14px] border border-blue-100/80 bg-blue-50/70 px-4 py-3"
        >
          <span class="text-base text-blue-500">☑</span>
          <div class="min-w-0">
            <div class="text-sm font-semibold text-[#0057b8]">AI 生成草稿</div>
            <div class="text-xs text-slate-500">
              本清单由病案首页 AI 抽取结果和 CDM 数据自动组装，需人工审核后方可上传医保系统。
            </div>
          </div>
          <a-tag color="blue" class="ml-auto flex-shrink-0 !rounded-full"> Draft </a-tag>
        </div>
        <section
          v-if="settlementCoverageGroupSummaries.length"
          class="mx-1 mb-3 rounded-[14px] border border-slate-200/80 bg-white/82 px-4 py-3"
        >
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div>
              <div class="text-[13px] font-semibold text-slate-900">清单字段覆盖</div>
              <div class="mt-0.5 text-[12px] font-medium text-slate-500">
                展示由首页草稿映射到医保结算清单的字段覆盖情况。
              </div>
            </div>
            <span
              class="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-[#0057b8]"
            >
              待人工复核
            </span>
          </div>
          <div class="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <article
              v-for="item in settlementCoverageGroupSummaries"
              :key="item.group"
              class="rounded-[12px] border border-slate-200/80 bg-slate-50/70 px-3 py-2"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="truncate text-[12px] font-bold text-slate-700">{{ item.group }}</span>
                <span
                  class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                  :class="
                    item.status === 'completed'
                      ? 'bg-emerald-50 text-emerald-700'
                      : item.status === 'review'
                        ? 'bg-amber-50 text-amber-700'
                        : 'bg-rose-50 text-rose-700'
                  "
                >
                  {{ coverageStatusText(item.status) }}
                </span>
              </div>
              <div class="mt-2 text-[20px] font-semibold leading-none text-slate-950">
                {{ item.present }}/{{ item.total }}
              </div>
            </article>
          </div>
          <div
            v-if="settlementMissingFields.length"
            class="mt-2 text-[12px] leading-5 text-rose-600"
          >
            优先补全：{{ settlementMissingFields.map((item) => item.field).join('、') }}
          </div>
        </section>
        <div
          class="mb-4 flex items-center justify-between rounded-[14px] border border-slate-200/80 bg-white/72 px-4 py-3"
        >
          <div class="text-[13px] text-slate-500">
            清单流水号
            <span class="font-mono font-bold text-slate-700">{{
              settlementData.medinsur_serial_no || '-'
            }}</span>
          </div>
          <div class="text-[12px] font-semibold text-slate-500">
            {{
              settlementData?.data_source === 'generated_from_frontpage'
                ? '待人工复核后上传医保系统'
                : '系统清单预览'
            }}
          </div>
        </div>

        <SettlementSheet :data="settlementData" />

        <div v-if="settlementQcReport" class="mb-6">
          <h4
            class="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400"
          >
            <CheckCircleOutlined class="text-blue-500" /> 质控结果
          </h4>
          <div class="mb-4 grid grid-cols-4 gap-2.5">
            <div class="rounded-[14px] border border-blue-100/80 bg-blue-50/70 p-3 text-center">
              <div class="text-2xl font-semibold text-[#0066cc]">
                {{ settlementQcReport.summary.total }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">总规则数</div>
            </div>
            <div class="rounded-[14px] border border-slate-200/80 bg-slate-50/88 p-3 text-center">
              <div class="text-2xl font-semibold text-slate-700">
                {{ settlementQcReport.summary.passed }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">通过</div>
            </div>
            <div class="rounded-[14px] border border-blue-100/80 bg-blue-50/50 p-3 text-center">
              <div class="text-2xl font-semibold text-[#0057b8]">
                {{ settlementQcReport.summary.failed }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">未通过</div>
            </div>
            <div class="rounded-[14px] border border-slate-200/80 bg-white/88 p-3 text-center">
              <div class="text-2xl font-semibold text-slate-700">
                {{ settlementQcReport.summary.pass_rate }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">通过率</div>
            </div>
          </div>
          <div class="space-y-2">
            <div
              v-for="r in settlementQcReport.results.filter((x: any) => !x.passed)"
              :key="r.rule_id"
              class="flex items-start gap-3 rounded-[14px] border bg-white/88 px-4 py-3"
              :class="
                r.severity === 'error' ? 'border-blue-200 bg-blue-50/35' : 'border-slate-200/80'
              "
            >
              <a-tag color="blue" class="mt-0.5 flex-shrink-0">
                {{ r.rule_id }}
              </a-tag>
              <div class="min-w-0">
                <div class="text-sm font-medium text-slate-800">
                  {{ r.field_name }}
                </div>
                <div class="text-xs text-slate-500 mt-0.5">
                  {{ r.message }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        v-else
        class="flex min-h-[360px] flex-col items-center justify-center rounded-[16px] border border-dashed border-slate-200/80 bg-white/86 px-6 py-12 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_2px_12px_rgba(0,0,0,0.055)]"
      >
        <div
          class="mb-4 flex h-16 w-16 items-center justify-center rounded-[20px] border border-blue-100/80 bg-blue-50/80 shadow-[0_4px_12px_rgba(0,102,204,0.12),inset_0_1px_0_rgba(255,255,255,0.8)]"
        >
          <MedicineBoxOutlined class="text-[28px] text-[#0066cc]" />
        </div>
        <div class="text-[18px] font-semibold text-slate-900">暂无结算清单数据</div>
        <div class="mt-2 max-w-[360px] text-[13px] leading-6 text-slate-500">
          当前病历还没有正式结算清单，可根据首页草稿和 CDM 数据生成一份结算草稿后继续质控。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircleOutlined,
  CheckOutlined,
  MedicineBoxOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import SettlementSheet from './SettlementSheet.vue'
import type { PatientRecord } from '../types'
import {
  coverageStatusText,
  extractCoverageFields,
  summarizeCoverageFields,
  topMissingCoverageFields,
} from '../../../types/frontpage'

interface SettlementQcRuleResult {
  rule_id: string
  passed: boolean
  severity: string
  field_name: string
  message: string
}

interface SettlementQcReport {
  summary: {
    total: number
    passed: number
    failed: number
    pass_rate: string
  }
  results: SettlementQcRuleResult[]
}

const props = defineProps<{
  settlementLoading: boolean
  settlementData: Record<string, any> | null
  settlementQcLoading: boolean
  settlementQcReport: SettlementQcReport | null
  canGenerateSettlement: boolean
  selectedRecord: PatientRecord | null
}>()

const emit = defineEmits<{
  'run-settlement-qc': []
  'generate-settlement-draft': []
  'reload-settlement': []
}>()

const settlementStatusLabel = computed(() => {
  if (props.settlementLoading) return '加载中'
  if (!props.settlementData) return '待生成'
  if (props.settlementData?.data_source === 'generated_from_frontpage') return 'AI 草稿'
  return '正式清单'
})

const settlementCoveragePayload = computed(() => {
  const data = props.settlementData
  if (!data) return null
  return data.coverage || data._coverage || data.field_coverage || null
})
const settlementCoverageFields = computed(() =>
  extractCoverageFields(settlementCoveragePayload.value),
)
const settlementCoverageGroupSummaries = computed(() =>
  summarizeCoverageFields(settlementCoverageFields.value),
)
const settlementMissingFields = computed(() =>
  topMissingCoverageFields(settlementCoverageFields.value, 5),
)
</script>

<style scoped>
.settlement-apple-workspace {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.settlement-apple-workspace > div,
.settlement-apple-workspace :deep(.bg-white\/86),
.settlement-apple-workspace :deep(.bg-white\/82),
.settlement-apple-workspace :deep(.bg-white\/88),
.settlement-apple-workspace :deep(.bg-white\/72) {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.settlement-apple-workspace :deep(.text-slate-950),
.settlement-apple-workspace :deep(.text-slate-900),
.settlement-apple-workspace :deep(.text-slate-800),
.settlement-apple-workspace :deep(.text-slate-700) {
  color: #1d1d1f !important;
}

.settlement-apple-workspace :deep(.text-slate-600),
.settlement-apple-workspace :deep(.text-slate-500),
.settlement-apple-workspace :deep(.text-slate-400) {
  color: rgba(29, 29, 31, 0.56) !important;
}

.settlement-apple-workspace :deep(.text-\[\#0057b8\]),
.settlement-apple-workspace :deep(.text-\[\#0066cc\]),
.settlement-apple-workspace :deep(.text-blue-500) {
  color: #0066cc !important;
}

.settlement-apple-workspace :deep(.bg-blue-50),
.settlement-apple-workspace :deep(.bg-blue-50\/35),
.settlement-apple-workspace :deep(.bg-blue-50\/50),
.settlement-apple-workspace :deep(.bg-blue-50\/70),
.settlement-apple-workspace :deep(.bg-blue-50\/80),
.settlement-apple-workspace :deep(.bg-blue-50\/85) {
  background: rgba(0, 102, 204, 0.08) !important;
}

.settlement-apple-workspace :deep(.border-blue-100),
.settlement-apple-workspace :deep(.border-blue-100\/80),
.settlement-apple-workspace :deep(.border-blue-200),
.settlement-apple-workspace :deep(.border-blue-200\/80),
.settlement-apple-workspace :deep(.border-slate-200),
.settlement-apple-workspace :deep(.border-slate-200\/55),
.settlement-apple-workspace :deep(.border-slate-200\/80) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.settlement-apple-workspace :deep(.ant-btn-primary) {
  border-color: #0066cc !important;
  background: #0066cc !important;
  color: #fff !important;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.16) !important;
}

.settlement-apple-workspace :deep(.ant-btn:not(.ant-btn-primary)) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  color: rgba(29, 29, 31, 0.72) !important;
}
</style>
