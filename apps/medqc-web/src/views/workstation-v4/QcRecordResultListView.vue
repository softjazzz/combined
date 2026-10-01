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
        @click="switchResultView('records')"
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
      <button
        type="button"
        data-testid="qc-result-view-defects"
        :class="{ 'is-active': activeView === 'defects' }"
        :aria-pressed="activeView === 'defects'"
        @click="switchResultView('defects')"
      >
        缺陷结果
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

    <section v-if="activeView !== 'analysis'" class="qc-record-result-list-view__workbench">
      <RecordFilterTemplateBar
        :page-key="filterTemplatePageKey"
        :current-filters="activeFilters"
        :resolve-initial-filters="!urlHadExplicitFilters && !filtersInitialized"
        :disabled="loading"
        :defect-view="activeView === 'defects'"
        @apply="handleTemplateFilters"
        @default-resolved="hasUserDefaultTemplate = $event"
      />
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
          <label class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">缺陷来源</span>
            <select v-model="defectSourceFilter" aria-label="缺陷来源筛选" @change="applyFilters">
              <option value="all">全部真实来源</option>
              <option value="auto">自动缺陷</option>
              <option value="manual">人工缺陷</option>
            </select>
          </label>
          <label v-if="activeView === 'records'" class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">缺陷状态</span>
            <select v-model="hasDefectSelection" aria-label="缺陷状态筛选" @change="applyFilters">
              <option value="">全部病历</option>
              <option value="true">存在缺陷</option>
              <option value="false">无确认缺陷</option>
            </select>
          </label>
          <label class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">主管医师</span>
            <select v-model="activeDoctor" aria-label="主管医师筛选" @change="applyFilters">
              <option value="全部主管医师">全部主管医师</option>
              <option v-for="doctor in doctorOptions" :key="doctor" :value="doctor">
                {{ doctor }}
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
          <label class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">评分标准</span>
            <select v-model="standardIdFilter" aria-label="评分标准筛选" @change="applyFilters">
              <option value="">
                {{
                  scoreStandardOptionsStatus === 'unavailable' ? '评分标准暂不可用' : '场景默认标准'
                }}
              </option>
              <option
                v-for="standard in scoreStandardOptions"
                :key="standard.id"
                :value="standard.id"
              >
                {{ standard.name }}{{ standard.isDefault ? '（默认）' : '' }}
              </option>
            </select>
          </label>
          <label class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">计分状态</span>
            <select v-model="scoreStatusFilter" aria-label="计分状态筛选" @change="applyFilters">
              <option value="">全部状态</option>
              <option value="scored">已计分</option>
              <option value="no_standard">未配置评分标准</option>
              <option value="unavailable">已质控但评分不可用</option>
            </select>
          </label>
          <label class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">评分等级</span>
            <select v-model="gradeFilter" aria-label="评分等级筛选" @change="applyFilters">
              <option value="">全部等级</option>
              <option v-for="grade in scoreGradeOptions" :key="grade" :value="grade">
                {{ grade }}
              </option>
            </select>
          </label>
          <div class="qc-record-result-list-view__filter-field">
            <span class="qc-record-result-list-view__field-label">分数区间</span>
            <div class="qc-record-result-list-view__score-range">
              <input
                v-model.number="scoreMinFilter"
                type="number"
                step="0.01"
                aria-label="最低得分"
              />
              <span>至</span>
              <input
                v-model.number="scoreMaxFilter"
                type="number"
                step="0.01"
                aria-label="最高得分"
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
                <span>按当前科室、主管医师、日期、关键词和审核状态导出</span>
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

      <div v-if="activeView === 'records'" class="review-workbench-split">
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
            <button
              v-if="canOpenUnreviewedDocuments"
              class="qc-record-result-list-view__document-button"
              type="button"
              data-testid="open-unchecked-record-documents"
              @click="handleOpenResult(activePreviewKey)"
            >
              <FileText :size="15" aria-hidden="true" />
              查看病历文书
            </button>
            <QcRecordColumnSettings
              v-model="visibleColumns"
              class="qc-record-result-list-view__column-settings"
              :user-id="currentUserId"
              :care-phase="carePhase"
              :available-columns="availableColumns"
              :default-columns="defaultColumns"
            />
          </div>
          <QcRecordResultTable
            :care-phase="carePhase"
            compact-review
            show-score
            :active-record-key="activePreviewKey"
            :rows="rows"
            :selected-record-keys="selectedRecordKeys"
            :visible-columns="visibleColumns"
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
      <div v-else class="review-workbench-list qc-record-result-list-view__defects">
        <div class="qc-record-result-list-view__list-heading">
          <h2>缺陷结果</h2>
          <span v-if="!loadError">共 {{ serverTotal }} 条 · 本页 {{ defects.length }} 条</span>
          <span v-else role="alert">缺陷数据加载失败，请重试</span>
        </div>
        <div
          class="qc-record-result-list-view__defect-table"
          role="table"
          aria-label="缺陷结果列表"
        >
          <div class="qc-record-result-list-view__defect-row is-header" role="row">
            <span>患者与病历</span><span>来源</span><span>质控点</span><span>文书/位置</span
            ><span>状态</span><span>操作</span>
          </div>
          <div
            v-for="item in defects"
            :key="defectRowKey(item)"
            class="qc-record-result-list-view__defect-row"
            role="row"
          >
            <span
              ><strong>{{ item.patient_name || '姓名未知' }}</strong
              ><small>{{ item.visit_id }} · {{ item.department || '科室未知' }}</small></span
            >
            <span>{{ item.source === 'auto' ? '自动缺陷' : '人工缺陷' }}</span>
            <span
              ><strong>{{ item.rule_id || '未编码' }}</strong
              ><small>{{ item.rule_name || item.description || '未返回名称' }}</small></span
            >
            <span>{{ item.document || '位置未知' }}</span>
            <span>{{ defectStatusLabel(item) }}</span>
            <span>
              <button type="button" @click="openDefectResult(item)">查看病例</button>
              <button type="button" @click="openDefectResult(item)">整改 / 催办</button>
            </span>
          </div>
          <p
            v-if="!loading && !loadError && defects.length === 0"
            class="qc-record-result-list-view__defect-empty"
          >
            当前条件下暂无缺陷
          </p>
        </div>
        <footer v-if="serverTotal > 0" class="qc-record-result-list-view__pagination">
          <Pagination
            :current="currentPage"
            :page-size="pageSize"
            :total="serverTotal"
            :disabled="loading"
            :show-total="(total: number) => `共 ${total} 条缺陷`"
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
      record-review
      :score-scene="scoreScene"
      :has-prev="drawerNavigation?.hasPrev"
      :has-next="drawerNavigation?.hasNext"
      :current-index="drawerNavigation?.currentIndex"
      :total-count="drawerNavigation?.totalCount"
      :initial-defect-partition="selectedDefectPartition"
      :initial-defect-target="selectedDefectTarget"
      @close="closeResultDrawer"
      @review-submitted="refreshAfterRecordReview"
      @navigate-prev="navigateResult(-1)"
      @navigate-next="navigateResult(1)"
    />
    <Drawer
      :open="documentDrawerOpen"
      placement="right"
      width="min(1380px, 100vw)"
      title="病历文书"
      :body-style="{ padding: 0 }"
      @close="closeResultDrawer"
    >
      <QCRecordCompareWorkbench
        v-if="documentDrawerOpen && selectedFocus"
        :visit-id="selectedFocus.visitId"
        :institute-id="selectedFocus.instituteId"
        :patient-id="selectedFocus.patientId"
        :issues="[]"
        document-only
      />
    </Drawer>
  </main>
</template>

<script setup lang="ts">
import { Drawer, Pagination } from 'ant-design-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronDown, Download, FileText } from 'lucide-vue-next'

import { exportFilteredLuxian0609RecordResults } from '@/services/sichuan-rule-workspace-service'
import { useAuthStore } from '@/stores/auth'

import QCRecordResultComparisonDrawer, {
  type QCRecordResultFocus,
} from './customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import QCRecordCompareWorkbench from './semantic-rules/components/QCRecordCompareWorkbench.vue'
import QcRecordResultTable, {
  type QcRecordCarePhase,
  type QcRecordResultRow,
  type QcRecordReviewState,
} from './components/qc/QcRecordResultTable.vue'
import QcRecordResultAnalysisPanel from './components/qc/QcRecordResultAnalysisPanel.vue'
import QcRecordReviewPreview from './components/qc/QcRecordReviewPreview.vue'
import QcRecordColumnSettings from './components/qc/QcRecordColumnSettings.vue'
import {
  QC_RECORD_COLUMN_OPTIONS,
  defaultQcRecordColumns,
  type QcRecordOptionalColumn,
} from './components/qc/qcRecordColumnPreferences'
import { resolveScoreCell, scoreSceneForCarePhase } from './components/qc/qcRecordScore'
import QcRunSelectedControl from './components/qc/QcRunSelectedControl.vue'
import RecordFilterTemplateBar from './components/qc/RecordFilterTemplateBar.vue'
import { isEmptyRecordFilter, parseRecordFilterQuery } from './composables/recordFilterQuery'
import { useRecordFilterUrlSync } from './composables/useRecordFilterUrlSync'
import { usePatientRecords } from './composables/usePatientRecords'
import type { WorkstationDefectItem } from './composables/usePatientRecords'
import type { PatientRecord, RecordLatestQcSummary } from './types'
import type { LuxianQcAnalysisRecordItem } from '@/services/luxian-qc-result-analysis-service'
import { downloadBlob } from './customer-sample-validation/batchExport'

const props = defineProps<{
  carePhase: QcRecordCarePhase
}>()

const route = useRoute()
const authStore = useAuthStore()
const detailNotice = ref('')
const exportNotice = ref('')
const exporting = ref(false)
const exportMenuOpen = ref(false)
const drawerOpen = ref(false)
const documentDrawerOpen = ref(false)
const selectedFocus = ref<QCRecordResultFocus | null>(null)
/** 当前抽屉对应的列表行；仅由列表行打开时有值，分析面板打开时为空（不提供导航）。 */
const selectedRecordKey = ref('')
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
const activeView = ref<'records' | 'defects' | 'analysis'>('records')
const selectedDefectPartition = ref<'confirmed' | 'manual'>('confirmed')
const selectedDefectTarget = ref<{
  source: 'auto' | 'manual'
  ruleId?: string
  defectId?: string
  rootJobId?: string
  envelopeId?: string
} | null>(null)
const startDate = ref('')
const endDate = ref('')

const isInpatient = computed(() => props.carePhase === 'inpatient')
const currentUserId = computed(() => String(authStore.user?.id || '').trim())
const actorKey = computed(() => {
  const roles = Array.isArray(authStore.userRoles) ? [...authStore.userRoles].sort() : []
  return `${currentUserId.value}|${roles.join(',')}`
})
const availableColumns = QC_RECORD_COLUMN_OPTIONS.map((option) => option.key)
const defaultColumns = defaultQcRecordColumns({ compactReview: true, showScore: true })
const visibleColumns = ref<QcRecordOptionalColumn[]>([...defaultColumns])
const pageTitle = computed(() => (isInpatient.value ? '运行病历质控' : '已出院病历质控结果'))
const scopeLabel = computed(() => (isInpatient.value ? '固定范围：在院' : '固定范围：已出院'))

const {
  allRecords,
  defects,
  activeDept,
  activeDoctor,
  currentPage,
  pageSize,
  dateField,
  dateRange,
  departments,
  doctors,
  fetchData,
  handlePageChange,
  loadError,
  loading,
  qcSummary,
  refreshData,
  reviewStateFilter,
  standardIdFilter,
  scoreStatusFilter,
  gradeFilter,
  scoreMinFilter,
  scoreMaxFilter,
  resultView,
  defectSourceFilter,
  defectWorkflowFilter,
  hasDefectFilter,
  scoreStandards,
  scoreStandardOptions,
  scoreStandardOptionsStatus,
  searchText,
  selectHospFilter,
  serverTotal,
} = usePatientRecords(props.carePhase)
/** 得分场景：运行列表 running、终末列表 final（与服务端列表计分口径一致）。 */
const scoreScene = computed(() => scoreSceneForCarePhase(props.carePhase))

const filterTemplatePageKey = computed(() =>
  isInpatient.value ? 'v5_records_inpatient' : 'v5_records_discharged',
)
// 筛选以 URL query 为唯一来源；URL 未显式给出时由模板栏发出初始筛选（默认模板 > 系统默认）。
const filterSync = useRecordFilterUrlSync({
  state: {
    activeDept,
    activeDoctor,
    searchText,
    startDate,
    endDate,
    dateRange,
    reviewStateFilter,
    standardIdFilter,
    scoreStatusFilter,
    gradeFilter,
    scoreMinFilter,
    scoreMaxFilter,
    resultView,
    defectSourceFilter,
    defectWorkflowFilter,
    hasDefectFilter,
    currentPage,
  },
  fetchData,
  onBeforeLoad: clearSelection,
})
const { activeFilters, urlHadExplicitFilters, filtersInitialized, commitFilters } = filterSync
const hasUserDefaultTemplate = ref(false)
const hasExplicitFilterSelection = ref(false)
let defectViewVisited = false
let lastDefectWorkflow: typeof defectWorkflowFilter.value = ''
let recordViewReviewStates = [...reviewStateFilter.value]

function handleTemplateFilters(filters: Parameters<typeof commitFilters>[0], scopeAll: boolean) {
  if (filtersInitialized.value) hasExplicitFilterSelection.value = true
  commitFilters(filters, scopeAll)
}

const departmentOptions = computed(() =>
  departments.value.map((item) => item.name).filter((name) => name && name !== '全部科室'),
)
const doctorOptions = computed(() =>
  doctors.value.map((item) => item.name).filter((name) => name && name !== '全部主管医师'),
)
const scoreGradeOptions = computed(() => {
  const selected = standardIdFilter.value
    ? scoreStandardOptions.value.find((item) => item.id === standardIdFilter.value)
    : scoreStandardOptions.value.find((item) => item.isDefault)
  return selected?.grades ?? []
})
const hasDefectSelection = computed({
  get: () => (hasDefectFilter.value === null ? '' : String(hasDefectFilter.value)),
  set: (value: string) => {
    hasDefectFilter.value = value === '' ? null : value === 'true'
  },
})

function switchResultView(view: 'records' | 'defects') {
  if (activeView.value === view && resultView.value === view) return
  activeView.value = view
  resultView.value = view
  if (view === 'defects') {
    recordViewReviewStates = [...reviewStateFilter.value]
    reviewStateFilter.value = []
    hasDefectFilter.value = null
    defectWorkflowFilter.value = defectViewVisited
      ? lastDefectWorkflow
      : !urlHadExplicitFilters && !hasUserDefaultTemplate.value && !hasExplicitFilterSelection.value
        ? 'pending_work'
        : defectWorkflowFilter.value
    defectViewVisited = true
  } else {
    defectViewVisited = true
    lastDefectWorkflow = defectWorkflowFilter.value
    defectWorkflowFilter.value = ''
    reviewStateFilter.value = [...recordViewReviewStates]
  }
  commitFilters(filterSync.currentFilterSnapshot())
}

function defectRowKey(item: WorkstationDefectItem): string {
  return [
    item.source,
    item.defect_id || item.rule_id,
    item.institute_id,
    item.patient_id,
    item.visit_id,
  ].join(':')
}

function defectStatusLabel(item: WorkstationDefectItem): string {
  if (item.source === 'manual') return item.status === 'approved' ? '审核通过' : '待审核'
  return '确认缺陷'
}

function openDefectResult(item: WorkstationDefectItem) {
  selectedDefectPartition.value = item.source === 'manual' ? 'manual' : 'confirmed'
  selectedDefectTarget.value =
    item.source === 'manual'
      ? { source: 'manual', defectId: item.defect_id || undefined }
      : { source: 'auto', ruleId: item.rule_id || undefined,
          rootJobId: item.root_job_id || undefined, envelopeId: item.envelope_id || undefined }
  selectedRecordKey.value = ''
  selectedFocus.value = {
    visitId: item.visit_id,
    instituteId: item.institute_id,
    patientId: item.patient_id,
    recordId: item.visit_id,
    patientName: item.patient_name,
    label: `${item.patient_name || item.visit_id} · ${item.source === 'manual' ? '人工缺陷' : '自动缺陷'}`,
  }
  drawerOpen.value = true
}

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

/** 抽屉可导航的行：仅当前页已质控（ready）的病历，跳过未质控与结果校验异常。 */
function isNavigableRow(row: QcRecordResultRow): boolean {
  return row.resultStatus !== 'not-run' && row.resultStatus !== 'technical-error'
}

const navigableRows = computed(() => rows.value.filter(isNavigableRow))

function findAdjacentNavigableKey(direction: -1 | 1): string {
  const currentPosition = rows.value.findIndex((row) => row.recordKey === selectedRecordKey.value)
  if (currentPosition < 0) return ''
  for (
    let index = currentPosition + direction;
    index >= 0 && index < rows.value.length;
    index += direction
  ) {
    const row = rows.value[index]
    if (isNavigableRow(row)) return row.recordKey
  }
  return ''
}

const drawerNavigation = computed(() => {
  if (!drawerOpen.value || !selectedRecordKey.value) return null
  const index = navigableRows.value.findIndex((row) => row.recordKey === selectedRecordKey.value)
  return {
    hasPrev: Boolean(findAdjacentNavigableKey(-1)),
    hasNext: Boolean(findAdjacentNavigableKey(1)),
    currentIndex: index >= 0 ? index + 1 : undefined,
    totalCount: navigableRows.value.length,
  }
})

function navigateResult(direction: -1 | 1) {
  const targetKey = findAdjacentNavigableKey(direction)
  if (targetKey) handleOpenResult(targetKey)
}
const activePreviewKey = ref('')
const previewRefreshKey = ref(0)
const previewRow = computed(
  () => rows.value.find((row) => row.recordKey === activePreviewKey.value) ?? null,
)
const canOpenUnreviewedDocuments = computed(() => {
  const row = previewRow.value
  return Boolean(row?.resultStatus === 'not-run' && row.instituteId && row.patientId && row.visitId)
})
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
  if (!isEmptyRecordFilter(activeFilters.value)) return '当前筛选条件下暂无病历，可调整筛选或重置'
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
    reviewState: resolveReviewState(record.latestQcSummary),
    score: resolveScoreCell(record.latestQcSummary, scoreStandards.value[scoreScene.value]),
  }
}

/** 审核状态只对已质控（ready）病历展示；服务端给 null 时显示为未知，不推断。 */
function resolveReviewState(summary?: RecordLatestQcSummary): QcRecordReviewState | undefined {
  if (summary?.status !== 'ready') return undefined
  return summary.reviewState ?? 'unknown'
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
  hasExplicitFilterSelection.value = true
  commitFilters(filterSync.currentFilterSnapshot())
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

/** 抽屉内审核决定经服务端复核后，重新拉取当前页以更新该行审核状态（不做本地推断）。 */
function refreshAfterRecordReview() {
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
      `${isInpatient.value ? '运行病历质控' : '已出院病历质控'}-所选${recordRefs.length}份.xlsx`,
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
  // 与列表同一审核状态筛选；为空表示不按审核状态筛选（勾选导出不带该参数）。
  const reviewStates = [...new Set(reviewStateFilter.value)]
  try {
    const response = await exportFilteredLuxian0609RecordResults({
      scope: isInpatient.value ? 'running' : 'final',
      ...(department && department !== '全部科室' ? { department } : {}),
      ...(doctor && doctor !== '全部主管医师' ? { doctor } : {}),
      date_field: isInpatient.value ? 'admission' : 'discharge',
      ...(rangeStart ? { start_date: rangeStart } : {}),
      ...(rangeEnd ? { end_date: rangeEnd } : {}),
      ...(keyword ? { keyword } : {}),
      ...(reviewStates.length > 0 ? { review_state: reviewStates } : {}),
    })
    if (!response.success || !response.data) {
      exportNotice.value = response.message || '导出当前筛选质控结果失败'
      return
    }
    downloadBlob(
      response.data,
      `${isInpatient.value ? '运行病历质控' : '已出院病历质控'}-当前筛选.xlsx`,
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

watch(actorKey, clearSelection)
watch(resultView, (view) => {
  if (activeView.value !== 'analysis') activeView.value = view
})

onMounted(async () => {
  dateField.value = props.carePhase === 'inpatient' ? 'admission' : 'discharge'
  if (!urlHadExplicitFilters) return
  const requestedRecordKey = routeQueryText('record_key')
  const requestedVisitId = routeQueryText('visit_id')
  const fromUrl = parseRecordFilterQuery(route.query)
  if (requestedRecordKey && requestedVisitId && !fromUrl.keyword) fromUrl.keyword = requestedVisitId
  await filterSync.loadFilters(fromUrl)
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
    ...(row.admissionTime && row.admissionTime !== '—' ? { admissionTime: row.admissionTime } : {}),
    ...(row.dischargeTime && row.dischargeTime !== '—' ? { dischargeTime: row.dischargeTime } : {}),
    label: labelParts.join(' · '),
  }
  selectedRecordKey.value = recordKey
  if (row.resultStatus === 'not-run') documentDrawerOpen.value = true
  else drawerOpen.value = true
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
  documentDrawerOpen.value = false
  selectedFocus.value = null
  selectedRecordKey.value = ''
  selectedDefectPartition.value = 'confirmed'
  selectedDefectTarget.value = null
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
  flex-wrap: wrap;
  min-width: 0;
  gap: 10px;
}

.qc-record-result-list-view__score-range {
  display: flex;
  align-items: center;
  gap: 6px;
}

.qc-record-result-list-view__score-range input[type='number'] {
  width: 84px;
  padding: 0 8px;
}

.qc-record-result-list-view__score-range span {
  color: rgba(29, 29, 31, 0.45);
  font-size: 12px;
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

.qc-record-result-list-view__defects {
  width: 100%;
}

.qc-record-result-list-view__defect-table {
  overflow-x: auto;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.qc-record-result-list-view__defect-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.2fr) 90px minmax(220px, 1.5fr) minmax(130px, 1fr) 90px 88px;
  min-width: 900px;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
}

.qc-record-result-list-view__defect-row.is-header {
  min-height: 40px;
  background: rgba(0, 0, 0, 0.025);
  color: rgba(29, 29, 31, 0.6);
}

.qc-record-result-list-view__defect-row span,
.qc-record-result-list-view__defect-row strong,
.qc-record-result-list-view__defect-row small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.qc-record-result-list-view__defect-row small {
  display: block;
  color: rgba(29, 29, 31, 0.6);
}

.qc-record-result-list-view__defect-row button {
  border: 0;
  background: transparent;
  color: #007aff;
  cursor: pointer;
}

.qc-record-result-list-view__defect-empty {
  margin: 0;
  padding: 32px 16px;
  text-align: center;
  color: rgba(29, 29, 31, 0.6);
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

.qc-record-result-list-view__column-settings {
  align-self: center;
  margin-left: auto;
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

.qc-record-result-list-view__document-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  margin-left: auto;
  padding: 0 10px;
  border: 1px solid rgba(0, 122, 255, 0.25);
  border-radius: 8px;
  background: #fff;
  color: #007aff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.qc-record-result-list-view__document-button:hover {
  background: #eaf2ff;
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

.running-qc-refined .qc-record-result-list-view__filters {
  grid-template-columns:
    minmax(140px, 1fr) minmax(125px, 150px) minmax(125px, 160px) minmax(280px, 330px)
    auto;
}

@media (max-width: 1100px) {
  .running-qc-refined .qc-record-result-list-view__filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .running-qc-refined .qc-record-result-list-view__filters {
    grid-template-columns: minmax(0, 1fr);
  }
}

.qc-record-result-list-view__filter-field,
.qc-record-result-list-view__date-field,
.qc-record-result-list-view__date-inputs {
  display: contents;
}
</style>
