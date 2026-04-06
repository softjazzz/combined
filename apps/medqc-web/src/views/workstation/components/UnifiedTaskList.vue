<template>
  <div class="flex flex-col flex-1 min-h-0 bg-white">
    <!-- 列表主体 -->
    <div
      v-if="urgentTasks.length"
      class="flex-1 overflow-y-auto custom-scrollbar"
    >
      <!-- 紧急组 - P0/P1 -->
      <div class="mb-4">
        <!-- 去掉夸张的红背景，使用极简的实线分割及左侧红杠标示 -->
        <div
          class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 backdrop-blur-sm px-6 py-3"
        >
          <div class="flex items-center gap-2">
            <span
              class="h-1.5 w-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]"
            />
            <span class="text-[12.5px] font-extrabold text-slate-800 tracking-wide">
              最高优先级 (P0/P1)
            </span>
          </div>
          <span class="text-[11.5px] font-medium text-slate-400">
            {{ urgentTasks.length }} 项
          </span>
        </div>
        <div class="flex flex-col">
          <UnifiedTaskRow
            v-for="task in urgentTasks"
            :key="task.id"
            :task="task"
            :expanded-id="expandedId"
            :format-date-time="formatDateTime"
            @open="emit('open', $event)"
            @toggle-expand="toggleExpand"
          />
        </div>
      </div>
    </div>

    <!-- 空态 -->
    <div
      v-else
      class="flex-1 flex flex-col items-center justify-center py-20 bg-white"
    >
      <div
        class="h-16 w-16 mb-4 rounded-full bg-slate-50 flex items-center justify-center border border-slate-100 shadow-sm"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="text-slate-300"
        >
          <path d="M18 8h1a4 4 0 0 1 0 8h-1" />
          <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
          <line
            x1="6"
            y1="1"
            x2="6"
            y2="4"
          />
          <line
            x1="10"
            y1="1"
            x2="10"
            y2="4"
          />
          <line
            x1="14"
            y1="1"
            x2="14"
            y2="4"
          />
        </svg>
      </div>
      <div class="text-[15px] font-semibold text-slate-800">
        当前无最高优先级任务
      </div>
      <div class="text-[13px] text-slate-400 mt-1">
        仅展示 P0/P1 常规待办已隐藏
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { UnifiedTaskItem } from '@/views/workstation-v2/types'
import UnifiedTaskRow from './UnifiedTaskRow.vue'

const props = defineProps<{
  tasks: UnifiedTaskItem[]
  formatDateTime: (value?: string | null) => string
}>()

const emit = defineEmits<{
  open: [task: UnifiedTaskItem]
}>()

const expandedId = ref('')

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? '' : id
}

function isUrgent(task: UnifiedTaskItem): boolean {
  const s = (task.severity || '').toLowerCase()
  const p = (task.priority || '').toLowerCase()
  return s === 'critical' || s === 'high' || p === 'critical' || p === 'high'
}

function sortWeight(task: UnifiedTaskItem): number {
  let w = 0
  if (task.task_status === 'overdue') w += 100000
  const sev = (task.severity || '').toLowerCase()
  if (sev === 'critical') w += 40000
  else if (sev === 'high') w += 30000
  else if (sev === 'warning' || sev === 'medium') w += 20000
  w += Math.min(task.unread_count || 0, 99) * 100
  w += Math.min(task.active_defect_count || 0, 99) * 10
  return w
}

function sortedGroup(items: UnifiedTaskItem[]): UnifiedTaskItem[] {
  return [...items].sort((a, b) => {
    const diff = sortWeight(b) - sortWeight(a)
    if (diff !== 0) return diff
    const ta = new Date(a.latest_created_at || a.due_at || '').getTime() || 0
    const tb = new Date(b.latest_created_at || b.due_at || '').getTime() || 0
    return tb - ta
  })
}

const urgentTasks = computed(() => sortedGroup(props.tasks.filter(isUrgent)))
</script>
