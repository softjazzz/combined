<template>
  <div class="custom-scrollbar flex-1 overflow-y-auto p-3 xl:p-3.5">
    <div v-if="records.length === 0" class="flex h-full flex-col items-center justify-center text-slate-400">
      <InboxOutlined class="mb-3 text-4xl" />
      <div class="text-sm">暂无病历记录</div>
    </div>

    <div v-else class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-6">
      <article
        v-for="record in records"
        :key="record.id"
        @click="$emit('select', record)"
        :class="[
          'group relative cursor-pointer overflow-hidden rounded-[18px] border bg-white px-3 py-2.5 transition-all duration-200',
          cardTone(record.status),
        ]"
      >
        <div class="mb-2.5 flex items-start">
          <div class="min-w-0">
            <div class="truncate text-[14px] font-black leading-tight tracking-[-0.02em] text-slate-800">
              {{ record.name || '未知患者' }}
            </div>
            <div class="mt-0.5 truncate text-[11px] font-medium text-slate-500">
              {{ record.id }}
            </div>
          </div>
        </div>

        <div class="mb-2.5 flex flex-wrap items-center gap-1.5">
          <span class="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-500">
            {{ record.department || '未分科' }}
          </span>
          <span :class="['rounded-full px-2.5 py-1 text-[10px] font-semibold', stayTone(record.days)]">
            住院 {{ record.days || 0 }} 天
          </span>
        </div>

        <div class="rounded-[14px] border border-slate-200/70 bg-slate-50/82 px-3 py-2">
          <div class="grid grid-cols-2 gap-2 text-[11px]">
            <div>
              <div class="text-[10px] text-slate-400">入院</div>
              <div class="mt-0.5 font-mono font-bold text-slate-700">{{ record.admissionDate || '--' }}</div>
            </div>
            <div>
              <div class="text-[10px] text-slate-400">出院</div>
              <div class="mt-0.5 font-mono font-bold text-slate-700">{{ record.dischargeDate || '--' }}</div>
            </div>
          </div>
        </div>

      </article>
    </div>

    <div v-if="totalPages > 1" class="flex justify-center py-4">
      <a-pagination
        v-model:current="currentPageModel"
        :total="total"
        :page-size="50"
        size="small"
        show-quick-jumper
        :show-total="(t: number) => `共 ${t} 例`"
        @change="$emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import { isDefectStatus } from '../normalize'
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
  set: (val) => emit('page-change', val),
})

function cardTone(status?: string) {
  if (isDefectStatus(status)) {
    return 'border-slate-200/85 shadow-[0_5px_16px_rgba(15,23,42,0.035)] hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-[0_10px_22px_rgba(37,99,235,0.05)]'
  }
  return 'border-slate-200/85 shadow-[0_5px_16px_rgba(15,23,42,0.035)] hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-[0_10px_22px_rgba(37,99,235,0.05)]'
}

function stayTone(days?: number) {
  if (!days || days <= 7) return 'bg-slate-100 text-slate-600'
  if (days <= 14) return 'bg-blue-50 text-blue-700'
  return 'bg-indigo-50 text-indigo-700'
}
</script>
