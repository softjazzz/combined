<template>
  <a-table
    :columns="columns"
    :data-source="dataSource"
    :loading="loading"
    :pagination="pagination"
    :row-selection="rowSelection"
    :row-key="rowKey"
    :custom-row="customRow"
    class="modern-table h-full"
    :scroll="scroll"
    @change="handleChange"
  >
    <template #bodyCell="slotProps">
      <slot
        name="bodyCell"
        v-bind="slotProps"
      />
    </template>
  </a-table>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'

const props = defineProps({
  columns: {
    type: Array as PropType<any[]>,
    default: () => [],
  },
  dataSource: {
    type: Array as PropType<any[]>,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  pagination: {
    type: Object as PropType<any>,
    default: () => ({}),
  },
  rowSelection: {
    type: Object as PropType<any>,
    default: undefined,
  },
  rowKey: {
    type: [String, Function] as PropType<string | ((record: any) => string)>,
    default: 'id',
  },
  customRow: {
    type: Function as PropType<(record: any, index: number) => Record<string, unknown>>,
    default: undefined,
  },
  scroll: {
    type: Object as PropType<any>,
    default: () => ({}),
  },
})

const emit = defineEmits<{
  change: [pagination: unknown, filters: unknown, sorter: unknown, extra: unknown]
}>()

const handleChange = (pagination: unknown, filters: unknown, sorter: unknown, extra: unknown) => {
  emit('change', pagination, filters, sorter, extra)
}
</script>
