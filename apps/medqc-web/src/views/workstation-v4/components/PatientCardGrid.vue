<template>
  <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-4 pt-3 xl:px-5">
    <div
      v-if="records.length === 0"
      class="flex h-full min-h-[360px] flex-col items-center justify-center rounded-[28px] border border-dashed border-slate-200 bg-white/72 text-slate-400"
    >
      <InboxOutlined class="mb-3 text-4xl text-slate-300" />
      <div class="text-sm font-medium text-slate-500">
        &#24403;&#21069;&#31579;&#36873;&#26465;&#20214;&#19979;&#26242;&#26080;&#30149;&#21382;
      </div>
      <div class="mt-1 text-xs text-slate-400">
        &#35843;&#25972;&#31185;&#23460;&#12289;&#29366;&#24577;&#25110;&#25628;&#32034;&#26465;&#20214;&#21518;&#20877;&#35797;
      </div>
    </div>

    <div
      v-else
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-5"
    >
      <article
        v-for="record in records"
        :key="record.id"
        :class="[
          'group cursor-pointer rounded-[24px] border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] px-4 py-4 transition-all duration-200',
          cardTone(record.status),
        ]"
        @click="$emit('select', record)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div
              class="truncate text-[22px] font-black leading-none tracking-[-0.04em] text-slate-900"
            >
              {{ record.name || '\u672a\u77e5\u60a3\u8005' }}
            </div>
            <div class="mt-2 truncate text-[14px] font-semibold tracking-[0.02em] text-slate-500">
              {{ record.id }}
            </div>
          </div>

          <span
            :class="statusTone(record.status)"
            class="inline-flex shrink-0 items-center rounded-full px-3 py-1 text-[11px] font-bold"
          >
            {{ getStatusLabel(record.status) }}
          </span>
        </div>

        <div class="mt-5 flex items-center gap-2 text-[13px] text-slate-600">
          <span class="truncate font-semibold text-slate-600">{{
            record.department || '\u672a\u5206\u79d1\u5ba4'
          }}</span>
          <span class="h-1 w-1 rounded-full bg-slate-300" />
          <span
            :class="stayTone(record.days)"
            class="font-semibold"
          >{{
            stayLabel(record.days)
          }}</span>
        </div>

        <div class="mt-4 border-t border-slate-100 pt-4">
          <div class="text-[12px] font-medium tracking-[0.08em] text-slate-400">
            &#20303;&#38498;&#21306;&#38388;
          </div>
          <div class="mt-1 text-[18px] font-bold tracking-[-0.02em] text-slate-700">
            {{ formatDateRange(record.admissionDate, record.dischargeDate) }}
          </div>
        </div>
      </article>
    </div>

    <div
      v-if="totalPages > 1"
      class="flex justify-center py-5"
    >
      <a-pagination
        v-model:current="currentPageModel"
        :total="total"
        :page-size="50"
        size="small"
        show-quick-jumper
        :show-total="(value: number) => `\u5171 ${value} \u4f8b`"
        @change="$emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import { getStatusLabel, getStatusTheme } from '../normalize'
import type { PatientRecord } from '../types'

const props = defineProps<{
  records: PatientRecord[]
  currentPage: number
  total: number
  totalPages: number
}>()

const emit = defineEmits<{
  select: [record: PatientRecord]
  'page-change': [page: number]
}>()

const currentPageModel = computed({
  get: () => props.currentPage,
  set: (value) => emit('page-change', value),
})

function cardTone(status?: string) {
  if (getStatusTheme(status || 'pending') === 'rose') {
    return 'border-rose-100/90 shadow-[0_10px_24px_rgba(15,23,42,0.045)] hover:-translate-y-1 hover:border-rose-200 hover:shadow-[0_16px_30px_rgba(225,29,72,0.08)]'
  }
  if (getStatusTheme(status || 'pending') === 'blue') {
    return 'border-blue-100/90 shadow-[0_10px_24px_rgba(15,23,42,0.045)] hover:-translate-y-1 hover:border-blue-200 hover:shadow-[0_16px_30px_rgba(37,99,235,0.08)]'
  }
  return 'border-slate-200/90 shadow-[0_10px_24px_rgba(15,23,42,0.04)] hover:-translate-y-1 hover:border-blue-200 hover:shadow-[0_16px_30px_rgba(37,99,235,0.07)]'
}

function statusTone(status?: string) {
  const theme = getStatusTheme(status || 'pending')
  if (theme === 'rose') return 'bg-rose-50 text-rose-600'
  if (theme === 'blue') return 'bg-blue-50 text-blue-700'
  if (theme === 'emerald') return 'bg-slate-100 text-slate-700'
  return 'bg-amber-50 text-amber-700'
}

function stayTone(days?: number) {
  if (!days || days <= 7) return 'text-slate-500'
  if (days <= 14) return 'text-blue-600'
  return 'text-indigo-600'
}

function stayLabel(days?: number) {
  return `\u4f4f\u9662 ${days || 0} \u5929`
}

function formatDateRange(admissionDate?: string, dischargeDate?: string) {
  const start = admissionDate || '--'
  const end = dischargeDate || '--'
  return `${start} -> ${end}`
}
</script>
