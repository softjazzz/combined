<template>
  <div>
    <div class="qc-table__toolbar">
      <slot name="filters" />
    </div>
    <a-table :dataSource="rows" :columns="columns" :pagination="pagination" :rowKey="rowKey" @change="onChange" />
  </div>
  </template>

<script setup lang="ts">
import { computed } from 'vue'

type Column = any

const props = withDefaults(defineProps<{
  rows: any[]
  columns: Column[]
  total: number
  page: number
  pageSize: number
  rowKey?: string
}>(), {
  rowKey: 'id'
})

const emit = defineEmits<{ (e: 'change', payload: { page: number; pageSize: number }): void }>()

const pagination = computed(() => ({
  total: props.total,
  current: props.page,
  pageSize: props.pageSize,
  showTotal: (t: number) => `共 ${t} 条`
}))

function onChange(p: any) {
  emit('change', { page: p.current, pageSize: p.pageSize })
}
</script>

<style scoped>
.qc-table__toolbar { margin: 12px 0; }
</style>



