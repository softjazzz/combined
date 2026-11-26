<template>
  <div class="qc-record-result-list-view running-qc-refined running-qc-apple">
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
            @click="setActiveView('records')"
          >
            病历结果
          </button>
          <button
            type="button"
            class="mq-segmented__item"
            data-testid="qc-result-view-analysis"
            :class="{ 'is-active': activeView === 'analysis' }"
            :aria-pressed="activeView === 'analysis'"
            :disabled="!sourceId || sourceId === 'independent_cdm'"
            :title="!sourceId ? '正在加载数据源…' : sourceId === 'independent_cdm' ? 'CDM来源暂不提供跨病例结果分析' : ''"
            @click="setActiveView('analysis')"
          >
            结果分析
          </button>
        </nav>
        <div class="review-workbench-primary">
          <QcRunSelectedControl
            :key="`${sourceId || 'pending'}:${carePhase}`"
            :source-id="sourceId"
            :care-phase="carePhase"
            :record-refs="selectedQcRecordRefs"
            :selected-count="selectedCount"
            :status-target="`#qc-record-result-task-status-${carePhase}`"
            :inline-result-viewer="true"
            @results-updated="refreshAfterSelectedQc"
            @view-results="handleViewBatchQcResults"
            @dismiss-task="handleDismissBatchQcTask"
          />
        </div>
      </div>
    </section>

    <section
      class="review-workbench-metrics mq-card"
      aria-label="质控结果汇总"
      :aria-busy="!qcTotalsReady && qcSummaryState === 'pending'"
    >
      <div
        v-for="metric in metricItems"
        :key="metric.key"
        :class="`review-metric--${metric.key}`"
      >
        <span>{{ metric.key === 'priority' ? '确定问题' : metric.label }}</span>
        <strong>{{ metric.key === 'records' || qcTotalsReady ? metric.value : '—' }}</strong>
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
      :message="qcTotalsReady ? '本页质控摘要暂不可用' : '质控摘要暂不可用'"
      show-icon
    >
      <template #action>
        <Button
          size="small"
          data-testid="qc-result-retry-summary"
          @click="handleRefreshData"
        >
          重试摘要
        </Button>
      </template>
    </Alert>

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
            class="qc-record-result-list-view__filter-field qc-record-result-list-view__source-field"
            aria-label="病历数据源"
          >
            <span class="qc-record-result-list-view__field-label">数据源</span>
            <span class="qc-record-result-list-view__source-badge">东华CDM</span>
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
            @keydown.esc="closeExportMenu"
          >
            <button
              ref="exportTriggerRef"
              class="qc-record-result-list-view__export-trigger"
              type="button"
              data-testid="qc-result-export-trigger"
              :disabled="loading || exporting"
              :aria-expanded="exportMenuOpen"
              aria-haspopup="menu"
              @click="exportMenuOpen = !exportMenuOpen"
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
            @click="handleRefreshData"
          >
            刷新
          </button>
        </div>
      </div>

      <p
        v-if="detailNotice || exportNotice"
        class="qc-record-result-list-view__notice"
        :class="{ 'qc-record-result-list-view__notice--error': noticeTone === 'error' }"
        data-testid="qc-result-notice"
        role="status"
      >
        {{ detailNotice || exportNotice }}
      </p>

      <BatchQcResultsPanel
        v-if="batchQcResults"
        :items="batchQcResults.items"
        :loading="batchQcResults.loading"
        :active-record-key="batchQcResults.activeRecordKey"
        :export-scope="isInpatient ? 'running' : 'final'"
        @open-record="handleOpenBatchQcResult"
        @exit="exitBatchQcResults"
      />
      <div v-else class="review-workbench-split">
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
                @click="handleRefreshData"
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
              @change="onPageChange"
            />
          </footer>
        </div>
        <QcRecordReviewPreview
          :key="`${resolvedSourceEpoch}:${carePhase}`"
          :care-phase="carePhase"
          :row="previewRow"
          :refresh-key="previewRefreshKey"
          @open-full="handleOpenResult"
        />
      </div>
    </section>

    <QcRecordResultAnalysisPanel
      v-else
      :key="`${resolvedSourceEpoch}:${analysisRefreshKey}`"
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
      :batch-records="comparisonBatchRecords"
      :active-batch-index="comparisonBatchIndex"
      presentation-mode="grouped"
      :load-job-metadata="!route.path?.startsWith('/workstation-v5/')"
      @select-batch-index="handleSelectComparisonBatchIndex"
      @close="closeResultDrawer"
    />
  </div>
</template>

<script setup lang="ts">
import { Alert, Button, Empty, Input, Pagination, RangePicker, Select, Spin } from 'ant-design-vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronDown, Download } from 'lucide-vue-next'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import type { MqIconName, MqIconTone } from '@/components/icons/mqIcons'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'

import { exportFilteredLuxian0609RecordResults } from '@/services/sichuan-rule-workspace-service'

import QCRecordResultComparisonDrawer, {
  type QCRecordResultBatchItem,
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
import QcRunSelectedControl, {
  type SelectedQcRecordRef,
} from './components/qc/QcRunSelectedControl.vue'
import BatchQcResultsPanel from './components/workbench/BatchQcResultsPanel.vue'
import type { SichuanBatchJob } from './semantic-rules/types'
import { buildCaseRecordKey } from './utils/caseRecordKey'
import {
  resolveBatchResultRecords,
  toComparisonFocusFromBatchItem,
  type BatchResultRecordItem,
} from './utils/batchResultViewer'
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
const instance = getCurrentInstance()
const { confirmedResultsOnly } = useQcResultVisibility()
const detailNotice = ref('')
const exportNotice = ref('')
const exportNoticeTone = ref<'info' | 'error'>('info')
const noticeTone = computed<'info' | 'error'>(() =>
  detailNotice.value ? 'error' : exportNoticeTone.value,
)
const exporting = ref(false)
const exportMenuOpen = ref(false)
const exportTriggerRef = ref<HTMLButtonElement | null>(null)
const drawerOpen = ref(false)
const selectedFocus = ref<QCRecordResultFocus | null>(null)
const comparisonBatchQueue = ref<BatchResultRecordItem[]>([])
const comparisonBatchIndex = ref(-1)
const batchQcResults = ref<{
  jobId: string
  loading: boolean
  items: BatchResultRecordItem[]
  activeRecordKey?: string
} | null>(null)
const knownRecordsByKey = new Map<string, PatientRecord>()
let batchQcResultSequence = 0
const comparisonBatchRecords = computed<QCRecordResultBatchItem[]>(() =>
  comparisonBatchQueue.value.map((item) => ({
    recordKey: item.recordKey,
    patientName: item.patientName,
    visitId: item.visitId,
    department: item.department,
    confirmedIssueCount: item.confirmedIssueCount,
    resultLabel: item.resultLabel,
  })),
)
const activeFocusRuleId = ref('')
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
const analysisRefreshKey = ref(0)
const resolvedSourceEpoch = ref(0)
const pendingDeepLinkKey = ref('')
let deepLinkGeneration = 0
let hasInitialMountFetch = false
let lastRequestedCarePhase: QcRecordCarePhase | null = null
let lastResolvedSourceId = ''

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
  hospFilter,
  loadError,
  loading,
  qcSummary,
  qcSummaryState,
  qcTotalsReady,
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
  { key: 'records', label: '纳入病历', value: qcTotalsReady.value ? qcSummary.value.totalRecords : serverTotal.value },
  { key: 'completed', label: '已完成质控', value: qcSummary.value.readyRecords },
  ...(!confirmedResultsOnly.value && (qcSummary.value.partialFailedRecords || qcSummary.value.failedRecords)
    ? [{ key: 'failed' as const, label: '未全部完成', value: (qcSummary.value.partialFailedRecords || 0) + (qcSummary.value.failedRecords || 0) }]
    : []),
  {
    key: 'priority',
    label: '需优先复核',
    value: statusCount(qcSummary.value.statusCounts, 'non_compliant'),
  },
  ...(!confirmedResultsOnly.value
    ? [{
        key: 'dataGap' as const,
        label: '资料待核实',
        value: statusCount(qcSummary.value.statusCounts, 'data_gap'),
      }]
    : []),
])

// 保持后端分页顺序，避免 deferred 摘要回填后客户端重排造成列表跳动
const rows = computed<QcRecordResultRow[]>(() =>
  allRecords.value.filter(hasCompleteRecordIdentity).map(toResultRow),
)
const selectedCount = computed(() => selectedRecordKeys.value.length)
const activePreviewKey = ref('')
const previewRefreshKey = ref(0)
const previewRow = computed(
  () => rows.value.find((row) => row.recordKey === activePreviewKey.value) ?? null,
)
watch(
  rows,
  (next) => {
    if (pendingDeepLinkKey.value && next.some((row) => row.recordKey === pendingDeepLinkKey.value)) {
      activePreviewKey.value = pendingDeepLinkKey.value
      return
    }
    if (!next.some((row) => row.recordKey === activePreviewKey.value)) {
      activePreviewKey.value = next[0]?.recordKey ?? ''
    }
  },
  { immediate: true },
)

// 仅当同一病历在相同非占位状态下发生原地摘要变更时主动刷新预览；
// recordKey / resultStatus 变更已由 QcRecordReviewPreview 自身监听处理，避免重复拉取。
watch(
  () => [
    previewRow.value?.recordKey ?? '',
    previewRow.value?.resultStatus ?? '',
    previewRow.value?.latestQcTime ?? '',
    previewRow.value?.issueSummary ?? '',
  ],
  ([nextKey, nextStatus, nextTime, nextSummary], [prevKey, prevStatus, prevTime, prevSummary]) => {
    if (!nextKey || nextKey !== prevKey) return
    if (nextStatus !== prevStatus) return
    if (nextStatus === 'unknown' || nextStatus === 'not-run') return
    if (nextTime !== prevTime || nextSummary !== prevSummary) {
      previewRefreshKey.value += 1
    }
  },
)

function cancelPendingDeepLink() {
  pendingDeepLinkKey.value = ''
  deepLinkGeneration += 1
}

function tryResolvePendingDeepLink() {
  const targetKey = pendingDeepLinkKey.value
  if (!targetKey) return
  if (loading.value || qcSummaryState.value === 'pending') return
  pendingDeepLinkKey.value = ''
  if (loadError.value) return
  if (rows.value.some((row) => row.recordKey === targetKey)) {
    activePreviewKey.value = targetKey
    handleOpenResult(targetKey)
    return
  }
  if (allRecords.value.some((candidate) => candidate.recordKey === targetKey)) {
    handleOpenResult(targetKey)
    return
  }
  closeResultDrawer()
  detailNotice.value = '未在当前筛选页找到目标病历，请调整筛选条件或翻页查看'
}

function handleSelectPreview(recordKey: string) {
  cancelPendingDeepLink()
  activePreviewKey.value = recordKey
}

function hasCompleteRecordIdentity(record: PatientRecord): boolean {
  return Boolean(record.recordKey && record.instituteId && record.patientId && record.visitId)
}

interface CommittedListFilters {
  department: string
  doctor: string
  keyword: string
  dateRange: [string, string] | null
}

const committedFilters = ref<CommittedListFilters>({
  department: ALL_DEPARTMENTS,
  doctor: '全部主管医师',
  keyword: '',
  dateRange: null,
})

function commitCurrentFilters() {
  committedFilters.value = {
    department: String(activeDept.value || '').trim() || ALL_DEPARTMENTS,
    doctor: String(activeDoctor.value || '').trim() || '全部主管医师',
    keyword: String(searchText.value || '').trim(),
    dateRange: dateRange.value ? [dateRange.value[0], dateRange.value[1]] : null,
  }
}

function toResultRow(record: PatientRecord): QcRecordResultRow {
  const result = resolveResultPresentation(record.latestQcSummary, qcSummaryState.value, {
    confirmedOnly: confirmedResultsOnly.value,
  })
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
      !confirmedResultsOnly.value && record.sourceState && record.sourceState.status !== 'unknown'
        ? '资料同步待核实'
        : undefined,
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

let manualRefreshSequence = 0

function pruneStaleSelectedRecordKeys() {
  if (selectedRecordKeys.value.length === 0) return
  const currentKeys = new Set(rows.value.map((row) => row.recordKey))
  const retainedKeys = selectedRecordKeys.value.filter((key) => currentKeys.has(key))
  if (retainedKeys.length === selectedRecordKeys.value.length) return
  const nextRefs: Record<string, { institute_id: string; patient_id: string; visit_id: string }> = {}
  for (const key of retainedKeys) {
    const refItem = selectedRecordRefs.value[key]
    if (refItem) nextRefs[key] = refItem
  }
  selectedRecordRefs.value = nextRefs
  selectedRecordKeys.value = retainedKeys
}

function applyFilters() {
  ++manualRefreshSequence
  exitBatchQcResults()
  cancelPendingDeepLink()
  clearSelection()
  commitCurrentFilters()
  currentPage.value = 1
  fetchData(1)
}

async function handleRefreshData() {
  const sequence = ++manualRefreshSequence
  cancelPendingDeepLink()
  await refreshData()
  if (sequence !== manualRefreshSequence || loading.value || loadError.value) return
  pruneStaleSelectedRecordKeys()
}

function onPageChange(page: number, nextPageSize?: number) {
  ++manualRefreshSequence
  cancelPendingDeepLink()
  handlePageChange(page, nextPageSize)
}

function handleSearchChange(event: Event) {
  // Ant Design Vue 先更新值，再用点击事件通知清除操作。
  if (event.type === 'click' && searchText.value === '') applyFilters()
}

function resetVisibleFilters() {
  searchText.value = ''
  activeDept.value = ALL_DEPARTMENTS
  activeDoctor.value = '全部主管医师'
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
    knownRecordsByKey.set(key, record)
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
  previewRefreshKey.value += 1
  analysisRefreshKey.value += 1
  refreshData()
}

function closeExportMenu() {
  if (!exportMenuOpen.value) return
  exportMenuOpen.value = false
  exportTriggerRef.value?.focus()
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
    exportNoticeTone.value = 'error'
    exportNotice.value = '所选病历身份已变化，请重新勾选后导出'
    clearSelection()
    return
  }

  exporting.value = true
  exportNotice.value = ''
  exportNoticeTone.value = 'info'
  try {
    const response = await exportFilteredLuxian0609RecordResults({
      scope: isInpatient.value ? 'running' : 'final',
      date_field: isInpatient.value ? 'admission' : 'discharge',
      record_refs: recordRefs,
    })
    if (!response.success || !response.data) {
      exportNoticeTone.value = 'error'
      exportNotice.value = response.message || '导出所选质控结果失败'
      return
    }
    downloadBlob(
      response.data,
      `${isInpatient.value ? '运行病历质控' : '终末病历质控'}-所选${recordRefs.length}份.xlsx`,
    )
    exportNoticeTone.value = 'info'
    exportNotice.value = `已开始下载所选 ${recordRefs.length} 份病历的质控结果`
  } catch {
    exportNoticeTone.value = 'error'
    exportNotice.value = '导出所选质控结果失败，请稍后重试'
  } finally {
    exporting.value = false
  }
}

async function exportCurrentFilter() {
  if (exporting.value) return
  exporting.value = true
  exportNotice.value = ''
  exportNoticeTone.value = 'info'
  const [rangeStart, rangeEnd] = committedFilters.value.dateRange || []
  const department = committedFilters.value.department
  const doctor = committedFilters.value.doctor
  const keyword = committedFilters.value.keyword
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
      exportNoticeTone.value = 'error'
      exportNotice.value = response.message || '导出当前筛选质控结果失败'
      return
    }
    downloadBlob(
      response.data,
      `${isInpatient.value ? '运行病历质控' : '终末病历质控'}-当前筛选.xlsx`,
    )
    exportNoticeTone.value = 'info'
    exportNotice.value = '当前筛选质控结果已开始下载'
  } catch {
    exportNoticeTone.value = 'error'
    exportNotice.value = '导出当前筛选质控结果失败，请稍后重试'
  } finally {
    exporting.value = false
  }
}

function updateDateRange(value: unknown) {
  dateRange.value = normalizeWorkstationDateRange(value)
  applyFilters()
}

function setActiveView(nextView: 'records' | 'analysis') {
  if (nextView === 'analysis' && (!sourceId.value || sourceId.value === 'independent_cdm')) {
    return
  }
  if (activeView.value === nextView) return
  activeView.value = nextView
}

watch(sourceId, (nextSourceId) => {
  if (nextSourceId === 'independent_cdm') {
    activeView.value = 'records'
  }
  if (!nextSourceId) return
  if (lastResolvedSourceId && lastResolvedSourceId !== nextSourceId) {
    resolvedSourceEpoch.value += 1
  }
  lastResolvedSourceId = nextSourceId
})

watch(
  () => props.carePhase,
  (carePhase, previousCarePhase) => {
    if (carePhase === previousCarePhase) return
    ++manualRefreshSequence
    exitBatchQcResults()
    cancelPendingDeepLink()
    medicalRecordFocus.value = null
    closeResultDrawer()
    clearSelection()
    exportNotice.value = ''
    exportNoticeTone.value = 'info'
    exportMenuOpen.value = false
    activePreviewKey.value = ''
    detailNotice.value = ''
    activeDept.value = ALL_DEPARTMENTS
    activeDoctor.value = '全部主管医师'
    searchText.value = ''
    dateRange.value = null
    commitCurrentFilters()
    currentPage.value = 1
    activeView.value = 'records'
    dateField.value = carePhase === 'inpatient' ? 'admission' : 'discharge'
    if (!hasInitialMountFetch) return
    lastRequestedCarePhase = carePhase
    const prevHospFilter = hospFilter?.value
    selectHospFilter(carePhase)
    if (prevHospFilter === carePhase) {
      void fetchData(1)
    }
  },
)

watch(
  () => [loading.value, qcSummaryState.value, loadError.value],
  () => {
    tryResolvePendingDeepLink()
  },
)

onBeforeUnmount(() => {
  ++manualRefreshSequence
  cancelPendingDeepLink()
})

onMounted(async () => {
  hasInitialMountFetch = true
  lastRequestedCarePhase = props.carePhase
  if (sourceId.value) {
    lastResolvedSourceId = sourceId.value
  }
  dateField.value = props.carePhase === 'inpatient' ? 'admission' : 'discharge'
  if (hospFilter && hospFilter.value !== props.carePhase) {
    hospFilter.value = props.carePhase
  }
  const requestedRecordKey = routeQueryText('record_key')
  const requestedVisitId = routeQueryText('visit_id')
  if (requestedRecordKey) {
    pendingDeepLinkKey.value = requestedRecordKey
    if (requestedVisitId) searchText.value = requestedVisitId
  }
  commitCurrentFilters()
  const generation = ++deepLinkGeneration
  await fetchData(1)
  if (generation !== deepLinkGeneration || !pendingDeepLinkKey.value) return
  tryResolvePendingDeepLink()
})

function routeQueryText(name: string): string {
  const value = route.query[name]
  return typeof value === 'string' ? value.trim() : ''
}

const medicalRecordFocus = ref<PatientRecord | null>(null)

function handleOpenMedicalRecord(recordKey: string) {
  cancelPendingDeepLink()
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

function handleOpenResult(
  recordKey: string,
  previousResult?: PreviousResultRequest,
  focusRuleId?: string,
) {
  if (pendingDeepLinkKey.value && pendingDeepLinkKey.value !== recordKey) {
    cancelPendingDeepLink()
  }
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
  activeFocusRuleId.value = typeof focusRuleId === 'string' ? focusRuleId.trim() : ''
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
    admissionTime: record.admissionDate,
    dischargeTime: record.dischargeDate,
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

function exitBatchQcResults() {
  batchQcResultSequence += 1
  batchQcResults.value = null
  closeResultDrawer()
}

function handleDismissBatchQcTask(jobId: string) {
  if (jobId && batchQcResults.value?.jobId === jobId) {
    exitBatchQcResults()
  }
}

function handleOpenBatchQcResult(payload: {
  item: BatchResultRecordItem
  queue: BatchResultRecordItem[]
  index: number
}) {
  medicalRecordFocus.value = null
  detailNotice.value = ''
  comparisonBatchQueue.value = payload.queue
  comparisonBatchIndex.value = payload.index
  selectedFocus.value = toComparisonFocusFromBatchItem(payload.item)
  drawerOpen.value = true
  if (batchQcResults.value) {
    batchQcResults.value = { ...batchQcResults.value, activeRecordKey: payload.item.recordKey }
  }
}

function handleSelectComparisonBatchIndex(nextIndex: number) {
  const nextItem = comparisonBatchQueue.value[nextIndex]
  if (!nextItem) return
  comparisonBatchIndex.value = nextIndex
  selectedFocus.value = toComparisonFocusFromBatchItem(nextItem)
  if (batchQcResults.value) {
    batchQcResults.value = { ...batchQcResults.value, activeRecordKey: nextItem.recordKey }
  }
}

async function handleViewBatchQcResults(payload: {
  job: SichuanBatchJob
  recordRefs: SelectedQcRecordRef[]
}) {
  const jobId = String(payload.job?.id || '').trim()
  if (!jobId) return
  const sequence = ++batchQcResultSequence
  const currentByKey = new Map<string, PatientRecord>()
  for (const record of allRecords.value) {
    if (!hasCompleteRecordIdentity(record)) continue
    const key = buildCaseRecordKey(
      record.instituteId as string,
      record.patientId as string,
      record.visitId as string,
    )
    if (key) {
      currentByKey.set(key, record)
      knownRecordsByKey.set(key, record)
    }
  }
  const submittedRecords = (payload.recordRefs || [])
    .map((refItem) => {
      const key = buildCaseRecordKey(refItem.institute_id, refItem.patient_id, refItem.visit_id)
      return currentByKey.get(key) ?? knownRecordsByKey.get(key)
    })
    .filter((record): record is PatientRecord => Boolean(record))
  const expectedTotal = Math.max(
    0,
    Math.trunc(Number(payload.job.total_records ?? payload.job.summary?.total_records ?? 0) || 0),
  )
  activeView.value = 'records'
  if (expectedTotal !== 1 && submittedRecords.length !== 1) {
    batchQcResults.value = {
      jobId,
      loading: true,
      items: [],
      activeRecordKey: '',
    }
  }
  const resolved = await resolveBatchResultRecords({
    job: payload.job,
    sourceId: sourceId.value,
    submittedRecords,
    currentRecords: allRecords.value,
    confirmedOnly: confirmedResultsOnly.value,
  })
  if (sequence !== batchQcResultSequence) return
  if (resolved.items.length === 1) {
    batchQcResults.value = null
    medicalRecordFocus.value = null
    detailNotice.value = ''
    comparisonBatchQueue.value = []
    comparisonBatchIndex.value = -1
    selectedFocus.value = toComparisonFocusFromBatchItem(resolved.items[0])
    drawerOpen.value = true
    return
  }
  if (resolved.items.length >= 2) {
    batchQcResults.value = {
      jobId,
      loading: false,
      items: resolved.items,
      activeRecordKey: '',
    }
    return
  }
  batchQcResults.value = null
  const fallbackUrl = `/workstation-v5/qc-task?job_id=${encodeURIComponent(jobId)}`
  const appRouter = instance?.appContext.config.globalProperties.$router as
    | { push?: (target: string) => unknown }
    | undefined
  if (typeof appRouter?.push === 'function') {
    void appRouter.push(fallbackUrl)
  } else if (typeof window !== 'undefined') {
    window.location.assign(fallbackUrl)
  }
}

function closeResultDrawer() {
  drawerOpen.value = false
  selectedFocus.value = null
  comparisonBatchQueue.value = []
  comparisonBatchIndex.value = -1
  activeFocusRuleId.value = ''
  detailNotice.value = ''
  if (batchQcResults.value) {
    batchQcResults.value = { ...batchQcResults.value, activeRecordKey: '' }
  }
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
  left: auto;
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
  border-bottom: 1px solid rgba(10, 108, 255, 0.12);
  background: rgba(10, 108, 255, 0.045);
  color: #0a6cff !important;
  font-weight: 600;
}

.qc-record-result-list-view__notice--error {
  border-bottom-color: rgba(239, 68, 68, 0.18);
  background: #fff4f2;
  color: #b42318 !important;
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
    justify-content: flex-end;
  }

  .qc-record-result-list-view__export-options {
    right: 0;
    left: auto;
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
