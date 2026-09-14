<template>
  <section
    class="rounded-[16px] border border-slate-200 bg-white px-5 py-4 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)]"
  >
    <div class="flex items-center justify-between gap-3 pb-3 border-b border-slate-100">
      <div>
        <h3 class="text-[15px] font-bold text-slate-900">
          我的待办汇总
        </h3>
      </div>
      <div class="rounded-md bg-[#eaf2ff] px-2 py-0.5 text-[11px] font-semibold text-[#2b6cf6]">
        个人执行项
      </div>
    </div>
    <div class="mt-4 grid grid-cols-2 gap-3">
      <article
        v-for="card in cards"
        :key="card.label"
        class="rounded-[12px] border border-slate-100 p-3.5 bg-slate-50/50"
      >
        <div class="flex items-center gap-2">
          <span
            class="h-2 w-2 rounded-full"
            :class="card.dotColor"
          />
          <span class="text-[12px] font-medium text-slate-600">{{ card.label }}</span>
        </div>
        <div
          class="mt-2 text-[24px] font-bold text-[#1d1d1f] font-mono"
          style="font-variant-numeric: tabular-nums"
        >
          {{ card.value }}
        </div>
        <div class="mt-1 text-[11px] text-slate-400">
          {{ card.desc }}
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  summary: {
    pending_total: number
    in_progress_total: number
    overdue_total: number
    high_priority_total: number
  }
}>()

const cards = computed(() => [
  {
    label: '待处理',
    value: props.summary.pending_total || 0,
    dotColor: 'bg-[#2b6cf6]',
    desc: '待进入处理流程',
  },
  {
    label: '进行中',
    value: props.summary.in_progress_total || 0,
    dotColor: 'bg-emerald-400',
    desc: '已在处理中的病历',
  },
  {
    label: '高优先级',
    value: props.summary.high_priority_total || 0,
    dotColor: 'bg-amber-400',
    desc: 'P0 / P1 事项',
  },
  {
    label: '已超时',
    value: props.summary.overdue_total || 0,
    dotColor: 'bg-rose-500',
    desc: '优先清理',
  },
])
</script>
