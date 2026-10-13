<template>
  <div v-if="recentCodes.length > 0" class="icd-recent-bar">
    <div class="recent-label">
      <MqIcon name="history" />
      <div>
        <div class="recent-label__title">最近查看</div>
        <div class="recent-label__sub">{{ recentCodes.length }} 个编码</div>
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

    <button class="recent-clear" @click="$emit('clear')">清除</button>
  </div>
</template>

<script setup lang="ts">
import MqIcon from '@/components/icons/MqIcon.vue'

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

<style scoped src="../styles/icd-recent-bar.css"></style>
