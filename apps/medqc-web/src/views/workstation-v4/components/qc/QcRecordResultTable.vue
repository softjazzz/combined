<template>
  <div
    class="qc-record-result-table"
    data-testid="qc-record-result-table"
  >
    <div class="qc-record-result-table__scroll">
      <table class="qc-record-result-table__table">
        <thead>
          <tr>
            <th scope="col">
              患者 / 住院号
            </th>
            <th scope="col">
              科室 / 床位
            </th>
            <th scope="col">
              {{ timeColumnLabel }}
            </th>
            <th scope="col">
              最新质控结果
            </th>
            <th scope="col">
              问题摘要
            </th>
            <th scope="col">
              最近质控
            </th>
            <th
              scope="col"
              class="qc-record-result-table__action-heading"
            >
              查看结果
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.recordKey"
            class="qc-record-result-table__row"
            :data-record-key="row.recordKey"
            tabindex="0"
            @click="openResult(row.recordKey)"
            @keydown.enter.prevent="openResult(row.recordKey)"
            @keydown.space.prevent="openResult(row.recordKey)"
          >
            <td>
              <strong>{{ row.patientName || '患者信息待接入' }}</strong>
              <span>{{ row.visitId || '住院号待接入' }}</span>
              <span class="qc-record-result-table__source-state">{{ row.sourceLabel }}</span>
            </td>
            <td>
              <strong>{{ row.department || '未分科室' }}</strong>
              <span>{{ row.bedNumber || '床位待接入' }}</span>
            </td>
            <td>{{ displayTime(row) }}</td>
            <td>
              <span
                class="qc-record-result-table__result-tag"
                :class="resultClass(row.resultStatus)"
              >
                {{ row.resultLabel }}
              </span>
            </td>
            <td class="qc-record-result-table__summary">
              {{ row.issueSummary }}
            </td>
            <td>{{ row.latestQcTime || '—' }}</td>
            <td class="qc-record-result-table__action-cell">
              <button
                class="qc-record-result-table__result-button"
                type="button"
                @click.stop="openResult(row.recordKey)"
              >
                查看结果
              </button>
            </td>
          </tr>
          <tr
            v-if="rows.length === 0"
            class="qc-record-result-table__empty-row"
          >
            <td colspan="7">
              {{ emptyMessage }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
export type QcRecordCarePhase = 'inpatient' | 'discharged'

export interface QcRecordResultRow {
  recordKey: string
  patientName?: string
  visitId?: string
  department?: string
  bedNumber?: string
  admissionTime?: string
  dischargeTime?: string
  resultStatus:
    | 'priority'
    | 'data-gap'
    | 'uncertain'
    | 'technical-error'
    | 'not-run'
    | 'completed'
    | 'unknown'
  resultLabel: string
  issueSummary: string
  latestQcTime?: string
  sourceLabel: '资料同步待核实' | '来源未知'
}

const props = withDefaults(defineProps<{
  carePhase: QcRecordCarePhase
  rows: QcRecordResultRow[]
  emptyMessage?: string
}>(), {
  emptyMessage: '暂无符合当前范围的病历',
})

const emit = defineEmits<{
  'open-result': [recordKey: string]
}>()

const timeColumnLabel = props.carePhase === 'inpatient' ? '入院时间' : '出院时间'

function displayTime(row: QcRecordResultRow): string {
  return props.carePhase === 'inpatient' ? row.admissionTime || '—' : row.dischargeTime || '—'
}

function openResult(recordKey: string) {
  emit('open-result', recordKey)
}

function resultClass(status: QcRecordResultRow['resultStatus']): string {
  if (status === 'priority') return 'qc-record-result-table__result-tag--priority'
  if (status === 'data-gap') return 'qc-record-result-table__result-tag--data-gap'
  if (status === 'uncertain') return 'qc-record-result-table__result-tag--uncertain'
  if (status === 'technical-error') return 'qc-record-result-table__result-tag--technical-error'
  if (status === 'not-run') return 'qc-record-result-table__result-tag--not-run'
  if (status === 'completed') return 'qc-record-result-table__result-tag--completed'
  return 'qc-record-result-table__result-tag--unknown'
}
</script>

<style scoped>
.qc-record-result-table {
  min-width: 0;
}

.qc-record-result-table__scroll {
  overflow-x: auto;
}

.qc-record-result-table__table {
  width: 100%;
  min-width: 1080px;
  border-collapse: collapse;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', sans-serif;
  font-size: 13px;
}

.qc-record-result-table__table th {
  height: 42px;
  padding: 0 16px;
  background: rgba(245, 245, 247, 0.82);
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}

.qc-record-result-table__table td {
  max-width: 230px;
  padding: 14px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  line-height: 20px;
  vertical-align: middle;
  white-space: nowrap;
}

.qc-record-result-table__row {
  cursor: pointer;
  outline: none;
  transition: background 220ms ease;
}

.qc-record-result-table__row:hover,
.qc-record-result-table__row:focus-visible {
  background: rgba(0, 102, 204, 0.035);
}

.qc-record-result-table__table td strong,
.qc-record-result-table__table td span:not(.qc-record-result-table__result-tag) {
  display: block;
}

.qc-record-result-table__table td strong {
  color: #1d1d1f;
  font-weight: 600;
}

.qc-record-result-table__table td span:not(.qc-record-result-table__result-tag) {
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
}

.qc-record-result-table__summary {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.72);
  text-overflow: ellipsis;
}

.qc-record-result-table__result-tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-table__result-tag--priority {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.qc-record-result-table__result-tag--data-gap {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.qc-record-result-table__result-tag--completed {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.qc-record-result-table__result-tag--uncertain {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}

.qc-record-result-table__result-tag--technical-error {
  background: rgba(148, 163, 184, 0.16);
  color: #475569;
}

.qc-record-result-table__result-tag--not-run {
  background: rgba(148, 163, 184, 0.1);
  color: #64748b;
}

.qc-record-result-table__source-state {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.45) !important;
}

.qc-record-result-table__result-tag--unknown {
  background: rgba(100, 116, 139, 0.1);
  color: #475569;
}

.qc-record-result-table__action-heading,
.qc-record-result-table__action-cell {
  text-align: right !important;
}

.qc-record-result-table__result-button {
  padding: 4px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #0066cc;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}

.qc-record-result-table__result-button:hover {
  background: rgba(0, 102, 204, 0.08);
}

.qc-record-result-table__empty-row td {
  padding: 48px 16px;
  color: rgba(29, 29, 31, 0.52);
  text-align: center;
}

@media (max-width: 768px) {
  .qc-record-result-table__scroll {
    margin: 0 -16px;
  }

  .qc-record-result-table__table th,
  .qc-record-result-table__table td {
    padding-right: 14px;
    padding-left: 14px;
  }
}
</style>
