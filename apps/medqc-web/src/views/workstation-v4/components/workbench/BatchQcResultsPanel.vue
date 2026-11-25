<template>
  <section
    class="batch-qc-results-panel"
    aria-label="本次质控结果列表"
    data-testid="batch-qc-results-panel"
  >
    <header class="batch-qc-results-panel__header">
      <div class="batch-qc-results-panel__summary">
        <div class="batch-qc-results-panel__title-row">
          <span class="batch-qc-results-panel__icon" aria-hidden="true">
            <ClipboardCheck :size="16" />
          </span>
          <h2 class="batch-qc-results-panel__title">本次质控结果</h2>
          <span class="batch-qc-results-panel__pill">共 {{ items.length }} 份</span>
          <span
            class="batch-qc-results-panel__pill"
            :class="issueRecordCount > 0 ? 'is-danger' : 'is-muted'"
          >
            有问题 {{ issueRecordCount }} 份
          </span>
          <span class="batch-qc-results-panel__pill is-success">
            未见确定问题 {{ compliantRecordCount }} 份
          </span>
        </div>
        <p class="batch-qc-results-panel__hint">
          默认按确定问题数降序排列；点击任意病历可打开原文与质控结果对照，并支持连续切换下一份。
        </p>
      </div>

      <div class="batch-qc-results-panel__actions">
        <button
          type="button"
          class="batch-qc-results-panel__toggle"
          :class="{ 'is-active': onlyIssues }"
          :aria-pressed="onlyIssues"
          data-testid="batch-qc-results-only-issues"
          @click="onlyIssues = !onlyIssues"
        >
          仅看有问题（{{ issueRecordCount }}）
        </button>
        <button
          type="button"
          class="batch-qc-results-panel__action"
          :disabled="exporting || items.length === 0"
          data-testid="batch-qc-results-export"
          @click="handleExport"
        >
          <Download :size="14" aria-hidden="true" />
          {{ exporting ? '正在导出…' : '导出本次结果' }}
        </button>
        <button
          type="button"
          class="batch-qc-results-panel__exit"
          data-testid="batch-qc-results-exit"
          @click="emit('exit')"
        >
          <ArrowLeft :size="14" aria-hidden="true" />
          退出本次结果
        </button>
      </div>
    </header>

    <div v-if="loading" class="batch-qc-results-panel__state">
      正在整理本次质控结果…
    </div>

    <div
      v-else-if="visibleItems.length === 0"
      class="batch-qc-results-panel__state"
      data-testid="batch-qc-results-empty"
    >
      <span>{{ onlyIssues ? '本次质控未发现确定问题病历。' : '暂无可展示的质控结果病历。' }}</span>
      <button
        v-if="onlyIssues"
        type="button"
        class="batch-qc-results-panel__link"
        @click="onlyIssues = false"
      >
        查看全部 {{ items.length }} 份
      </button>
    </div>

    <div v-else class="batch-qc-results-panel__table-wrap">
      <table class="batch-qc-results-panel__table">
        <thead>
          <tr>
            <th scope="col">患者 / 住院号</th>
            <th scope="col">科室 / 状态</th>
            <th scope="col">质控结论</th>
            <th scope="col">问题摘要</th>
            <th scope="col">质控完成时间</th>
            <th scope="col" class="is-action">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, index) in visibleItems"
            :key="item.recordKey || item.visitId"
            class="batch-qc-results-panel__row"
            :class="{ 'is-active': activeRecordKey && item.recordKey === activeRecordKey }"
            data-testid="batch-qc-result-row"
            @click="openComparison(item, index)"
          >
            <td>
              <div class="batch-qc-results-panel__patient">
                <img
                  class="batch-qc-results-panel__avatar"
                  :src="patientAvatarSrc({ patientSex: item.patientSex, patientAge: item.patientAge })"
                  :alt="`${item.patientName}头像`"
                >
                <div class="batch-qc-results-panel__patient-copy">
                  <strong class="batch-qc-results-panel__patient-name" :title="item.patientName">
                    {{ item.patientName }}
                  </strong>
                  <span class="batch-qc-results-panel__visit" :title="item.visitId">
                    住院号：{{ item.visitId }}
                  </span>
                </div>
              </div>
            </td>
            <td>
              <div class="batch-qc-results-panel__dept">
                <span>{{ item.department }}</span>
                <span
                  v-if="item.hospitalizationStatus === 'inpatient' || item.hospitalizationStatus === 'discharged'"
                  class="batch-qc-results-panel__hosp-tag"
                  :class="`is-${item.hospitalizationStatus}`"
                >
                  {{ item.hospitalizationStatus === 'inpatient' ? '在院' : '已出院' }}
                </span>
              </div>
            </td>
            <td>
              <span
                class="batch-qc-results-panel__status"
                :class="statusClass(item.resultStatus)"
              >
                {{ item.resultLabel }}
              </span>
            </td>
            <td>
              <span
                class="batch-qc-results-panel__issue"
                :class="{ 'has-issues': item.confirmedIssueCount > 0 }"
              >
                {{ item.issueSummary }}
              </span>
            </td>
            <td class="batch-qc-results-panel__time">
              {{ item.latestQcTime }}
            </td>
            <td class="is-action">
              <button
                type="button"
                class="batch-qc-results-panel__open-btn"
                data-testid="batch-qc-result-open-btn"
                @click.stop="openComparison(item, index)"
              >
                查看对照
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, ref } from 'vue'
import { ArrowLeft, ClipboardCheck, Download } from 'lucide-vue-next'
import { exportFilteredLuxian0609RecordResults } from '@/services/sichuan-rule-workspace-service'
import { downloadBlob } from '../../customer-sample-validation/batchExport'
import { patientAvatarSrc } from '../qc/patient-avatar'
import type { BatchResultRecordItem } from '../../utils/batchResultViewer'

const props = withDefaults(
  defineProps<{
    items: BatchResultRecordItem[]
    loading?: boolean
    activeRecordKey?: string
    exportScope?: 'all' | 'running' | 'final'
  }>(),
  {
    loading: false,
    activeRecordKey: '',
    exportScope: 'all',
  },
)

const emit = defineEmits<{
  'open-record': [payload: { item: BatchResultRecordItem; queue: BatchResultRecordItem[]; index: number }]
  exit: []
}>()

const onlyIssues = ref(false)
const exporting = ref(false)

const issueRecordCount = computed(
  () => props.items.filter((item) => item.confirmedIssueCount > 0).length,
)
const compliantRecordCount = computed(
  () =>
    props.items.filter(
      (item) => item.confirmedIssueCount === 0 && item.resultStatus === 'completed',
    ).length,
)

const visibleItems = computed(() =>
  onlyIssues.value
    ? props.items.filter((item) => item.confirmedIssueCount > 0)
    : props.items,
)

function statusClass(status: BatchResultRecordItem['resultStatus']): string {
  if (status === 'priority') return 'is-danger'
  if (status === 'completed') return 'is-success'
  if (status === 'technical-error' || status === 'data-gap' || status === 'uncertain') {
    return 'is-warning'
  }
  return 'is-neutral'
}

function openComparison(item: BatchResultRecordItem, index: number) {
  emit('open-record', { item, queue: visibleItems.value, index })
}

async function handleExport() {
  if (exporting.value || props.items.length === 0) return
  const recordRefs = props.items
    .filter((item) => item.instituteId && item.patientId && item.visitId)
    .map((item) => ({
      institute_id: item.instituteId,
      patient_id: item.patientId,
      visit_id: item.visitId,
    }))
  if (!recordRefs.length) return
  exporting.value = true
  try {
    const response = await exportFilteredLuxian0609RecordResults({
      scope: props.exportScope,
      date_field: props.exportScope === 'final' ? 'discharge' : 'admission',
      record_refs: recordRefs,
    })
    if (!response.success || !response.data) {
      message.error(response.message || '导出本次质控结果失败')
      return
    }
    downloadBlob(response.data, `本次质控结果-${recordRefs.length}份.xlsx`)
    message.success(`已开始下载本次 ${recordRefs.length} 份病历的质控结果`)
  } catch {
    message.error('导出本次质控结果失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.batch-qc-results-panel {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.batch-qc-results-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 16px;
  padding: 14px 18px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.batch-qc-results-panel__summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.batch-qc-results-panel__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.batch-qc-results-panel__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: #edf5ff;
  color: #0a6cff;
  flex: 0 0 26px;
}

.batch-qc-results-panel__title {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  line-height: 22px;
  font-weight: 700;
}

.batch-qc-results-panel__pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.batch-qc-results-panel__pill.is-danger {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.batch-qc-results-panel__pill.is-success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.batch-qc-results-panel__pill.is-muted {
  color: #64748b;
}

.batch-qc-results-panel__hint {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
}

.batch-qc-results-panel__actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.batch-qc-results-panel__toggle,
.batch-qc-results-panel__action,
.batch-qc-results-panel__exit {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 11px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 140ms ease,
    background-color 140ms ease,
    color 140ms ease;
}

.batch-qc-results-panel__toggle:hover,
.batch-qc-results-panel__action:hover:not(:disabled),
.batch-qc-results-panel__exit:hover {
  border-color: #93c5fd;
  background: #f0f7ff;
  color: #0a6cff;
}

.batch-qc-results-panel__toggle.is-active {
  border-color: #ef4444;
  background: #fef2f2;
  color: #b91c1c;
  font-weight: 600;
}

.batch-qc-results-panel__action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.batch-qc-results-panel__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 20px;
  color: #64748b;
  font-size: 13px;
}

.batch-qc-results-panel__link {
  border: 0;
  background: transparent;
  color: #0a6cff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.batch-qc-results-panel__table-wrap {
  width: 100%;
  overflow-x: auto;
}

.batch-qc-results-panel__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.batch-qc-results-panel__table thead th {
  padding: 10px 14px;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}

.batch-qc-results-panel__table thead th.is-action,
.batch-qc-results-panel__table tbody td.is-action {
  text-align: right;
  white-space: nowrap;
}

.batch-qc-results-panel__row {
  cursor: pointer;
  transition: background-color 120ms ease;
}

.batch-qc-results-panel__row td {
  padding: 11px 14px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}

.batch-qc-results-panel__row:last-child td {
  border-bottom: 0;
}

.batch-qc-results-panel__row:hover {
  background: #f8fafc;
}

.batch-qc-results-panel__row.is-active {
  background: #eff6ff;
}

.batch-qc-results-panel__patient {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 160px;
}

.batch-qc-results-panel__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex: 0 0 32px;
  object-fit: cover;
  background: #f1f5f9;
}

.batch-qc-results-panel__patient-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.batch-qc-results-panel__patient-name {
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
}

.batch-qc-results-panel__visit {
  color: #64748b;
  font-size: 12px;
  line-height: 17px;
  font-variant-numeric: tabular-nums;
}

.batch-qc-results-panel__dept {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  white-space: nowrap;
}

.batch-qc-results-panel__hosp-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}

.batch-qc-results-panel__hosp-tag.is-inpatient {
  background: #eff6ff;
  color: #1d4ed8;
}

.batch-qc-results-panel__hosp-tag.is-discharged {
  background: #f1f5f9;
  color: #475569;
}

.batch-qc-results-panel__status {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.batch-qc-results-panel__status.is-danger {
  background: #fef2f2;
  color: #b91c1c;
}

.batch-qc-results-panel__status.is-success {
  background: #f0fdf4;
  color: #15803d;
}

.batch-qc-results-panel__status.is-warning {
  background: #fffbeb;
  color: #b45309;
}

.batch-qc-results-panel__status.is-neutral {
  background: #f1f5f9;
  color: #475569;
}

.batch-qc-results-panel__issue {
  color: #475569;
  font-size: 13px;
}

.batch-qc-results-panel__issue.has-issues {
  color: #b91c1c;
  font-weight: 600;
}

.batch-qc-results-panel__time {
  color: #64748b;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.batch-qc-results-panel__open-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  padding: 0 11px;
  border: 1px solid #bfdbfe;
  border-radius: 7px;
  background: #eff6ff;
  color: #0a6cff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color 140ms ease,
    border-color 140ms ease,
    color 140ms ease;
}

.batch-qc-results-panel__open-btn:hover {
  border-color: #0a6cff;
  background: #0a6cff;
  color: #ffffff;
}
</style>
