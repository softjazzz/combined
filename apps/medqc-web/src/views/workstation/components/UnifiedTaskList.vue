<template>
  <section
    class="flex flex-col flex-1 min-h-0 bg-white rounded-xl border border-slate-200 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.04)] overflow-hidden"
  >
    <!-- 列表主体 -->
    <div
      v-if="urgentTasks.length || normalTasks.length"
      class="flex-1 overflow-y-auto custom-scrollbar"
    >
      <!-- 紧急组 - P0/P1 -->
      <div
        v-if="urgentTasks.length"
        class="mb-6"
      >
        <div
          class="sticky top-0 z-10 flex items-center justify-between border-b border-red-100 bg-red-50/40 backdrop-blur-md px-6 py-2.5"
        >
          <div class="flex items-center gap-2">
            <span class="relative flex h-2 w-2">
              <span
                class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"
              />
              <span class="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
            </span>
            <span
              class="text-[12px] font-black text-red-900 uppercase tracking-widest leading-none mt-0.5"
            >
              紧急
            </span>
          </div>
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

      <!-- 常规组 -->
      <div v-if="normalTasks.length">
        <div
          class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-slate-50/40 backdrop-blur-md px-6 py-2.5"
        >
          <div class="flex items-center gap-2">
            <span class="h-2 w-2 rounded-full bg-slate-300" />
            <span
              class="text-[12px] font-black text-slate-500 uppercase tracking-widest leading-none mt-0.5"
            >
              常规待办
            </span>
          </div>
        </div>
        <div class="flex flex-col">
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
      class="flex-1 flex flex-col items-center justify-center py-20 bg-slate-50/30"
    >
      <div
        class="h-20 w-20 rounded-full border border-dashed border-slate-200 bg-white flex items-center justify-center shadow-sm mb-5 relative group cursor-default"
      >
        <div
          class="absolute inset-0 bg-blue-50/50 rounded-full scale-0 transition-transform duration-500 group-hover:scale-100"
        />
        <CoffeeOutlined
          class="text-[28px] text-slate-300 relative z-10 transition-colors group-hover:text-blue-400"
        />
      </div>
      <div class="text-[15px] font-extrabold text-slate-800 tracking-tight">
        今天干得不错，特急待办已清空
      </div>
      <div class="text-[13px] text-slate-400 mt-2 font-medium">
        您可以喝杯咖啡，或筛查一下其他日期的记录
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { CoffeeOutlined } from '@ant-design/icons-vue'
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
