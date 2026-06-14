<template>
  <section class="grid grid-cols-1 gap-5 xl:grid-cols-[1.1fr_0.9fr_0.9fr]">
    <article
      class="rounded-[16px] border border-slate-200 bg-white px-5 py-4 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)]"
    >
      <div class="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <h3 class="text-[15px] font-bold text-slate-900">首屏关键指标通报</h3>
        </div>
      </div>
      <div class="mt-4 space-y-3 max-h-[360px] overflow-y-auto custom-scrollbar">
        <article
          v-for="item in batchSummaries"
          :key="item.id"
          class="rounded-[12px] border border-slate-100 bg-slate-50/50 p-3"
        >
          <div class="flex items-center justify-between gap-3 min-w-0">
            <div class="truncate text-[13px] font-bold text-slate-900">
              {{ item.title }}
            </div>
            <a-tag
              color="blue"
              class="!mr-0 !text-[10px] !border-[#0066cc]/15 !bg-[#eaf2ff] !text-[#0066cc] shrink-0"
            >
              {{ workflowLabel(item.workflow_type) }}
            </a-tag>
          </div>
          <div class="mt-2 text-[12px] leading-relaxed text-slate-600">
            {{ item.content }}
          </div>
          <div
            class="mt-2 text-[11px] text-slate-400 font-mono"
            style="font-variant-numeric: tabular-nums"
          >
            {{ formatDateTime(item.created_at) }}
          </div>
        </article>
        <a-empty v-if="!batchSummaries.length" description="暂无通报提示" class="py-10" />
      </div>
    </article>

    <article
      class="rounded-[16px] border border-slate-200 bg-white px-5 py-4 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)]"
    >
      <div class="pb-3 border-b border-slate-100">
        <h3 class="text-[15px] font-bold text-slate-900">科室风险分布</h3>
      </div>
      <div class="mt-4 space-y-3 max-h-[360px] overflow-y-auto custom-scrollbar">
        <div
          v-for="item in departmentRisk"
          :key="item.department"
          class="rounded-[12px] border border-slate-100 bg-slate-50/50 p-3"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="text-[13px] font-bold text-slate-900 truncate">{{ item.department }}</span>
            <span
              class="text-[13px] font-bold text-[#1d1d1f] font-mono"
              style="font-variant-numeric: tabular-nums"
              >{{ item.count }}</span
            >
          </div>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div
              class="h-full rounded-full bg-[#0066cc]"
              :style="{ width: `${calcPercent(item.count)}%` }"
            />
          </div>
        </div>
        <a-empty v-if="!departmentRisk.length" description="暂无科室风险数据" class="py-10" />
      </div>
    </article>

    <article
      class="rounded-[16px] border border-slate-200 bg-white px-5 py-4 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)]"
    >
      <div class="pb-3 border-b border-slate-100">
        <h3 class="text-[15px] font-bold text-slate-900">Workflow 状态分布</h3>
      </div>
      <div class="mt-4 space-y-3 max-h-[360px] overflow-y-auto custom-scrollbar">
        <div
          v-for="item in workflowStatus"
          :key="item.workflow_type"
          class="rounded-[12px] border border-slate-100 bg-slate-50/50 p-3"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="text-[13px] font-bold text-slate-900">{{
              workflowLabel(item.workflow_type)
            }}</span>
            <span
              class="text-[11px] text-slate-500 font-mono"
              style="font-variant-numeric: tabular-nums"
            >
              总数: {{ workflowTotal(item) }}
            </span>
          </div>
          <div class="mt-3 grid grid-cols-3 gap-2">
            <div class="rounded-lg bg-amber-50 px-2 py-2 text-center">
              <div
                class="text-[14px] font-bold text-amber-700 font-mono"
                style="font-variant-numeric: tabular-nums"
              >
                {{ item.pending || 0 }}
              </div>
              <div class="text-[10px] font-bold text-amber-600 mt-1">待处理</div>
            </div>
            <div class="rounded-lg bg-emerald-50 px-2 py-2 text-center">
              <div
                class="text-[14px] font-bold text-emerald-700 font-mono"
                style="font-variant-numeric: tabular-nums"
              >
                {{ item.in_progress || item.running || 0 }}
              </div>
              <div class="text-[10px] font-bold text-emerald-600 mt-1">处理中</div>
            </div>
            <div class="rounded-lg bg-rose-50 px-2 py-2 text-center">
              <div
                class="text-[14px] font-bold text-rose-700 font-mono"
                style="font-variant-numeric: tabular-nums"
              >
                {{ item.overdue || item.failed || 0 }}
              </div>
              <div class="text-[10px] font-bold text-rose-600 mt-1">风险项</div>
            </div>
          </div>
        </div>
        <a-empty v-if="!workflowStatus.length" description="暂无状态数据" class="py-10" />
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  WorkstationHomeBatchSummary,
  WorkstationHomeDepartmentRiskItem,
  WorkstationHomeWorkflowStatusItem,
} from '@/views/workstation-v2/types'

const props = defineProps<{
  batchSummaries: WorkstationHomeBatchSummary[]
  departmentRisk: WorkstationHomeDepartmentRiskItem[]
  workflowStatus: WorkstationHomeWorkflowStatusItem[]
  formatDateTime: (value?: string | null) => string
  workflowLabel: (value?: string) => string
}>()

const maxCount = computed(() =>
  Math.max(1, ...props.departmentRisk.map((item) => Number(item.count || 0))),
)

function calcPercent(value: number): number {
  return Math.max(12, Math.round((Number(value || 0) / maxCount.value) * 100))
}

function workflowTotal(item: WorkstationHomeWorkflowStatusItem): number {
  return (
    Number(item.pending || 0) +
    Number(item.in_progress || item.running || 0) +
    Number(item.overdue || item.failed || 0)
  )
}
</script>
