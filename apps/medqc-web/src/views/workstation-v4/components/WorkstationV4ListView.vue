<template>
  <main
    class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden"
    :class="{ 'record-pool-refined': !isStageQueueMode }"
  >
    <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
      <div class="mx-auto w-full max-w-[1440px]">
        <div class="workstation-surface-enter mb-4">
          <section
            class="wv4-analysis-overview wv4-record-pool-hero"
            aria-labelledby="workstation-list-overview-title"
          >
            <div class="wv4-analysis-overview__header">
              <div>
                <div v-if="isFrontpageGenerateStage" class="wv4-analysis-overview__eyebrow">
                  {{ overviewEyebrow }}
                </div>
                <h3 id="workstation-list-overview-title" class="wv4-analysis-overview__title">
                  <span v-if="!isStageQueueMode" class="record-pool-title-icon"
                    ><FolderHeart :size="21" aria-hidden="true"
                  /></span>
                  {{ overviewTitle }}
                </h3>
                <p v-if="isStageQueueMode" class="wv4-analysis-overview__subtitle">
                  {{ overviewSubtitle }}
                </p>
                <div
                  v-if="isFrontpageGenerateStage"
                  class="wv4-stage-context mt-2 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold"
                >
                  <span class="h-1.5 w-1.5 rounded-full" />
                  当前阶段：参考首页生成
                </div>
                <div
                  v-if="drilldownScopeParts && drilldownScopeParts.length"
                  class="wv4-drilldown-context mt-2"
                  data-testid="workstation-drilldown-scope"
                >
                  <span class="wv4-drilldown-context__label">统计下钻范围</span>
                  <span
                    v-for="part in drilldownScopeParts"
                    :key="part"
                    class="wv4-drilldown-context__part"
                  >
                    {{ part }}
                  </span>
                  <button
                    type="button"
                    class="wv4-drilldown-context__clear"
                    data-testid="workstation-clear-drilldown"
                    @click="emit('clear-drilldown')"
                  >
                    清除下钻
                  </button>
                </div>
              </div>
              <div v-if="isFrontpageGenerateStage" class="wv4-analysis-overview__actions">
                <a-button
                  size="small"
                  class="wv4-analysis-overview__action"
                  data-testid="frontpage-tender-validation-entry"
                  @click="tenderValidationOpen = true"
                >
                  招标字段验证
                </a-button>
                <a-button
                  size="small"
                  class="wv4-analysis-overview__action"
                  @click="emit('page-change', currentPage)"
                >
                  刷新
                </a-button>
              </div>
            </div>

            <div class="wv4-analysis-overview__controls wv4-record-pool-filter">
              <div class="workbench-filter-toolbar">
                <a-input
                  :value="searchText"
                  class="workbench-controls__search-input"
                  :placeholder="searchPlaceholder"
                  size="large"
                  allow-clear
                  @update:value="emit('update:searchText', $event)"
                >
                  <template #prefix>
                    <SearchOutlined class="text-slate-400" />
                  </template>
                </a-input>

                <div
                  v-if="!isStageQueueMode"
                  class="record-pool-date-field"
                  role="group"
                  aria-labelledby="record-pool-date-label"
                >
                  <span id="record-pool-date-label" class="record-pool-field-label"
                    ><CalendarDays :size="15" aria-hidden="true" />{{
                      formatWorkstationDateFieldLabel(dateField)
                    }}</span
                  >
                  <a-range-picker
                    :value="dateRange || undefined"
                    class="workbench-date-row__range"
                    size="large"
                    allow-clear
                    value-format="YYYY-MM-DD"
                    format="YYYY-MM-DD"
                    :placeholder="['开始日期', '结束日期']"
                    @update:value="emit('update:dateRange', normalizeDateRange($event))"
                  />
                </div>

                <div
                  v-if="!isStageQueueMode"
                  class="workbench-hosp-filter"
                  role="group"
                  aria-label="住院状态筛选"
                >
                  <span class="workbench-hosp-filter__label">住院状态</span>
                  <a-segmented
                    :value="hospFilter"
                    :options="hospOptions"
                    class="workbench-hosp-segmented"
                    @update:value="emit('selectHospFilter', normalizeHospFilterValue($event))"
                  />
                  <a-button
                    :type="syncScope === 'today_inpatient' ? 'primary' : 'default'"
                    :loading="hospitalizationStatusVerifying"
                    :disabled="hospitalizationStatusVerifying"
                    class="wv4-record-pool-filter__sync-shortcut"
                    @click="emit('toggleTodayInpatient')"
                  >
                    <component
                      :is="syncScope === 'today_inpatient' ? BadgeCheck : ShieldCheck"
                      :size="15"
                      aria-hidden="true"
                      class="record-pool-verify-icon"
                    />
                    {{ syncScope === 'today_inpatient' ? '当日在院 · 已核验' : '核验当日在院' }}
                  </a-button>
                </div>

                <a-select
                  v-if="!isStageQueueMode && showInpatientSort"
                  :value="inpatientSort"
                  class="wv4-record-pool-filter__inpatient-sort"
                  size="large"
                  popup-class-name="wv4-record-pool-select-popup"
                  aria-label="在院病历排序"
                  @update:value="emit('selectInpatientSort', normalizeInpatientSort($event))"
                >
                  <a-select-option value="default"> 默认排序 </a-select-option>
                  <a-select-option value="longest"> 住院最久优先 </a-select-option>
                  <a-select-option value="recent"> 最近入院优先 </a-select-option>
                </a-select>
                <div class="workbench-dept-filter">
                  <span
                    v-if="!isStageQueueMode"
                    id="record-pool-dept-label"
                    class="record-pool-field-label"
                    ><Building2 :size="15" aria-hidden="true" />科室</span
                  >
                  <a-select
                    :aria-labelledby="!isStageQueueMode ? 'record-pool-dept-label' : undefined"
                    :value="activeDept"
                    class="workbench-dept-select"
                    size="large"
                    show-search
                    popup-class-name="wv4-record-pool-select-popup"
                    :filter-option="filterDepartmentSelectOption"
                    @update:value="emit('selectDept', normalizeDepartmentValue($event))"
                  >
                    <a-select-option
                      v-for="dept in departmentSelectOptions"
                      :key="dept.name"
                      :value="dept.name"
                      :label="dept.name"
                    >
                      <span class="workbench-dept-select__option">
                        <span class="workbench-dept-select__name">{{ dept.name }}</span>
                        <span v-if="isStageQueueMode" class="workbench-dept-select__count">{{
                          dept.total
                        }}</span>
                      </span>
                    </a-select-option>
                  </a-select>
                  <span
                    v-if="isStageQueueMode"
                    class="workbench-dept-filter__count"
                    :aria-label="`当前科室共 ${activeDepartmentTotal} 份病历`"
                  >
                    {{ activeDepartmentTotal }}
                  </span>
                </div>

                <div v-if="!isStageQueueMode" class="workbench-doctor-filter">
                  <span id="record-pool-doctor-label" class="record-pool-field-label"
                    ><Stethoscope :size="15" aria-hidden="true" />主管医师</span
                  >
                  <a-select
                    aria-labelledby="record-pool-doctor-label"
                    :value="activeDoctor"
                    class="workbench-doctor-select"
                    size="large"
                    show-search
                    popup-class-name="wv4-record-pool-select-popup"
                    :filter-option="filterDepartmentSelectOption"
                    @update:value="emit('selectDoctor', normalizeDoctorValue($event))"
                  >
                    <a-select-option
                      v-for="doctor in doctorSelectOptions"
                      :key="doctor.name"
                      :value="doctor.name"
                      :label="doctor.name"
                    >
                      <span class="workbench-dept-select__option">
                        <span class="workbench-dept-select__name">{{ doctor.name }}</span>
                      </span>
                    </a-select-option>
                  </a-select>
                </div>

                <div class="wv4-filter-actions">
                  <a-button
                    type="primary"
                    size="small"
                    class="wv4-filter-actions__button"
                    @click="emit('page-change', 1)"
                  >
                    查询
                  </a-button>
                  <a-button
                    size="small"
                    class="wv4-filter-actions__button"
                    @click="emit('clear-filters')"
                  >
                    重置
                  </a-button>
                </div>
              </div>
              <div class="workbench-filter-summary wv4-record-pool-filter__summary">
                {{ tableSummaryText }}
              </div>
            </div>

            <div v-if="isFrontpageGenerateStage" class="wv4-analysis-kpis">
              <article
                v-for="card in kpiCards"
                :key="card.key"
                :class="['wv4-analysis-kpi-card', `wv4-analysis-kpi-card--${card.tone}`]"
              >
                <div class="wv4-analysis-kpi-card__icon">
                  <component :is="card.icon" />
                </div>
                <div class="min-w-0">
                  <div class="wv4-analysis-kpi-card__label">
                    {{ card.label }}
                  </div>
                  <div class="wv4-analysis-kpi-card__value">
                    {{ card.value }}
                  </div>
                  <div class="wv4-analysis-kpi-card__desc">
                    {{ card.desc }}
                  </div>
                </div>
              </article>
            </div>
          </section>
        </div>

        <div
          v-if="loadError"
          class="workstation-empty-state mb-4 flex items-center gap-2 px-4 py-3 text-[13px]"
          role="alert"
        >
          病历池暂未加载成功，请检查网络后重试。
        </div>

        <div v-if="isFrontpageGenerateStage" class="workstation-surface-enter mb-4">
          <section class="wv4-stage-notice">
            <div class="wv4-stage-notice__title">生成指引</div>
            <div class="wv4-stage-notice__items">
              <span>优先处理“待生成 / 生成失败”病历，降低阻塞积压。</span>
              <span>批量生成后可在详情页复核草稿内容，不写入正式首页表。</span>
            </div>
          </section>
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-1">
          <div class="wv4-record-pool-main">
            <div class="wv4-record-pool-main__list">
              <BatchTablePanel
                :rows="workbenchRows"
                :selected-row-keys="selectedWorkbenchKeys"
                :summary-text="tableSummaryText"
                :current-page="currentPage"
                :page-size="pageSize"
                :total="displayServerTotal"
                :loading="displayLoading"
                :title="isStageQueueMode ? stageMeta.tableTitle || '批量工作台' : '病历池列表'"
                :primary-action-label="
                  isStageQueueMode
                    ? stageMeta.batchActionText
                    : `质控所选（${selectedWorkbenchKeys.length}）`
                "
                :primary-action-loading="batchActionLoading"
                :show-filter-qc-action="!isStageQueueMode"
                :filter-qc-count="qcSummary.totalRecords"
                :filter-qc-loading="batchActionLoading"
                :row-action-label="stageMeta.singleActionText"
                :show-primary-action="true"
                :show-selection="true"
                :record-pool-mode="!isStageQueueMode"
                :show-defer-action="false"
                :show-assign-action="false"
                @update:selected-row-keys="emit('update:selectedRowKeys', $event)"
                @open-record="emit('open-record', $event)"
                @batch-extract="emit('batch-extract', $event)"
                @filter-qc="emit('filter-qc')"
                @batch-defer="emit('batch-defer', $event)"
                @batch-assign="emit('batch-assign', $event)"
                @clear-filters="emit('clear-filters')"
                @page-change="handleBatchPageChange"
              >
                <template v-if="!isStageQueueMode" #toolbar-actions>
                  <RecordPoolQcTaskHistory />
                </template>
                <template v-if="recordPoolQcTask && !isStageQueueMode" #task-status>
                  <RecordPoolQcTaskStatusBar
                    :job="recordPoolQcTask"
                    @dismiss="emit('dismiss-qc-task')"
                  />
                </template>
              </BatchTablePanel>
            </div>
          </div>
        </div>

        <div
          v-if="listRecords.length === 0"
          class="workstation-empty-state mt-4 flex min-h-[160px] flex-col items-center justify-center px-5 py-10 text-center"
        >
          <InboxOutlined class="workstation-empty-state__icon mb-3 text-[36px]" />
          <div class="workstation-empty-state__text text-[13px] font-medium">
            {{ stageEmptyText }}
          </div>
        </div>
      </div>
    </div>
    <FrontpageTenderValidationDrawer v-model:open="tenderValidationOpen" />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  FolderHeart,
  Building2,
  Stethoscope,
  CalendarDays,
  ShieldCheck,
  BadgeCheck,
} from 'lucide-vue-next'
import {
  CheckCircleOutlined,
  FileTextOutlined,
  InboxOutlined,
  SearchOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'

import BatchTablePanel, { type WorkbenchRow } from './workbench/BatchTablePanel.vue'
import RecordPoolQcTaskHistory from './workbench/RecordPoolQcTaskHistory.vue'
import RecordPoolQcTaskStatusBar from './workbench/RecordPoolQcTaskStatusBar.vue'
import FrontpageTenderValidationDrawer from './FrontpageTenderValidationDrawer.vue'
import type { SichuanBatchJob } from '../semantic-rules/types'
import type { PriorityCard, PriorityGroup } from './workbench/PriorityLane.vue'
import type { DeptInfo, DoctorInfo, RecordPoolQcSummary } from '../types'
import type { WorkflowStageKey } from '@/types/workflow'
import type {
  InpatientSort,
  WorkstationDateField,
  WorkstationDateRange,
} from '../composables/usePatientRecords'
import {
  filterDepartmentOption,
  formatWorkstationDateFieldLabel,
} from '../utils/workstationFilterPresentation'

interface StageMetaLike {
  pageTitle?: string
  pageDesc?: string
  tableTitle?: string
  batchActionText: string
  singleActionText: string
}

type HospFilterValue = 'all' | 'inpatient' | 'discharged'

interface HospFilterOption {
  value: HospFilterValue
  label: string
}

const props = defineProps<{
  activePriorityGroup: string
  priorityGroups: PriorityGroup[]
  priorityCardsFiltered: PriorityCard[]
  isStageQueueMode: boolean
  searchText: string
  dateRange: WorkstationDateRange
  dateField: WorkstationDateField
  departmentSelectOptions: DeptInfo[]
  doctorSelectOptions: DoctorInfo[]
  quickDepartments: DeptInfo[]
  activeDept: string
  activeDoctor: string
  hospFilter: string
  hospOptions: HospFilterOption[]
  syncScope: 'all' | 'today_inpatient'
  inpatientSort: InpatientSort
  hospitalizationStatusVerifying: boolean
  workbenchRows: WorkbenchRow[]
  selectedWorkbenchKeys: string[]
  tableSummaryText: string
  displayLoading: boolean
  batchActionLoading: boolean
  stageMeta: StageMetaLike
  currentStageFilter?: WorkflowStageKey | ''
  listRecords: unknown[]
  stageEmptyText: string
  displayServerTotalPages: number
  currentPage: number
  pageSize: number
  displayServerTotal: number
  qcSummary: RecordPoolQcSummary
  recordPoolQcTask?: SichuanBatchJob | null
  loadError: boolean
  /** 来自统计分析等入口的下钻范围标签；为空表示当前不是下钻视图。 */
  drilldownScopeParts?: string[]
}>()

const emit = defineEmits<{
  'update:activePriorityGroup': [value: string]
  'update:searchText': [value: string]
  'update:dateRange': [value: WorkstationDateRange]
  'update:dateField': [value: WorkstationDateField]
  'update:selectedRowKeys': [keys: string[]]
  'priority-open': [recordId: string]
  'priority-defer': [recordId: string]
  selectDept: [deptName: string]
  selectDoctor: [doctorName: string]
  selectHospFilter: [value: HospFilterValue]
  selectInpatientSort: [value: InpatientSort]
  toggleTodayInpatient: []
  'open-record': [recordId: string]
  'batch-extract': [keys: string[]]
  'filter-qc': []
  'dismiss-qc-task': []
  'batch-defer': [keys: string[]]
  'batch-assign': [keys: string[]]
  'clear-filters': []
  'clear-drilldown': []
  'page-change': [page: number, pageSize?: number]
}>()

function handleBatchPageChange(page: number, pageSize?: number) {
  emit('page-change', page, pageSize)
}

function normalizeDateRange(value: unknown): WorkstationDateRange {
  if (!Array.isArray(value) || value.length < 2) return null
  const start = typeof value[0] === 'string' ? value[0] : ''
  const end = typeof value[1] === 'string' ? value[1] : ''
  return start && end ? [start, end] : null
}

function normalizeDepartmentValue(value: unknown): string {
  return String(value || '全部科室').trim() || '全部科室'
}

function normalizeDoctorValue(value: unknown): string {
  return String(value || '全部主管医师').trim() || '全部主管医师'
}

function normalizeHospFilterValue(value: unknown): HospFilterValue {
  const normalized = String(value || 'all').trim()
  return normalized === 'inpatient' || normalized === 'discharged' ? normalized : 'all'
}

function normalizeInpatientSort(value: unknown): InpatientSort {
  const normalized = String(value || 'default').trim()
  return normalized === 'longest' || normalized === 'recent' ? normalized : 'default'
}

function filterDepartmentSelectOption(
  input: string,
  option?: { value?: unknown; label?: unknown },
) {
  return filterDepartmentOption(input, option)
}

const tenderValidationOpen = ref(false)

const isFrontpageGenerateStage = computed(() => props.currentStageFilter === 'frontpage_generate')
const showInpatientSort = computed(
  () => props.hospFilter === 'inpatient' || props.syncScope === 'today_inpatient',
)

const overviewEyebrow = computed(() =>
  isFrontpageGenerateStage.value ? 'Workstation / Frontpage Generate' : 'Workstation / Record Pool',
)

const overviewTitle = computed(() =>
  isFrontpageGenerateStage.value ? props.stageMeta.pageTitle || '参考首页生成队列' : '病历池',
)

const overviewSubtitle = computed(() =>
  isFrontpageGenerateStage.value
    ? props.stageMeta.pageDesc || '对待生成病历进行批量生成和阻塞清理，不影响正式首页数据。'
    : '筛选病历，发起质控',
)

const searchPlaceholder = computed(() =>
  isFrontpageGenerateStage.value ? '搜索病案号、姓名、住院号、生成状态' : '搜索患者、住院号、科室',
)

const activeDepartmentTotal = computed(() => {
  const selected = props.departmentSelectOptions.find(
    (department) => department.name === props.activeDept,
  )
  return selected?.total ?? props.qcSummary.totalRecords
})

const totalRows = computed(() =>
  isFrontpageGenerateStage.value ? props.displayServerTotal : props.qcSummary.totalRecords,
)

const pendingGenerateCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(待生成|待处理|pending)/i.test(row.stageStatus)).length,
)

const generatingCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(生成中|处理中|running)/i.test(row.stageStatus)).length,
)

const failedGenerateCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(失败|异常|错误|failed)/i.test(row.stageStatus)).length,
)

const failedRate = computed(() => {
  if (totalRows.value <= 0) return 0
  return Math.round((failedGenerateCount.value / totalRows.value) * 100)
})

const kpiCards = computed(() => [
  {
    key: 'total',
    label: '待生成总量',
    value: totalRows.value,
    desc: '当前筛选范围内病历总数',
    icon: FileTextOutlined,
    tone: 'brand',
  },
  {
    key: 'pending',
    label: '待生成',
    value: pendingGenerateCount.value,
    desc: '尚未启动生成任务',
    icon: CheckCircleOutlined,
    tone: 'success',
  },
  {
    key: 'running',
    label: '生成中',
    value: generatingCount.value,
    desc: '后台任务执行中',
    icon: SyncOutlined,
    tone: 'info',
  },
  {
    key: 'failed-rate',
    label: '失败占比',
    value: `${failedRate.value}%`,
    desc: '需优先排查失败病历',
    icon: WarningOutlined,
    tone: 'warning',
  },
])
</script>

<style scoped>
@import '../styles/record-pool-refined.css';
</style>
