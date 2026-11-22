<template>
  <main class="qc-record-result-list-view running-qc-refined running-qc-apple">
    <!-- 页头：眉标 + 大标题；右侧视图切换与“质控所选” -->
    <section class="qc-record-result-list-view__header mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">质控作业 · 泸县0609质控点</span>
        <h1 class="mq-page-title">
          {{ pageTitle
          }}<span
            class="review-workbench-scope"
            :title="scopeLabel"
          >{{
            isInpatient ? '在院' : '已出院'
          }}</span>
        </h1>
      </div>
      <div class="mq-page-head__actions">
        <nav
          class="qc-record-result-list-view__view-switch mq-segmented"
          aria-label="质控结果视图"
        >
          <button
            type="button"
            class="mq-segmented__item"
            data-testid="qc-result-view-records"
            :class="{ 'is-active': activeView === 'records' }"
            :aria-pressed="activeView === 'records'"
            @click="activeView = 'records'"
          >
            病历结果
          </button>
          <button
            type="button"
            class="mq-segmented__item"
            data-testid="qc-result-view-analysis"
            :class="{ 'is-active': activeView === 'analysis' }"
            :aria-pressed="activeView === 'analysis'"
            :disabled="sourceId === 'independent_cdm'"
            :title="sourceId === 'independent_cdm' ? 'CDM来源暂不提供跨病例结果分析' : ''"
            @click="activeView = 'analysis'"
          >
            结果分析
          </button>
        </nav>
        <div class="review-workbench-primary">
          <QcRunSelectedControl
            :key="sourceId"
            :source-id="sourceId"
            :care-phase="carePhase"
            :record-refs="selectedQcRecordRefs"
            :selected-count="selectedCount"
            :status-target="`#qc-record-result-task-status-${carePhase}`"
            @results-updated="refreshAfterSelectedQc"
          />
        </div>
      </div>
    </section>

    <section
      class="review-workbench-metrics mq-card"
      aria-label="质控结果汇总"
      :aria-busy="qcSummaryState === 'pending'"
    >
      <div
        v-for="metric in metricItems"
        :key="metric.key"
        :class="`review-metric--${metric.key}`"
      >
        <span>{{ metric.key === 'priority' ? '确定问题' : metric.label }}</span>
        <strong>{{ metric.key === 'records' || qcSummaryState === 'ready' ? metric.value : '—' }}</strong>
        <span>{{ metric.key === 'records' || metric.key === 'completed' || metric.key === 'failed' ? '份' : '项' }}</span>
        <MqIconTile
          class="review-metric__icon"
          :name="METRIC_ICONS[metric.key].name"
          :tone="METRIC_ICONS[metric.key].tone"
          :size="38"
          :icon-size="22"
        />
      </div>
    </section>

    <Alert
      v-if="!loading && !loadError && qcSummaryState === 'unavailable'"
      type="warning"
      message="质控摘要暂不可用"
      show-icon
    />

    <div
      :id="`qc-record-result-task-status-${carePhase}`"
      class="qc-record-result-list-view__task-status review-workbench-task-status"
    />

    <section
      v-if="activeView === 'records'"
      class="qc-record-result-list-view__workbench"
    >
      <div class="qc-record-result-list-view__toolbar">
        <div
          class="qc-record-result-list-view__filters"
          aria-label="病历筛选条件"
        >
          <div
            class="qc-record-result-list-view__filter-field"
            aria-label="病历数据源"
          >
            <span class="qc-record-result-list-view__field-label">数据源</span>
            <span>东华CDM</span>
          </div>
          <div class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">关键词</span>
            <Input
              v-model:value="searchText"
              class="qc-record-result-list-view__search"
              placeholder="搜索患者、住院号、科室"
              aria-label="关键词筛选"
              size="large"
              allow-clear
              @change="handleSearchChange"
              @press-enter="applyFilters"
            >
              <template #prefix>
                <SearchOutlined aria-hidden="true" />
              </template>
            </Input>
          </div>
          <div class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">科室</span>
            <Select
              v-model:value="activeDept"
              class="qc-record-result-list-view__department"
              aria-label="科室筛选"
              size="large"
              show-search
              :options="departmentOptions"
              :filter-option="filterDepartmentOption"
              @change="applyFilters"
            />
          </div>
          <div
            class="qc-record-result-list-view__date-field"
            role="group"
            :aria-label="isInpatient ? '入院日期范围' : '出院日期范围'"
          >
            <span class="qc-record-result-list-view__field-label">{{
              isInpatient ? '入院日期' : '出院日期'
            }}</span>
            <span class="qc-record-result-list-view__date-label">{{ isInpatient ? '入院' : '出院' }}</span>
            <RangePicker
              :value="dateRange || undefined"
              class="qc-record-result-list-view__date-range"
              size="large"
              allow-clear
              :allow-empty="[true, true]"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              :placeholder="['开始日期', '结束日期']"
              @update:value="updateDateRange"
            />
          </div>
          <Button
            type="primary"
            :loading="loading"
            @click="applyFilters"
          >
            查询
          </Button>
          <Button :disabled="loading" data-testid="qc-result-reset-filters" @click="resetVisibleFilters">
            重置
          </Button>
        </div>
        <div class="qc-record-result-list-view__toolbar-actions">
          <div
            class="qc-record-result-list-view__export-menu"
            @focusout="handleExportMenuFocusOut"
          >
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
              <Download
                :size="15"
                aria-hidden="true"
              />
              {{ exporting ? '正在导出…' : '导出 Excel' }}
              <ChevronDown
                :size="14"
                aria-hidden="true"
              />
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
        <div
          class="review-workbench-list"
          :aria-busy="loading"
        >
          <div class="qc-record-result-list-view__list-heading">
            <h2>病历结果</h2>
            <span>共 {{ serverTotal }} 份 · 本页 {{ rows.length }} 份</span>
            <span
              v-if="selectedCount > 0"
              class="qc-record-result-list-view__selected-count"
              role="status"
            >已选 {{ selectedCount }} 份</span>
            <Button
              v-if="selectedCount > 0"
              type="link"
              size="small"
              data-testid="qc-result-clear-selection"
              @click="clearSelection"
            >
              清空
            </Button>
          </div>
          <Alert
            v-if="loadError"
            type="error"
            message="病历列表加载失败"
            show-icon
          >
            <template #action>
              <Button
                size="small"
                data-testid="qc-result-retry-list"
                @click="refreshData"
              >
                重试
              </Button>
            </template>
          </Alert>
          <Spin
            v-else
            :spinning="loading"
            tip="正在加载病历列表…"
          >
            <QcRecordResultTable
              v-if="rows.length"
              :care-phase="carePhase"
              compact-review
              :active-record-key="activePreviewKey"
              :rows="rows"
              :selected-record-keys="selectedRecordKeys"
              @open-result="handleSelectPreview"
              @open-full="handleOpenResult"
              @open-record="handleOpenMedicalRecord"
              @update:selected-record-keys="updateSelectedRecordKeys"
            />
            <div
              v-else-if="loading"
              class="qc-record-result-list-view__loading-space"
            />
            <Empty
              v-else
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
              description="暂无符合当前范围的病历"
            />
          </Spin>

          <footer
            v-if="serverTotal > 0"
            class="qc-record-result-list-view__pagination"
          >
            <Pagination
              :current="currentPage"
              :page-size="pageSize"
              :total="serverTotal"
              :disabled="loading"
              :show-total="(total: number) => `共 ${total} 例`"
              :page-size-options="WORKSTATION_LIST_PAGE_SIZE_OPTIONS"
              :locale="WORKSTATION_LIST_PAGINATION_LOCALE"
              show-size-changer
              show-quick-jumper
              show-less-items
              size="small"
              @change="handlePageChange"
            />
          </footer>
        </div>
        <QcRecordReviewPreview
          :key="sourceId"
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
      :key="sourceId"
      :care-phase="carePhase"
      @open-result="handleOpenAnalysisResult"
    />

    <CurrentMedicalRecordDrawer
      :record="medicalRecordFocus"
      @close="medicalRecordFocus = null"
    />
    <QCRecordResultComparisonDrawer
      :open="drawerOpen"
      :focus="selectedFocus"
      presentation-mode="grouped"
      :load-job-metadata="!route.path?.startsWith('/workstation-v5/')"
      @close="closeResultDrawer"
    />
  </main>
</template>

<script setup lang="ts">
import { Alert, Button, Empty, Input, Pagination, RangePicker, Select, Spin } from 'ant-design-vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronDown, Download } from 'lucide-vue-next'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import type { MqIconName, MqIconTone } from '@/components/icons/mqIcons'

import { exportFilteredLuxian0609RecordResults } from '@/services/sichuan-rule-workspace-service'

import QCRecordResultComparisonDrawer, {
  type QCRecordResultFocus,
} from './customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import type { PreviousResultRequest } from './customer-sample-validation/single-record-result-model'
import QcRecordResultTable, {
  type QcRecordCarePhase,
  type QcRecordResultRow,
} from './components/qc/QcRecordResultTable.vue'
import QcRecordResultAnalysisPanel from './components/qc/QcRecordResultAnalysisPanel.vue'
import QcRecordReviewPreview from './components/qc/QcRecordReviewPreview.vue'
import CurrentMedicalRecordDrawer from './components/CurrentMedicalRecordDrawer.vue'
import QcRunSelectedControl from './components/qc/QcRunSelectedControl.vue'
import { usePatientRecords } from './composables/usePatientRecords'
import type { PatientRecord, RecordLatestQcSummary } from './types'
import type { LuxianQcAnalysisRecordItem } from '@/services/luxian-qc-result-analysis-service'
import { downloadBlob } from './customer-sample-validation/batchExport'
import {
  ALL_DEPARTMENTS,
  buildDepartmentSelectOptions,
  filterDepartmentOption,
  normalizeWorkstationDateRange,
} from './utils/workstationFilterPresentation'
import {
  WORKSTATION_LIST_PAGE_SIZE_OPTIONS,
  WORKSTATION_LIST_PAGINATION_LOCALE,
} from './utils/workstationListPagination'
import {
  formatQcCompletedAt,
  resolveResultPresentation,
  statusCount,
} from './components/qc/latestQcSummaryPresentation'

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

const isInpatient = computed(() => props.carePhase === 'inpatient')
const pageTitle = computed(() => (isInpatient.value ? '运行病历质控' : '终末病历质控'))
const scopeLabel = computed(() => (isInpatient.value ? '固定范围：在院' : '固定范围：已出院'))

const {
  sourceId,
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
  qcSummaryState,
  refreshData,
  searchText,
  selectHospFilter,
  serverTotal,
} = usePatientRecords(props.carePhase)

const departmentOptions = computed(() =>
  buildDepartmentSelectOptions(departments.value).map(({ name }) => ({ value: name, label: name })),
)

type QcRecordMetricKey = 'records' | 'completed' | 'priority' | 'dataGap' | 'failed'

interface QcRecordMetricItem {
  key: QcRecordMetricKey
  label: string
  value: number
}

// 指标卡图标：与首页、设计稿 RunningV71 一致
const METRIC_ICONS: Record<string, { name: MqIconName; tone: MqIconTone }> = {
  records: { name: 'stack', tone: 'brand' },
  completed: { name: 'fp_qc', tone: 'success' },
  priority: { name: 'issue', tone: 'danger' },
  dataGap: { name: 'data_gap', tone: 'warning' },
  failed: { name: 'failed', tone: 'warning' },
}

const metricItems = computed<QcRecordMetricItem[]>(() => [
  { key: 'records', label: '纳入病历', value: qcSummaryState.value === 'ready' ? qcSummary.value.totalRecords : serverTotal.value },
  { key: 'completed', label: '已完成质控', value: qcSummary.value.readyRecords },
  ...(qcSummary.value.partialFailedRecords || qcSummary.value.failedRecords
    ? [{ key: 'failed' as const, label: '未全部完成', value: (qcSummary.value.partialFailedRecords || 0) + (qcSummary.value.failedRecords || 0) }]
    : []),
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
  const result = resolveResultPresentation(record.latestQcSummary, qcSummaryState.value)
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

function formatMedicalRecordTimestamp(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/u)
  if (!match) return '—'
  return match[2] && match[3] ? `${match[1]} ${match[2]}:${match[3]}` : match[1]
}

function applyFilters() {
  clearSelection()
  currentPage.value = 1
  fetchData(1)
}

function handleSearchChange(event: Event) {
  // Ant Design Vue 先更新值，再用点击事件通知清除操作。
  if (event.type === 'click' && searchText.value === '') applyFilters()
}

function resetVisibleFilters() {
  searchText.value = ''
  activeDept.value = ALL_DEPARTMENTS
  dateRange.value = null
  applyFilters()
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

function updateDateRange(value: unknown) {
  dateRange.value = normalizeWorkstationDateRange(value)
  applyFilters()
}

watch(
  () => props.carePhase,
  (carePhase) => {
    medicalRecordFocus.value = null
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

const medicalRecordFocus = ref<PatientRecord | null>(null)

function handleOpenMedicalRecord(recordKey: string) {
  medicalRecordFocus.value = null
  closeResultDrawer()
  const record = allRecords.value.find(
    (candidate) => candidate.recordKey === recordKey && hasCompleteRecordIdentity(candidate),
  )
  if (!record) {
    detailNotice.value = '无法确认当前病历身份，已停止读取病历文书'
    return
  }
  medicalRecordFocus.value = record
}

function handleOpenResult(recordKey: string, previousResult?: PreviousResultRequest) {
  medicalRecordFocus.value = null
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
  selectedFocus.value = {
    visitId: record.visitId as string,
    instituteId: record.instituteId as string,
    patientId: record.patientId as string,
    recordId: record.id || (record.visitId as string),
    patientName: record.name,
    patientSex: record.sex,
    patientAge: record.age,
    listQcTime: row.latestQcTime && row.latestQcTime !== '—' ? `质控结束 ${row.latestQcTime}` : undefined,
    previousResult,
    label: labelParts.join(' · '),
  }
  drawerOpen.value = true
}

function handleOpenAnalysisResult(record: LuxianQcAnalysisRecordItem) {
  medicalRecordFocus.value = null
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
  selectedFocus.value = {
    visitId,
    instituteId,
    patientId,
    recordId: visitId,
    patientName: String(record.patient_name || '').trim(),
    listQcTime: completedAt !== '—' ? `质控完成 ${completedAt}` : undefined,
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
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
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
  color: #0a6cff;
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
  border: 1px solid #0a6cff;
  border-radius: 10px;
  background: #0a6cff;
  color: #fff;
  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 0 7px 16px rgba(10, 108, 255, 0.18);
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
  background: rgba(10, 108, 255, 0.07);
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

.qc-record-result-list-view__refresh-button {
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: #fff;
  color: #0a6cff;
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
  color: #0a6cff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__refresh-button {
  border-color: #0a6cff;
  background: #0a6cff;
  color: #fff;
}

.qc-record-result-list-view__refresh-button:hover:not(:disabled) {
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
  border-top: 1px solid rgba(10, 108, 255, 0.1);
  background: rgba(10, 108, 255, 0.045);
  color: #0a6cff !important;
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
</style>
