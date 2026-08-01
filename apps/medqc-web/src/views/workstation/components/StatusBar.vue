<template>
  <div class="flex items-center gap-2 mb-2">
    <!-- 将原来分散的指标整合为无缝分段选择器 (Segmented Control / Linear Style Tabs) -->
    <div
      class="flex p-0.5 rounded-lg bg-slate-100/80 border border-slate-200/60 shadow-inner overflow-hidden"
    >
      <button
        type="button"
        class="flex items-center gap-2 rounded-md px-4 py-1.5 transition-all duration-200 outline-none select-none min-w-[120px] justify-center"
        :class="
          activeKey === ''
            ? 'bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] ring-1 ring-black/5 text-slate-800'
            : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
        "
        @click="emit('select', '')"
      >
        <span class="text-[12.5px] font-bold">全部任务</span>
        <span
          class="rounded px-1.5 py-0.5 text-[11px] font-bold font-mono leading-none bg-slate-100 text-slate-500"
          style="font-variant-numeric: tabular-nums"
        >
          {{ totalTasks }}
        </span>
      </button>

      <button
        v-for="item in indicators"
        :key="item.key"
        type="button"
        class="flex items-center gap-2 rounded-md px-4 py-1.5 transition-all duration-200 outline-none select-none min-w-[110px] justify-center"
        :class="
          activeKey === item.key
            ? `bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] ring-1 ring-black/5 ${item.activeTextColor}`
            : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
        "
        @click="emit('select', item.key)"
      >
        <div class="flex items-center gap-1.5">
          <span
            class="h-2 w-2 rounded-full"
            :class="item.dotBgClass"
          />
          <span class="text-[12.5px] font-bold">
            {{ item.label }}
          </span>
        </div>
        <span
          class="rounded px-1.5 py-0.5 text-[11px] font-bold font-mono leading-none transition-colors"
          :class="
            activeKey === item.key
              ? item.numActiveBgColor
              : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200/60'
          "
          style="font-variant-numeric: tabular-nums"
        >
          {{ item.value }}
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HomeKpis } from '@/views/workstation-v2/types'

const props = defineProps<{
  kpis: HomeKpis
  activeKey: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()

const totalTasks = computed(() => {
  return props.kpis.my_pending_total + props.kpis.my_in_progress_total + props.kpis.my_overdue_total
})

// P0/P1 合计的高风险通常是指系统性高风险，但也包括超时等急症
const indicators = computed(() => [
  {
    key: 'high_risk_total',
    label: '高风险',
    value: props.kpis.high_risk_total,
    dotBgClass: 'bg-red-500',
    activeTextColor: 'text-red-700',
    numActiveBgColor: 'bg-red-50 text-red-700',
  },
  {
    key: 'my_overdue_total',
    label: '已超时',
    value: props.kpis.my_overdue_total,
    dotBgClass: 'bg-orange-500',
    activeTextColor: 'text-orange-700',
    numActiveBgColor: 'bg-orange-50 text-orange-700',
  },
  {
    key: 'my_in_progress_total',
    label: '进行中',
    value: props.kpis.my_in_progress_total,
    dotBgClass: 'bg-[#0066cc]',
    activeTextColor: 'text-[#0066cc]',
    numActiveBgColor: 'bg-[#eaf2ff] text-[#0066cc]',
  },
])
</script>
