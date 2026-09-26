<template>
  <section
    class="task-assignment-result"
    data-testid="assign-result"
  >
    <header class="task-assignment-result__header">
      <div>
        <div class="task-assignment-result__title">
          分配结果<span v-if="taskName"> · {{ taskName }}</span>
        </div>
        <div class="task-assignment-result__meta">
          共分配 {{ result.total_assigned }} 条病历<span v-if="result.idempotent">（已是既有分配，未重新计算）</span>
        </div>
      </div>
      <button
        type="button"
        class="task-assignment-result__close"
        data-testid="assign-result-close"
        aria-label="关闭分配结果"
        @click="emit('close')"
      >
        ×
      </button>
    </header>
    <ul
      v-if="rows.length"
      class="task-assignment-result__list"
    >
      <li
        v-for="row in rows"
        :key="row.key"
        class="task-assignment-result__row"
        data-testid="assign-result-row"
      >
        <span class="task-assignment-result__name">{{ row.name }}</span>
        <span class="task-assignment-result__count">{{ row.count }} 条</span>
        <span
          v-if="row.parts.length"
          class="task-assignment-result__parts"
          data-testid="assign-result-parts"
        >
          {{ row.parts.map((part) => `${part.label} ${part.count}`).join(' / ') }}
        </span>
      </li>
    </ul>
    <div
      v-else
      class="task-assignment-result__meta"
    >
      后端未返回每人分配明细
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TaskAssignResult } from '@/api/tasks'
import { assignReasonParts, type AssignReasonPart } from '@/utils/taskAssignment'

const props = defineProps<{
  result: TaskAssignResult
  taskName?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

interface ResultRow {
  key: string
  name: string
  count: number | string
  parts: AssignReasonPart[]
}

const rows = computed<ResultRow[]>(() => {
  const details = Array.isArray(props.result.assignment_details) ? props.result.assignment_details : []
  if (details.length) {
    return details.map((item, index) => ({
      key: item.user_id || `row-${index}`,
      name: item.user_name || item.user_id || '未知人员',
      count: typeof item.count === 'number' ? item.count : '未知',
      parts: assignReasonParts(item.reason_counts),
    }))
  }
  const summary = props.result.assignment_summary
  if (summary && typeof summary === 'object') {
    return Object.entries(summary).map(([name, count]) => ({
      key: name,
      name,
      count: typeof count === 'number' ? count : '未知',
      parts: [],
    }))
  }
  return []
})
</script>

<style scoped>
.task-assignment-result {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 4%);
}

.task-assignment-result__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.task-assignment-result__title {
  font-weight: 600;
  color: #1f2937;
}

.task-assignment-result__meta {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.task-assignment-result__close {
  border: none;
  background: transparent;
  color: #9ca3af;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.task-assignment-result__list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.task-assignment-result__row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 16px;
  padding: 8px 0;
  border-top: 1px solid #f3f4f6;
}

.task-assignment-result__name {
  min-width: 96px;
  color: #374151;
}

.task-assignment-result__count {
  font-weight: 600;
  color: #1d4ed8;
}

.task-assignment-result__parts {
  font-size: 13px;
  color: #6b7280;
}
</style>
