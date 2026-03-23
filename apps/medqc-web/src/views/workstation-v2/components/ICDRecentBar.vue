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
  border-top: 1px solid rgba(191, 219, 254, 0.85);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(239, 246, 255, 0.92) 100%);
  box-shadow: 0 -12px 28px rgba(148, 163, 184, 0.08);
}

.recent-label {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  min-width: 116px;
  color: #334155;
}

.recent-label :deep(svg) {
  width: 18px;
  height: 18px;
  color: #2563eb;
}

.recent-label__title {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.recent-label__sub {
  margin-top: 2px;
  font-size: 11px;
  color: #94a3b8;
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
  border: 1px solid rgba(191, 219, 254, 0.95);
  background: linear-gradient(180deg, #eff6ff, #ffffff);
  padding: 8px 14px;
  color: #0f172a;
  box-shadow: 0 8px 16px rgba(148, 163, 184, 0.12);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}

.recent-tag:hover {
  transform: translateY(-1px);
  border-color: rgba(59, 130, 246, 0.45);
  box-shadow: 0 12px 22px rgba(59, 130, 246, 0.14);
}

.recent-tag__code {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 800;
  color: #1d4ed8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.recent-tag__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
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
  border-color: rgba(59, 130, 246, 0.28);
  color: #1d4ed8;
}
</style>
