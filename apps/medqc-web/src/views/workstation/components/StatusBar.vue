<template>
  <div
    class="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
  >
    <button
      v-for="item in indicators"
      :key="item.key"
      type="button"
      class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-[13px] transition-colors duration-150"
      :class="
        activeKey === item.key
          ? 'bg-blue-50 text-blue-700 font-bold'
          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
      "
      @click="emit('select', item.key)"
    >
      <span
        class="h-2 w-2 rounded-full shrink-0"
        :class="item.dotColor"
      />
      <span class="font-medium">{{ item.label }}</span>
      <span
        class="font-mono font-extrabold"
        style="font-variant-numeric: tabular-nums"
      >{{
        item.value
      }}</span>
    </button>

    <div class="ml-auto flex items-center text-[12px] text-slate-400">
      <CalendarOutlined class="mr-1 text-[11px]" />
      {{ dateLabel }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CalendarOutlined } from '@ant-design/icons-vue'
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
    value: props.kpis.my_pending_total,
    dotColor: 'bg-amber-500',
  },
  {
    key: 'high_risk_total',
    label: '高风险',
    value: props.kpis.high_risk_total,
    dotColor: 'bg-red-500',
  },
  {
    key: 'my_overdue_total',
    label: '已超时',
    value: props.kpis.my_overdue_total,
    dotColor: 'bg-orange-500',
  },
  {
    key: 'my_in_progress_total',
    label: '进行中',
    value: props.kpis.my_in_progress_total,
    dotColor: 'bg-blue-500',
  },
])
</script>
