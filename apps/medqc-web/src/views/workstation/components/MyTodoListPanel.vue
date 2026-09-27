<template>
  <section
    class="rounded-[16px] border border-slate-200 bg-white shadow-[0_4px_12px_-4px_rgba(0,0,0,0.03)] flex flex-col h-full overflow-hidden"
  >
    <header class="border-b border-slate-100 px-4 py-3 shrink-0 bg-slate-50/30">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5">
          <div
            class="flex h-6 w-6 items-center justify-center rounded-md bg-[#eaf2ff] text-[#0a6cff] shadow-sm"
          >
            <CheckSquareFilled class="text-[12px]" />
          </div>
          <div>
            <div class="text-[11px] font-semibold text-[#0a6cff]">
              我的紧急队列
            </div>
            <h3 class="text-[16px] font-semibold text-[#1d1d1f]">
              我的特急待办
            </h3>
          </div>
        </div>
        <div>
          <span
            class="rounded-full border border-black/10 bg-white px-2.5 py-0.5 text-[11px] font-semibold text-black/60 font-mono shadow-sm"
            style="font-variant-numeric: tabular-nums"
          >
            {{ items.length }} 项
          </span>
        </div>
      </div>

      <div class="mt-3 grid grid-cols-3 gap-2">
        <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <div class="text-[11px] text-slate-400">
            待处理
          </div>
          <div class="mt-1 text-[18px] font-bold text-[#1d1d1f] font-mono">
            {{ summary.pending_total || 0 }}
          </div>
        </div>
        <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <div class="text-[11px] text-slate-400">
            进行中
          </div>
          <div class="mt-1 text-[18px] font-bold text-[#0a6cff] font-mono">
            {{ summary.in_progress_total || 0 }}
          </div>
        </div>
        <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <div class="text-[11px] text-slate-400">
            已超时
          </div>
          <div class="mt-1 text-[18px] font-bold text-red-600 font-mono">
            {{ summary.overdue_total || 0 }}
          </div>
        </div>
      </div>
    </header>

    <div class="flex-1 overflow-y-auto custom-scrollbar">
      <div class="divide-y divide-slate-100/70">
        <div
          v-for="item in items"
          :key="item.id"
          class="group relative flex cursor-pointer items-start gap-3 px-4 py-3 transition-all duration-300 hover:bg-black/[0.025]"
          @click="emit('open', item)"
        >
          <div
            class="absolute left-0 top-2.5 bottom-2.5 w-1 rounded-r-md transition-all duration-300 group-hover:scale-y-110"
            :class="priorityStripeClass(item.priority)"
          />

          <div class="flex-1 min-w-0">
            <div class="flex items-baseline justify-between gap-3">
              <div class="flex items-center gap-3 min-w-0">
                <span class="text-[14px] font-bold text-slate-900 truncate">
                  {{ item.patient_name || '--' }}
                </span>
                <span class="text-[12px] font-medium text-slate-500 truncate mt-0.5">
                  {{ item.visit_id || '--' }} <span class="mx-1 text-slate-300">/</span>
                  {{ item.department || '未分科室' }}
                </span>
              </div>

              <div class="flex items-center gap-3 shrink-0">
                <div
                  class="text-[11px] text-slate-400 font-mono tracking-wide opacity-80 group-hover:opacity-100 transition-opacity"
                >
                  {{ formatDateTime(item.due_at) }}
                </div>
                <div
                  class="flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0 text-[#0a6cff]"
                >
                  <ArrowRightOutlined class="text-[12px]" />
                </div>
              </div>
            </div>

            <div class="mt-2 flex items-center justify-between gap-3">
              <div
                class="text-[12px] leading-relaxed text-slate-400 line-clamp-1 group-hover:text-slate-600 transition-colors duration-300 flex-1 min-w-0"
              >
                {{ item.summary || '暂无详细摘要' }}
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <span
                  v-if="item.active_defect_count > 0"
                  class="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-[10.5px] font-semibold text-red-600 ring-1 ring-inset ring-red-500/20 shadow-sm transition-transform group-hover:scale-105"
                >
                  <CloseCircleFilled class="mr-1 text-[10px]" />
                  {{ item.active_defect_count }} 缺陷
                </span>

                <span
                  class="rounded bg-slate-100 px-1.5 py-0.5 text-[10.5px] font-bold text-slate-500"
                >
                  {{ workflowLabel(item.workflow_type) }}
                </span>

                <span
                  class="rounded px-1.5 py-0.5 text-[10.5px] font-bold"
                  :class="taskStatusClass(item.task_status)"
                >
                  {{ taskStatusLabel(item.task_status) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="!items.length"
        class="py-16 flex flex-col items-center justify-center text-center"
      >
        <div
          class="h-12 w-12 rounded-full bg-slate-50 border-2 border-dashed border-slate-200 flex items-center justify-center text-slate-300 mb-3 shadow-inner"
        >
          <CheckOutlined class="text-[20px]" />
        </div>
        <div class="text-[13.5px] font-medium text-slate-500">
          太棒了，当前没有需要跟进的待办
        </div>
        <div class="text-[12px] text-slate-400 mt-1">
          您可以通过其他纬度筛选工作
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import {
  CheckSquareFilled,
  ArrowRightOutlined,
  CheckOutlined,
  CloseCircleFilled,
} from '@ant-design/icons-vue'
import type { WorkstationHomeTodoItem } from '@/views/workstation-v2/types'

defineProps<{
  items: WorkstationHomeTodoItem[]
  summary: {
    pending_total: number
    in_progress_total: number
    overdue_total: number
    high_priority_total: number
  }
  formatDateTime: (value?: string | null) => string
  workflowLabel: (value?: string) => string
  taskStatusLabel: (value?: string) => string
  taskStatusColor: (value?: string) => string
  priorityLabel: (value?: string) => string
  priorityColor: (value?: string) => string
}>()

const emit = defineEmits<{
  open: [item: WorkstationHomeTodoItem]
}>()

function priorityStripeClass(priority?: string) {
  if (priority === 'critical') return 'bg-red-500 shadow-[0_0_0_3px_rgba(239,68,68,0.08)]'
  if (priority === 'high') return 'bg-orange-400'
  if (priority === 'medium') return 'bg-amber-300'
  return 'bg-[#0a6cff]'
}

function taskStatusClass(status?: string) {
  if (status === 'in_progress') return 'bg-[#eaf2ff] text-[#0a6cff]'
  if (status === 'overdue') return 'bg-red-50 text-red-600'
  return 'bg-amber-50 text-amber-600'
}
</script>
