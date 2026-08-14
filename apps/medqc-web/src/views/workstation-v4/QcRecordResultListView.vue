<template>
  <main class="qc-record-result-list-view">
    <section class="qc-record-result-list-view__header">
      <div>
        <div class="qc-record-result-list-view__eyebrow">
          {{ carePhaseLabel }} · 质控结果
        </div>
        <h1>{{ pageTitle }}</h1>
        <p>仅展示当前范围内病历的最新质控结果，不混入其他业务流程。</p>
      </div>
      <span class="qc-record-result-list-view__scope">{{ scopeLabel }}</span>
    </section>

    <section
      class="qc-record-result-list-view__metrics"
      aria-label="质控结果汇总"
    >
      <div
        v-for="metric in metricItems"
        :key="metric.label"
        class="qc-record-result-list-view__metric"
      >
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
      </div>
    </section>

    <section class="qc-record-result-list-view__workbench">
      <div class="qc-record-result-list-view__toolbar">
        <div
          class="qc-record-result-list-view__filters"
          aria-label="病历筛选条件"
        >
          <input
            v-model="searchText"
            placeholder="搜索患者、住院号、科室"
            aria-label="关键词筛选"
            @keydown.enter.prevent="applyFilters"
          >
          <select
            v-model="activeDept"
            aria-label="科室筛选"
            @change="applyFilters"
          >
            <option value="全部科室">
              全部科室
            </option>
            <option
              v-for="department in departmentOptions"
              :key="department"
              :value="department"
            >
              {{ department }}
            </option>
          </select>
          <input
            type="date"
            aria-label="开始日期筛选"
            :value="startDate"
            @change="updateStartDate"
          >
          <span class="qc-record-result-list-view__date-separator">至</span>
          <input
            type="date"
            aria-label="结束日期筛选"
            :value="endDate"
            @change="updateEndDate"
          >
          <button
            class="qc-record-result-list-view__query-button"
            type="button"
            :disabled="loading"
            @click="applyFilters"
          >
            查询
          </button>
        </div>
        <div class="qc-record-result-list-view__toolbar-actions">
          <button
            class="qc-record-result-list-view__export-button"
            type="button"
            :disabled="loading || exporting"
            @click="exportCurrentFilter"
          >
            {{ exporting ? '正在导出…' : '导出当前筛选 Excel' }}
          </button>
          <button
            class="qc-record-result-list-view__refresh-button"
            type="button"
            :disabled="loading"
            @click="refreshData"
          >
            刷新
          </button>
        </div>
      </div>

      <QcRecordResultTable
        :care-phase="carePhase"
        :rows="rows"
        :empty-message="emptyMessage"
        @open-result="handleOpenResult"
      />

      <footer
        v-if="serverTotal > 0"
        class="qc-record-result-list-view__pagination"
      >
        <span>共 {{ serverTotal }} 份病历</span>
        <div>
          <button
            type="button"
            :disabled="loading || currentPage <= 1"
            @click="goToPage(currentPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ currentPage }} / {{ serverTotalPages }} 页</span>
          <button
            type="button"
            :disabled="loading || currentPage >= serverTotalPages"
            @click="goToPage(currentPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>

      <p
        v-if="detailNotice || exportNotice"
        class="qc-record-result-list-view__notice"
        role="status"
      >
        {{ detailNotice || exportNotice }}
      </p>
    </section>

    <QCRecordResultComparisonDrawer
      :open="drawerOpen"
      :focus="selectedFocus"
      presentation-mode="grouped"
      @close="closeResultDrawer"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { exportFilteredLuxian0609RecordResults } from '@/services/sichuan-rule-workspace-service'

import QCRecordResultComparisonDrawer, {
  type QCRecordResultFocus,
} from './customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import QcRecordResultTable, {
  type QcRecordCarePhase,
  type QcRecordResultRow,
} from './components/qc/QcRecordResultTable.vue'
import { usePatientRecords } from './composables/usePatientRecords'
import type { PatientRecord, RecordLatestQcSummary } from './types'
import { downloadBlob } from './customer-sample-validation/batchExport'

const props = defineProps<{
  carePhase: QcRecordCarePhase
}>()

const route = useRoute()
const detailNotice = ref('')
const exportNotice = ref('')
const exporting = ref(false)
const drawerOpen = ref(false)
const selectedFocus = ref<QCRecordResultFocus | null>(null)
const startDate = ref('')
const endDate = ref('')

const isInpatient = computed(() => props.carePhase === 'inpatient')
const pageTitle = computed(() => (isInpatient.value ? '运行病历质控' : '终末病历质控'))
const carePhaseLabel = computed(() => (isInpatient.value ? '在院病历' : '已出院病历'))
const scopeLabel = computed(() => (isInpatient.value ? '固定范围：在院' : '固定范围：已出院'))

const {
  allRecords,
  activeDept,
  activeDoctor,
  currentPage,
  dateField,
  dateRange,
  departments,
  fetchData,
  handlePageChange,
  loadError,
  loading,
  qcSummary,
  refreshData,
  searchText,
  selectHospFilter,
  serverTotal,
  serverTotalPages,
} = usePatientRecords(props.carePhase)

const departmentOptions = computed(() =>
  departments.value.map((item) => item.name).filter((name) => name && name !== '全部科室'),
)

const metricItems = computed(() => [
  { label: '纳入病历', value: qcSummary.value.totalRecords },
  { label: '已完成质控', value: qcSummary.value.readyRecords },
  { label: '需优先复核', value: statusCount(qcSummary.value.statusCounts, 'non_compliant') },
  { label: '资料待核实', value: statusCount(qcSummary.value.statusCounts, 'data_gap') },
])

const rows = computed<QcRecordResultRow[]>(() =>
  allRecords.value.filter(hasCompleteRecordIdentity).map(toResultRow),
)

const emptyMessage = computed(() => {
  if (loading.value) return '正在加载质控结果…'
  if (loadError.value) return '加载失败，请重试'
  return '暂无符合当前范围的病历'
})

function statusCount(statusCounts: Record<string, number>, status: string): number {
  const value = Number(statusCounts[status] || 0)
  return Number.isFinite(value) && value > 0 ? value : 0
}

function hasCompleteRecordIdentity(record: PatientRecord): boolean {
  return Boolean(record.recordKey && record.instituteId && record.patientId && record.visitId)
}

function toResultRow(record: PatientRecord): QcRecordResultRow {
  const result = resolveResultPresentation(record.latestQcSummary)
  return {
    recordKey: record.recordKey as string,
    instituteId: record.instituteId as string,
    patientId: record.patientId as string,
    patientName: record.name,
    patientSex: record.sex,
    patientAge: record.age,
    visitId: record.visitId,
    department: record.department,
    bedNumber: record.bedNo,
    admissionTime: formatQcTimestamp(record.admissionDate),
    dischargeTime: formatQcTimestamp(record.dischargeDate),
    sourceLabel:
      record.sourceState && record.sourceState.status !== 'unknown' ? '资料同步待核实' : undefined,
    ...result,
  }
}

function resolveResultPresentation(
  summary?: RecordLatestQcSummary,
): Pick<QcRecordResultRow, 'resultStatus' | 'resultLabel' | 'issueSummary' | 'latestQcTime'> {
  if (summary?.status === 'technical_error') {
    return {
      resultStatus: 'technical-error',
      resultLabel: '结果校验异常',
      issueSummary: '请复核结果交付',
      latestQcTime: '—',
    }
  }
  if (summary?.status !== 'ready') {
    return {
      resultStatus: 'not-run',
      resultLabel: '未质控',
      issueSummary: '暂无结果',
      latestQcTime: '—',
    }
  }

  const statusCounts = summary.statusCounts || {}
  const nonCompliant = statusCount(statusCounts, 'non_compliant')
  const dataGap = statusCount(statusCounts, 'data_gap')
  const uncertain = statusCount(statusCounts, 'uncertain')
  const issueSummary =
    [
      nonCompliant > 0 ? `确定问题 ${nonCompliant}` : '',
      dataGap > 0 ? `待核实 ${dataGap}` : '',
      uncertain > 0 ? `待判断 ${uncertain}` : '',
    ]
      .filter(Boolean)
      .join(' · ') || '未发现确定问题'

  if (nonCompliant > 0) {
    return {
      resultStatus: 'priority',
      resultLabel: '需优先复核',
      issueSummary,
      latestQcTime: formatQcTimestamp(summary.completedAt),
    }
  }
  if (dataGap > 0) {
    return {
      resultStatus: 'data-gap',
      resultLabel: '资料待核实',
      issueSummary,
      latestQcTime: formatQcTimestamp(summary.completedAt),
    }
  }
  if (uncertain > 0) {
    return {
      resultStatus: 'uncertain',
      resultLabel: '待判断',
      issueSummary,
      latestQcTime: formatQcTimestamp(summary.completedAt),
    }
  }
  return {
    resultStatus: 'completed',
    resultLabel: '已完成',
    issueSummary,
    latestQcTime: formatQcTimestamp(summary.completedAt),
  }
}

function formatQcTimestamp(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/u)
  if (!match) return '—'
  return match[2] && match[3] ? `${match[1]} ${match[2]}:${match[3]}` : match[1]
}

function applyFilters() {
  dateRange.value = startDate.value || endDate.value ? [startDate.value, endDate.value] : null
  currentPage.value = 1
  fetchData(1)
}

async function exportCurrentFilter() {
  if (exporting.value) return
  exporting.value = true
  exportNotice.value = ''
  const [rangeStart, rangeEnd] = dateRange.value || []
  const department = String(activeDept.value || '').trim()
  const doctor = String(activeDoctor.value || '').trim()
  const keyword = String(searchText.value || '').trim()
  try {
    const response = await exportFilteredLuxian0609RecordResults({
      scope: isInpatient.value ? 'running' : 'final',
      ...(department && department !== '全部科室' ? { department } : {}),
      ...(doctor && doctor !== '全部主管医师' ? { doctor } : {}),
      date_field: isInpatient.value ? 'admission' : 'discharge',
      ...(rangeStart ? { start_date: rangeStart } : {}),
      ...(rangeEnd ? { end_date: rangeEnd } : {}),
      ...(keyword ? { keyword } : {}),
    })
    if (!response.success || !response.data) {
      exportNotice.value = response.message || '导出当前筛选质控结果失败'
      return
    }
    downloadBlob(
      response.data,
      `${isInpatient.value ? '运行病历质控' : '终末病历质控'}-当前筛选.xlsx`,
    )
    exportNotice.value = '当前筛选质控结果已开始下载'
  } catch {
    exportNotice.value = '导出当前筛选质控结果失败，请稍后重试'
  } finally {
    exporting.value = false
  }
}

function updateStartDate(event: Event) {
  startDate.value = (event.target as HTMLInputElement).value
  applyFilters()
}

function updateEndDate(event: Event) {
  endDate.value = (event.target as HTMLInputElement).value
  applyFilters()
}

function goToPage(page: number) {
  handlePageChange(page)
}

watch(
  () => props.carePhase,
  (carePhase) => {
    closeResultDrawer()
    dateField.value = carePhase === 'inpatient' ? 'admission' : 'discharge'
    selectHospFilter(carePhase)
  },
)

onMounted(async () => {
  dateField.value = props.carePhase === 'inpatient' ? 'admission' : 'discharge'
  const requestedRecordKey = routeQueryText('record_key')
  const requestedVisitId = routeQueryText('visit_id')
  if (requestedRecordKey && requestedVisitId) searchText.value = requestedVisitId
  await fetchData(1)
  if (requestedRecordKey) handleOpenResult(requestedRecordKey)
})

function routeQueryText(name: string): string {
  const value = route.query[name]
  return typeof value === 'string' ? value.trim() : ''
}

function handleOpenResult(recordKey: string) {
  const record = allRecords.value.find(
    (candidate) => candidate.recordKey === recordKey && hasCompleteRecordIdentity(candidate),
  )
  const row = rows.value.find((candidate) => candidate.recordKey === recordKey)
  closeResultDrawer()

  if (!record || !row) {
    detailNotice.value = '无法确认当前病历身份，已停止读取质控结果'
    return
  }
  if (row.resultStatus === 'not-run') {
    detailNotice.value = '这份病历暂无已保存质控结果'
    return
  }

  detailNotice.value = ''
  const labelParts = [
    record.name || '患者信息待核实',
    record.department || '未分科室',
    `住院号 ${record.visitId}`,
  ]
  if (row.latestQcTime && row.latestQcTime !== '—') {
    labelParts.push(`质控完成 ${row.latestQcTime}`)
  }
  selectedFocus.value = {
    visitId: record.visitId as string,
    instituteId: record.instituteId as string,
    patientId: record.patientId as string,
    recordId: record.id || (record.visitId as string),
    label: labelParts.join(' · '),
  }
  drawerOpen.value = true
}

function closeResultDrawer() {
  drawerOpen.value = false
  selectedFocus.value = null
  detailNotice.value = ''
}
</script>

<style scoped>
.qc-record-result-list-view {
  min-height: 100%;
  padding: 24px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', sans-serif;
}

.qc-record-result-list-view__header,
.qc-record-result-list-view__workbench {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.035);
  backdrop-filter: blur(18px);
}

.qc-record-result-list-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 24px;
  border-radius: 20px;
}

.qc-record-result-list-view__eyebrow {
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.qc-record-result-list-view h1 {
  margin: 4px 0 6px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 31px;
}

.qc-record-result-list-view p {
  margin: 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  line-height: 22px;
}

.qc-record-result-list-view__scope {
  margin-top: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 16px 0;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
}

.qc-record-result-list-view__metric {
  position: relative;
  display: grid;
  gap: 8px;
  min-height: 88px;
  padding: 17px 20px;
}

.qc-record-result-list-view__metric + .qc-record-result-list-view__metric {
  border-left: 1px solid rgba(0, 0, 0, 0.07);
}

.qc-record-result-list-view__metric span {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 600;
}

.qc-record-result-list-view__metric strong {
  color: #1d1d1f;
  font-size: 23px;
  font-weight: 700;
  line-height: 24px;
}

.qc-record-result-list-view__workbench {
  overflow: hidden;
  border-color: rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 14px 32px rgba(148, 163, 184, 0.12);
}

.qc-record-result-list-view__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}

.qc-record-result-list-view__toolbar-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 8px;
}

.qc-record-result-list-view__export-button {
  min-height: 38px;
  padding: 0 15px;
  border: 1px solid rgba(0, 102, 204, 0.2);
  border-radius: 10px;
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;
  cursor: pointer;
}

.qc-record-result-list-view__export-button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.qc-record-result-list-view__filters {
  display: flex;
  flex: 1;
  min-width: 0;
  gap: 10px;
}

.qc-record-result-list-view__filters input,
.qc-record-result-list-view__filters select {
  height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: rgba(245, 245, 247, 0.8);
  color: rgba(29, 29, 31, 0.78);
  font: inherit;
  font-size: 13px;
}

.qc-record-result-list-view__filters input:first-child {
  min-width: 260px;
  padding: 0 11px;
}

.qc-record-result-list-view__filters select {
  min-width: 190px;
  padding: 0 10px;
}

.qc-record-result-list-view__filters input[type='date'] {
  min-width: 144px;
  padding: 0 8px;
}

.qc-record-result-list-view__date-separator {
  align-self: center;
  color: rgba(29, 29, 31, 0.45);
  font-size: 12px;
}

.qc-record-result-list-view__query-button,
.qc-record-result-list-view__refresh-button,
.qc-record-result-list-view__pagination button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: #fff;
  color: #0066cc;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__query-button {
  border-color: #0066cc;
  background: #0066cc;
  color: #fff;
}

.qc-record-result-list-view__query-button:disabled,
.qc-record-result-list-view__refresh-button:disabled,
.qc-record-result-list-view__pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.qc-record-result-list-view__pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 20px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
}

.qc-record-result-list-view__pagination > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.qc-record-result-list-view__notice {
  padding: 12px 20px;
  border-top: 1px solid rgba(0, 102, 204, 0.1);
  background: rgba(0, 102, 204, 0.045);
  color: #0066cc !important;
  font-weight: 600;
}

@media (max-width: 900px) {
  .qc-record-result-list-view {
    padding: 16px;
  }

  .qc-record-result-list-view__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .qc-record-result-list-view__metric:nth-child(3) {
    border-left: 0;
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }

  .qc-record-result-list-view__metric:nth-child(4) {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }

  .qc-record-result-list-view__toolbar,
  .qc-record-result-list-view__filters {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-record-result-list-view__filters input:first-child,
  .qc-record-result-list-view__filters select,
  .qc-record-result-list-view__filters input[type='date'] {
    width: 100%;
    min-width: 0;
  }

  .qc-record-result-list-view__date-separator {
    display: none;
  }

  .qc-record-result-list-view__pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 560px) {
  .qc-record-result-list-view__header {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-record-result-list-view__scope {
    align-self: flex-start;
  }
}
</style>
