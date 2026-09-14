<template>
  <a-drawer
    :open="drawerOpen"
    title="AI 编码优化建议"
    placement="right"
    width="450"
    root-class-name="coding-optimization-drawer"
    :mask-closable="true"
    @update:open="handleOpenUpdate"
  >
    <div
      v-if="loading"
      class="flex justify-center items-center h-40"
    >
      <a-spin />
    </div>
    <div
      v-else-if="suggestions.length === 0"
      class="flex flex-col items-center justify-center h-64 text-slate-400"
    >
      <CheckCircleOutlined class="text-4xl text-green-500 mb-4" />
      <p>暂无优化建议，编码质量良好</p>
    </div>
    <div
      v-else
      class="space-y-4"
    >
      <div
        v-for="item in suggestions"
        :key="item.suggestion_id"
        class="coding-suggestion-card border border-slate-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-800 shadow-sm relative overflow-hidden"
      >
        <div
          class="absolute left-0 top-0 bottom-0 w-1"
          :class="{
            'bg-red-500': item.severity === 'error' || item.severity === 'high',
            'bg-amber-500': item.severity === 'warning',
            'bg-[#2b6cf6]': item.severity === 'info',
          }"
        />
        <div class="flex justify-between items-start mb-2 pl-3">
          <span
            class="font-semibold text-slate-800 dark:text-slate-200 text-sm flex items-center gap-2"
          >
            <ExclamationCircleOutlined
              v-if="item.severity === 'error'"
              class="text-red-500"
            />
            <QuestionCircleOutlined
              v-else
              class="text-amber-500"
            />
            {{ getSuggestionTitle(item.suggestion_type) }}
          </span>
          <span class="text-xs text-slate-400">{{ item.created_at?.substring(5, 16) }}</span>
        </div>
        <p class="text-sm text-slate-600 dark:text-slate-400 mb-3 pl-3 leading-relaxed">
          {{ item.message }}
        </p>
        <div
          v-if="item.evidence"
          class="coding-evidence bg-slate-50 dark:bg-slate-900/50 p-2 rounded text-xs text-slate-500 mb-3 pl-3 border-l-2 border-slate-300 italic"
        >
          "{{ item.evidence }}"
        </div>

        <div class="flex justify-end gap-2 pl-3">
          <a-button
            size="small"
            @click="$emit('handle', item.suggestion_id, 'reject')"
          >
            忽略
          </a-button>
          <a-button
            type="primary"
            size="small"
            @click="$emit('handle', item.suggestion_id, 'accept')"
          >
            采纳建议
          </a-button>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons-vue'

export interface Suggestion {
  suggestion_id: number
  suggestion_type: string
  message: string
  evidence?: string
  severity: string
  created_at?: string
}

const props = defineProps<{
  visible?: boolean
  open?: boolean
  loading: boolean
  suggestions: Suggestion[]
  getSuggestionTitle: (type: string) => string
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'update:visible', value: boolean): void
  (e: 'handle', id: number, action: 'accept' | 'reject'): void
}>()

const drawerOpen = computed(() => {
  if (typeof props.open === 'boolean') return props.open
  return !!props.visible
})

const handleOpenUpdate = (value: boolean) => {
  emit('update:open', value)
  emit('update:visible', value)
}
</script>

<style scoped>
:global(.coding-optimization-drawer .ant-drawer-content),
:global(.coding-optimization-drawer .ant-drawer-header),
:global(.coding-optimization-drawer .ant-drawer-body) {
  background: rgba(255, 255, 255, 0.9);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:global(.coding-optimization-drawer .ant-drawer-content) {
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

:global(.coding-optimization-drawer .ant-drawer-header) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

:global(.coding-optimization-drawer .ant-drawer-title) {
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 600;
}

:global(.coding-optimization-drawer .ant-btn-primary) {
  border-color: #2b6cf6;
  background: #2b6cf6;
  box-shadow: 0 5px 14px rgba(43, 108, 246, 0.16);
}

.coding-suggestion-card {
  border-color: rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
}

.coding-suggestion-card :deep(.dark\:text-slate-200),
.coding-suggestion-card :deep(.text-slate-800) {
  color: #1d1d1f;
}

.coding-suggestion-card :deep(.dark\:text-slate-400),
.coding-suggestion-card :deep(.text-slate-600),
.coding-suggestion-card :deep(.text-slate-500) {
  color: rgba(29, 29, 31, 0.6);
}

.coding-evidence {
  border-left-color: rgba(0, 0, 0, 0.12);
  background: rgba(255, 255, 255, 0.72);
  color: rgba(29, 29, 31, 0.6);
}
</style>
