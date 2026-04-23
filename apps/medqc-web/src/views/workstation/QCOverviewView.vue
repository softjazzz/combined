<template>
  <div
    class="workstation-shell min-h-[calc(100vh-64px)] bg-[linear-gradient(180deg,#f8fafc_0%,#f1f5f9_46%,#edf2f7_100%)]"
  >
    <div class="custom-scrollbar h-[calc(100vh-64px)] overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
      <div class="mx-auto w-full max-w-[1440px]">
        <div class="workstation-surface-enter mb-4">
          <section class="wv4-analysis-overview">
            <div class="wv4-analysis-overview__header">
              <div>
                <div class="wv4-analysis-overview__eyebrow">
                  Dashboard / Analysis
                </div>
                <h3 class="wv4-analysis-overview__title">
                  质控首页概览
                </h3>
                <p class="wv4-analysis-overview__subtitle">
                  对当日任务做风险聚合与优先级排序，保持处理节奏和闭环效率
                </p>
              </div>
              <div class="wv4-analysis-overview__actions">
                <a-button
                  type="primary"
                  size="small"
                  class="wv4-analysis-overview__action"
                  :loading="loading"
                  @click="void handleQuery()"
                >
                  查询
                </a-button>
                <a-button
                  size="small"
                  class="wv4-analysis-overview__action"
                  :disabled="loading"
                  @click="void handleReset()"
                >
                  重置
                </a-button>
                <a-button
                  size="small"
                  class="wv4-analysis-overview__action"
                  :loading="loading"
                  @click="void fetchHome()"
                >
                  刷新
                </a-button>
              </div>
            </div>

            <div class="wv4-analysis-overview__controls">
              <HomeHeroBar
                v-model:keyword="keyword"
                v-model:selected-date="selectedDate"
                v-model:department-filter="departmentFilter"
                v-model:workflow-filter="workflowFilter"
                :department-options="departmentOptions"
                :loading="loading"
                :disabled-future-date="disabledFutureDate"
                :show-refresh="false"
                @refresh="void fetchHome()"
              />
            </div>
          </section>
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-1 mb-4">
          <div class="wv4-analysis-kpis">
            <article
              v-for="card in kpiCards"
              :key="card.key"
              :class="['wv4-analysis-kpi-card', `wv4-analysis-kpi-card--${card.tone}`]"
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
                  tab="状态分布"
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
                  tab="流程负载"
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
                    科室风险排行
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
                    风险原因 TopN
                  </div>
                  <ol class="space-y-2">
                    <li
                      v-for="item in riskReasonRanking"
                      :key="`risk-rank-${item.label}`"
                      class="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
                    >
                      <span class="truncate text-sm text-slate-700">{{ item.label }}</span>
                      <span class="text-sm font-bold text-blue-700">{{ item.count }}</span>
                    </li>
                  </ol>
                </div>

                <div>
                  <div class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    优先组别
                  </div>
                  <ol class="space-y-2">
                    <li
                      v-for="item in priorityRanking"
                      :key="`priority-rank-${item.label}`"
                      class="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
                    >
                      <span class="truncate text-sm text-slate-700">{{ item.label }}</span>
                      <span class="text-sm font-bold text-indigo-700">{{ item.count }}</span>
                    </li>
                  </ol>
                </div>
              </div>
            </a-card>
          </div>
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-2">
          <section class="wv4-analysis-list-panel">
            <div class="wv4-analysis-list-panel__head">
              <div>
                <h4 class="wv4-analysis-list-panel__title">
                  任务明细
                </h4>
                <p class="wv4-analysis-list-panel__subtitle">
                  当前筛选下共 {{ totalTaskCount }} 条任务
                </p>
              </div>
            </div>

            <div class="px-4 pt-3">
              <StatusBar
                :kpis="homeData.kpis"
                :active-key="activeStatusKey"
                @select="handleStatusSelect"
              />
            </div>

            <div class="min-h-[420px]">
              <UnifiedTaskList
                :tasks="unifiedTasks"
                :format-date-time="formatDateTime"
                @open="handleOpenTask"
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs, { type Dayjs } from 'dayjs'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'
import type { UnifiedTaskItem, WorkstationHomePayload } from '@/views/workstation-v2/types'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import HomeHeroBar from './components/HomeHeroBar.vue'
import StatusBar from './components/StatusBar.vue'
import UnifiedTaskList from './components/UnifiedTaskList.vue'

interface RankItem {
  label: string
  count: number
}

interface DistributionItem extends RankItem {
  percent: number
  color?: string
}

interface KpiCard {
  key: string
  label: string
  value: string | number
  desc: string
  tone: 'brand' | 'danger' | 'warning' | 'success'
}

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const selectedDate = ref<Dayjs>(dayjs())
const departmentFilter = ref('all')
const workflowFilter = ref('all')
const keyword = ref('')
const activeStatusKey = ref('')
const syncingFromRoute = ref(false)
const analysisTab = ref<'stage' | 'workflow'>('stage')

const homeData = ref<WorkstationHomePayload>({
  date: dayjs().format('YYYY-MM-DD'),
  kpis: {
    hotspot_total: 0,
    high_risk_total: 0,
    my_pending_total: 0,
    my_in_progress_total: 0,
    my_overdue_total: 0,
    batch_summary_total: 0,
  },
  hotspots: [],
  my_todo_summary: {
    pending_total: 0,
    in_progress_total: 0,
    overdue_total: 0,
    high_priority_total: 0,
  },
  my_todo_items: [],
  batch_summaries: [],
  department_options: [],
})

const departmentOptions = computed(() => homeData.value.department_options || [])

const unifiedTasks = computed<UnifiedTaskItem[]>(() => {
  const hotspotItems: UnifiedTaskItem[] = (homeData.value.hotspots || []).map((h) => ({
    id: `hotspot-${h.id}`,
    source_type: 'hotspot' as const,
    record_id: h.record_id,
    visit_id: h.visit_id,
    patient_name: h.patient_name,
    department: h.department,
    workflow_type: h.workflow_type,
    severity: h.severity,
    priority: h.severity === 'critical' ? 'critical' : h.severity === 'high' ? 'high' : 'normal',
    summary: h.summary,
    title: h.title,
    active_defect_count: h.active_defect_count,
    unread_count: h.unread_count,
    task_status: undefined,
    queue_status: h.queue_status,
    latest_qc_score: h.latest_qc_score,
    latest_qc_grade: h.latest_qc_grade,
    latest_created_at: h.latest_created_at,
    due_at: undefined,
    launch_action: h.launch_action,
    launch_stage: h.launch_stage,
  }))

  const todoItems: UnifiedTaskItem[] = (homeData.value.my_todo_items || []).map((t) => ({
    id: `todo-${t.id}`,
    source_type: 'todo' as const,
    record_id: t.record_id,
    visit_id: t.visit_id,
    patient_name: t.patient_name,
    department: t.department,
    workflow_type: t.workflow_type,
    severity: t.priority === 'critical' ? 'critical' : t.priority === 'high' ? 'high' : 'info',
    priority: t.priority,
    summary: t.summary,
    title: undefined,
    active_defect_count: t.active_defect_count,
    unread_count: 0,
    task_status: t.task_status,
    queue_status: t.queue_status,
    latest_qc_score: t.latest_qc_score,
    latest_qc_grade: t.latest_qc_grade,
    latest_created_at: undefined,
    due_at: t.due_at,
    launch_action: t.launch_action,
    launch_stage: t.launch_stage,
  }))

  const seen = new Set<string>()
  const result: UnifiedTaskItem[] = []
  for (const item of [...hotspotItems, ...todoItems]) {
    const key = `${item.record_id}__${item.workflow_type}`
    if (seen.has(key)) continue
    seen.add(key)
    result.push(item)
  }

  if (activeStatusKey.value === 'high_risk_total') {
    return result.filter((t) => {
      const severity = (t.severity || '').toLowerCase()
      return severity === 'critical' || severity === 'high'
    })
  }
  if (activeStatusKey.value === 'my_overdue_total') {
    return result.filter((t) => t.task_status === 'overdue')
  }
  if (activeStatusKey.value === 'my_in_progress_total') {
    return result.filter((t) => t.task_status === 'in_progress')
  }

  return result
})

const totalTaskCount = computed(() => unifiedTasks.value.length)

const highRiskTaskCount = computed(
  () =>
    unifiedTasks.value.filter((task) => {
      const severity = (task.severity || task.priority || '').toLowerCase()
      return severity === 'critical' || severity === 'high' || task.task_status === 'overdue'
    }).length,
)

const inProgressTaskCount = computed(
  () =>
    unifiedTasks.value.filter((task) => {
      const status = (task.task_status || '').toLowerCase()
      const queue = (task.queue_status || '').toLowerCase()
      return status === 'in_progress' || status === 'pending' || queue.includes('running')
    }).length,
)

const passRate = computed(() => {
  const gradedTasks = unifiedTasks.value.filter(
    (task) => typeof task.latest_qc_score === 'number' || !!task.latest_qc_grade,
  )
  if (gradedTasks.length > 0) {
    const passed = gradedTasks.filter((task) => {
      const scorePass = typeof task.latest_qc_score === 'number' && task.latest_qc_score >= 90
      const grade = (task.latest_qc_grade || '').toUpperCase()
      const gradePass = grade === 'A' || grade === 'B'
      return scorePass || gradePass
    }).length
    return Math.round((passed / gradedTasks.length) * 100)
  }
  if (totalTaskCount.value <= 0) return 0
  const riskRate = Math.round((highRiskTaskCount.value / totalTaskCount.value) * 100)
  return Math.max(0, 100 - riskRate)
})

const kpiCards = computed<KpiCard[]>(() => [
  {
    key: 'total',
    label: '任务总量',
    value: totalTaskCount.value,
    desc: '当前筛选范围的任务总数',
    tone: 'brand',
  },
  {
    key: 'risk',
    label: '高风险任务',
    value: highRiskTaskCount.value,
    desc: '优先建议立即处理',
    tone: 'danger',
  },
  {
    key: 'progress',
    label: '处理中',
    value: inProgressTaskCount.value,
    desc: '待办与执行中的任务',
    tone: 'warning',
  },
  {
    key: 'pass',
    label: '质控通过率',
    value: `${passRate.value}%`,
    desc: '按评分与等级估算',
    tone: 'success',
  },
])

const stageDistribution = computed<DistributionItem[]>(() => {
  const source = [
    { label: '待处理', count: Number(homeData.value.kpis.my_pending_total || 0), color: '#64748b' },
    {
      label: '进行中',
      count: Number(homeData.value.kpis.my_in_progress_total || 0),
      color: '#2563eb',
    },
    { label: '已超时', count: Number(homeData.value.kpis.my_overdue_total || 0), color: '#f59e0b' },
    { label: '高风险', count: Number(homeData.value.kpis.high_risk_total || 0), color: '#ef4444' },
  ]
  const total = Math.max(
    1,
    source.reduce((sum, item) => sum + item.count, 0),
  )
  return source.map((item) => ({
    ...item,
    percent: Math.round((item.count / total) * 100),
  }))
})

function resolveWorkflowLabel(workflowType: string | undefined): string {
  const value = (workflowType || '').toLowerCase()
  if (value.includes('coding') || value.includes('编码')) return '编码质控'
  if (value.includes('frontpage') || value.includes('首页')) return '首页质控'
  if (value.includes('settlement') || value.includes('结算')) return '结算质控'
  return '综合质控'
}

const workflowLoad = computed<DistributionItem[]>(() => {
  const map = new Map<string, number>()
  for (const task of unifiedTasks.value) {
    const key = resolveWorkflowLabel(task.workflow_type)
    map.set(key, (map.get(key) || 0) + 1)
  }
  const total = Math.max(1, unifiedTasks.value.length)
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({
      label,
      count,
      percent: Math.round((count / total) * 100),
    }))
})

const departmentRanking = computed<RankItem[]>(() => {
  const summary = homeData.value.team_summary?.department_risk_distribution
  if (summary?.length) {
    return summary
      .map((item) => ({
        label: item.department || '未分科室',
        count: Number(item.count || 0),
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
  }

  const map = new Map<string, number>()
  for (const task of unifiedTasks.value) {
    if (!task.department) continue
    map.set(task.department, (map.get(task.department) || 0) + 1)
  }
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({ label, count }))
})

function classifyRiskReason(task: UnifiedTaskItem): string {
  const text = `${task.title || ''} ${task.summary || ''}`
  if (/(编码|icd|drg)/i.test(text)) return '编码规范风险'
  if (/(首页|字段|漏填|缺失|主诊断|手术)/i.test(text)) return '首页完整性风险'
  if (/(结算|费用|医保|支付|清单)/i.test(text)) return '结算费用风险'
  if (/(超时|逾期|时效|截止)/i.test(text)) return '处理时效风险'
  return '其他质控风险'
}

const riskReasonRanking = computed<RankItem[]>(() => {
  const map = new Map<string, number>()
  for (const task of unifiedTasks.value) {
    const reason = classifyRiskReason(task)
    map.set(reason, (map.get(reason) || 0) + 1)
  }
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({ label, count }))
})

function resolvePriorityBucket(task: UnifiedTaskItem): string {
  const severity = (task.severity || task.priority || '').toLowerCase()
  if (task.task_status === 'overdue' || severity === 'critical') return 'P0 紧急'
  if (severity === 'high') return 'P1 高优先'
  if (task.task_status === 'in_progress' || task.task_status === 'pending') return 'P2 处理中'
  return 'P3 常规'
}

const priorityRanking = computed<RankItem[]>(() => {
  const map = new Map<string, number>()
  for (const task of unifiedTasks.value) {
    const bucket = resolvePriorityBucket(task)
    map.set(bucket, (map.get(bucket) || 0) + 1)
  }
  return [...map.entries()].sort((a, b) => b[1] - a[1]).map(([label, count]) => ({ label, count }))
})

function disabledFutureDate(current: Dayjs) {
  return current.isAfter(dayjs(), 'day')
}

function formatDateTime(value?: string | null) {
  if (!value) return '--'
  const parsed = dayjs(value)
  if (!parsed.isValid()) return String(value)
  return parsed.format('MM-DD HH:mm')
}

function handleStatusSelect(key: string) {
  activeStatusKey.value = activeStatusKey.value === key ? '' : key
}

function launchIntoWorklist(recordId: string, action?: string, fromStage?: string) {
  if (!recordId) {
    message.info('当前项未绑定具体病历')
    return
  }
  const detailTab =
    fromStage === 'frontpage_generate'
      ? 'records'
      : fromStage === 'settlement_qc'
        ? 'settlement'
        : fromStage === 'coding_qc' || fromStage === 'frontpage_qc'
          ? 'frontpage'
          : undefined
  router.push({
    path: '/workstation-v4',
    query: {
      source: 'dashboard',
      record_id: recordId,
      action: action as WorkstationLaunchAction,
      from_stage: fromStage as WorkflowStageKey,
      detail_tab: detailTab,
    },
  })
}

function handleOpenTask(task: UnifiedTaskItem) {
  launchIntoWorklist(task.record_id, task.launch_action, task.launch_stage)
}

function applyRouteFilters() {
  const queryDate =
    typeof route.query.date === 'string' ? route.query.date : dayjs().format('YYYY-MM-DD')
  const queryDepartment =
    typeof route.query.department === 'string' ? route.query.department : 'all'
  const queryWorkflow = typeof route.query.workflow === 'string' ? route.query.workflow : 'all'
  const queryKeyword = typeof route.query.keyword === 'string' ? route.query.keyword : ''

  syncingFromRoute.value = true
  selectedDate.value = dayjs(queryDate)
  departmentFilter.value = queryDepartment || 'all'
  workflowFilter.value = queryWorkflow || 'all'
  keyword.value = queryKeyword
  syncingFromRoute.value = false
}

function normalizeRouteValue(value: unknown): string | undefined {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    const first = value[0]
    return typeof first === 'string' ? first : undefined
  }
  return undefined
}

function buildNextQuery() {
  return {
    ...route.query,
    date: selectedDate.value.format('YYYY-MM-DD'),
    department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
    workflow: workflowFilter.value !== 'all' ? workflowFilter.value : undefined,
    keyword: keyword.value.trim() || undefined,
  }
}

function routeQueryChanged(nextQuery: ReturnType<typeof buildNextQuery>): boolean {
  const keys = new Set([...Object.keys(route.query), ...Object.keys(nextQuery)])
  for (const key of keys) {
    const current = normalizeRouteValue((route.query as Record<string, unknown>)[key])
    const next = normalizeRouteValue((nextQuery as Record<string, unknown>)[key])
    if (current !== next) return true
  }
  return false
}

async function syncFiltersToQuery() {
  const nextQuery = buildNextQuery()
  if (!routeQueryChanged(nextQuery)) {
    return false
  }
  await router.replace({ path: route.path, query: nextQuery })
  return true
}

async function handleQuery() {
  const changed = await syncFiltersToQuery()
  if (!changed) {
    await fetchHome()
  }
}

async function handleReset() {
  syncingFromRoute.value = true
  selectedDate.value = dayjs()
  departmentFilter.value = 'all'
  workflowFilter.value = 'all'
  keyword.value = ''
  activeStatusKey.value = ''
  syncingFromRoute.value = false

  const changed = await syncFiltersToQuery()
  if (!changed) {
    await fetchHome()
  }
}

async function fetchHome() {
  loading.value = true
  try {
    const res = await ApiService.get<WorkstationHomePayload>('/api/v1/workstation/home', {
      date: selectedDate.value.format('YYYY-MM-DD'),
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      severity: undefined,
      workflow_type: workflowFilter.value !== 'all' ? workflowFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
      hotspot_limit: 60,
      todo_limit: 30,
    })
    if (!res.success || !res.data) {
      throw new Error(String(res.error || '加载工作台首页失败'))
    }
    homeData.value = res.data
  } catch (error) {
    message.error('加载工作台首页失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    applyRouteFilters()
    void fetchHome()
  },
  { immediate: true },
)

watch(
  () => [
    selectedDate.value.format('YYYY-MM-DD'),
    departmentFilter.value,
    workflowFilter.value,
    keyword.value,
  ],
  () => {
    if (syncingFromRoute.value) return
    void syncFiltersToQuery()
  },
)
</script>

<style>
@import '../workstation-v4/styles/workstation-v4-view.css';
</style>
