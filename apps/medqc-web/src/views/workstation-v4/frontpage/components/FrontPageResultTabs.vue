<template>
  <div
    class="bg-white/90 rounded-2xl shadow-sm p-1.5 flex gap-1 border border-black/[0.08] backdrop-blur-[18px]"
  >
    <button
      v-for="tab in tabs"
      :key="tab.key"
      :class="[
        'flex-1 py-2.5 text-sm font-medium rounded-xl transition-all text-center',
        activeTab === tab.key
          ? 'bg-[#0066cc] text-white shadow-[0_5px_14px_rgba(0,102,204,0.18)]'
          : 'text-[rgba(29,29,31,0.6)] hover:bg-black/[0.04]',
      ]"
      @click="$emit('update:activeTab', tab.key)"
    >
      {{ tab.label }}
    </button>

    <div class="w-px bg-black/[0.08] my-2 mx-1" />

    <button
      class="px-3 text-[rgba(29,29,31,0.38)] hover:text-[#0066cc] hover:bg-[rgba(0,102,204,0.06)] rounded-xl transition-all flex items-center justify-center"
      :title="isExpanded ? '恢复分栏' : '展开工作台'"
      @click="$emit('toggleExpand')"
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
