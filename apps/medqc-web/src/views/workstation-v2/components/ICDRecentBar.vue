<template>
  <div v-if="recentCodes.length > 0" class="icd-recent-bar">
    <div class="recent-label">
      <ClockCircleOutlined />
      <span>最近查看</span>
    </div>
    <div class="recent-tags">
      <a-tag
        v-for="item in recentCodes"
        :key="item.code"
        :color="item.type === 'icd10' ? 'blue' : 'green'"
        class="recent-tag"
        @click="$emit('select', item)"
      >
        {{ item.code }} {{ item.name }}
      </a-tag>
    </div>
    <a-button type="text" size="small" class="recent-clear" @click="$emit('clear')">
      清除
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { ClockCircleOutlined } from '@ant-design/icons-vue'

export interface RecentCode {
  code: string
  name: string
  type: 'icd10' | 'icd9cm3'
}

defineProps<{
  recentCodes: RecentCode[]
}>()

defineEmits<{
  select: [item: RecentCode]
  clear: []
}>()
</script>

<style scoped>
.icd-recent-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
  border-top: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 -10px 24px rgba(148, 163, 184, 0.08);
}

.recent-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  flex-shrink: 0;
}

.recent-tags {
  display: flex;
  gap: 6px;
  flex: 1;
  overflow-x: auto;
  min-width: 0;
}

.recent-tags::-webkit-scrollbar {
  height: 0;
}

.recent-tag {
  cursor: pointer;
  border-radius: 999px !important;
  font-size: 12px;
  padding-inline: 10px;
  border-color: rgba(191, 219, 254, 0.9) !important;
  background: rgba(239, 246, 255, 0.75) !important;
  color: #0f172a !important;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
  flex-shrink: 0;
}

.recent-tag:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.95) !important;
  box-shadow: 0 10px 18px rgba(148, 163, 184, 0.18);
}

.recent-clear {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
}
</style>
