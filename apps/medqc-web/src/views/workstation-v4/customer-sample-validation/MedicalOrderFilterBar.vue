<template>
  <div class="medical-order-filters">
    <label>
      <span>医嘱类型</span>
      <select
        aria-label="医嘱类型筛选"
        :value="modelValue.category"
        @change="update('category', $event)"
      >
        <option value="">全部类型</option>
        <option v-for="category in categories" :key="category" :value="category">
          {{ category }}
        </option>
      </select>
    </label>
    <label>
      <span>医嘱状态</span>
      <select
        aria-label="医嘱状态筛选"
        :value="modelValue.status"
        @change="update('status', $event)"
      >
        <option value="">全部状态</option>
        <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
      </select>
    </label>
    <label class="medical-order-filters__search">
      <span>医嘱项目</span>
      <input
        type="search"
        aria-label="搜索医嘱项目"
        placeholder="搜索项目或药品名称"
        :value="modelValue.query"
        @input="update('query', $event)"
      />
    </label>
    <button
      type="button"
      aria-label="重置医嘱筛选"
      :disabled="!hasMedicalOrderFilters(modelValue)"
      @click="emit('update:modelValue', emptyMedicalOrderFilters())"
    >
      重置
    </button>
    <span class="medical-order-filters__count" role="status" aria-live="polite"
      >显示 {{ visibleCount }} / {{ totalCount }} 条</span
    >
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { emptyMedicalOrderFilters, hasMedicalOrderFilters } from './medicalOrderFilters'
import type { FilterableMedicalOrderRow, MedicalOrderFilters } from './medicalOrderFilters'

const props = defineProps<{
  modelValue: MedicalOrderFilters
  rows: FilterableMedicalOrderRow[]
  visibleCount: number
  totalCount: number
}>()
const emit = defineEmits<{ (event: 'update:modelValue', value: MedicalOrderFilters): void }>()
const categories = computed(() => [
  ...new Set(props.rows.map((row) => row.orderType).filter(Boolean)),
])
const statuses = computed(() => [...new Set(props.rows.map((row) => row.status).filter(Boolean))])
function update(key: keyof MedicalOrderFilters, event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return
  emit('update:modelValue', { ...props.modelValue, [key]: target.value })
}
</script>

<style scoped>
.medical-order-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--mq-border, #e2e8f0);
  background: var(--mq-surface, #fff);
}
.medical-order-filters label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--mq-text-muted, #64748b);
  font-size: 12px;
}
.medical-order-filters select,
.medical-order-filters input {
  min-width: 116px;
  height: 32px;
  border: 1px solid var(--mq-border, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  color: var(--mq-text, #0f172a);
  padding: 4px 9px;
  font: inherit;
  font-size: 13px;
}
.medical-order-filters__search {
  flex: 1 1 200px;
}
.medical-order-filters button {
  height: 32px;
  padding: 4px 10px;
  border: 1px solid var(--mq-border, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  color: var(--mq-primary, #2563eb);
  cursor: pointer;
}
.medical-order-filters button:disabled {
  color: #94a3b8;
  cursor: default;
}
.medical-order-filters__count {
  align-self: flex-end;
  padding-bottom: 6px;
  white-space: nowrap;
  color: var(--mq-text-muted, #64748b);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.medical-order-filters :is(input, select, button):focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
</style>
