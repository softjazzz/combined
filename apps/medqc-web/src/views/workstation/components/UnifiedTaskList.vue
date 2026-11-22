<template>
  <div class="flex flex-1 flex-col bg-transparent">
    <div
      v-if="displayTasks.length"
      class="flex-1 overflow-y-auto custom-scrollbar"
    >
      <div class="flex flex-col">
        <UnifiedTaskRow
          v-for="task in displayTasks"
          :key="task.id"
          :task="task"
          :format-date-time="formatDateTime"
          @open="emit('open', $event)"
        />
      </div>
    </div>

    <div
      v-else
      class="flex flex-1 flex-col items-center justify-center bg-transparent py-16"
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
        {{ emptyTitle }}
      </div>
      <div class="text-[13px] text-slate-400 mt-1">
        {{ emptyDesc }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { UnifiedTaskItem } from './legacyHomeTypes'
import UnifiedTaskRow from './UnifiedTaskRow.vue'

const props = defineProps<{
  tasks: UnifiedTaskItem[]
  formatDateTime: (value?: string | null) => string
  previewLimit?: number
  emptyTitle?: string
  emptyDesc?: string
}>()

const emit = defineEmits<{
  open: [task: UnifiedTaskItem]
}>()

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

const displayTasks = computed(() => {
  const sorted = sortedGroup(props.tasks)
  if (props.previewLimit && props.previewLimit > 0) {
    return sorted.slice(0, props.previewLimit)
  }
  return sorted
})

const emptyTitle = computed(() => props.emptyTitle || '当前无任务')
const emptyDesc = computed(() => props.emptyDesc || '可以调整筛选条件后再查看。')
</script>
