<template>
  <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-1.5 flex gap-1 border border-slate-100 dark:border-slate-700">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      @click="$emit('update:activeTab', tab.key)"
      :class="[
        'flex-1 py-2.5 text-sm font-medium rounded-xl transition-all text-center',
        activeTab === tab.key
          ? 'bg-blue-500 text-white shadow-sm'
          : 'text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
      ]"
    >
      {{ tab.label }}
    </button>

    <div class="w-px bg-slate-100 dark:bg-slate-700 my-2 mx-1"></div>

    <button
      @click="$emit('toggleExpand')"
      class="px-3 text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-slate-700 rounded-xl transition-all flex items-center justify-center"
      :title="isExpanded ? '恢复分栏' : '展开工作台'"
    >
      <MenuUnfoldOutlined v-if="isExpanded" class="text-lg" />
      <ArrowsAltOutlined v-else class="text-lg" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ArrowsAltOutlined, MenuUnfoldOutlined } from '@ant-design/icons-vue'

export interface FrontPageTabItem {
  key: string
  label: string
}

defineProps<{
  tabs: FrontPageTabItem[]
  activeTab: string
  isExpanded: boolean
}>()

defineEmits<{
  (e: 'update:activeTab', value: string): void
  (e: 'toggleExpand'): void
}>()
</script>
