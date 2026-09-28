<template>
  <div
    class="qc-record-result-table"
    :class="{
      'qc-record-result-table--inpatient': carePhase === 'inpatient' || compactReview,
      'qc-record-result-table--compact-review': compactReview,
    }"
    data-testid="qc-record-result-table"
  >
    <div class="qc-record-result-table__scroll">
      <table class="qc-record-result-table__table">
        <thead>
          <tr>
            <th
              scope="col"
              class="qc-record-result-table__selection-heading"
            >
              <input
                type="checkbox"
                aria-label="选择当前页全部病历"
                :checked="allPageRowsSelected"
                :disabled="rows.length === 0"
                @click.stop
                @change="togglePageSelection"
              >
            </th>
            <th scope="col">
              患者 / 住院号
            </th>
            <th scope="col">
              {{ compactReview ? '科室' : '科室 / 床位' }}
            </th>
            <th
              v-if="!compactReview"
              scope="col"
            >
              {{ timeColumnLabel }}
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
              {{ compactReview ? '操作' : '查看结果' }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.recordKey"
            class="qc-record-result-table__row"
            :class="{
              'qc-record-result-table__row--selected': selectedRecordKeys.includes(row.recordKey),
              'qc-record-result-table__row--active':
                compactReview && activeRecordKey === row.recordKey,
            }"
            :data-record-key="row.recordKey"
            :aria-selected="selectedRecordKeys.includes(row.recordKey)"
            tabindex="0"
            @click="openResult(row.recordKey)"
            @keydown.enter.self.prevent="openResult(row.recordKey)"
            @keydown.space.self.prevent="openResult(row.recordKey)"
          >
            <td class="qc-record-result-table__selection-cell">
              <input
                type="checkbox"
                :aria-label="`选择${row.patientName || row.visitId || '当前病历'}`"
                :checked="selectedRecordKeys.includes(row.recordKey)"
                @click.stop
                @change="toggleRowSelection(row.recordKey, $event)"
              >
            </td>
            <td>
              <div class="qc-record-result-table__patient-cell">
                <img
                  class="qc-record-result-table__avatar"
                  :src="patientAvatarSrc(row)"
                  :alt="`${row.patientName || '患者'}头像`"
                >
                <span class="qc-record-result-table__patient-meta">
                  <span
                    class="qc-record-result-table__patient-name"
                    :title="compactReview ? row.patientName : undefined"
                  >
                    {{ row.patientName || '患者信息待接入' }}
                  </span>
                  <span class="qc-record-result-table__visit-line">
                    <span
                      v-if="carePhase !== 'inpatient' || compactReview"
                      class="qc-record-result-table__visit-label"
                    >住院号：</span>
                    <span
                      class="qc-record-result-table__visit-id"
                      :title="carePhase === 'inpatient' || compactReview ? row.visitId : undefined"
                    >{{ row.visitId || '待接入' }}</span>
                  </span>
                  <span
                    v-if="row.sourceLabel"
                    class="qc-record-result-table__source-state"
                  >{{
                    row.sourceLabel
                  }}</span>
                </span>
              </div>
            </td>
            <td>
              <span
                class="qc-record-result-table__department"
                :title="compactReview ? row.department : undefined"
              >
                {{ row.department || '未分科室' }}
              </span>
              <span
                v-if="row.bedNumber"
                class="qc-record-result-table__bed-number"
              >{{
                row.bedNumber
              }}</span>
            </td>
            <td v-if="!compactReview">
              {{ displayTime(row) }}
            </td>
            <td
              class="qc-record-result-table__summary"
              :title="row.issueSummary"
            >
              <span
                v-if="carePhase === 'inpatient' || compactReview"
                class="qc-record-result-table__summary-items"
              >
                <template
                  v-for="(part, index) in row.issueSummary.split(' · ')"
                  :key="index"
                >
                  <span
                    v-if="index > 0"
                    class="qc-record-result-table__summary-separator"
                  >{{
                    ' · '
                  }}</span>
                  <span
                    class="qc-record-result-table__summary-item"
                    :class="{
                      'qc-record-result-table__summary-item--issue': part.startsWith('确定问题 '),
                    }"
                  >{{ part }}</span>
                </template>
              </span>
              <template v-else>
                {{ row.issueSummary }}
              </template>
            </td>
            <td>{{ formatDisplayTime(row.latestQcTime) }}</td>
            <td class="qc-record-result-table__action-cell">
              <button
                v-if="compactReview"
                class="qc-record-result-table__view-button"
                type="button"
                :aria-label="`查看${row.patientName || '当前病历'}完整质控结果`"
                @click.stop="emit('open-full', row.recordKey)"
              >
                查看
              </button>
              <button
                v-else
                class="qc-record-result-table__result-button"
                :class="{
                  'qc-record-result-table__result-button--available':
                    row.resultStatus !== 'not-run',
                }"
                type="button"
                @click.stop="openResult(row.recordKey)"
              >
                {{ row.resultStatus === 'not-run' ? '暂无结果' : '查看结果' }}
              </button>
            </td>
          </tr>
          <tr
            v-if="rows.length === 0"
            class="qc-record-result-table__empty-row"
          >
            <td :colspan="compactReview ? 6 : 7">
              {{ emptyMessage }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { patientAvatarSrc } from './patient-avatar'

export type QcRecordCarePhase = 'inpatient' | 'discharged'

export interface QcRecordResultRow {
  recordKey: string
  instituteId: string
  patientId: string
  patientName?: string
  patientSex?: string
  patientAge?: number
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
  sourceLabel?: '资料同步待核实'
}

const props = withDefaults(
  defineProps<{
    carePhase: QcRecordCarePhase
    rows: QcRecordResultRow[]
    selectedRecordKeys?: string[]
    emptyMessage?: string
    compactReview?: boolean
    activeRecordKey?: string
  }>(),
  {
    selectedRecordKeys: () => [],
    emptyMessage: '暂无符合当前范围的病历',
    compactReview: false,
  },
)

const emit = defineEmits<{
  'open-result': [recordKey: string]
  'open-full': [recordKey: string]
  'update:selectedRecordKeys': [recordKeys: string[]]
}>()

const timeColumnLabel = computed(() => (props.carePhase === 'inpatient' ? '入院时间' : '出院时间'))
const allPageRowsSelected = computed(
  () =>
    props.rows.length > 0 &&
    props.rows.every((row) => props.selectedRecordKeys.includes(row.recordKey)),
)

function displayTime(row: QcRecordResultRow): string {
  return formatDisplayTime(props.carePhase === 'inpatient' ? row.admissionTime : row.dischargeTime)
}

function formatDisplayTime(value?: string): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/u)
  if (!match) return '—'
  return match[2] && match[3] ? `${match[1]} ${match[2]}:${match[3]}` : match[1]
}

function openResult(recordKey: string) {
  emit('open-result', recordKey)
}

function toggleRowSelection(recordKey: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(props.selectedRecordKeys)
  if (checked) next.add(recordKey)
  else next.delete(recordKey)
  emit('update:selectedRecordKeys', [...next])
}

function togglePageSelection(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(props.selectedRecordKeys)
  for (const row of props.rows) {
    if (checked) next.add(row.recordKey)
    else next.delete(row.recordKey)
  }
  emit('update:selectedRecordKeys', [...next])
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
  min-width: 1120px;
  border-collapse: collapse;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', sans-serif;
  font-size: 13px;
}

.qc-record-result-table__table th {
  height: 46px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.88);
  background: rgba(248, 250, 252, 0.92);
  color: #64748b;
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.01em;
  line-height: 20px;
  text-align: left;
  white-space: nowrap;
}

.qc-record-result-table__selection-heading,
.qc-record-result-table__selection-cell {
  width: 44px;
  max-width: 44px !important;
  padding-right: 4px !important;
  text-align: center !important;
}

.qc-record-result-table__selection-heading input,
.qc-record-result-table__selection-cell input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: #0a6cff;
  cursor: pointer;
}

.qc-record-result-table__table td {
  max-width: 230px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  line-height: 20px;
  vertical-align: middle;
  white-space: nowrap;
}

.qc-record-result-table__row {
  cursor: pointer;
  outline: none;
  transition:
    background-color 220ms ease,
    box-shadow 220ms ease;
}

.qc-record-result-table__row:hover,
.qc-record-result-table__row:focus-visible {
  background: rgba(248, 250, 252, 0.88);
  box-shadow: inset 3px 0 0 #0a6cff;
}

.qc-record-result-table__row--selected {
  background: rgba(10, 108, 255, 0.045);
}

.qc-record-result-table__patient-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.qc-record-result-table__avatar {
  display: block;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #eaf2ff;
  object-fit: cover;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.96),
    0 2px 6px rgba(10, 108, 255, 0.08);
}

.qc-record-result-table__patient-meta {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.qc-record-result-table__patient-name {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.qc-record-result-table__visit-line {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 2px;
}

.qc-record-result-table__visit-label {
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
}

.qc-record-result-table__visit-id,
.qc-record-result-table__department,
.qc-record-result-table__bed-number {
  color: #5b6b84;
  font-size: 12px;
}

.qc-record-result-table__department,
.qc-record-result-table__bed-number {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qc-record-result-table__department {
  font-weight: 600;
}

.qc-record-result-table__bed-number {
  color: #94a3b8;
}

.qc-record-result-table__summary {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.72);
  text-overflow: ellipsis;
}

.qc-record-result-table__source-state {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}

.qc-record-result-table__action-heading,
.qc-record-result-table__action-cell {
  width: 136px;
  text-align: right !important;
}

.qc-record-result-table__result-button {
  display: inline-flex;
  min-width: 84px;
  height: 30px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 11px;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 8px;
  background: #fff;
  color: #5b6b84;
  box-shadow: 0 1px 5px rgba(15, 42, 74, 0.05);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  transition:
    color 180ms ease,
    background-color 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.qc-record-result-table__result-button--available {
  border-color: #0a6cff;
  background: #0a6cff;
  color: #fff;
  box-shadow: 0 3px 9px rgba(10, 108, 255, 0.16);
}

.qc-record-result-table__result-button:hover {
  color: #0a6cff;
  border-color: #0a6cff;
  box-shadow: 0 4px 11px rgba(10, 108, 255, 0.15);
  transform: translateY(-1px);
}

.qc-record-result-table__result-button--available:hover {
  color: #fff;
  background: #005bb8;
}

.qc-record-result-table__empty-row td {
  padding: 48px 16px;
  color: rgba(29, 29, 31, 0.52);
  text-align: center;
}

/* 运行病历使用安静的数据行；出院病历继续沿用原有展示。 */
.qc-record-result-table--inpatient .qc-record-result-table__table th {
  height: 44px;
  background: #f8fafc;
  font-weight: 500;
}

.qc-record-result-table--inpatient .qc-record-result-table__row td {
  padding-top: 10px;
  padding-bottom: 10px;
  border-bottom-color: rgba(29, 29, 31, 0.065);
}

.qc-record-result-table--inpatient .qc-record-result-table__row td:nth-child(2) {
  min-width: 190px;
}

.qc-record-result-table--inpatient .qc-record-result-table__row td:nth-child(3) {
  min-width: 130px;
}

.qc-record-result-table--inpatient .qc-record-result-table__row td:nth-child(4),
.qc-record-result-table--inpatient .qc-record-result-table__row td:nth-child(6) {
  min-width: 160px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.qc-record-result-table--inpatient .qc-record-result-table__summary {
  min-width: 230px;
  max-width: 340px;
  white-space: normal;
}

.qc-record-result-table__summary-items {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
}
.qc-record-result-table__summary-separator {
  display: none;
}
.qc-record-result-table__summary-item {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 5px;
  background: #f2f5f9;
  color: #52647b;
  font-size: 12px;
  line-height: 20px;
  overflow-wrap: anywhere;
}
.qc-record-result-table--inpatient .qc-record-result-table__table input[type='checkbox'] {
  appearance: none;
  width: 16px;
  height: 16px;
  border: 1px solid #bdcbdd;
  border-radius: 4px;
  background: #fff;
  vertical-align: middle;
}
.qc-record-result-table--inpatient .qc-record-result-table__table input[type='checkbox']:checked {
  appearance: auto;
  accent-color: #0a6cff;
}
.qc-record-result-table--inpatient .qc-record-result-table__table input[type='checkbox']:disabled {
  background: #f1f4f8;
  cursor: not-allowed;
}

.qc-record-result-table--inpatient .qc-record-result-table__patient-meta {
  gap: 2px;
}

.qc-record-result-table--inpatient .qc-record-result-table__patient-name {
  font-weight: 700;
  letter-spacing: 0;
}

.qc-record-result-table--inpatient .qc-record-result-table__visit-id {
  overflow: hidden;
  color: #64748b;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
}

.qc-record-result-table--inpatient .qc-record-result-table__department {
  font-weight: 400;
}

.qc-record-result-table--inpatient .qc-record-result-table__row:hover {
  background: #f8fafc;
  box-shadow: none;
}

.qc-record-result-table--inpatient .qc-record-result-table__row--selected,
.qc-record-result-table--inpatient .qc-record-result-table__row--selected:hover {
  background: #edf4fc;
}

.qc-record-result-table--inpatient .qc-record-result-table__row:focus-visible {
  background: #edf4fc;
  box-shadow: inset 3px 0 0 #0a6cff;
}

.qc-record-result-table--inpatient .qc-record-result-table__result-button {
  border-color: transparent;
  background: transparent;
  color: #64748b;
  box-shadow: none;
  font-size: 13px;
  font-weight: 500;
}

.qc-record-result-table--inpatient .qc-record-result-table__result-button--available {
  background: transparent;
  color: #0a6cff;
}

.qc-record-result-table--inpatient .qc-record-result-table__result-button:hover {
  border-color: rgba(10, 108, 255, 0.14);
  background: rgba(10, 108, 255, 0.09);
  color: #0a6cff;
  transform: none;
}

.qc-record-result-table--inpatient .qc-record-result-table__result-button:focus-visible,
.qc-record-result-table--inpatient input:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 3px;
}

/* 主从复核列表：与病历池列表同一套外观（患者 / 住院号、科室、摘要、最近质控、查看胶囊）。 */
.qc-record-result-table--compact-review .qc-record-result-table__table {
  min-width: 640px;
  table-layout: fixed;
}

.qc-record-result-table--compact-review .qc-record-result-table__table th,
.qc-record-result-table--compact-review .qc-record-result-table__row td:nth-child(n) {
  box-sizing: border-box;
  min-width: 0;
  max-width: none;
  padding-right: 12px;
  padding-left: 12px;
}

.qc-record-result-table--compact-review th:nth-child(1) {
  width: 40px;
}
.qc-record-result-table--compact-review th:nth-child(3) {
  width: 120px;
}
.qc-record-result-table--compact-review th:nth-child(4) {
  width: 160px;
}
.qc-record-result-table--compact-review th:nth-child(5) {
  width: 132px;
}
.qc-record-result-table--compact-review th:nth-child(6) {
  width: 76px;
}
.qc-record-result-table--compact-review .qc-record-result-table__table thead th {
  font-size: 12px;
  font-weight: 500;
  text-align: left;
}

.qc-record-result-table--compact-review .qc-record-result-table__patient-name {
  display: block;
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-record-result-table--compact-review .qc-record-result-table__visit-line {
  display: flex;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}
.qc-record-result-table--compact-review .qc-record-result-table__visit-label,
.qc-record-result-table--compact-review .qc-record-result-table__visit-id {
  color: #7a8390;
  font-family: inherit;
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
}
.qc-record-result-table--compact-review .qc-record-result-table__visit-id {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.qc-record-result-table--compact-review .qc-record-result-table__department {
  display: block;
  overflow: hidden;
  color: #1d1d1f;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-record-result-table--compact-review .qc-record-result-table__bed-number {
  display: block;
  color: #7a8390;
  font-size: 12px;
}
.qc-record-result-table--compact-review .qc-record-result-table__summary {
  text-align: left;
}
.qc-record-result-table--compact-review .qc-record-result-table__summary-items {
  justify-content: flex-start;
}

.qc-record-result-table--compact-review .qc-record-result-table__summary-item {
  font-size: 13px;
  color: #667487;
  background: transparent;
  padding: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  overflow-wrap: normal;
}
.qc-record-result-table--compact-review .qc-record-result-table__summary-item--issue {
  color: #b74b50;
}
.qc-record-result-table--compact-review .qc-record-result-table__row td:nth-child(n) {
  height: 58px;
  padding-top: 8px;
  padding-bottom: 8px;
}
.qc-record-result-table--compact-review .qc-record-result-table__row td:nth-child(5) {
  color: #727b87;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.qc-record-result-table--compact-review .qc-record-result-table__summary-separator {
  display: inline;
  color: #c4ccd7;
}

/* 「查看」胶囊：与病历池一致，浅灰底，悬停与当前行转浅蓝 */
.qc-record-result-table__view-button {
  height: 26px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: rgba(118, 128, 160, 0.12);
  color: #1d1d1f;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background-color 140ms ease,
    color 140ms ease;
}
.qc-record-result-table__view-button:hover,
.qc-record-result-table__row--active .qc-record-result-table__view-button {
  background: rgba(10, 108, 255, 0.12);
  color: #0a5fd6;
}
.qc-record-result-table__view-button:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 2px;
}

.qc-record-result-table--compact-review .qc-record-result-table__row--active,
.qc-record-result-table--compact-review .qc-record-result-table__row--active:hover {
  background: #f2f7fd;
  box-shadow: inset 3px 0 0 #0a6cff;
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

  .qc-record-result-table--compact-review .qc-record-result-table__scroll {
    margin: 0;
  }
}
</style>
