<template>
  <main class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
      <div class="mx-auto w-full max-w-[1440px]">
        <div class="workstation-surface-enter mb-4">
          <section class="wv4-analysis-overview wv4-record-pool-hero">
            <div class="wv4-analysis-overview__header">
              <div>
                <div
                  v-if="isFrontpageGenerateStage"
                  class="wv4-analysis-overview__eyebrow"
                >
                  {{ overviewEyebrow }}
                </div>
                <h3 class="wv4-analysis-overview__title">
                  {{ overviewTitle }}
                </h3>
                <p class="wv4-analysis-overview__subtitle">
                  {{ overviewSubtitle }}
                </p>
                <div
                  v-if="isFrontpageGenerateStage"
                  class="wv4-stage-context mt-2 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold"
                >
                  <span class="h-1.5 w-1.5 rounded-full" />
                  当前阶段：参考首页生成
                </div>
              </div>
              <div
                v-if="isFrontpageGenerateStage"
                class="wv4-analysis-overview__actions"
              >
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

                <a-range-picker
                  v-if="!isStageQueueMode"
                  :value="dateRange || undefined"
                  class="workbench-date-row__range"
                  size="large"
                  allow-clear
                  value-format="YYYY-MM-DD"
                  format="YYYY-MM-DD"
                  @update:value="emit('update:dateRange', normalizeDateRange($event))"
                />

                <a-select
                  v-if="!isStageQueueMode"
                  :value="hospFilter"
                  class="workbench-hosp-select"
                  size="large"
                  @update:value="emit('selectHospFilter', normalizeHospFilterValue($event))"
                >
                  <a-select-option
                    v-for="option in hospOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </a-select-option>
                </a-select>

                <a-select
                  :value="activeDept"
                  class="workbench-dept-select"
                  size="large"
                  show-search
                  :filter-option="filterDepartmentSelectOption"
                  @update:value="emit('selectDept', normalizeDepartmentValue($event))"
                >
                  <a-select-option
                    v-for="dept in departmentSelectOptions"
                    :key="dept.name"
                    :value="dept.name"
                  >
                    <span class="workbench-dept-select__option">
                      <span class="workbench-dept-select__name">{{ dept.name }}</span>
                      <span class="workbench-dept-select__count">{{ dept.total }}</span>
                    </span>
                  </a-select-option>
                </a-select>

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
              <div
                v-if="!isStageQueueMode"
                class="wv4-record-pool-filter__notice"
              >
                在院、已出院均按服务端病历范围筛选。
              </div>
            </div>

            <div
              v-if="isFrontpageGenerateStage"
              class="wv4-analysis-kpis"
            >
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

        <div
          v-if="isFrontpageGenerateStage"
          class="workstation-surface-enter mb-4"
        >
          <section class="wv4-stage-notice">
            <div class="wv4-stage-notice__title">
              生成指引
            </div>
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
                <template
                  v-if="recordPoolQcTask && !isStageQueueMode"
                  #task-status
                >
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
  CheckCircleOutlined,
  FileTextOutlined,
  InboxOutlined,
  SearchOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'

import BatchTablePanel, { type WorkbenchRow } from './workbench/BatchTablePanel.vue'
import RecordPoolQcTaskStatusBar from './workbench/RecordPoolQcTaskStatusBar.vue'
import FrontpageTenderValidationDrawer from './FrontpageTenderValidationDrawer.vue'
import type { SichuanBatchJob } from '../semantic-rules/types'
import type { PriorityCard, PriorityGroup } from './workbench/PriorityLane.vue'
import type { DeptInfo, RecordPoolQcSummary } from '../types'
import type { WorkflowStageKey } from '@/types/workflow'
import type { WorkstationDateField, WorkstationDateRange } from '../composables/usePatientRecords'
import { filterDepartmentOption } from '../utils/workstationFilterPresentation'

interface StageMetaLike {
  pageTitle?: string
  pageDesc?: string
  tableTitle?: string
  batchActionText: string
  singleActionText: string
}

type HospFilterValue = 'all' | 'inpatient' | 'discharged'

interface HospFilterOption {
  value: string
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
  quickDepartments: DeptInfo[]
  activeDept: string
  hospFilter: string
  hospOptions: HospFilterOption[]
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
  selectHospFilter: [value: HospFilterValue]
  'open-record': [recordId: string]
  'batch-extract': [keys: string[]]
  'filter-qc': []
  'dismiss-qc-task': []
  'batch-defer': [keys: string[]]
  'batch-assign': [keys: string[]]
  'clear-filters': []
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

function normalizeHospFilterValue(value: unknown): HospFilterValue {
  const normalized = String(value || 'all').trim()
  return normalized === 'inpatient' || normalized === 'discharged' ? normalized : 'all'
}

function filterDepartmentSelectOption(
  input: string,
  option?: { value?: unknown; label?: unknown },
) {
  return filterDepartmentOption(input, option)
}

const tenderValidationOpen = ref(false)

const isFrontpageGenerateStage = computed(() => props.currentStageFilter === 'frontpage_generate')

const overviewEyebrow = computed(() =>
  isFrontpageGenerateStage.value ? 'Workstation / Frontpage Generate' : 'Workstation / Record Pool',
)

const overviewTitle = computed(() =>
  isFrontpageGenerateStage.value ? props.stageMeta.pageTitle || '参考首页生成队列' : '病历池',
)

const overviewSubtitle = computed(() =>
  isFrontpageGenerateStage.value
    ? props.stageMeta.pageDesc || '对待生成病历进行批量生成和阻塞清理，不影响正式首页数据。'
    : '用于筛选病例并发起质控；质控结果请在运行病历质控或终末病历质控中查看。',
)

const searchPlaceholder = computed(() =>
  isFrontpageGenerateStage.value ? '搜索病案号、姓名、住院号、生成状态' : '搜索患者、住院号、科室',
)

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
