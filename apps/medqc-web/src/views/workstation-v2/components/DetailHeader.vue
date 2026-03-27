<template>
  <header
    class="grid flex-shrink-0 grid-cols-[auto,minmax(0,1fr),auto] items-center gap-3 border-b border-slate-200/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,250,252,0.82))] px-4 py-1.5 backdrop-blur-xl"
  >
    <div class="flex items-center pr-1">
      <button
        class="group flex h-9 items-center gap-2 rounded-full border border-slate-200/75 bg-white/72 px-3.5 text-[13px] font-semibold text-slate-600 shadow-[0_2px_8px_rgba(15,23,42,0.03)] transition-all hover:border-blue-200 hover:text-blue-700 hover:shadow-[0_6px_14px_rgba(37,99,235,0.08)]"
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
          <h1
            class="m-0 truncate text-[19px] font-black leading-none tracking-[-0.04em] text-slate-950"
          >
            {{ record.name }}
          </h1>
          <span
            v-if="record.status === 'completed'"
            class="rounded-full border border-blue-200/80 bg-blue-50/80 px-2.5 py-0.5 text-[10px] font-bold text-blue-700"
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
            class="rounded-full border border-blue-200/80 bg-blue-50/80 px-2.5 py-0.5 text-[10px] font-bold text-blue-700"
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

    <div
      class="flex items-center justify-end gap-1.5 rounded-full border border-slate-200/75 bg-white/72 px-1.5 py-1 shadow-[0_4px_14px_rgba(15,23,42,0.04)]"
    >
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
                : 'text-slate-500 hover:bg-blue-50/80 hover:text-blue-700',
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
                : 'text-slate-500 hover:bg-blue-50/80 hover:text-blue-700',
            ]"
            @click="$emit('next')"
          >
            <RightOutlined />
          </button>
        </a-tooltip>
      </div>

      <a-button
        class="!h-9 !rounded-full !border-slate-200/80 !bg-white/92 !px-4 !font-semibold !text-slate-700 !shadow-none hover:!border-blue-200 hover:!text-blue-700"
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
          class="!h-9 !rounded-full !border !border-blue-500 !bg-[linear-gradient(135deg,#2563eb,#1d4ed8)] !px-5 !font-bold !text-white hover:!text-white active:!text-white disabled:!text-white/75 !shadow-[0_8px_18px_rgba(37,99,235,0.16)] transition-shadow duration-300 hover:!shadow-[0_12px_22px_rgba(37,99,235,0.22)]"
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
