<template>
  <div
    class="group relative flex flex-col transition-colors duration-200 border-b last:border-b-0 border-slate-100/60"
    :class="isExpanded ? 'bg-slate-50/60' : 'bg-white hover:bg-[#f8fafc]'"
  >
    <!-- 左侧优先级超细边线 (P0/P1可见) -->
    <div
      v-if="isUrgent"
      class="absolute left-0 top-0 bottom-0 w-[3px]"
      :class="urgencyLineColor"
    />

    <!-- 卡片主体区 -->
    <div
      class="flex items-stretch px-6 py-4 cursor-pointer"
      @click="emit('toggleExpand', task.id)"
    >
      <!-- 中间信息区 (两行结构) -->
      <div
        class="flex-1 flex flex-col justify-center min-w-0 pr-6 pl-1 border-r border-transparent group-hover:border-slate-100 transition-colors"
      >
        <!-- 第一行：身份与场景 -->
        <div class="flex items-center gap-2 mb-1.5">
          <span class="text-[14px] font-bold text-[#1e293b] truncate">
            {{ task.patient_name || '--' }}
          </span>
          <span class="text-[12px] text-[#64748b] font-mono truncate mx-1">
            {{ task.visit_id || '--' }}
          </span>
          <div class="flex items-center gap-1.5 shrink-0">
            <!-- 科室次级标签 (Ghost) -->
            <span
              class="text-[11px] font-medium text-slate-500 bg-slate-100/50 px-1.5 py-0.5 rounded border border-slate-200/50"
            >
              {{ task.department || '未分科室' }}
            </span>
            <!-- 流程类型标签 (Ghost) -->
            <span
              class="text-[11px] font-medium text-blue-600 bg-blue-50/50 px-1.5 py-0.5 rounded border border-blue-100/50"
            >
              {{ workflowLabel(task.workflow_type) }}
            </span>
            <!-- 来源 Mini Tag (彻底虚化) -->
            <span class="text-[10px] font-bold text-slate-400 bg-transparent px-1">
              {{ task.source_type === 'hotspot' ? '#问题' : '#待办' }}
            </span>
          </div>
        </div>

        <!-- 第二行：问题与摘要 -->
        <div class="flex items-center gap-3">
          <!-- 红色缺陷 Badge 排前以引起注意 -->
          <span
            v-if="task.active_defect_count > 0"
            class="inline-flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-[10.5px] font-bold text-red-600 border border-red-100/80 shrink-0"
          >
            <WarningFilled class="text-[10px]" />
            {{ task.active_defect_count }} 活跃缺陷
          </span>
          <!-- 摘要文本 -->
          <span class="text-[13px] text-[#475569] truncate flex-1 min-w-0 font-medium">
            {{ task.title || task.summary || '暂无详细摘要' }}
          </span>
        </div>
      </div>

      <!-- 右侧时间与行动区 -->
      <div class="w-[140px] shrink-0 flex flex-col items-end justify-center pl-4">
        <span
          class="text-[11.5px] text-[#94a3b8] font-mono transition-opacity duration-200"
          :class="isExpanded ? 'opacity-0' : 'group-hover:opacity-0'"
        >
          {{ formatDateTime(task.latest_created_at || task.due_at) }}
        </span>

        <!-- Hover 行动按钮 (Ghost) -->
        <div
          class="absolute right-6 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
          :class="{ 'opacity-100': isExpanded }"
        >
          <button
            type="button"
            class="flex items-center justify-center gap-1.5 rounded-full px-4 py-1.5 text-[12px] font-bold transition-all border outline-none"
            :class="
              isExpanded
                ? 'bg-blue-600 border-blue-600 text-white shadow-sm hover:bg-blue-700 hover:border-blue-700'
                : 'bg-white border-blue-200 text-blue-600 shadow-sm hover:bg-blue-50 hover:border-blue-300'
            "
            @click.stop="handleClickAction"
          >
            <span
              v-if="isLoading"
              class="animate-spin"
            ><LoadingOutlined /></span>
            <span v-else>立即处理</span>
            <ArrowRightOutlined
              v-if="!isLoading"
              class="text-[10px]"
            />
          </button>
        </div>
      </div>
    </div>

    <!-- 行内展开上下文 (Inline Expansion) -->
    <div
      v-if="isExpanded"
      class="bg-[#f8fafc] border-t border-slate-200/60 px-6 py-4 shadow-inner"
    >
      <div class="flex gap-12 text-[12px]">
        <!-- 左侧 Key-Value 数据 -->
        <div class="flex flex-col gap-3 min-w-[200px]">
          <div
            class="flex justify-between items-center border-b border-dashed border-slate-200 pb-1"
          >
            <span class="text-slate-400">风险评估</span>
            <span
              class="font-bold"
              :class="severityTextClass"
            >{{
              severityLabel(task.severity)
            }}</span>
          </div>
          <div
            class="flex justify-between items-center border-b border-dashed border-slate-200 pb-1"
          >
            <span class="text-slate-400">任务状态</span>
            <span class="font-bold text-slate-700">{{ taskStatusLabel(task.task_status) }}</span>
          </div>
          <div
            class="flex justify-between items-center border-b border-dashed border-slate-200 pb-1"
          >
            <span class="text-slate-400">未读消息</span>
            <span class="font-bold font-mono text-slate-700">{{ task.unread_count || 0 }}</span>
          </div>
        </div>

        <!-- 右侧文本块 -->
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">质控上下文概括</span>
            <span
              v-if="task.latest_qc_grade"
              class="rounded bg-slate-200 px-1 py-0.5 text-[10px] font-bold text-slate-700 font-mono leading-none"
            >{{ task.latest_qc_grade }} / {{ task.latest_qc_score ?? '-' }}分</span>
          </div>
          <p
            class="text-[13px] leading-relaxed text-slate-600 bg-white p-3 rounded border border-slate-100 shadow-sm m-0"
          >
            {{
              task.summary ||
                task.title ||
                '无进一步上下文。由于当前质控记录已被标记为缺陷，请点击「立即处理」穿透至病历原件进行详细核对与修正。'
            }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { WarningFilled, ArrowRightOutlined, LoadingOutlined } from '@ant-design/icons-vue'
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
const isLoading = ref(false)

function handleClickAction() {
  isLoading.value = true
  // 短暂 loading 后触发，增强即时响应感
  setTimeout(() => {
    emit('open', props.task)
    isLoading.value = false
  }, 150)
}

const isUrgent = computed(() => {
  const s = (props.task.severity || '').toLowerCase()
  const p = (props.task.priority || '').toLowerCase()
  return s === 'critical' || s === 'high' || p === 'critical' || p === 'high'
})

const urgencyLineColor = computed(() => {
  const s = (props.task.severity || '').toLowerCase()
  const p = (props.task.priority || '').toLowerCase()
  if (s === 'critical' || p === 'critical')
    return 'bg-red-500 shadow-[2px_0_6px_rgba(239,68,68,0.3)]'
  return 'bg-orange-400 shadow-[2px_0_6px_rgba(251,146,60,0.3)]'
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
