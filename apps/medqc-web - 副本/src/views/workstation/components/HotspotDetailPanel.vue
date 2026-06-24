<template>
  <section
    class="rounded-[16px] border border-slate-200 bg-white p-4 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)] overflow-y-auto custom-scrollbar"
  >
    <template v-if="item">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">
            Selected Context
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <a-tag
              :color="severityColor(item.severity)"
              class="!mr-0 !text-[11px] !leading-[20px] !border-transparent"
            >
              {{ severityLabel(item.severity) }}
            </a-tag>
            <a-tag
              color="blue"
              class="!mr-0 !text-[11px] !leading-[20px] !border-transparent !bg-blue-50 !text-blue-600"
            >
              {{ workflowLabel(item.workflow_type) }}
            </a-tag>
          </div>
          <h3 class="mt-2 text-[18px] font-extrabold leading-tight text-slate-900 line-clamp-2">
            {{ item.title }}
          </h3>
          <p class="mt-1.5 text-[13px] leading-relaxed text-slate-500">
            {{ item.summary }}
          </p>
        </div>
        <div
          class="rounded-xl border border-slate-100 bg-slate-50/50 px-3 py-2.5 text-right shrink-0"
        >
          <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            活跃问题
          </div>
          <div
            class="mt-1 text-[22px] font-extrabold text-slate-900 font-mono"
            style="font-variant-numeric: tabular-nums"
          >
            {{ item.active_defect_count || 0 }}
          </div>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-2 gap-3">
        <article class="rounded-xl border border-slate-100 bg-slate-50/50 p-3.5">
          <div class="text-[11px] font-bold text-slate-400">
            患者信息
          </div>
          <div class="mt-1.5 text-[14px] font-bold text-slate-800">
            {{ item.patient_name || '--' }}
          </div>
          <div
            class="mt-0.5 text-[12px] text-slate-500 font-mono"
            style="font-variant-numeric: tabular-nums"
          >
            {{ item.visit_id || item.record_id || '--' }}
          </div>
        </article>
        <article class="rounded-xl border border-slate-100 bg-slate-50/50 p-3.5">
          <div class="text-[11px] font-bold text-slate-400">
            科室及时间
          </div>
          <div class="mt-1.5 text-[14px] font-bold text-slate-800">
            {{ item.department || '未分科室' }}
          </div>
          <div
            class="mt-0.5 text-[12px] text-slate-500 font-mono"
            style="font-variant-numeric: tabular-nums"
          >
            {{ formatDateTime(item.latest_created_at) }}
          </div>
        </article>
        <article class="rounded-xl border border-slate-100 bg-slate-50/50 p-3.5">
          <div class="text-[11px] font-bold text-slate-400">
            流程状态
          </div>
          <div class="mt-1.5 text-[14px] font-bold text-slate-800">
            {{ queueStatusLabel(item.queue_status) }}
          </div>
          <div class="mt-0.5 text-[12px] text-slate-500">
            来源: <span class="font-mono">{{ item.queue_status_source || 'backfill' }}</span> /
            未读: <span class="font-mono">{{ item.unread_count || 0 }}</span>
          </div>
        </article>
        <article class="rounded-xl border border-slate-100 bg-slate-50/50 p-3.5">
          <div class="text-[11px] font-bold text-slate-400">
            质控与缺陷
          </div>
          <div class="mt-1.5 flex items-center gap-2">
            <span class="text-[14px] font-bold text-slate-800">{{
              item.latest_qc_grade || '--'
            }}</span>
            <span
              class="rounded bg-slate-200 px-1.5 text-[10px] font-bold text-slate-600 font-mono"
            >{{ item.latest_qc_score ?? '--' }}</span>
          </div>
          <div class="mt-0.5 text-[12px] text-slate-500">
            活跃缺陷:
            <span class="font-mono font-bold text-red-500">{{
              item.active_defect_count || 0
            }}</span>
          </div>
        </article>
      </div>

      <div class="mt-4 rounded-xl border border-blue-100 bg-blue-50/50 p-3.5">
        <div class="flex items-center gap-2 text-[12px] font-bold text-blue-700">
          <span>处理建议</span>
        </div>
        <div class="mt-2 text-[13px] leading-relaxed text-blue-900/80">
          优先进入
          <span class="font-semibold">{{ workflowLabel(item.workflow_type) }}</span>
          流程，先核对当前活跃缺陷和最新质控结果，再决定是否继续复核、补充说明或关闭问题。
        </div>
      </div>

      <div class="mt-5 flex flex-wrap gap-3">
        <a-button
          type="primary"
          class="!h-10 !rounded-lg !border-0 !bg-blue-600 !px-6 !font-bold !text-white hover:!bg-blue-500 shadow-sm"
          :disabled="!item.record_id"
          @click="emit('open', item)"
        >
          立即处理
        </a-button>
        <a-button
          class="!h-10 !rounded-lg !border-slate-300 !bg-white !px-5 !font-bold !text-slate-600 hover:!text-blue-600 hover:!border-blue-300 shadow-sm"
          @click="emit('openWorklist', item)"
        >
          查看病历池
        </a-button>
      </div>
    </template>

    <div
      v-else
      class="flex h-full min-h-[420px] flex-col items-center justify-center rounded-xl bg-slate-50/60 text-center"
    >
      <div class="text-[15px] font-bold text-slate-600">
        请在左侧选择一个问题集中点
      </div>
      <div class="mt-2 max-w-[260px] text-[12px] leading-relaxed text-slate-400">
        此处将展示深入的病历上下文、活跃缺陷分布以及下一步处理推荐。
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { WorkstationHomeHotspotItem } from '@/views/workstation-v2/types'

defineProps<{
  item: WorkstationHomeHotspotItem | null
  formatDateTime: (value?: string | null) => string
  severityLabel: (value?: string) => string
  severityColor: (value?: string) => string
  workflowLabel: (value?: string) => string
  queueStatusLabel: (value?: string) => string
}>()

const emit = defineEmits<{
  open: [item: WorkstationHomeHotspotItem]
  openWorklist: [item: WorkstationHomeHotspotItem]
}>()
</script>
