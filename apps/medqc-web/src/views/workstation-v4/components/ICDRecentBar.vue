<template>
  <div
    v-if="recentCodes.length > 0"
    class="icd-recent-bar"
  >
    <div class="recent-label">
      <ClockCircleOutlined />
      <div>
        <div class="recent-label__title">
          最近查看
        </div>
        <div class="recent-label__sub">
          {{ recentCodes.length }} 个编码
        </div>
      </div>
    </div>

    <div class="recent-tags">
      <button
        v-for="item in recentCodes"
        :key="item.code"
        class="recent-tag"
        @click="$emit('select', item)"
      >
        <span class="recent-tag__code">{{ item.code }}</span>
        <span class="recent-tag__name">{{ item.name }}</span>
      </button>
    </div>

    <button
      class="recent-clear"
      @click="$emit('clear')"
    >
      清除
    </button>
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
  gap: 14px;
  padding: 12px 22px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 -8px 20px rgba(0, 0, 0, 0.04);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.recent-label {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  min-width: 116px;
  color: #1d1d1f;
}

.recent-label :deep(svg) {
  width: 18px;
  height: 18px;
  color: #0a6cff;
}

.recent-label__title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.recent-label__sub {
  margin-top: 2px;
  font-size: 11px;
  color: rgba(29, 29, 31, 0.38);
}

.recent-tags {
  display: flex;
  flex: 1;
  gap: 10px;
  min-width: 0;
  overflow-x: auto;
  padding-bottom: 2px;
}

.recent-tags::-webkit-scrollbar {
  height: 0;
}

.recent-tag {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  max-width: 300px;
  cursor: pointer;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.92);
  padding: 8px 14px;
  color: #1d1d1f;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.recent-tag:hover {
  transform: translateY(-1px);
  border-color: rgba(10, 108, 255, 0.18);
  box-shadow: 0 5px 14px rgba(10, 108, 255, 0.08);
}

.recent-tag__code {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #0a5fd6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.recent-tag__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: rgba(29, 29, 31, 0.72);
}

.recent-clear {
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.94);
  padding: 8px 12px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.15s ease;
}

.recent-clear:hover {
  border-color: rgba(10, 108, 255, 0.18);
  color: #0a5fd6;
}
</style>
