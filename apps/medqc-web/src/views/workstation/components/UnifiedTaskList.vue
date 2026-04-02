<template>
  <section
    class="flex flex-col flex-1 min-h-0 rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden"
  >
    <!-- 列表主体 -->
    <div
      v-if="urgentTasks.length || normalTasks.length"
      class="flex-1 overflow-y-auto custom-scrollbar"
    >
      <!-- 紧急组 -->
      <div v-if="urgentTasks.length">
        <div
          class="sticky top-0 z-10 flex items-center gap-2 border-b border-red-100 bg-red-50/80 px-5 py-2 backdrop-blur-sm"
        >
          <span class="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
          <span class="text-[12px] font-bold text-red-700 uppercase tracking-wider">
            P0 / P1 紧急
          </span>
          <span
            class="ml-1 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-extrabold text-red-600 font-mono"
            style="font-variant-numeric: tabular-nums"
          >{{ urgentTasks.length }}</span>
        </div>
        <div class="divide-y divide-slate-100">
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

      <!-- 常规组 -->
      <div v-if="normalTasks.length">
        <div
          class="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-slate-50/80 px-5 py-2 backdrop-blur-sm"
        >
          <span class="h-2 w-2 rounded-full bg-blue-400" />
          <span class="text-[12px] font-bold text-slate-600 uppercase tracking-wider">
            常规待办
          </span>
          <span
            class="ml-1 rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-extrabold text-slate-600 font-mono"
            style="font-variant-numeric: tabular-nums"
          >{{ normalTasks.length }}</span>
        </div>
        <div class="divide-y divide-slate-100">
          <UnifiedTaskRow
            v-for="task in normalTasks"
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
      class="flex-1 flex flex-col items-center justify-center py-20"
    >
      <div
        class="h-14 w-14 rounded-full bg-slate-50 border-2 border-dashed border-slate-200 flex items-center justify-center text-slate-300 mb-4"
      >
        <CheckOutlined class="text-[24px]" />
      </div>
      <div class="text-[15px] font-semibold text-slate-600">
        当前没有需要处理的任务
      </div>
      <div class="text-[13px] text-slate-400 mt-1.5">
        可以切换日期或调整筛选条件查看更多
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { CheckOutlined } from '@ant-design/icons-vue'
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

/** 紧急组：severity=critical/high 或 priority=critical/high */
function isUrgent(task: UnifiedTaskItem): boolean {
  const s = (task.severity || '').toLowerCase()
  const p = (task.priority || '').toLowerCase()
  return s === 'critical' || s === 'high' || p === 'critical' || p === 'high'
}

/** 排序权重：超时优先 → 高风险优先 → 未读优先 → 缺陷多优先 → 最近触发优先 */
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
    // 最近触发优先
    const ta = new Date(a.latest_created_at || a.due_at || '').getTime() || 0
    const tb = new Date(b.latest_created_at || b.due_at || '').getTime() || 0
    return tb - ta
  })
}

const urgentTasks = computed(() => sortedGroup(props.tasks.filter(isUrgent)))
const normalTasks = computed(() => sortedGroup(props.tasks.filter((t) => !isUrgent(t))))
</script>
