<template>
  <header
    class="detail-apple-header grid flex-shrink-0 grid-cols-[auto,minmax(0,1fr),auto] items-center gap-3 border-b px-4 py-1.5"
  >
    <div class="flex items-center pr-1">
      <button
        class="group flex h-9 items-center gap-2 rounded-full border px-3.5 text-[13px] font-semibold transition-all"
        @click="$emit('back')"
      >
        <LeftOutlined class="transition-transform group-hover:-translate-x-1" />
        <span>&#x8FD4;&#x56DE;&#x5217;&#x8868;</span>
      </button>
    </div>

    <div class="min-w-0">
      <div
        v-if="record"
        class="flex min-w-0 items-center px-2 py-1"
      >
        <div class="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
          <h1 class="m-0 truncate text-[19px] font-semibold leading-none text-slate-950">
            {{ record.name }}
          </h1>
          <span
            v-if="record.status === 'completed'"
            class="rounded-full border border-blue-200/80 bg-blue-50/80 px-2.5 py-0.5 text-[10px] font-bold text-[#0057b8]"
          >
            &#x5DF2;&#x5B8C;&#x6210;
          </span>
          <span
            v-else-if="isDefectStatus(record.status)"
            class="rounded-full border border-slate-200/90 bg-slate-50/92 px-2.5 py-0.5 text-[10px] font-bold text-slate-600"
          >
            &#x6709;&#x7F3A;&#x9677;
          </span>
          <span
            v-else-if="record.status === 'processing'"
            class="rounded-full border border-blue-200/80 bg-blue-50/80 px-2.5 py-0.5 text-[10px] font-bold text-[#0057b8]"
          >
            &#x5904;&#x7406;&#x4E2D;
          </span>
          <span
            v-else
            class="rounded-full border border-slate-200/90 bg-slate-50/92 px-2.5 py-0.5 text-[10px] font-bold text-slate-600"
          >
            &#x5F85;&#x5904;&#x7406;
          </span>
          <span class="h-1.5 w-1.5 rounded-full bg-slate-300" />
          <span class="font-mono text-[14px] font-bold text-slate-600">{{ record.id }}</span>
          <span class="h-1.5 w-1.5 rounded-full bg-slate-300" />
          <span class="truncate text-[14px] font-semibold text-slate-500">{{
            record.department
          }}</span>
          <template v-if="record.doctor">
            <span class="h-1.5 w-1.5 rounded-full bg-slate-300" />
            <span class="truncate text-[14px] font-semibold text-slate-500">{{
              record.doctor
            }}</span>
          </template>
        </div>
      </div>
    </div>

    <div class="flex items-center justify-end gap-1.5 rounded-full border px-1.5 py-1">
      <div
        class="rounded-full border border-slate-200/80 bg-white/92 px-3 py-1.5 text-[12px] font-semibold text-slate-400"
      >
        &#x5F53;&#x524D;&#x75C5;&#x6848;
        <span class="ml-1 font-mono font-bold text-slate-700">{{ currentIndex + 1 }} / {{ totalCount }}</span>
      </div>

      <div
        class="flex items-center gap-1 rounded-full border border-slate-200/80 bg-white/92 px-1.5 py-1"
      >
        <a-tooltip :title="'\u4E0A\u4E00\u4F8B'">
          <button
            :disabled="currentIndex <= 0"
            :class="[
              'flex h-[30px] w-[30px] items-center justify-center rounded-full text-sm transition-all',
              currentIndex <= 0
                ? 'cursor-not-allowed text-slate-300'
                : 'text-slate-500 hover:bg-blue-50/80 hover:text-[#0057b8]',
            ]"
            @click="$emit('prev')"
          >
            <LeftOutlined />
          </button>
        </a-tooltip>
        <a-tooltip :title="'\u4E0B\u4E00\u4F8B'">
          <button
            :disabled="currentIndex >= totalCount - 1"
            :class="[
              'flex h-[30px] w-[30px] items-center justify-center rounded-full text-sm transition-all',
              currentIndex >= totalCount - 1
                ? 'cursor-not-allowed text-slate-300'
                : 'text-slate-500 hover:bg-blue-50/80 hover:text-[#0057b8]',
            ]"
            @click="$emit('next')"
          >
            <RightOutlined />
          </button>
        </a-tooltip>
      </div>

      <a-button
        class="!h-9 !rounded-full !border-slate-200/80 !bg-white/92 !px-4 !font-semibold !text-slate-700 !shadow-none hover:!border-blue-200 hover:!text-[#0057b8]"
        @click="$emit('open-icd')"
      >
        <template #icon>
          <SearchOutlined />
        </template>
        ICD &#x67E5;&#x8BE2;
      </a-button>

      <a-tooltip
        :title="disabledReason"
        :open="!canGenerate && !hasDraft ? undefined : false"
      >
        <a-button
          type="primary"
          :loading="generating"
          :disabled="!canGenerate && !hasDraft"
          class="!h-9 !rounded-full !border !px-5 !font-semibold !text-white hover:!text-white active:!text-white disabled:!text-white/75 transition-shadow duration-300"
          @click="$emit('generate-frontpage')"
        >
          <template #icon>
            <ThunderboltOutlined />
          </template>
          {{ hasDraft ? '\u91CD\u65B0\u751F\u6210' : 'AI \u751F\u6210\u9996\u9875' }}
        </a-button>
      </a-tooltip>
    </div>
  </header>
</template>

<script setup lang="ts">
import {
  LeftOutlined,
  RightOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { isDefectStatus } from '../normalize'
import type { PatientRecord } from '../types'

defineProps<{
  record: PatientRecord | undefined
  currentIndex: number
  totalCount: number
  generating: boolean
  hasDraft: boolean
  canGenerate: boolean
  disabledReason: string
}>()

defineEmits<{
  back: []
  prev: []
  next: []
  'open-icd': []
  'generate-frontpage': []
}>()
</script>

<style scoped>
.detail-apple-header {
  min-height: 64px;
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.76);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.detail-apple-header h1 {
  color: #1d1d1f !important;
  font-size: 19px !important;
  font-weight: 650 !important;
  letter-spacing: 0 !important;
  line-height: 24px !important;
}

.detail-apple-header button,
.detail-apple-header :deep(.ant-btn) {
  font-family: inherit;
}

.detail-apple-header button:not(:disabled) {
  color: rgba(29, 29, 31, 0.68) !important;
}

.detail-apple-header button:not(:disabled):hover {
  border-color: rgba(0, 102, 204, 0.2) !important;
  background: rgba(0, 102, 204, 0.06) !important;
  color: #0066cc !important;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.08) !important;
}

.detail-apple-header :deep(.ant-btn:not(.ant-btn-primary)) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  color: rgba(29, 29, 31, 0.7) !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82) !important;
}

.detail-apple-header :deep(.ant-btn:not(.ant-btn-primary):hover) {
  border-color: rgba(0, 102, 204, 0.2) !important;
  color: #0066cc !important;
}

.detail-apple-header :deep(.ant-btn-primary) {
  border-color: #0066cc !important;
  background: #0066cc !important;
  color: #fff !important;
  font-size: 13px !important;
  font-weight: 650 !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 4px 12px rgba(0, 102, 204, 0.16) !important;
}

.detail-apple-header :deep(.ant-btn-primary:hover) {
  border-color: #0057b8 !important;
  background: #0057b8 !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 6px 16px rgba(0, 102, 204, 0.2) !important;
}

.detail-apple-header :deep(.ant-btn-primary[disabled]),
.detail-apple-header :deep(.ant-btn-primary.ant-btn-disabled) {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(29, 29, 31, 0.08) !important;
  color: rgba(29, 29, 31, 0.38) !important;
  box-shadow: none !important;
}

.detail-apple-header span {
  letter-spacing: 0 !important;
}

.detail-apple-header .font-mono {
  font-family:
    'SF Pro Text', 'Source Han Sans SC', 'Cascadia Code', 'Roboto Mono', monospace !important;
  font-weight: 600 !important;
}

.detail-apple-header .text-slate-950,
.detail-apple-header .text-slate-900,
.detail-apple-header .text-slate-800,
.detail-apple-header .text-slate-700 {
  color: #1d1d1f !important;
}

.detail-apple-header .text-slate-600,
.detail-apple-header .text-slate-500,
.detail-apple-header .text-slate-400 {
  color: rgba(29, 29, 31, 0.58) !important;
}

.detail-apple-header .bg-slate-300 {
  background: rgba(29, 29, 31, 0.18) !important;
}

.detail-apple-header .bg-blue-50\/80,
.detail-apple-header .bg-slate-50\/92 {
  background: rgba(0, 102, 204, 0.07) !important;
}

.detail-apple-header .border-blue-200\/80,
.detail-apple-header .border-slate-200\/90 {
  border-color: rgba(0, 102, 204, 0.16) !important;
}

.detail-apple-header .text-\[\#0057b8\] {
  color: #0066cc !important;
}
</style>
