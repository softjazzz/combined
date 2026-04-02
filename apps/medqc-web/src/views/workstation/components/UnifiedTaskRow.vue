<template>
  <div
    class="group relative flex flex-col transition-colors duration-150 border-b border-slate-100"
    :class="isExpanded ? 'bg-slate-50/70' : 'bg-white hover:bg-[#F8FAFC]'"
  >
    <!-- 卡片主体区 -->
    <div
      class="flex items-start gap-4 px-6 py-4 cursor-pointer"
      @click="emit('toggleExpand', task.id)"
    >
      <!-- 左侧图标标识 -->
      <div class="mt-0.5 shrink-0">
        <div
          v-if="isUrgent"
          class="h-3 w-3 rounded-sm bg-red-100 border border-red-200 flex items-center justify-center shadow-sm"
        >
          <div class="h-1.5 w-1.5 rounded-full bg-red-500" />
        </div>
        <div
          v-else
          class="h-3 w-3 rounded-sm border border-slate-200 bg-slate-50 flex items-center justify-center"
        >
          <div
            class="h-1.5 w-1.5 rounded-full"
            :class="task.source_type === 'hotspot' ? 'bg-amber-400' : 'bg-blue-400'"
          />
        </div>
      </div>

      <!-- 中心内容区 (两行排布：核心在标题) -->
      <div class="flex-1 min-w-0 pr-6 flex flex-col gap-1.5">
        <!-- 第一行：问题核心 (Task Title) -->
        <div class="flex items-center gap-2.5">
          <span
            class="text-[14px] text-slate-900 truncate"
            :class="isUrgent ? 'font-bold' : 'font-medium'"
          >
            {{ task.summary || task.title || '无核心问题摘要，请展开查看详情' }}
          </span>
          <!-- 缺陷 Badge 作为状态补丁，紧跟问题旁边 -->
          <span
            v-if="task.active_defect_count > 0"
            class="shrink-0 inline-flex items-center px-1.5 rounded border border-red-200 bg-red-50 text-[11px] font-bold text-red-600 leading-tight"
          >
            {{ task.active_defect_count }} 缺陷
          </span>
        </div>

        <!-- 第二行：病历元数据与标签连击 -->
        <div class="flex items-center gap-1.5 text-[12.5px] text-slate-500 font-medium">
          <!-- 患者 -->
          <span class="text-slate-700 font-bold">{{ task.patient_name || '未知患者' }}</span>

          <span class="text-slate-300">·</span>

          <!-- ID -->
          <span class="font-mono text-slate-400">{{ task.visit_id || '--' }}</span>

          <span class="text-slate-300">·</span>

          <!-- 科室/流程 -->
          <span>{{ task.department || '未分科' }} ({{ workflowLabel(task.workflow_type) }})</span>

          <!-- 额外属性（未读、来源等）用极简标签表示 -->
          <span
            v-if="task.unread_count > 0"
            class="ml-1 text-[11px] text-blue-600 font-bold flex items-center"
          >
            <div class="w-1.5 h-1.5 bg-blue-500 rounded-full mr-1" />
            未读
          </span>

          <span
            v-if="task.source_type === 'hotspot'"
            class="ml-1 text-[11px] text-amber-600 bg-amber-50 px-1 rounded shadow-sm border border-amber-100/50"
          >集中点</span>
        </div>
      </div>

      <!-- 右侧信息与互动 (固定宽度对齐) -->
      <div class="w-[120px] shrink-0 flex items-center justify-end relative h-8">
        <!-- 默认展示日期时间 -->
        <div
          class="text-[12px] text-slate-400 font-mono tracking-tight absolute right-0 transition-opacity duration-200"
          :class="isExpanded ? 'opacity-0' : 'group-hover:opacity-0'"
        >
          {{ formatDateTime(task.latest_created_at || task.due_at) }}
        </div>

        <!-- Hover 行动按钮 (完全干净的浅灰底/深色字组件) -->
        <div
          class="absolute right-0 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
          :class="{ 'opacity-100': isExpanded }"
        >
          <button
            type="button"
            class="flex items-center justify-center gap-1 rounded-[4px] px-3 py-1.5 text-[12px] font-bold border transition-all"
            :class="
              isExpanded
                ? 'bg-blue-600 border-blue-600 text-white shadow hover:bg-blue-700'
                : 'bg-white border-slate-300 text-slate-700 shadow-sm hover:border-slate-800 hover:text-slate-900'
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

    <!-- 行内展开上下文 -->
    <div
      v-if="isExpanded"
      class="bg-slate-50 border-t border-slate-200/60 px-[52px] py-4"
    >
      <div class="grid grid-cols-3 gap-6 text-[12.5px]">
        <!-- 左栏：关键评估 -->
        <div class="flex flex-col gap-2">
          <div
            class="flex justify-between items-center text-slate-500 border-b border-slate-200/50 pb-1"
          >
            <span>风险级别</span>
            <span class="font-bold text-slate-700">{{ severityLabel(task.severity) }}</span>
          </div>
          <div
            class="flex justify-between items-center text-slate-500 border-b border-slate-200/50 pb-1"
          >
            <span>当前状态</span>
            <span
              class="font-bold"
              :class="task.task_status === 'overdue' ? 'text-orange-600' : 'text-slate-700'"
            >
              {{ taskStatusLabel(task.task_status) }}
            </span>
          </div>
        </div>

        <!-- 中栏：质控上下文 -->
        <div class="flex flex-col gap-2">
          <div
            class="flex justify-between items-center text-slate-500 border-b border-slate-200/50 pb-1"
          >
            <span>质控评级</span>
            <span class="font-bold text-slate-700">{{ task.latest_qc_grade || '--' }}</span>
          </div>
          <div
            class="flex justify-between items-center text-slate-500 border-b border-slate-200/50 pb-1"
          >
            <span>质控得分</span>
            <span class="font-bold font-mono text-slate-700">{{
              task.latest_qc_score ?? '--'
            }}</span>
          </div>
        </div>

        <!-- 右栏：额外详情 -->
        <div
          class="bg-white border border-slate-200 rounded p-2 text-slate-600 leading-relaxed max-h-[80px] overflow-y-auto custom-scrollbar shadow-sm"
        >
          <span class="font-bold text-slate-400 text-[10px] uppercase mb-1 block">扩展摘要</span>
          {{ task.summary || task.title || '无补充摘要' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ArrowRightOutlined, LoadingOutlined } from '@ant-design/icons-vue'
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
  return '常规待办'
}
</script>
