<template>
  <div class="flex items-center gap-3">
    <button
      v-for="item in indicators"
      :key="item.key"
      type="button"
      class="group relative flex items-center gap-2 rounded-md border px-3 py-1.5 transition-all duration-200 outline-none select-none"
      :class="
        activeKey === item.key
          ? [item.activeBgColor, item.activeBorderColor, 'shadow-[0_1px_2px_rgba(0,0,0,0.03)]']
          : 'bg-white border-transparent hover:bg-slate-100/60 hover:border-slate-200'
      "
      @click="emit('select', item.key)"
    >
      <div class="flex items-center gap-1.5">
        <span
          class="text-[12px] font-bold"
          :class="activeKey === item.key ? item.activeTextColor : 'text-slate-500'"
        >
          <span class="mr-1 opacity-80">{{ item.dotEmoji }}</span>
          {{ item.label }}
        </span>
      </div>
      <span
        class="ml-2 rounded-sm px-1.5 py-0.5 text-[11px] font-black font-mono leading-none transition-colors"
        :class="
          activeKey === item.key
            ? item.numActiveBgColor + ' ' + item.activeTextColor
            : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200/60'
        "
        style="font-variant-numeric: tabular-nums"
      >
        {{ item.value }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HomeKpis } from '@/views/workstation-v2/types'

const props = defineProps<{
  kpis: HomeKpis
  activeKey: string
  dateLabel: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()

const indicators = computed(() => [
  {
    key: 'my_pending_total',
    label: '待处理',
    dotEmoji: '🟡',
    value: props.kpis.my_pending_total,
    activeBgColor: 'bg-amber-50',
    activeBorderColor: 'border-amber-200',
    activeTextColor: 'text-amber-800',
    numActiveBgColor: 'bg-amber-100',
  },
  {
    key: 'high_risk_total',
    label: '高风险',
    dotEmoji: '🔴',
    value: props.kpis.high_risk_total,
    activeBgColor: 'bg-red-50',
    activeBorderColor: 'border-red-200',
    activeTextColor: 'text-red-700',
    numActiveBgColor: 'bg-red-100',
  },
  {
    key: 'my_overdue_total',
    label: '已超时',
    dotEmoji: '🟠',
    value: props.kpis.my_overdue_total,
    activeBgColor: 'bg-orange-50',
    activeBorderColor: 'border-orange-200',
    activeTextColor: 'text-orange-800',
    numActiveBgColor: 'bg-orange-100',
  },
  {
    key: 'my_in_progress_total',
    label: '进行中',
    dotEmoji: '🔵',
    value: props.kpis.my_in_progress_total,
    activeBgColor: 'bg-blue-50',
    activeBorderColor: 'border-blue-200',
    activeTextColor: 'text-blue-700',
    numActiveBgColor: 'bg-blue-100',
  },
])
</script>
