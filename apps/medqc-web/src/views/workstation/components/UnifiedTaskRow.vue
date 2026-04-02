<template>
  <div
    class="group relative transition-colors duration-150"
    :class="isExpanded ? 'bg-blue-50/30' : 'hover:bg-slate-50/80'"
  >
    <!-- 左侧优先级色线 -->
    <div
      class="absolute left-0 top-0 bottom-0 w-1 transition-all"
      :class="stripeClass"
    />

    <!-- 主行 -->
    <div
      class="flex items-center gap-4 px-5 py-3 cursor-pointer"
      @click="emit('toggleExpand', task.id)"
    >
      <!-- 来源标签 -->
      <span
        class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold leading-none"
        :class="
          task.source_type === 'hotspot'
            ? 'bg-orange-50 text-orange-600 ring-1 ring-inset ring-orange-200'
            : 'bg-blue-50 text-blue-600 ring-1 ring-inset ring-blue-200'
        "
      >
        {{ task.source_type === 'hotspot' ? '问题' : '待办' }}
      </span>

      <!-- 患者 + 住院号 -->
      <div class="flex items-center gap-2 min-w-[140px] shrink-0">
        <span
          v-if="task.unread_count > 0"
          class="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0"
        />
        <span class="text-[14px] font-bold text-slate-900 truncate">
          {{ task.patient_name || '--' }}
        </span>
        <span class="text-[12px] text-slate-400 font-mono truncate">
          {{ task.visit_id || '--' }}
        </span>
      </div>

      <!-- 科室 -->
      <span class="text-[12px] text-slate-500 truncate min-w-[60px] shrink-0">
        {{ task.department || '未分科室' }}
      </span>

      <!-- 流程类型 -->
      <span
        class="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600"
      >
        {{ workflowLabel(task.workflow_type) }}
      </span>

      <!-- 问题摘要（弹性填充） -->
      <div class="flex-1 min-w-0">
        <span class="text-[13px] text-slate-700 truncate block">
          {{ task.title || task.summary || '暂无摘要' }}
        </span>
      </div>

      <!-- 缺陷数 -->
      <span
        v-if="task.active_defect_count > 0"
        class="shrink-0 inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-black text-red-600 ring-1 ring-inset ring-red-500/20"
      >
        <CloseCircleFilled class="mr-0.5 text-[9px]" />
        {{ task.active_defect_count }}
      </span>

      <!-- 时间 -->
      <span
        class="shrink-0 text-[11px] text-slate-400 font-mono w-[80px] text-right"
        style="font-variant-numeric: tabular-nums"
      >
        {{ formatDateTime(task.latest_created_at || task.due_at) }}
      </span>

      <!-- 操作按钮 -->
      <button
        type="button"
        class="shrink-0 rounded-lg bg-blue-600 px-3 py-1 text-[12px] font-bold text-white shadow-sm transition-all hover:bg-blue-500 hover:shadow active:scale-95"
        @click.stop="emit('open', task)"
      >
        立即处理
      </button>
    </div>

    <!-- 行内展开详情 -->
    <div
      v-if="isExpanded"
      class="border-t border-slate-100 bg-slate-50/50 px-5 py-3 ml-5"
    >
      <div class="flex flex-wrap gap-x-6 gap-y-2 text-[12px]">
        <div>
          <span class="text-slate-400">风险级别</span>
          <span
            class="ml-1.5 font-bold"
            :class="severityTextClass"
          >{{
            severityLabel(task.severity)
          }}</span>
        </div>
        <div v-if="task.task_status">
          <span class="text-slate-400">任务状态</span>
          <span class="ml-1.5 font-bold text-slate-700">{{
            taskStatusLabel(task.task_status)
          }}</span>
        </div>
        <div v-if="task.latest_qc_grade">
          <span class="text-slate-400">质控等级</span>
          <span class="ml-1.5 font-bold text-slate-700">{{ task.latest_qc_grade }}</span>
          <span
            v-if="task.latest_qc_score != null"
            class="ml-1 rounded bg-slate-200 px-1 text-[10px] font-bold text-slate-600 font-mono"
          >{{ task.latest_qc_score }}</span>
        </div>
        <div>
          <span class="text-slate-400">活跃缺陷</span>
          <span
            class="ml-1.5 font-bold font-mono"
            :class="task.active_defect_count > 0 ? 'text-red-600' : 'text-slate-500'"
          >{{ task.active_defect_count || 0 }}</span>
        </div>
        <div>
          <span class="text-slate-400">未读消息</span>
          <span class="ml-1.5 font-bold text-slate-700 font-mono">{{
            task.unread_count || 0
          }}</span>
        </div>
      </div>
      <div
        v-if="task.summary"
        class="mt-2 text-[12px] leading-relaxed text-slate-500 line-clamp-2"
      >
        {{ task.summary }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CloseCircleFilled } from '@ant-design/icons-vue'
import type { UnifiedTaskItem } from '@/views/workstation-v2/types'

const props = defineProps<{
  task: UnifiedTaskItem
  expandedId: string
  formatDateTime: (value?: string | null) => string
}>()

const emit = defineEmits<{
  open: [task: UnifiedTaskItem]
  toggleExpand: [id: string]
}>()

const isExpanded = computed(() => props.expandedId === props.task.id)

const stripeClass = computed(() => {
  const s = (props.task.severity || '').toLowerCase()
  const p = (props.task.priority || '').toLowerCase()
  if (s === 'critical' || p === 'critical') return 'bg-red-500'
  if (s === 'high' || p === 'high') return 'bg-orange-400'
  if (s === 'warning' || s === 'medium' || p === 'medium') return 'bg-amber-300'
  return 'bg-blue-300'
})

const severityTextClass = computed(() => {
  const s = (props.task.severity || '').toLowerCase()
  if (s === 'critical') return 'text-red-600'
  if (s === 'high') return 'text-orange-600'
  if (s === 'warning' || s === 'medium') return 'text-amber-600'
  return 'text-blue-600'
})

function workflowLabel(value?: string) {
  if (value === 'frontpage') return '首页质控'
  if (value === 'coding') return '编码质控'
  if (value === 'settlement') return '结算质控'
  if (value === 'frontpage_generate') return '首页生成'
  return '未知流程'
}

function severityLabel(value?: string) {
  const n = (value || '').toLowerCase()
  if (n === 'critical') return '严重'
  if (n === 'high') return '高风险'
  if (n === 'warning' || n === 'medium') return '警告'
  return '提示'
}

function taskStatusLabel(value?: string) {
  if (value === 'in_progress') return '进行中'
  if (value === 'overdue') return '已超时'
  return '待处理'
}
</script>
