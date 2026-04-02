<template>
  <a-drawer
    :open="drawerOpen"
    title="AI 编码优化建议"
    placement="right"
    width="450"
    :mask-closable="true"
    @update:open="handleOpenUpdate"
  >
    <div v-if="loading" class="flex justify-center items-center h-40">
      <a-spin />
    </div>
    <div
      v-else-if="suggestions.length === 0"
      class="flex flex-col items-center justify-center h-64 text-slate-400"
    >
      <CheckCircleOutlined class="text-4xl text-green-500 mb-4" />
      <p>暂无优化建议，编码质量良好</p>
    </div>
    <div v-else class="space-y-4">
      <div
        v-for="item in suggestions"
        :key="item.suggestion_id"
        class="border border-slate-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-800 shadow-sm relative overflow-hidden"
      >
        <div
          class="absolute left-0 top-0 bottom-0 w-1"
          :class="{
            'bg-red-500': item.severity === 'error' || item.severity === 'high',
            'bg-amber-500': item.severity === 'warning',
            'bg-blue-500': item.severity === 'info',
          }"
        />
        <div class="flex justify-between items-start mb-2 pl-3">
          <span
            class="font-bold text-slate-800 dark:text-slate-200 text-sm flex items-center gap-2"
          >
            <ExclamationCircleOutlined v-if="item.severity === 'error'" class="text-red-500" />
            <QuestionCircleOutlined v-else class="text-amber-500" />
            {{ getSuggestionTitle(item.suggestion_type) }}
          </span>
          <span class="text-xs text-slate-400">{{ item.created_at?.substring(5, 16) }}</span>
        </div>
        <p class="text-sm text-slate-600 dark:text-slate-400 mb-3 pl-3 leading-relaxed">
          {{ item.message }}
        </p>
        <div
          v-if="item.evidence"
          class="bg-slate-50 dark:bg-slate-900/50 p-2 rounded text-xs text-slate-500 mb-3 pl-3 border-l-2 border-slate-300 italic"
        >
          "{{ item.evidence }}"
        </div>

        <div class="flex justify-end gap-2 pl-3">
          <a-button size="small" @click="$emit('handle', item.suggestion_id, 'reject')">
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
