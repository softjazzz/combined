<template>
  <div class="frontpage-apple-workspace px-4 pb-5 pt-3 lg:px-5">
    <div
      class="mx-auto w-full max-w-[1480px] rounded-[18px] border border-slate-200/55 bg-white/86 p-3 shadow-[0_2px_12px_rgba(0,0,0,0.055)]"
    >
      <div
        class="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-slate-200/80 bg-white/82 px-4 py-3"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <div class="text-[17px] font-semibold text-slate-950">
              病案首页工作区
            </div>
            <span
              class="rounded-full border border-blue-100 bg-blue-50/85 px-2.5 py-0.5 text-[11px] font-bold text-[#0a5fd6]"
            >
              {{ sourceLabel }}
            </span>
            <span
              v-if="reportResult?.coverage"
              class="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11px] font-bold text-slate-600"
            >
              覆盖 {{ reportResult.coverage.present }}/{{ reportResult.coverage.total }}
            </span>
          </div>
          <div class="mt-1 text-[12px] font-medium text-slate-500">
            提取结果、首页预览/打印、系统首页集中在当前工作区完成。
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <a-tooltip title="基于当前已选病历/同步文书">
            <a-button
              type="primary"
              class="!h-9 !rounded-full !border-0 !px-4 !text-sm !font-bold !shadow-[0_8px_18px_rgba(37,99,235,0.16)]"
              :loading="frontpageGenerating"
              :disabled="!canGenerateFrontpage"
              @click="emit('generate-frontpage')"
            >
              <template #icon>
                <ThunderboltOutlined />
              </template>
              AI 生成首页
            </a-button>
          </a-tooltip>
          <a-tooltip title="直接粘贴完整病历原文抽取">
            <a-button
              class="!h-9 !rounded-full !border-blue-100 !bg-blue-50/70 !px-4 !text-sm !font-semibold !text-[#0a5fd6] hover:!border-blue-200 hover:!bg-blue-50"
              :disabled="frontpageGenerating || frontpagePostProcessing"
              @click="emit('paste-frontpage')"
            >
              <template #icon>
                <FileTextOutlined />
              </template>
              粘贴病历生成首页
            </a-button>
          </a-tooltip>
          <a-button
            class="!h-9 !rounded-full !border-slate-200/90 !bg-white/85 !px-4 !text-sm !font-semibold !text-slate-600"
            :disabled="frontpageGenerating || frontpagePostProcessing"
            @click="emit('reload-frontpage-sheet')"
          >
            <template #icon>
              <SyncOutlined />
            </template>
            重新加载
          </a-button>
        </div>
      </div>

      <div
        v-if="
          !frontpageGenerating &&
            !frontpagePostProcessing &&
            !draft &&
            !frontpageSheetLoading &&
            !frontpageSheetData
        "
        class="flex min-h-[360px] flex-col items-center justify-center rounded-[16px] border border-dashed border-slate-200/80 bg-white/86 px-6 py-12 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_2px_12px_rgba(0,0,0,0.055)]"
      >
        <div
          class="mb-4 flex h-16 w-16 items-center justify-center rounded-[20px] border border-blue-100/80 bg-blue-50/80 shadow-[0_4px_12px_rgba(10, 108, 255,0.12),inset_0_1px_0_rgba(255,255,255,0.8)]"
        >
          <FileSearchOutlined class="text-[28px] text-[#0a6cff]" />
        </div>
        <div class="text-[18px] font-semibold text-slate-900">
          暂无病案首页数据
        </div>
        <div class="mt-2 max-w-[360px] text-[13px] leading-6 text-slate-500">
          当前病历还没有可展示的病案首页正式数据，可使用上方工具栏生成首页草稿或重新加载系统首页。
        </div>
      </div>
      <FrontpageWorkspacePanel
        v-else
        :generating="frontpageGenerating"
        :post-processing="frontpagePostProcessing"
        :draft="draft"
        :frontpage-tab="frontpageTab"
        :module-cards="frontpageModuleCards"
        :completed-count="completedCount"
        :total-count="totalCount"
        :sheet-loading="frontpageSheetLoading"
        :sheet-data="frontpageSheetData"
        @update:frontpage-tab="emit('update:frontpage-tab', $event)"
        @export-frontpage="emit('export-frontpage', $event)"
        @save-frontpage="emit('save-frontpage')"
      />
      <a-alert
        v-if="reportResult?.coverage"
        class="mt-2"
        :type="reportResult.coverage.status === 'complete' ? 'success' : 'warning'"
        show-icon
      >
        <template #message>
          <div class="flex flex-wrap items-center gap-2 text-[13px]">
            <span>生成场景：{{ sceneLabel(reportResult.scene) }}</span>
            <span>{{ textCoverageLabel(reportResult) }}</span>
            <span>{{ settlementDraftLabel(reportResult) }}</span>
            <span>总覆盖 {{ reportResult.coverage.present }}/{{ reportResult.coverage.total }}</span>
            <span v-if="reportResult.coverage.missing">缺失 {{ reportResult.coverage.missing }} 项</span>
          </div>
        </template>
        <template #description>
          <div class="text-[12px] leading-5">
            {{
              (reportResult.warnings || reportResult.coverage.warnings || [])
                .slice(0, 5)
                .join('；') || '字段覆盖报告已生成'
            }}
          </div>
        </template>
      </a-alert>
      <section
        v-if="coverageGroupSummaries.length"
        class="mt-3 rounded-[16px] border border-slate-200/80 bg-white/82 p-4"
      >
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="text-[14px] font-semibold text-slate-900">
              字段覆盖报告
            </div>
            <div class="mt-0.5 text-[12px] font-medium text-slate-500">
              按首页生成条款分组展示抽取完成度，缺失字段需复核后再进入正式首页。
            </div>
          </div>
          <span
            class="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-[#0a5fd6]"
          >
            {{ reportResult.coverage.status === 'complete' ? '可复核提交' : '待补全复核' }}
          </span>
        </div>
        <div class="grid gap-2.5 md:grid-cols-2 xl:grid-cols-4">
          <article
            v-for="item in coverageGroupSummaries"
            :key="item.group"
            class="rounded-[14px] border border-slate-200/80 bg-slate-50/70 px-3 py-2.5"
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
            <div class="mt-2 flex items-end justify-between">
              <div class="text-[24px] font-semibold leading-none text-slate-950">
                {{ item.present }}/{{ item.total }}
              </div>
              <div class="text-right text-[11px] leading-4 text-slate-500">
                <div v-if="item.missing">
                  缺失 {{ item.missing }}
                </div>
                <div v-if="item.partial">
                  需复核 {{ item.partial }}
                </div>
                <div v-if="!item.missing && !item.partial">
                  字段完整
                </div>
              </div>
            </div>
          </article>
        </div>
        <div
          v-if="topMissingFields.length"
          class="mt-3 rounded-[12px] border border-rose-100 bg-rose-50/55 px-3 py-2"
        >
          <div class="mb-1 text-[12px] font-bold text-rose-700">
            优先补全字段
          </div>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="field in topMissingFields"
              :key="field.path || field.field"
              class="rounded-full border border-rose-100 bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-rose-700"
            >
              {{ field.group }} / {{ field.field }}
            </span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  FileSearchOutlined,
  FileTextOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import FrontpageWorkspacePanel from './FrontpageWorkspacePanel.vue'
import {
  coverageStatusText,
  extractCoverageFields,
  summarizeCoverageFields,
  topMissingCoverageFields,
} from '../../../types/frontpage'

type FrontpageTabKey = 'fields' | 'preview' | 'official'
type FrontpageModuleCard = {
  key: string
  label: string
  status: 'done' | 'active' | 'pending'
  entry?: {
    preview?: { label: string; value: string; isLongText?: boolean }[]
    timestamp?: number
  }
}

const props = defineProps<{
  frontpageGenerating: boolean
  frontpagePostProcessing: boolean
  draft: Record<string, any> | null
  frontpageTab: FrontpageTabKey
  frontpageModuleCards: FrontpageModuleCard[]
  completedCount: number
  totalCount: number
  frontpageSheetLoading: boolean
  frontpageSheetData: Record<string, any> | null
  canGenerateFrontpage: boolean
  reportResult?: Record<string, any> | null
}>()

const emit = defineEmits<{
  'generate-frontpage': []
  'paste-frontpage': []
  'reload-frontpage-sheet': []
  'update:frontpage-tab': [tab: FrontpageTabKey]
  'export-frontpage': [format: 'health' | 'insurance' | 'settlement']
  'save-frontpage': []
}>()

const sourceLabel = computed(() => {
  if (props.frontpageSheetData) return '官方首页'
  if (props.draft) return 'AI 草稿'
  if (props.frontpageGenerating || props.frontpagePostProcessing) return '生成中'
  return '待生成'
})

const coverageFields = computed(() => extractCoverageFields(props.reportResult))
const coverageGroupSummaries = computed(() => summarizeCoverageFields(coverageFields.value))
const topMissingFields = computed(() => topMissingCoverageFields(coverageFields.value, 6))

function sceneLabel(scene?: string) {
  if (scene === 'nhc_frontpage') return '病案首页'
  if (scene === 'insurance_settlement') return '医保结算清单'
  if (scene === 'combined') return '联合草稿'
  return scene || '未指定'
}

function textCoverageLabel(report?: Record<string, any> | null) {
  const textCoverage = report?.coverage?.text_extraction
  if (textCoverage?.total) {
    return `文本抽取覆盖率 ${textCoverage.present}/${textCoverage.total}`
  }
  const fields = Array.isArray(report?.coverage?.fields) ? report.coverage.fields : []
  const textFields = fields.filter((item: any) => String(item?.path || '').startsWith('frontpage.'))
  const present = textFields.filter((item: any) => item?.status === 'present').length
  return `文本抽取覆盖率 ${present}/${textFields.length}`
}

function settlementDraftLabel(report?: Record<string, any> | null) {
  const settlementCoverage = report?.coverage?.settlement_from_frontpage
  if (settlementCoverage?.total) {
    return `结算草稿 ${settlementCoverage.present}/${settlementCoverage.total}`
  }
  return report?.settlement ? '结算草稿已生成' : '结算草稿未生成'
}
</script>

<style scoped>
.frontpage-apple-workspace {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.frontpage-apple-workspace > div,
.frontpage-apple-workspace :deep(.bg-white\/86),
.frontpage-apple-workspace :deep(.bg-white\/82),
.frontpage-apple-workspace :deep(.bg-white\/88) {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.frontpage-apple-workspace :deep(.text-slate-950),
.frontpage-apple-workspace :deep(.text-slate-900),
.frontpage-apple-workspace :deep(.text-slate-800),
.frontpage-apple-workspace :deep(.text-slate-700) {
  color: #1d1d1f !important;
}

.frontpage-apple-workspace :deep(.text-slate-600),
.frontpage-apple-workspace :deep(.text-slate-500),
.frontpage-apple-workspace :deep(.text-slate-400) {
  color: rgba(29, 29, 31, 0.56) !important;
}

.frontpage-apple-workspace :deep(.text-\[\#0a5fd6\]),
.frontpage-apple-workspace :deep(.text-\[\#0a6cff\]),
.frontpage-apple-workspace :deep(.text-blue-500) {
  color: #0a6cff !important;
}

.frontpage-apple-workspace :deep(.bg-blue-50),
.frontpage-apple-workspace :deep(.bg-blue-50\/70),
.frontpage-apple-workspace :deep(.bg-blue-50\/80),
.frontpage-apple-workspace :deep(.bg-blue-50\/85) {
  background: rgba(10, 108, 255, 0.08) !important;
}

.frontpage-apple-workspace :deep(.border-blue-100),
.frontpage-apple-workspace :deep(.border-blue-100\/80),
.frontpage-apple-workspace :deep(.border-blue-200\/80),
.frontpage-apple-workspace :deep(.border-slate-200),
.frontpage-apple-workspace :deep(.border-slate-200\/55),
.frontpage-apple-workspace :deep(.border-slate-200\/80) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.frontpage-apple-workspace :deep(.ant-btn-primary) {
  border-color: #0a6cff !important;
  background: #0a6cff !important;
  color: #fff !important;
  box-shadow: 0 4px 12px rgba(10, 108, 255, 0.16) !important;
}

.frontpage-apple-workspace :deep(.ant-btn:not(.ant-btn-primary)) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  color: rgba(29, 29, 31, 0.72) !important;
}
</style>
