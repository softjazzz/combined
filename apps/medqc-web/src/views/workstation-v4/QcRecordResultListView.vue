<template>
  <main class="qc-record-result-list-view running-qc-refined running-qc-apple">
    <section class="qc-record-result-list-view__header">
      <div>
        <h1>
          {{ pageTitle
          }}<span class="review-workbench-scope" :title="scopeLabel">{{
            isInpatient ? '在院' : '已出院'
          }}</span>
        </h1>
      </div>
    </section>

    <nav class="qc-record-result-list-view__view-switch" aria-label="质控结果视图">
      <button
        type="button"
        data-testid="qc-result-view-records"
        :class="{ 'is-active': activeView === 'records' }"
        :aria-pressed="activeView === 'records'"
        @click="activeView = 'records'"
      >
        病历结果
      </button>
      <button
        type="button"
        data-testid="qc-result-view-analysis"
        :class="{ 'is-active': activeView === 'analysis' }"
        :aria-pressed="activeView === 'analysis'"
        @click="activeView = 'analysis'"
      >
        结果分析
      </button>
    </nav>

    <div class="review-workbench-primary">
      <QcRunSelectedControl
        :care-phase="carePhase"
        :record-refs="selectedQcRecordRefs"
        :selected-count="selectedCount"
        :status-target="`#qc-record-result-task-status-${carePhase}`"
        @completed="refreshAfterSelectedQc"
      />
    </div>

    <section class="review-workbench-metrics" aria-label="质控结果汇总">
      <div v-for="metric in metricItems" :key="metric.key" :class="`review-metric--${metric.key}`">
        <span>{{ metric.key === 'priority' ? '确定问题' : metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <span>{{ metric.key === 'records' || metric.key === 'completed' ? '份' : '项' }}</span>
      </div>
    </section>

    <div
      :id="`qc-record-result-task-status-${carePhase}`"
      class="qc-record-result-list-view__task-status review-workbench-task-status"
    />

    <section v-if="activeView === 'records'" class="qc-record-result-list-view__workbench">
      <div class="qc-record-result-list-view__toolbar">
        <div class="qc-record-result-list-view__filters" aria-label="病历筛选条件">
          <label
            class="qc-record-result-list-view__filter-field qc-record-result-list-view__search-field"
          >
            <span class="qc-record-result-list-view__field-label">关键词</span>
            <input
              v-model="searchText"
              type="search"
              placeholder="搜索患者、住院号、科室"
              aria-label="关键词筛选"
              @keydown.enter.prevent="applyFilters"
            />
          </label>
          <label class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">科室</span>
            <select v-model="activeDept" aria-label="科室筛选" @change="applyFilters">
              <option value="全部科室">全部科室</option>
              <option v-for="department in departmentOptions" :key="department" :value="department">
                {{ department }}
              </option>
            </select>
          </label>
          <div
            class="qc-record-result-list-view__date-field"
            role="group"
            :aria-label="isInpatient ? '入院日期范围' : '出院日期范围'"
          >
            <span class="qc-record-result-list-view__field-label">{{
              isInpatient ? '入院日期' : '出院日期'
            }}</span>
            <div class="qc-record-result-list-view__date-inputs">
              <span class="review-date-label">{{ isInpatient ? '入院' : '出院' }}</span>
              <input
                type="date"
                aria-label="开始日期筛选"
                :value="startDate"
                @change="updateStartDate"
              />
              <span class="qc-record-result-list-view__date-separator">至</span>
              <input
                type="date"
                aria-label="结束日期筛选"
                :value="endDate"
                @change="updateEndDate"
              />
            </div>
          </div>
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
          <div class="qc-record-result-list-view__export-menu" @focusout="handleExportMenuFocusOut">
            <button
              class="qc-record-result-list-view__export-trigger"
              type="button"
              data-testid="qc-result-export-trigger"
              :disabled="loading || exporting"
              :aria-expanded="exportMenuOpen"
              aria-haspopup="menu"
              @click="exportMenuOpen = !exportMenuOpen"
              @keydown.esc="exportMenuOpen = false"
            >
              <Download :size="15" aria-hidden="true" />
              {{ exporting ? '正在导出…' : '导出 Excel' }}
              <ChevronDown :size="14" aria-hidden="true" />
            </button>
            <div
              v-if="exportMenuOpen"
              class="qc-record-result-list-view__export-options"
              role="menu"
            >
              <button
                type="button"
                role="menuitem"
                data-testid="qc-result-export-selected"
                :disabled="selectedCount === 0"
                @click="runSelectedExport"
              >
                <strong>导出所选病历</strong>
                <span>{{ selectedCount > 0 ? `${selectedCount} 份病历` : '请先勾选病历' }}</span>
              </button>
              <button
                type="button"
                role="menuitem"
                data-testid="qc-result-export-filtered"
                @click="runFilteredExport"
              >
                <strong>导出当前筛选结果</strong>
                <span>按当前科室、日期和关键词导出</span>
              </button>
            </div>
          </div>
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

      <div class="review-workbench-split">
        <div class="review-workbench-list">
          <div class="qc-record-result-list-view__list-heading">
            <h2>病历结果</h2>
            <span>共 {{ serverTotal }} 份 · 本页 {{ rows.length }} 份</span>
            <span
              v-if="selectedCount > 0"
              class="qc-record-result-list-view__selected-count"
              role="status"
              >已选 {{ selectedCount }} 份</span
            >
          </div>
          <QcRecordResultTable
            :care-phase="carePhase"
            compact-review
            :active-record-key="activePreviewKey"
            :rows="rows"
            :selected-record-keys="selectedRecordKeys"
            :empty-message="emptyMessage"
            @open-result="handleSelectPreview"
            @update:selected-record-keys="updateSelectedRecordKeys"
          />

          <footer v-if="serverTotal > 0" class="qc-record-result-list-view__pagination">
            <Pagination
              :current="currentPage"
              :page-size="pageSize"
              :total="serverTotal"
              :disabled="loading"
              :show-total="(total: number) => `共 ${total} 例`"
              :page-size-options="['15', '30', '50', '100']"
              :locale="{ items_per_page: '条/页', jump_to: '跳至', page: '页' }"
              show-size-changer
              show-quick-jumper
              show-less-items
              size="small"
              @change="handlePageChange"
            />
          </footer>
        </div>
        <QcRecordReviewPreview
          :care-phase="carePhase"
          :row="previewRow"
          :refresh-key="previewRefreshKey"
          @open-full="handleOpenResult"
        />
      </div>

      <p
        v-if="detailNotice || exportNotice"
        class="qc-record-result-list-view__notice"
        role="status"
      >
        {{ detailNotice || exportNotice }}
      </p>
    </section>

    <QcRecordResultAnalysisPanel
      v-else
      :care-phase="carePhase"
      @open-result="handleOpenAnalysisResult"
    />

    <QCRecordResultComparisonDrawer
      :open="drawerOpen"
      :focus="selectedFocus"
      presentation-mode="grouped"
      @close="closeResultDrawer"
    />
  </main>
</template>

<script setup lang="ts">
import { Pagination } from 'ant-design-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronDown, Download } from 'lucide-vue-next'

import { exportFilteredLuxian0609RecordResults } from '@/services/sichuan-rule-workspace-service'

import QCRecordResultComparisonDrawer, {
  type QCRecordResultFocus,
} from './customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import QcRecordResultTable, {
  type QcRecordCarePhase,
  type QcRecordResultRow,
} from './components/qc/QcRecordResultTable.vue'
import QcRecordResultAnalysisPanel from './components/qc/QcRecordResultAnalysisPanel.vue'
import QcRecordReviewPreview from './components/qc/QcRecordReviewPreview.vue'
import QcRunSelectedControl from './components/qc/QcRunSelectedControl.vue'
import { usePatientRecords } from './composables/usePatientRecords'
import type { PatientRecord, RecordLatestQcSummary } from './types'
import type { LuxianQcAnalysisRecordItem } from '@/services/luxian-qc-result-analysis-service'
import { downloadBlob } from './customer-sample-validation/batchExport'

const props = defineProps<{
  carePhase: QcRecordCarePhase
}>()

const route = useRoute()
const detailNotice = ref('')
const exportNotice = ref('')
const exporting = ref(false)
const exportMenuOpen = ref(false)
const drawerOpen = ref(false)
const selectedFocus = ref<QCRecordResultFocus | null>(null)
const selectedRecordKeys = ref<string[]>([])
const selectedRecordRefs = ref<
  Record<string, { institute_id: string; patient_id: string; visit_id: string }>
>({})
const selectedQcRecordRefs = computed(() =>
  selectedRecordKeys.value
    .map((recordKey) => selectedRecordRefs.value[recordKey])
    .filter(
      (recordRef): recordRef is { institute_id: string; patient_id: string; visit_id: string } =>
        Boolean(recordRef),
    ),
)
const activeView = ref<'records' | 'analysis'>('records')
const startDate = ref('')
const endDate = ref('')

const isInpatient = computed(() => props.carePhase === 'inpatient')
const pageTitle = computed(() => (isInpatient.value ? '运行病历质控' : '终末病历质控'))
const scopeLabel = computed(() => (isInpatient.value ? '固定范围：在院' : '固定范围：已出院'))

const {
  allRecords,
  activeDept,
  activeDoctor,
  currentPage,
  pageSize,
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
} = usePatientRecords(props.carePhase)

const departmentOptions = computed(() =>
  departments.value.map((item) => item.name).filter((name) => name && name !== '全部科室'),
)

type QcRecordMetricKey = 'records' | 'completed' | 'priority' | 'dataGap'

interface QcRecordMetricItem {
  key: QcRecordMetricKey
  label: string
  value: number
}

const metricItems = computed<QcRecordMetricItem[]>(() => [
  { key: 'records', label: '纳入病历', value: qcSummary.value.totalRecords },
  { key: 'completed', label: '已完成质控', value: qcSummary.value.readyRecords },
  {
    key: 'priority',
    label: '需优先复核',
    value: statusCount(qcSummary.value.statusCounts, 'non_compliant'),
  },
  {
    key: 'dataGap',
    label: '资料待核实',
    value: statusCount(qcSummary.value.statusCounts, 'data_gap'),
  },
])

const rows = computed<QcRecordResultRow[]>(() => {
  const resultRows = allRecords.value.filter(hasCompleteRecordIdentity).map(toResultRow)
  return resultRows.sort(compareLatestQcTimeDesc)
})
const selectedCount = computed(() => selectedRecordKeys.value.length)
const activePreviewKey = ref('')
const previewRefreshKey = ref(0)
const previewRow = computed(
  () => rows.value.find((row) => row.recordKey === activePreviewKey.value) ?? null,
)
watch(
  rows,
  (next) => {
    if (!next.some((row) => row.recordKey === activePreviewKey.value)) {
      activePreviewKey.value = next[0]?.recordKey ?? ''
    }
    previewRefreshKey.value += 1
  },
  { immediate: true },
)

function handleSelectPreview(recordKey: string) {
  activePreviewKey.value = recordKey
}

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

function qcTimeSortValue(value?: string): number {
  const text = String(value || '').trim()
  if (!text || text === '—') return 0
  const timestamp = Date.parse(`${text.replace(' ', 'T')}+08:00`)
  return Number.isFinite(timestamp) ? timestamp : 0
}

function compareLatestQcTimeDesc(left: QcRecordResultRow, right: QcRecordResultRow): number {
  return qcTimeSortValue(right.latestQcTime) - qcTimeSortValue(left.latestQcTime)
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
    admissionTime: formatMedicalRecordTimestamp(record.admissionDate),
    dischargeTime: formatMedicalRecordTimestamp(record.dischargeDate),
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
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (dataGap > 0) {
    return {
      resultStatus: 'data-gap',
      resultLabel: '资料待核实',
      issueSummary,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (uncertain > 0) {
    return {
      resultStatus: 'uncertain',
      resultLabel: '待判断',
      issueSummary,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  return {
    resultStatus: 'completed',
    resultLabel: '已完成',
    issueSummary,
    latestQcTime: formatQcCompletedAt(summary.completedAt),
  }
}

function formatMedicalRecordTimestamp(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/u)
  if (!match) return '—'
  return match[2] && match[3] ? `${match[1]} ${match[2]}:${match[3]}` : match[1]
}

const beijingQcTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

function formatQcCompletedAt(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const normalized = text.replace(' ', 'T')
  // 工作区任务时间由 datetime.utcnow() 产生，历史值没有时区后缀，但语义为 UTC。
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/iu.test(normalized) ? normalized : `${normalized}Z`
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '—'
  const parts = Object.fromEntries(
    beijingQcTimeFormatter
      .formatToParts(date)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

function applyFilters() {
  clearSelection()
  dateRange.value = startDate.value || endDate.value ? [startDate.value, endDate.value] : null
  currentPage.value = 1
  fetchData(1)
}

function updateSelectedRecordKeys(recordKeys: string[]) {
  const nextKeys = [...new Set(recordKeys)]
  const nextRefs = { ...selectedRecordRefs.value }
  const currentRows = new Map(
    allRecords.value
      .filter(hasCompleteRecordIdentity)
      .map((record) => [record.recordKey as string, record] as const),
  )
  const nextKeySet = new Set(nextKeys)
  for (const key of currentRows.keys()) {
    if (!nextKeySet.has(key)) delete nextRefs[key]
  }
  for (const key of nextKeys) {
    const record = currentRows.get(key)
    if (!record) continue
    nextRefs[key] = {
      institute_id: record.instituteId as string,
      patient_id: record.patientId as string,
      visit_id: record.visitId as string,
    }
  }
  selectedRecordRefs.value = nextRefs
  selectedRecordKeys.value = nextKeys.filter((key) => Boolean(nextRefs[key]))
}

function clearSelection() {
  selectedRecordKeys.value = []
  selectedRecordRefs.value = {}
}

function refreshAfterSelectedQc() {
  clearSelection()
  refreshData()
}

function handleExportMenuFocusOut(event: FocusEvent) {
  const currentTarget = event.currentTarget
  const nextTarget = event.relatedTarget
  if (
    currentTarget instanceof HTMLElement &&
    nextTarget instanceof Node &&
    currentTarget.contains(nextTarget)
  ) {
    return
  }
  exportMenuOpen.value = false
}

function runSelectedExport() {
  exportMenuOpen.value = false
  void exportSelectedRecords()
}

function runFilteredExport() {
  exportMenuOpen.value = false
  void exportCurrentFilter()
}

async function exportSelectedRecords() {
  if (exporting.value || selectedCount.value === 0) return
  const recordRefs = selectedRecordKeys.value
    .map((key) => selectedRecordRefs.value[key])
    .filter((value): value is { institute_id: string; patient_id: string; visit_id: string } =>
      Boolean(value),
    )
  if (recordRefs.length !== selectedCount.value) {
    exportNotice.value = '所选病历身份已变化，请重新勾选后导出'
    clearSelection()
    return
  }

  exporting.value = true
  exportNotice.value = ''
  try {
    const response = await exportFilteredLuxian0609RecordResults({
      scope: isInpatient.value ? 'running' : 'final',
      date_field: isInpatient.value ? 'admission' : 'discharge',
      record_refs: recordRefs,
    })
    if (!response.success || !response.data) {
      exportNotice.value = response.message || '导出所选质控结果失败'
      return
    }
    downloadBlob(
      response.data,
      `${isInpatient.value ? '运行病历质控' : '终末病历质控'}-所选${recordRefs.length}份.xlsx`,
    )
    exportNotice.value = `已开始下载所选 ${recordRefs.length} 份病历的质控结果`
  } catch {
    exportNotice.value = '导出所选质控结果失败，请稍后重试'
  } finally {
    exporting.value = false
  }
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

watch(
  () => props.carePhase,
  (carePhase) => {
    closeResultDrawer()
    clearSelection()
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
    patientName: record.name,
    patientSex: record.sex,
    patientAge: record.age,
    label: labelParts.join(' · '),
  }
  drawerOpen.value = true
}

function handleOpenAnalysisResult(record: LuxianQcAnalysisRecordItem) {
  closeResultDrawer()
  const visitId = String(record.visit_id || '').trim()
  const instituteId = String(record.institute_id || '').trim()
  const patientId = String(record.patient_id || '').trim()
  if (!visitId || !instituteId || !patientId) {
    detailNotice.value = '无法确认当前病历身份，已停止读取质控结果'
    return
  }
  const labelParts = [
    String(record.patient_name || '').trim() || '患者信息待核实',
    String(record.department || '').trim() || '未分科室',
    `住院号 ${visitId}`,
  ]
  const completedAt = formatQcCompletedAt(record.completed_at)
  if (completedAt !== '—') labelParts.push(`质控完成 ${completedAt}`)
  selectedFocus.value = {
    visitId,
    instituteId,
    patientId,
    recordId: visitId,
    patientName: String(record.patient_name || '').trim(),
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

.qc-record-result-list-view h1 {
  margin: 0;
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
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__metrics {
  margin: 16px 0;
}

.qc-record-result-list-view__view-switch {
  display: inline-flex;
  gap: 3px;
  margin-top: 14px;
  padding: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.78);
}

.qc-record-result-list-view__view-switch button {
  min-height: 32px;
  border: 0;
  border-radius: 7px;
  padding: 0 12px;
  background: transparent;
  color: rgba(29, 29, 31, 0.58);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
}

.qc-record-result-list-view__view-switch button.is-active {
  background: #fff;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.1);
  color: #2b6cf6;
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
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}

.qc-record-result-list-view__toolbar-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 10px;
}

.qc-record-result-list-view__export-menu {
  position: relative;
}

.qc-record-result-list-view__export-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 15px;
  border: 1px solid #2b6cf6;
  border-radius: 10px;
  background: #2b6cf6;
  color: #fff;
  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 0 7px 16px rgba(43, 108, 246, 0.18);
}

.qc-record-result-list-view__export-options {
  position: absolute;
  z-index: 20;
  top: calc(100% + 8px);
  right: 0;
  display: grid;
  min-width: 246px;
  overflow: hidden;
  padding: 6px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(18px);
}

.qc-record-result-list-view__export-options button {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(29, 29, 31, 0.82);
  text-align: left;
  cursor: pointer;
}

.qc-record-result-list-view__export-options button:hover:not(:disabled),
.qc-record-result-list-view__export-options button:focus-visible {
  background: rgba(43, 108, 246, 0.07);
  outline: none;
}

.qc-record-result-list-view__export-options button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.qc-record-result-list-view__export-options strong {
  font-size: 13px;
  font-weight: 650;
}

.qc-record-result-list-view__export-options span {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  line-height: 17px;
}

.qc-record-result-list-view__export-trigger:disabled {
  cursor: not-allowed;
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

.qc-record-result-list-view__filters input[type='search'] {
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
.qc-record-result-list-view__refresh-button {
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: #fff;
  color: #2b6cf6;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__pagination button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: #fff;
  color: #2b6cf6;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__query-button {
  border-color: #2b6cf6;
  background: #2b6cf6;
  color: #fff;
}

.qc-record-result-list-view__refresh-button {
  border-color: #2b6cf6;
  background: #2b6cf6;
  color: #fff;
}

.qc-record-result-list-view__refresh-button:hover:not(:disabled),
.qc-record-result-list-view__query-button:hover:not(:disabled) {
  background: #0059b3;
}

.qc-record-result-list-view__qc-control {
  display: inline-flex;
}

.qc-record-result-list-view__qc-control :deep(.qc-run-selected-control__trigger) {
  min-height: 38px;
  padding: 0 15px;
  border-radius: 10px;
}

.qc-record-result-list-view__task-status {
  width: 100%;
  padding: 0 20px;
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
  border-top: 1px solid rgba(43, 108, 246, 0.1);
  background: rgba(43, 108, 246, 0.045);
  color: #2b6cf6 !important;
  font-weight: 600;
}

@media (max-width: 1100px) {
  .qc-record-result-list-view {
    padding: 16px;
  }

  .qc-record-result-list-view__toolbar,
  .qc-record-result-list-view__filters {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-record-result-list-view__filters input[type='search'],
  .qc-record-result-list-view__filters select,
  .qc-record-result-list-view__filters input[type='date'] {
    width: 100%;
    min-width: 0;
  }

  .qc-record-result-list-view__date-separator {
    display: none;
  }

  .qc-record-result-list-view__toolbar-actions {
    justify-content: flex-start;
  }

  .qc-record-result-list-view__export-options {
    right: auto;
    left: 0;
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

<style scoped>
@import './styles/running-qc-refined.css';

.qc-record-result-list-view__filter-field,
.qc-record-result-list-view__date-field,
.qc-record-result-list-view__date-inputs {
  display: contents;
}
</style>
