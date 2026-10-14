<template>
  <div class="fpqc-table-wrap">
    <table
      class="mq-table fpqc-table"
      data-testid="fpqc-record-table"
    >
      <thead>
        <tr>
          <th class="fpqc-table__check">
            <input
              type="checkbox"
              aria-label="全选本页"
              :checked="allChecked"
              :indeterminate.prop="someChecked && !allChecked"
              :disabled="!rows.length"
              @change="toggleAll"
            >
          </th>
          <th>患者</th>
          <th>科室</th>
          <th>出院日期</th>
          <th class="fpqc-table__num">
            得分
          </th>
          <th>等级</th>
          <th>问题</th>
          <th>质控时间</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.record_key"
          :class="{ 'is-active': row.record_key === activeKey }"
          data-testid="fpqc-record-row"
          tabindex="0"
          @click="emit('select', row.record_key)"
          @keydown.enter.prevent="emit('select', row.record_key)"
        >
          <td
            class="fpqc-table__check"
            @click.stop
          >
            <input
              type="checkbox"
              :aria-label="`选择 ${row.patient_name || row.visit_id}`"
              :checked="selected.includes(row.record_key)"
              @change="toggle(row.record_key)"
            >
          </td>
          <td>
            <div class="fpqc-table__patient">
              <strong>{{ row.patient_name || '姓名待核实' }}</strong>
              <span class="mq-mono">{{ row.inpat_no || row.visit_id }}</span>
            </div>
          </td>
          <td class="fpqc-table__nowrap">
            {{ row.result?.department || row.department || '—' }}
          </td>
          <td class="fpqc-table__nowrap">
            {{ row.discharge_date || row.result?.discharge_date || '—' }}
          </td>
          <td class="fpqc-table__num">
            <strong v-if="row.result">{{ formatScore(row.result.score) }}</strong>
            <span
              v-else
              class="fpqc-table__muted"
            >—</span>
          </td>
          <td>
            <span
              v-if="row.result"
              :class="['mq-status', `mq-status--${GRADE_TONES[row.result.grade]}`]"
            >{{ GRADE_LABELS[row.result.grade] }}</span>
            <span
              v-else
              class="mq-status"
            >未质控</span>
          </td>
          <td class="fpqc-table__nowrap">
            <template v-if="row.result">
              <span
                v-if="row.result.fail_count"
                class="fpqc-table__issue fpqc-table__issue--danger"
              >扣分 {{ row.result.fail_count }}</span>
              <span
                v-if="row.result.hint_count"
                class="fpqc-table__issue fpqc-table__issue--warning"
              >提示 {{ row.result.hint_count }}</span>
              <span
                v-if="!row.result.fail_count && !row.result.hint_count"
                class="fpqc-table__muted"
              >无</span>
            </template>
            <span
              v-else
              class="fpqc-table__muted"
            >—</span>
          </td>
          <td class="fpqc-table__nowrap fpqc-table__muted">
            {{ row.result ? formatDateTime(row.result.created_at) : '—' }}
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td
            colspan="8"
            class="fpqc-table__empty"
          >
            {{ emptyMessage }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { FrontpageQcRecordItem } from '@/services/frontpage-qc-v2-service'

import { formatDateTime, formatScore, GRADE_LABELS, GRADE_TONES } from './presentation'

const props = defineProps<{
  rows: FrontpageQcRecordItem[]
  selected: string[]
  activeKey: string
  emptyMessage: string
}>()
const emit = defineEmits<{ select: [recordKey: string]; 'update:selected': [keys: string[]] }>()

const pageKeys = computed(() => props.rows.map((row) => row.record_key))
const allChecked = computed(
  () => pageKeys.value.length > 0 && pageKeys.value.every((key) => props.selected.includes(key)),
)
const someChecked = computed(() => pageKeys.value.some((key) => props.selected.includes(key)))

function toggle(key: string) {
  const next = props.selected.includes(key)
    ? props.selected.filter((item) => item !== key)
    : [...props.selected, key]
  emit('update:selected', next)
}

function toggleAll() {
  if (allChecked.value) {
    emit(
      'update:selected',
      props.selected.filter((key) => !pageKeys.value.includes(key)),
    )
  } else {
    emit('update:selected', [...new Set([...props.selected, ...pageKeys.value])])
  }
}
</script>

<style scoped>
.fpqc-table-wrap {
  overflow-x: auto;
}

.fpqc-table {
  min-width: 640px;
}

/* 列表与预览并排时可用宽度有限，收紧单元格左右留白，避免出现横向滚动 */
.fpqc-table th,
.fpqc-table td {
  padding-right: 12px;
  padding-left: 12px;
}

.fpqc-table tbody tr {
  cursor: pointer;
  transition: background 0.15s ease;
}

.fpqc-table tbody tr:hover {
  background: rgba(10, 108, 255, 0.04);
}

.fpqc-table tbody tr.is-active {
  background: rgba(10, 108, 255, 0.08);
}

.fpqc-table tbody tr:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: -2px;
}

.fpqc-table__check {
  width: 36px;
  padding-right: 0 !important;
}

.fpqc-table__patient {
  display: flex;
  flex-direction: column;
  gap: 2px;
  white-space: nowrap;
}

.fpqc-table__patient span {
  color: var(--mq-text-tertiary);
}

.fpqc-table__nowrap {
  white-space: nowrap;
}

.fpqc-table__num {
  text-align: right !important;
  white-space: nowrap;
}

.fpqc-table__muted {
  color: var(--mq-text-tertiary);
}

.fpqc-table__issue {
  display: inline-block;
  margin-right: 6px;
  font-size: var(--mq-font-12);
  font-weight: 600;
}

.fpqc-table__issue--danger {
  color: var(--mq-danger-text);
}

.fpqc-table__issue--warning {
  color: var(--mq-warning-text);
}

.fpqc-table__empty {
  height: 120px !important;
  color: var(--mq-text-tertiary);
  text-align: center;
  cursor: default;
}
</style>
