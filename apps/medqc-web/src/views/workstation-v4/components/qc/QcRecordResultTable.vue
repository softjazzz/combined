<template>
  <div class="qc-record-result-table" data-testid="qc-record-result-table">
    <div class="qc-record-result-table__scroll">
      <table class="qc-record-result-table__table">
        <thead>
          <tr>
            <th scope="col" class="qc-record-result-table__selection-heading">
              <input
                type="checkbox"
                aria-label="选择当前页全部病历"
                :checked="allPageRowsSelected"
                :disabled="rows.length === 0"
                @click.stop
                @change="togglePageSelection"
              />
            </th>
            <th scope="col">患者 / 住院号</th>
            <th scope="col">科室 / 床位</th>
            <th scope="col">
              {{ timeColumnLabel }}
            </th>
            <th scope="col">问题摘要</th>
            <th scope="col">最近质控</th>
            <th scope="col" class="qc-record-result-table__action-heading">查看结果</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.recordKey"
            class="qc-record-result-table__row"
            :class="{
              'qc-record-result-table__row--selected': selectedRecordKeys.includes(row.recordKey),
            }"
            :data-record-key="row.recordKey"
            :aria-selected="selectedRecordKeys.includes(row.recordKey)"
            tabindex="0"
            @click="openResult(row.recordKey)"
            @keydown.enter.prevent="openResult(row.recordKey)"
            @keydown.space.prevent="openResult(row.recordKey)"
          >
            <td class="qc-record-result-table__selection-cell">
              <input
                type="checkbox"
                :aria-label="`选择${row.patientName || row.visitId || '当前病历'}`"
                :checked="selectedRecordKeys.includes(row.recordKey)"
                @click.stop
                @change="toggleRowSelection(row.recordKey, $event)"
              />
            </td>
            <td>
              <div class="qc-record-result-table__patient-cell">
                <img
                  class="qc-record-result-table__avatar"
                  :src="patientAvatarSrc(row)"
                  :alt="`${row.patientName || '患者'}头像`"
                />
                <span class="qc-record-result-table__patient-meta">
                  <span class="qc-record-result-table__patient-name">
                    {{ row.patientName || '患者信息待接入' }}
                  </span>
                  <span class="qc-record-result-table__visit-line">
                    <span class="qc-record-result-table__visit-label">住院号：</span>
                    <span class="qc-record-result-table__visit-id">{{
                      row.visitId || '待接入'
                    }}</span>
                  </span>
                  <span v-if="row.sourceLabel" class="qc-record-result-table__source-state">{{
                    row.sourceLabel
                  }}</span>
                </span>
              </div>
            </td>
            <td>
              <span class="qc-record-result-table__department">
                {{ row.department || '未分科室' }}
              </span>
              <span v-if="row.bedNumber" class="qc-record-result-table__bed-number">{{
                row.bedNumber
              }}</span>
            </td>
            <td>{{ displayTime(row) }}</td>
            <td class="qc-record-result-table__summary" :title="row.issueSummary">
              {{ row.issueSummary }}
            </td>
            <td>{{ formatDisplayTime(row.latestQcTime) }}</td>
            <td class="qc-record-result-table__action-cell">
              <button
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
          <tr v-if="rows.length === 0" class="qc-record-result-table__empty-row">
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
import { computed } from 'vue'

import patientIconBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import patientIconElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import patientIconElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import patientIconGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import patientIconMan from '@/assets/avatar-icons/patient-icon-man.png'
import patientIconWoman from '@/assets/avatar-icons/patient-icon-woman.png'

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
    'priority' | 'data-gap' | 'uncertain' | 'technical-error' | 'not-run' | 'completed' | 'unknown'
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
  }>(),
  {
    selectedRecordKeys: () => [],
    emptyMessage: '暂无符合当前范围的病历',
  },
)

const emit = defineEmits<{
  'open-result': [recordKey: string]
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

function isFemale(sex?: string): boolean {
  return /女|female|^f$/i.test(String(sex || '').trim())
}

function patientAvatarSrc(row: Pick<QcRecordResultRow, 'patientSex' | 'patientAge'>): string {
  const age = Number(row.patientAge || 0)
  const female = isFemale(row.patientSex)
  if (Number.isFinite(age) && age > 0 && age < 14) {
    return female ? patientIconGirl : patientIconBoy
  }
  if (Number.isFinite(age) && age >= 55) {
    return female ? patientIconElderWoman : patientIconElderMan
  }
  return female ? patientIconWoman : patientIconMan
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
  accent-color: #0066cc;
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
  box-shadow: inset 3px 0 0 #0066cc;
}

.qc-record-result-table__row--selected {
  background: rgba(0, 102, 204, 0.045);
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
    0 2px 6px rgba(0, 102, 204, 0.08);
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
  border-color: #0066cc;
  background: #0066cc;
  color: #fff;
  box-shadow: 0 3px 9px rgba(0, 102, 204, 0.16);
}

.qc-record-result-table__result-button:hover {
  color: #0066cc;
  border-color: #0066cc;
  box-shadow: 0 4px 11px rgba(0, 102, 204, 0.15);
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
