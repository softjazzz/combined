<template>
  <div class="qc-record-card">
    <div class="qc-record-card__header">
      <div class="qc-record-card__title">{{ title }}</div>
      <a-tag v-if="status" :color="statusColor">{{ status }}</a-tag>
    </div>
    <div class="qc-record-card__meta">
      <span>ID: {{ id }}</span>
      <span v-if="createdAt">{{ createdAt }}</span>
    </div>
    <div class="qc-record-card__body"><slot /></div>
  </div>
  </template>

<script setup lang="ts">
import { computed } from 'vue'

defineProps<{
  id?: string | number
  title?: string
  status?: 'normal' | 'warning' | 'error' | string
  createdAt?: string
}>()

const props = defineProps<{ status?: string }>()
const statusColor = computed(() => {
  switch (props.status) {
    case 'error':
      return 'red'
    case 'warning':
      return 'orange'
    default:
      return 'blue'
  }
})
</script>

<style scoped>
.qc-record-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}
.qc-record-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.qc-record-card__title {
  font-weight: 600;
}
.qc-record-card__meta {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
  display: flex;
  gap: 12px;
}
.qc-record-card__body {
  margin-top: 8px;
}
</style>


