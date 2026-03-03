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
  padding: 8px 20px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.03);
}

.recent-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #999;
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
  border-radius: 6px !important;
  font-size: 12px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: transform 0.15s, box-shadow 0.15s;
  flex-shrink: 0;
}
.recent-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.recent-clear {
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
}
</style>
