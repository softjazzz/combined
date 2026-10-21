<template>
  <section class="readonly-medical-order-table" data-testid="readonly-medical-order-table">
    <div class="editable-copy-order-type-switch">
      <button
        type="button"
        :class="{ 'is-active': activeType === 'long' }"
        @click="activeType = 'long'"
      >
        长期医嘱
      </button>
      <button
        type="button"
        :class="{ 'is-active': activeType === 'temporary' }"
        @click="activeType = 'temporary'"
      >
        临时医嘱
      </button>
    </div>
    <MedicalOrderFilterBar
      v-model="filters"
      :rows="rows"
      :visible-count="visibleRows.length"
      :total-count="scopedRows.length"
    />
    <div
      v-if="hasIncompleteOrders"
      class="mq-soft readonly-medical-order-notice"
      role="alert"
      data-testid="readonly-medical-order-incomplete"
    >
      医嘱超过查看上限，当前列表未完整，不得据此判断医嘱缺失。
    </div>
    <div class="editable-copy-order-table-wrap">
      <table class="editable-copy-order-table">
        <thead>
          <tr>
            <th>开始时间</th>
            <th>医嘱类型</th>
            <th>医嘱项目</th>
            <th>医嘱号</th>
            <th>规格</th>
            <th>剂量</th>
            <th>频次</th>
            <th>用法</th>
            <th>数量</th>
            <th title="北京时间；计划结束不代表已实际停止">计划结束时间</th>
            <th>实际停止时间</th>
            <th>医嘱状态</th>
            <th>下达医生</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in visibleRows"
            :key="row.document.key"
            :class="{ 'is-active': row.document.key === selectedKey }"
            @click="emit('select', row.document.key)"
          >
            <td>{{ row.startTime }}</td>
            <td>{{ row.orderType }}</td>
            <td :title="row.item">
              {{ row.item }}
            </td>
            <td :title="row.orderId">
              {{ row.orderId || '-' }}
            </td>
            <td :title="row.specification">
              {{ row.specification || '-' }}
            </td>
            <td :title="row.dosage">
              {{ row.dosage || '-' }}
            </td>
            <td :title="row.frequency">
              {{ row.frequency || '-' }}
            </td>
            <td :title="row.route">
              {{ row.route || '-' }}
            </td>
            <td :title="row.quantity">
              {{ row.quantity || '-' }}
            </td>
            <td>{{ row.plannedEndTime || '-' }}</td>
            <td>{{ row.stopTime || '-' }}</td>
            <td>{{ row.status }}</td>
            <td :title="row.prescribedDoctor">
              {{ row.prescribedDoctor || '-' }}
            </td>
          </tr>
          <tr v-if="!visibleRows.length">
            <td colspan="13" class="editable-copy-order-empty">
              {{
                hasMedicalOrderFilters(filters)
                  ? '暂无符合筛选条件的医嘱'
                  : `暂无${activeType === 'long' ? '长期医嘱' : '临时医嘱'}`
              }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EditableMedicalRecordDocument } from './types'
import { isMedicalOrderDocument } from './medicalDocumentDisplay'
import {
  buildMedicalOrderRow,
  compareMedicalOrderByTimeDesc,
  resolveMedicalOrderTypeKey,
} from './medicalOrderDisplay'
import type { MedicalOrderTypeKey } from './medicalOrderDisplay'
import MedicalOrderFilterBar from './MedicalOrderFilterBar.vue'
import {
  emptyMedicalOrderFilters,
  hasMedicalOrderFilters,
  matchesMedicalOrderFilters,
} from './medicalOrderFilters'

const props = withDefaults(
  defineProps<{
    documents: EditableMedicalRecordDocument[]
    selectedKey?: string
  }>(),
  {
    selectedKey: '',
  },
)

const emit = defineEmits<{
  (event: 'select', key: string): void
}>()

const orderDocuments = computed(() =>
  props.documents
    .filter((document) => isMedicalOrderDocument(document))
    .slice()
    .sort(compareMedicalOrderByTimeDesc),
)
const hasIncompleteOrders = computed(() =>
  orderDocuments.value.some((document) => document.projection_incomplete === true),
)
const rows = computed(() => orderDocuments.value.map((document) => buildMedicalOrderRow(document)))
const activeType = ref<MedicalOrderTypeKey>('temporary')
const filters = ref(emptyMedicalOrderFilters())
const scopedRows = computed(() => rows.value.filter((row) => row.orderTypeKey === activeType.value))
const visibleRows = computed(() =>
  scopedRows.value.filter((row) => matchesMedicalOrderFilters(row, filters.value)),
)
watch(
  () => orderDocuments.value.map((document) => document.key).join('\u0000'),
  () => {
    filters.value = emptyMedicalOrderFilters()
  },
)

watch(
  [() => props.selectedKey, orderDocuments],
  ([selectedKey, documents]) => {
    const selected = documents.find((document) => document.key === selectedKey)
    if (selected) {
      activeType.value = resolveMedicalOrderTypeKey(selected)
      return
    }
    activeType.value = documents.some(
      (document) => resolveMedicalOrderTypeKey(document) === 'temporary',
    )
      ? 'temporary'
      : 'long'
  },
  { immediate: true },
)
</script>

<style scoped>
.readonly-medical-order-table {
  min-height: 0;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: #fff;
}

.editable-copy-order-type-switch {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 54px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.editable-copy-order-type-switch button {
  position: relative;
  border: 0;
  background: transparent;
  padding: 5px 4px 5px 24px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

.editable-copy-order-type-switch button::before {
  position: absolute;
  top: 50%;
  left: 2px;
  width: 16px;
  height: 16px;
  border: 1px solid rgba(0, 0, 0, 0.18);
  border-radius: 999px;
  background: #fff;
  content: '';
  transform: translateY(-50%);
}

.editable-copy-order-type-switch button.is-active {
  color: #1d1d1f;
}

.editable-copy-order-type-switch button.is-active::before {
  border: 5px solid #0a6cff;
}

.readonly-medical-order-notice {
  margin: 12px 16px;
  padding: 12px 16px;
  color: var(--mq-warning-text);
  font-size: 13px;
  line-height: 20px;
}

.editable-copy-order-table-wrap {
  max-height: min(56vh, 620px);
  overflow: auto;
}

.editable-copy-order-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
  table-layout: fixed;
}

.editable-copy-order-table th {
  position: sticky;
  z-index: 1;
  top: 0;
  background: #f5f5f7;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 700;
  text-align: left;
}

.editable-copy-order-table th,
.editable-copy-order-table td {
  padding: 11px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  line-height: 20px;
}

.editable-copy-order-table th:nth-child(1),
.editable-copy-order-table td:nth-child(1) {
  width: 160px;
}

.editable-copy-order-table th:nth-child(2),
.editable-copy-order-table td:nth-child(2) {
  width: 88px;
}

.editable-copy-order-table th:nth-child(3),
.editable-copy-order-table td:nth-child(3) {
  width: 240px;
}

.editable-copy-order-table th:nth-child(4),
.editable-copy-order-table td:nth-child(4) {
  width: 160px;
}

.editable-copy-order-table th:nth-child(5),
.editable-copy-order-table td:nth-child(5) {
  width: 130px;
}

.editable-copy-order-table th:nth-child(6),
.editable-copy-order-table td:nth-child(6) {
  width: 100px;
}

.editable-copy-order-table th:nth-child(7),
.editable-copy-order-table td:nth-child(7) {
  width: 100px;
}

.editable-copy-order-table th:nth-child(8),
.editable-copy-order-table td:nth-child(8) {
  width: 100px;
}

.editable-copy-order-table th:nth-child(9),
.editable-copy-order-table td:nth-child(9) {
  width: 90px;
}

.editable-copy-order-table th:nth-child(10),
.editable-copy-order-table td:nth-child(10) {
  width: 160px;
}

.editable-copy-order-table th:nth-child(11),
.editable-copy-order-table td:nth-child(11) {
  width: 160px;
}

.editable-copy-order-table th:nth-child(12),
.editable-copy-order-table td:nth-child(12),
.editable-copy-order-table th:nth-child(13),
.editable-copy-order-table td:nth-child(13) {
  width: 100px;
}

.editable-copy-order-table td {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.82);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editable-copy-order-table tbody tr {
  cursor: pointer;
  transition: background 180ms ease;
}

.editable-copy-order-table tbody tr:hover,
.editable-copy-order-table tbody tr.is-active {
  background: rgba(10, 108, 255, 0.07);
}

.editable-copy-order-empty {
  padding: 28px !important;
  color: rgba(29, 29, 31, 0.42) !important;
  text-align: center;
}
</style>
