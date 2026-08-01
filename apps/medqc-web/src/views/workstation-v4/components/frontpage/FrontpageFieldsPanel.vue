<template>
  <div
    class="frontpage-fields-panel mb-3 rounded-[18px] border border-slate-200/80 bg-white/86 px-4 py-3.5 shadow-[0_2px_12px_rgba(0,0,0,0.055)]"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="flex min-w-0 items-start gap-3">
        <div
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-[#0066cc] shadow-[0_5px_14px_rgba(0,102,204,0.16)]"
        >
          <CheckCircleOutlined class="text-base text-white" />
        </div>
        <div class="min-w-0">
          <div class="text-[16px] font-semibold text-slate-950">
            病案首页提取结果
          </div>
          <div class="mt-1 text-[12px] leading-5 text-slate-500">
            按首页模块归并结构化字段，用于复核后预览、导出或保存。
          </div>
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        <a-button
          size="small"
          class="!h-8 !rounded-full !border-slate-200/80 !bg-white !px-3 !font-semibold !shadow-none"
          @click="emit('export-frontpage', 'health')"
        >
          <template #icon>
            <DownloadOutlined />
          </template>
          导出
        </a-button>
        <a-button
          size="small"
          type="primary"
          class="!h-8 !rounded-full !px-3 !font-semibold !shadow-[0_6px_14px_rgba(37,99,235,0.14)]"
          @click="emit('save-frontpage')"
        >
          <template #icon>
            <SaveOutlined />
          </template>
          保存到数据库
        </a-button>
      </div>
    </div>

    <div class="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
      <div
        v-for="metric in summaryMetrics"
        :key="metric.label"
        class="rounded-[14px] border border-slate-200/70 bg-white/82 px-3 py-2.5"
      >
        <div class="text-[11px] font-bold text-slate-400">
          {{ metric.label }}
        </div>
        <div class="mt-1 flex items-end gap-1">
          <span class="text-[22px] font-semibold leading-none text-slate-950">{{
            metric.value
          }}</span>
          <span
            v-if="metric.suffix"
            class="pb-0.5 text-[11px] font-semibold text-slate-400"
          >{{
            metric.suffix
          }}</span>
        </div>
      </div>
    </div>
  </div>

  <div class="grid gap-3 pb-2 lg:grid-cols-[260px_minmax(0,1fr)]">
    <div
      class="self-start rounded-[18px] border border-slate-200/80 bg-white/88 p-2 shadow-[0_6px_16px_rgba(15,23,42,0.025)] lg:sticky lg:top-3"
    >
      <div class="px-2 pb-2 pt-1">
        <div class="text-[12px] font-semibold text-slate-900">
          提取模块
        </div>
        <div class="mt-0.5 text-[11px] text-slate-400">
          点击定位到对应字段组
        </div>
      </div>
      <div
        v-for="module in moduleCards"
        :key="module.key"
        class="mb-1 last:mb-0"
      >
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-[12px] px-2.5 py-2 text-left transition hover:bg-blue-50/60"
          @click="scrollToModule(module.key)"
        >
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px]"
            :class="moduleIconClass(module)"
          >
            <CheckCircleOutlined
              v-if="module.entry?.preview?.length"
              class="text-[12px]"
            />
            <span
              v-else
              class="h-2 w-2 rounded-full bg-current"
            />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-[13px] font-bold text-slate-700">{{
              module.label
            }}</span>
            <span class="mt-0.5 block text-[11px] text-slate-400">
              {{ moduleFieldCount(module) }} 项字段
            </span>
          </span>
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-bold"
            :class="moduleStatusClass(module)"
          >
            {{ moduleStatusLabel(module) }}
          </span>
        </button>
      </div>
    </div>

    <div class="space-y-3">
      <div
        v-for="module in moduleCards"
        :id="moduleDomId(module.key)"
        :key="module.key"
        class="scroll-mt-4 rounded-[18px] border border-slate-200/75 bg-white/92 px-4 py-3.5 shadow-[0_4px_14px_rgba(15,23,42,0.025)]"
      >
        <div
          class="mb-3 flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 pb-3"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px]"
                :class="moduleIconClass(module)"
              >
                <CheckCircleOutlined
                  v-if="module.entry?.preview?.length"
                  class="text-[13px]"
                />
                <span
                  v-else
                  class="h-2 w-2 rounded-full bg-current"
                />
              </span>
              <span class="text-[15px] font-semibold text-slate-950">{{ module.label }}</span>
              <span
                class="rounded-full px-2.5 py-0.5 text-[11px] font-bold"
                :class="moduleStatusClass(module)"
              >
                {{ moduleStatusLabel(module) }}
              </span>
            </div>
            <div class="mt-1 text-[12px] font-medium text-slate-400">
              {{ moduleFieldCount(module) }} 项字段
              <span v-if="moduleTimestampLabel(module)"> · {{ moduleTimestampLabel(module) }}</span>
            </div>
          </div>
        </div>

        <div
          v-if="module.entry?.preview?.length"
          class="grid gap-2.5 sm:grid-cols-2 2xl:grid-cols-3"
        >
          <div
            v-for="(preview, pi) in module.entry.preview"
            :key="pi"
            class="rounded-[12px] border border-slate-100 bg-slate-50/55 px-3 py-2.5"
            :class="preview.isLongText ? 'sm:col-span-2 2xl:col-span-3' : ''"
          >
            <div class="text-[11px] font-bold text-slate-400">
              {{ preview.label }}
            </div>
            <div
              class="mt-1 text-[13px] font-semibold leading-6 text-slate-800"
              :class="preview.isLongText ? 'whitespace-pre-wrap font-medium' : 'truncate'"
              :title="preview.value"
            >
              {{ preview.value || '-' }}
            </div>
          </div>
        </div>

        <div
          v-else
          class="rounded-[14px] border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center"
        >
          <div class="text-[13px] font-bold text-slate-500">
            未提取到结构化字段
          </div>
          <div class="mt-1 text-[12px] text-slate-400">
            可在病历文书中复核该模块来源，必要时重新生成首页草稿。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircleOutlined, DownloadOutlined, SaveOutlined } from '@ant-design/icons-vue'

interface PreviewItem {
  label: string
  value: string
  isLongText?: boolean
}

interface ModuleCard {
  key: string
  label: string
  status?: 'done' | 'active' | 'pending'
  entry?: {
    preview?: PreviewItem[]
    timestamp?: number
  }
}

const props = defineProps<{
  moduleCards: ModuleCard[]
  completedCount: number
}>()

const emit = defineEmits<{
  'export-frontpage': [format: 'health' | 'insurance' | 'settlement']
  'save-frontpage': []
}>()

const fieldCount = computed(() =>
  props.moduleCards.reduce((sum, module) => sum + moduleFieldCount(module), 0),
)

const emptyModuleCount = computed(
  () => props.moduleCards.filter((module) => !module.entry?.preview?.length).length,
)

const totalSeconds = computed(
  () =>
    props.moduleCards.reduce((sum, module) => sum + Number(module.entry?.timestamp || 0), 0) / 1000,
)

const summaryMetrics = computed(() => [
  { label: '完成模块', value: props.completedCount, suffix: `/${props.moduleCards.length}` },
  { label: '结构化字段', value: fieldCount.value, suffix: '项' },
  { label: '待复核模块', value: emptyModuleCount.value, suffix: '个' },
  {
    label: '累计耗时',
    value: totalSeconds.value ? totalSeconds.value.toFixed(1) : '-',
    suffix: 's',
  },
])

function moduleFieldCount(module: ModuleCard) {
  return module.entry?.preview?.length || 0
}

function moduleDomId(key: string) {
  return `frontpage-module-${key}`
}

function moduleTimestampLabel(module: ModuleCard) {
  if (!module.entry?.timestamp) return ''
  return `提取耗时 ${(module.entry.timestamp / 1000).toFixed(1)}s`
}

function moduleStatusLabel(module: ModuleCard) {
  if (module.entry?.preview?.length) return '已提取'
  if (module.status === 'active') return '提取中'
  return '待复核'
}

function moduleStatusClass(module: ModuleCard) {
  if (module.entry?.preview?.length) return 'bg-blue-50 text-[#0057b8]'
  if (module.status === 'active') return 'bg-cyan-50 text-cyan-700'
  return 'bg-slate-100 text-slate-500'
}

function moduleIconClass(module: ModuleCard) {
  if (module.entry?.preview?.length) return 'bg-[#0066cc] text-white'
  if (module.status === 'active') return 'bg-cyan-500 text-white'
  return 'bg-slate-100 text-slate-400'
}

function scrollToModule(key: string) {
  document.getElementById(moduleDomId(key))?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
</script>

<style scoped>
.frontpage-fields-panel {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  color: #1d1d1f;
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.frontpage-fields-panel div[class*='rounded-'] {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.frontpage-fields-panel .text-slate-950,
.frontpage-fields-panel .text-slate-900,
.frontpage-fields-panel .text-slate-800,
.frontpage-fields-panel .text-slate-700 {
  color: #1d1d1f !important;
}

.frontpage-fields-panel .text-slate-500,
.frontpage-fields-panel .text-slate-400 {
  color: rgba(29, 29, 31, 0.56) !important;
}

.frontpage-fields-panel .bg-blue-50,
.frontpage-fields-panel .bg-blue-50\/70,
.frontpage-fields-panel .bg-blue-50\/85 {
  background: rgba(0, 102, 204, 0.08) !important;
}

.frontpage-fields-panel .text-\[\#0057b8\],
.frontpage-fields-panel .text-\[\#0066cc\],
.frontpage-fields-panel .text-blue-500 {
  color: #0066cc !important;
}

:deep(.ant-btn-primary) {
  border-color: #0066cc !important;
  background: #0066cc !important;
  color: #fff !important;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.16) !important;
}

:deep(.ant-btn:not(.ant-btn-primary)) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  color: rgba(29, 29, 31, 0.72) !important;
}
</style>
