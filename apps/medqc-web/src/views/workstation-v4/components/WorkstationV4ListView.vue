<template>
  <main class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
      <div class="mx-auto w-full max-w-[1440px]">
        <div class="workstation-surface-enter mb-4">
          <section class="wv4-analysis-overview">
            <div class="wv4-analysis-overview__header">
              <div>
                <div class="wv4-analysis-overview__eyebrow">
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
                  class="wv4-stage-context mt-2 inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700"
                >
                  <span class="h-1.5 w-1.5 rounded-full bg-sky-500" />
                  当前阶段：参考首页生成
                </div>
              </div>
              <div class="wv4-analysis-overview__actions">
                <a-button
                  size="small"
                  class="wv4-analysis-overview__action"
                  @click="emit('clear-filters')"
                >
                  重置
                </a-button>
                <a-button
                  size="small"
                  class="wv4-analysis-overview__action"
                  data-testid="qc-agent-entry"
                  @click="qcAgentOpen = true"
                >
                  质控助手
                </a-button>
                <a-button
                  v-if="isFrontpageGenerateStage"
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

            <div class="wv4-analysis-kpis">
              <article
                v-for="card in kpiCards"
                :key="card.key"
                class="wv4-analysis-kpi-card"
              >
                <div class="wv4-analysis-kpi-card__label">
                  {{ card.label }}
                </div>
                <div class="wv4-analysis-kpi-card__value">
                  {{ card.value }}
                </div>
                <div class="wv4-analysis-kpi-card__desc">
                  {{ card.desc }}
                </div>
              </article>
            </div>
          </section>
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

        <div
          v-if="!isFrontpageGenerateStage"
          class="workstation-surface-enter"
        >
          <PriorityLane
            :active-group="activePriorityGroup"
            class="mb-4"
            :groups="priorityGroups"
            :cards="priorityCardsFiltered"
            :readonly="isStageQueueMode"
            @update:active-group="emit('update:activePriorityGroup', $event)"
            @open-record="emit('priority-open', $event)"
            @defer-record="emit('priority-defer', $event)"
          />
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-1 mb-4">
          <div class="workstation-panel workstation-panel--filters">
            <div class="relative workbench-hero">
              <div class="workbench-controls-panel">
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

                  <a-select
                    v-if="!isStageQueueMode"
                    :value="dateField"
                    class="workbench-date-row__field"
                    size="large"
                    @update:value="emit('update:dateField', normalizeDateField($event))"
                  >
                    <a-select-option value="visit">
                      入/出院日期
                    </a-select-option>
                    <a-select-option value="admission">
                      入院日期
                    </a-select-option>
                    <a-select-option value="discharge">
                      出院日期
                    </a-select-option>
                    <a-select-option value="updated">
                      更新时间
                    </a-select-option>
                  </a-select>
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
                    <a-button
                      size="small"
                      class="wv4-filter-actions__button"
                      @click="emit('page-change', currentPage)"
                    >
                      刷新
                    </a-button>
                  </div>
                </div>

                <div class="workbench-dept-row">
                  <div class="workbench-filter-summary">
                    {{ tableSummaryText }}
                  </div>
                  <div class="workbench-dept-row__list">
                    <button
                      v-for="dept in quickDepartments"
                      :key="dept.name"
                      type="button"
                      :class="[
                        'workbench-dept-chip',
                        activeDept === dept.name
                          ? 'workbench-dept-chip--active'
                          : 'workbench-dept-chip--idle',
                      ]"
                      @click="emit('selectDept', dept.name)"
                    >
                      <span>{{ dept.name }}</span>
                      <span class="workbench-dept-chip__count">{{ dept.total }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-2 mb-4">
          <div class="wv4-analysis-split">
            <a-card
              size="small"
              :bordered="false"
              class="wv4-analysis-split__left"
            >
              <template #title>
                <span class="wv4-analysis-card__title">趋势与分布</span>
              </template>
              <a-tabs
                v-model:active-key="analysisTab"
                size="small"
                class="wv4-analysis-tabs"
              >
                <a-tab-pane
                  key="stage"
                  tab="阶段分布"
                >
                  <div class="space-y-3">
                    <div
                      v-for="item in stageDistribution"
                      :key="`stage-${item.label}`"
                    >
                      <div class="mb-1.5 flex items-center justify-between text-xs">
                        <span class="font-medium text-slate-600">{{ item.label }}</span>
                        <span class="font-semibold text-slate-700">{{ item.count }}</span>
                      </div>
                      <a-progress
                        :percent="item.percent"
                        :show-info="false"
                        :stroke-color="item.color"
                        size="small"
                      />
                    </div>
                  </div>
                </a-tab-pane>
                <a-tab-pane
                  key="workflow"
                  :tab="analysisSecondaryTabLabel"
                >
                  <div class="space-y-3">
                    <div
                      v-for="item in workflowLoad"
                      :key="`workflow-${item.label}`"
                    >
                      <div class="mb-1.5 flex items-center justify-between text-xs">
                        <span class="font-medium text-slate-600">{{ item.label }}</span>
                        <span class="font-semibold text-slate-700">{{ item.count }}</span>
                      </div>
                      <a-progress
                        :percent="item.percent"
                        :show-info="false"
                        stroke-color="#2563eb"
                        size="small"
                      />
                    </div>
                  </div>
                </a-tab-pane>
              </a-tabs>
            </a-card>

            <a-card
              size="small"
              :bordered="false"
              class="wv4-analysis-split__right"
            >
              <template #title>
                <span class="wv4-analysis-card__title">排行洞察</span>
              </template>
              <div class="space-y-4">
                <div>
                  <div class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {{ departmentRankingTitle }}
                  </div>
                  <ol class="space-y-2">
                    <li
                      v-for="(item, index) in departmentRanking"
                      :key="`dept-rank-${item.label}`"
                      class="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
                    >
                      <span class="truncate text-sm text-slate-700">{{ index + 1 }}. {{ item.label }}</span>
                      <span class="text-sm font-bold text-slate-800">{{ item.count }}</span>
                    </li>
                  </ol>
                </div>

                <div>
                  <div class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {{ secondaryRankingTitle }}
                  </div>
                  <ol class="space-y-2">
                    <li
                      v-for="item in secondaryRankingData"
                      :key="`secondary-rank-${item.label}`"
                      class="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
                    >
                      <span class="truncate text-sm text-slate-700">{{ item.label }}</span>
                      <span class="text-sm font-bold text-blue-700">{{ item.count }}</span>
                    </li>
                  </ol>
                </div>
              </div>
            </a-card>
          </div>
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-2">
          <BatchTablePanel
            :rows="workbenchRows"
            :selected-row-keys="selectedWorkbenchKeys"
            :summary-text="tableSummaryText"
            :current-page="currentPage"
            :page-size="pageSize"
            :total="displayServerTotal"
            :loading="displayLoading"
            :primary-action-label="stageMeta.batchActionText"
            :row-action-label="stageMeta.singleActionText"
            :show-primary-action="isStageQueueMode"
            :show-defer-action="false"
            :show-assign-action="false"
            @update:selected-row-keys="emit('update:selectedRowKeys', $event)"
            @open-record="emit('open-record', $event)"
            @batch-extract="emit('batch-extract', $event)"
            @batch-defer="emit('batch-defer', $event)"
            @batch-assign="emit('batch-assign', $event)"
            @clear-filters="emit('clear-filters')"
            @page-change="handleBatchPageChange"
          />
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
    <QCAgentChatDrawer
      v-model:open="qcAgentOpen"
      :user-context="qcAgentUserContext"
      :context-label="qcAgentContextLabel"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { InboxOutlined, SearchOutlined } from '@ant-design/icons-vue'

import PriorityLane, { type PriorityCard, type PriorityGroup } from './workbench/PriorityLane.vue'
import BatchTablePanel, { type WorkbenchRow } from './workbench/BatchTablePanel.vue'
import FrontpageTenderValidationDrawer from './FrontpageTenderValidationDrawer.vue'
import QCAgentChatDrawer from './QCAgentChatDrawer.vue'
import type { QCAgentUserContext } from '@/api/qcAgent'
import type { DeptInfo } from '../types'
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
  workbenchRows: WorkbenchRow[]
  selectedWorkbenchKeys: string[]
  tableSummaryText: string
  displayLoading: boolean
  stageMeta: StageMetaLike
  currentStageFilter?: WorkflowStageKey | ''
  listRecords: unknown[]
  stageEmptyText: string
  displayServerTotalPages: number
  currentPage: number
  pageSize: number
  displayServerTotal: number
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
  'open-record': [recordId: string]
  'batch-extract': [keys: string[]]
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

function normalizeDateField(value: unknown): WorkstationDateField {
  if (value === 'admission' || value === 'discharge' || value === 'updated') {
    return value
  }
  return 'visit'
}

function normalizeDepartmentValue(value: unknown): string {
  return String(value || '全部科室').trim() || '全部科室'
}

function filterDepartmentSelectOption(
  input: string,
  option?: { value?: unknown; label?: unknown },
) {
  return filterDepartmentOption(input, option)
}

const analysisTab = ref<'stage' | 'workflow'>('stage')
const tenderValidationOpen = ref(false)
const qcAgentOpen = ref(false)

const isFrontpageGenerateStage = computed(() => props.currentStageFilter === 'frontpage_generate')

const selectedSingleWorkbenchRow = computed(() => {
  if (props.selectedWorkbenchKeys.length !== 1) return null
  const selectedId = props.selectedWorkbenchKeys[0]
  return props.workbenchRows.find((row) => row.id === selectedId) || null
})

const qcAgentUserContext = computed<QCAgentUserContext>(() => {
  const row = selectedSingleWorkbenchRow.value
  if (!row) return {}
  return {
    visit_id: row.visitId,
    name: row.patientName,
    patient_name: row.patientName,
    department: row.department,
  }
})

const qcAgentContextLabel = computed(() => {
  const row = selectedSingleWorkbenchRow.value
  if (row) return `${row.patientName} / ${row.department} / visit_id=${row.visitId}`
  if (props.selectedWorkbenchKeys.length > 1)
    return '已选择多份病历；质控助手本轮仅支持单病历，请输入明确 visit_id'
  return '请输入 visit_id、住院号、姓名或科室'
})

const overviewEyebrow = computed(() =>
  isFrontpageGenerateStage.value ? 'Workstation / Frontpage Generate' : 'Workstation / Analysis',
)

const overviewTitle = computed(() =>
  isFrontpageGenerateStage.value
    ? props.stageMeta.pageTitle || '参考首页生成队列'
    : '质控工作台总览',
)

const overviewSubtitle = computed(() =>
  isFrontpageGenerateStage.value
    ? props.stageMeta.pageDesc || '对待生成病历进行批量生成和阻塞清理，不影响正式首页数据。'
    : '以分析视图汇总当前筛选结果，快速定位高风险与处理优先级',
)

const searchPlaceholder = computed(() =>
  isFrontpageGenerateStage.value
    ? '搜索病案号、姓名、住院号、生成状态'
    : '搜索病案号、姓名、住院号',
)

const totalRows = computed(() =>
  props.displayServerTotal > 0 ? props.displayServerTotal : props.workbenchRows.length,
)

const pendingGenerateCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(待生成|待处理|pending)/i.test(row.stageStatus)).length,
)

const generatingCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(生成中|处理中|running)/i.test(row.stageStatus)).length,
)

const generatedCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(已生成|完成|成功|succeeded)/i.test(row.stageStatus))
      .length,
)

const failedGenerateCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(失败|异常|错误|failed)/i.test(row.stageStatus)).length,
)

const failedRate = computed(() => {
  if (totalRows.value <= 0) return 0
  return Math.round((failedGenerateCount.value / totalRows.value) * 100)
})

const highRiskCount = computed(
  () =>
    props.workbenchRows.filter((row) => /(高风险|严重|缺失|超时|失败|异常)/.test(row.riskReason))
      .length,
)

const inProgressCount = computed(
  () =>
    props.workbenchRows.filter((row) =>
      /(处理中|进行中|待处理|待审核|待复核|抽取)/.test(row.stageStatus),
    ).length,
)

const completedCount = computed(
  () => props.workbenchRows.filter((row) => /(完成|已完成|终末|通过)/.test(row.stageStatus)).length,
)

const completionRate = computed(() => {
  if (totalRows.value <= 0) return 0
  return Math.round((completedCount.value / totalRows.value) * 100)
})

const kpiCards = computed(() =>
  isFrontpageGenerateStage.value
    ? [
        {
          key: 'total',
          label: '待生成总量',
          value: totalRows.value,
          desc: '当前筛选范围内病历总数',
        },
        {
          key: 'pending',
          label: '待生成',
          value: pendingGenerateCount.value,
          desc: '尚未启动生成任务',
        },
        {
          key: 'running',
          label: '生成中',
          value: generatingCount.value,
          desc: '后台任务执行中',
        },
        {
          key: 'failed-rate',
          label: '失败占比',
          value: `${failedRate.value}%`,
          desc: '需优先排查失败病历',
        },
      ]
    : [
        {
          key: 'total',
          label: '当前任务总量',
          value: totalRows.value,
          desc: '当前筛选范围内病历总数',
        },
        {
          key: 'risk',
          label: '高风险任务',
          value: highRiskCount.value,
          desc: '优先建议立即处理',
        },
        {
          key: 'progress',
          label: '处理中',
          value: inProgressCount.value,
          desc: '正在执行中的任务',
        },
        {
          key: 'rate',
          label: '完成率',
          value: `${completionRate.value}%`,
          desc: '按阶段状态估算闭环率',
        },
      ],
)

const stageDistribution = computed(() => {
  const palette = ['#2563eb', '#0ea5e9', '#10b981', '#f59e0b', '#f43f5e']
  const total = Math.max(props.workbenchRows.length, 1)
  const map = new Map<string, number>()

  for (const row of props.workbenchRows) {
    const key = row.stageStatus || '未标注'
    map.set(key, (map.get(key) || 0) + 1)
  }

  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count], index) => ({
      label,
      count,
      percent: Math.round((count / total) * 100),
      color: palette[index % palette.length],
    }))
})

const workflowLoad = computed(() => {
  const total = Math.max(props.workbenchRows.length, 1)
  const map = new Map<string, number>()

  if (isFrontpageGenerateStage.value) {
    const statusGroups = [
      { label: '待生成', count: pendingGenerateCount.value },
      { label: '生成中', count: generatingCount.value },
      { label: '已生成', count: generatedCount.value },
      { label: '生成失败', count: failedGenerateCount.value },
    ]
    return statusGroups
      .filter((item) => item.count > 0)
      .map((item) => ({
        label: item.label,
        count: item.count,
        percent: Math.round((item.count / total) * 100),
      }))
  }

  const detectWorkflow = (row: WorkbenchRow) => {
    const text = `${row.riskReason} ${row.stageStatus}`
    if (/(编码|icd|drg)/i.test(text)) return '编码质控'
    if (/(首页|frontpage)/i.test(text)) return '首页质控'
    if (/(结算|费用|settlement)/i.test(text)) return '结算质控'
    return '综合质控'
  }

  for (const row of props.workbenchRows) {
    const key = detectWorkflow(row)
    map.set(key, (map.get(key) || 0) + 1)
  }

  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({
      label,
      count,
      percent: Math.round((count / total) * 100),
    }))
})

const departmentRanking = computed(() => {
  const map = new Map<string, number>()
  for (const row of props.workbenchRows) {
    const key = row.department || '未分科室'
    map.set(key, (map.get(key) || 0) + 1)
  }
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({ label, count }))
})

const frontpageRiskRanking = computed(() => {
  const map = new Map<string, number>()
  for (const row of props.workbenchRows) {
    const key = row.riskReason || '其他生成阻塞'
    map.set(key, (map.get(key) || 0) + 1)
  }
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({ label, count }))
})

const priorityGroupRanking = computed(() =>
  [...props.priorityGroups]
    .map((group) => ({ label: group.label, count: Number(group.count || 0) }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5),
)

const analysisSecondaryTabLabel = computed(() =>
  isFrontpageGenerateStage.value ? '生成状态占比' : '工作流负载',
)

const departmentRankingTitle = computed(() =>
  isFrontpageGenerateStage.value ? '待生成科室排行' : '科室风险排行',
)

const secondaryRankingTitle = computed(() =>
  isFrontpageGenerateStage.value ? '生成阻塞原因 TopN' : '优先池分组',
)

const secondaryRankingData = computed(() =>
  isFrontpageGenerateStage.value ? frontpageRiskRanking.value : priorityGroupRanking.value,
)
</script>
