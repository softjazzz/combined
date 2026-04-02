<template>
  <div
    class="mb-3 flex flex-wrap items-center gap-2.5 rounded-[16px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(255,255,255,0.98)_100%)] px-4 py-2.5 shadow-[0_6px_16px_rgba(15,23,42,0.03)]"
  >
    <div
      class="flex h-7 w-7 items-center justify-center rounded-[10px] bg-blue-500/95 shadow-[0_6px_14px_rgba(37,99,235,0.1)]"
    >
      <CheckCircleOutlined class="text-sm text-white" />
    </div>
    <div class="flex-1">
      <div class="text-[13px] font-bold text-slate-800">病案首页提取完成</div>
      <div class="mt-0.5 text-xs text-slate-400">
        已从病历中提取 {{ completedCount }} 个模块的结构化字段信息
      </div>
    </div>
    <div class="flex flex-wrap gap-2">
      <a-button
        size="small"
        class="!rounded-full !border-slate-200/80 !bg-white !shadow-none"
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
        class="!rounded-full !shadow-[0_6px_14px_rgba(37,99,235,0.14)]"
        @click="emit('save-frontpage')"
      >
        <template #icon>
          <SaveOutlined />
        </template>
        保存到数据库
      </a-button>
    </div>
  </div>

  <div class="columns-1 xl:columns-2 gap-3 space-y-3 pb-2 pt-1">
    <div
      v-for="module in moduleCards"
      :key="module.key"
      class="break-inside-avoid rounded-[16px] border border-slate-200/70 bg-white px-4 py-3.5 shadow-[0_2px_10px_rgba(15,23,42,0.02)] transition-shadow hover:shadow-[0_6px_16px_rgba(15,23,42,0.04)]"
    >
      <div class="mb-3 flex items-center gap-2.5 border-b border-slate-100/80 pb-2.5">
        <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-500/10">
          <CheckCircleOutlined class="text-[11px] text-blue-600" />
        </div>
        <span class="text-[14px] font-semibold tracking-wide text-slate-800">{{
          module.label
        }}</span>
        <span
          v-if="module.entry?.timestamp"
          class="ml-auto rounded-full bg-slate-50 px-2.5 py-0.5 text-[11px] font-medium tabular-nums text-slate-400"
          >{{ (module.entry.timestamp / 1000).toFixed(1) }}s</span
        >
        <span
          v-if="!module.entry?.preview?.length"
          class="ml-auto text-[11px] italic text-slate-400"
          >未提取到数据</span
        >
      </div>

      <div v-if="module.entry?.preview?.length" class="flex flex-col gap-3">
        <div
          v-for="(preview, pi) in module.entry.preview"
          :key="pi"
          class="text-[13px] leading-relaxed"
        >
          <template v-if="preview.isLongText">
            <div class="mb-1 text-[11px] font-medium tracking-wide text-slate-400">
              {{ preview.label }}
            </div>
            <div class="rounded-lg bg-slate-50/80 px-3 py-2 text-[13px] text-slate-700">
              {{ preview.value }}
            </div>
          </template>
          <template v-else>
            <div class="flex items-start justify-between">
              <span class="w-24 shrink-0 text-[12px] text-slate-400">{{ preview.label }}</span>
              <span class="text-right text-[13px] font-medium text-slate-800">{{
                preview.value
              }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CheckCircleOutlined, DownloadOutlined, SaveOutlined } from '@ant-design/icons-vue'

interface PreviewItem {
  label: string
  value: string
  isLongText?: boolean
}

interface ModuleCard {
  key: string
  label: string
  entry?: {
    preview?: PreviewItem[]
    timestamp?: number
  }
}

defineProps<{
  moduleCards: ModuleCard[]
  completedCount: number
}>()

const emit = defineEmits<{
  'export-frontpage': [format: 'health' | 'insurance' | 'settlement']
  'save-frontpage': []
}>()
</script>
