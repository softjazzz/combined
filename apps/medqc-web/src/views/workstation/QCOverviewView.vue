<template>
  <div class="qc-home-shell workstation-shell min-h-screen">
    <div class="custom-scrollbar h-screen overflow-y-auto px-5 py-8 xl:px-8">
      <div class="qc-home-canvas mx-auto w-full max-w-[1440px]">
        <section class="qc-home-hero workstation-surface-enter">
          <div class="qc-home-hero__header">
            <div class="qc-home-hero__main">
              <h2>质控首页概览</h2>
              <p>高风险、超时与待处理任务的实时汇总</p>
            </div>
            <div class="qc-home-topbar">
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
              <div class="qc-home-profile">
                <a-avatar :size="38">
                  <template #icon>
                    <UserOutlined />
                  </template>
                </a-avatar>
                <div>
                  <strong>张医生</strong>
                  <span>质控管理员</span>
                </div>
                <DownOutlined />
              </div>
            </div>
          </div>
        </section>

        <section class="qc-home-kpis workstation-surface-enter workstation-surface-enter--delay-1">
          <article
            v-for="card in kpiCards"
            :key="card.key"
            :class="['qc-home-kpi-card', `qc-home-kpi-card--${card.tone}`]"
          >
            <div class="qc-home-kpi-icon">
              <component :is="card.icon" />
            </div>
            <div class="qc-home-kpi-card__body">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <p>
                较昨日
                <em :class="card.deltaTone">{{ card.delta }}</em>
              </p>
            </div>
          </article>
        </section>

        <section
          class="qc-home-main-grid workstation-surface-enter workstation-surface-enter--delay-2"
        >
          <section class="qc-home-card qc-home-card--trend">
            <div class="qc-home-card__head">
              <div>
                <h3>质控态势趋势</h3>
              </div>
              <div class="qc-home-range-switch">
                <button type="button">
                  近7天
                </button>
                <button type="button">
                  近30天
                </button>
              </div>
            </div>

            <div class="qc-home-line-chart">
              <div class="qc-home-line-legend">
                <span><i class="qc-home-dot--blue" />待处理</span>
                <span><i class="qc-home-dot--red" />高风险</span>
                <span><i class="qc-home-dot--amber" />已超时</span>
                <span><i class="qc-home-dot--cyan" />处理中</span>
              </div>
              <svg
                viewBox="0 0 760 250"
                role="img"
                aria-label="质控态势趋势"
              >
                <defs>
                  <linearGradient
                    id="qcLineFill"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stop-color="#3b82f6"
                      stop-opacity="0.16"
                    />
                    <stop
                      offset="100%"
                      stop-color="#3b82f6"
                      stop-opacity="0"
                    />
                  </linearGradient>
                </defs>
                <g class="qc-home-grid-lines">
                  <line
                    v-for="y in [50, 95, 140, 185, 230]"
                    :key="y"
                    x1="42"
                    :y1="y"
                    x2="722"
                    :y2="y"
                  />
                </g>
                <path
                  d="M42 168 C122 148 168 154 240 128 C320 98 398 134 462 112 C540 86 606 82 722 56 L722 230 L42 230 Z"
                  fill="url(#qcLineFill)"
                />
                <path
                  d="M42 168 C122 148 168 154 240 128 C320 98 398 134 462 112 C540 86 606 82 722 56"
                  class="qc-home-series qc-home-series--blue"
                />
                <path
                  d="M42 194 C128 176 188 180 246 160 C320 136 392 166 466 148 C552 126 610 118 722 132"
                  class="qc-home-series qc-home-series--red"
                />
                <path
                  d="M42 214 C124 202 196 204 252 188 C318 168 388 194 462 184 C548 166 620 170 722 166"
                  class="qc-home-series qc-home-series--amber"
                />
                <path
                  d="M42 226 C128 214 196 216 258 204 C326 190 402 206 470 196 C560 182 622 188 722 180"
                  class="qc-home-series qc-home-series--cyan"
                />
                <g class="qc-home-axis-labels">
                  <text
                    v-for="(label, index) in trendAxisLabels"
                    :key="label"
                    :x="54 + index * 112"
                    y="248"
                  >
                    {{ label }}
                  </text>
                </g>
                <g class="qc-home-chart-values">
                  <circle
                    cx="722"
                    cy="56"
                    r="5"
                    fill="#3b82f6"
                  />
                  <text
                    x="738"
                    y="61"
                    fill="#2563eb"
                  >
                    {{ Number(homeData.kpis.my_pending_total || 0) }}
                  </text>
                  <circle
                    cx="722"
                    cy="132"
                    r="5"
                    fill="#ef4444"
                  />
                  <text
                    x="738"
                    y="137"
                    fill="#ef4444"
                  >{{ highRiskTaskCount }}</text>
                  <circle
                    cx="722"
                    cy="166"
                    r="5"
                    fill="#f59e0b"
                  />
                  <text
                    x="738"
                    y="171"
                    fill="#f59e0b"
                  >
                    {{ Number(homeData.kpis.my_overdue_total || 0) }}
                  </text>
                  <circle
                    cx="722"
                    cy="180"
                    r="5"
                    fill="#06b6d4"
                  />
                  <text
                    x="738"
                    y="185"
                    fill="#06b6d4"
                  >{{ inProgressTaskCount }}</text>
                </g>
              </svg>
            </div>
          </section>

          <section class="qc-home-card qc-home-card--insight">
            <div class="qc-home-card__head">
              <div>
                <h3>风险洞察</h3>
              </div>
              <a-tag color="processing">
                AI
              </a-tag>
            </div>

            <div class="qc-home-insight-layout">
              <div class="qc-home-insight-list">
                <div
                  v-for="item in riskReasonRanking.slice(0, 3)"
                  :key="`insight-${item.label}`"
                  class="qc-home-insight-row"
                >
                  <span>{{ item.label }}</span>
                  <small>风险占比 {{ insightPercent(item.count) }}%</small>
                  <RightOutlined />
                </div>
              </div>
              <div class="qc-home-medical-visual">
                <div class="qc-home-medical-orbit qc-home-medical-orbit--one" />
                <div class="qc-home-medical-orbit qc-home-medical-orbit--two" />
                <div class="qc-home-medical-core">
                  <MedicineBoxOutlined />
                </div>
              </div>
            </div>
          </section>
        </section>

        <section
          class="qc-home-task-panel workstation-surface-enter workstation-surface-enter--delay-2"
        >
          <div class="qc-home-task-panel__head">
            <div>
              <h3>{{ taskPanelTitle }}</h3>
            </div>
            <StatusBar
              :kpis="homeData.kpis"
              :active-key="activeStatusKey"
              @select="handleStatusSelect"
            />
          </div>

          <div class="qc-home-task-table">
            <div class="qc-home-task-table__head">
              <span>患者信息</span>
              <span>科室</span>
              <span>风险等级</span>
              <span>风险原因</span>
              <span>截止时间</span>
              <span>操作</span>
            </div>
            <UnifiedTaskList
              :tasks="taskListItems"
              :preview-limit="activeStatusKey ? undefined : 3"
              :format-date-time="formatDateTime"
              :empty-title="activeStatusKey ? '当前筛选无任务' : '当前无高优先级任务'"
              :empty-desc="
                activeStatusKey
                  ? '可以切换筛选条件或重置筛选后查看。'
                  : '今日暂未发现 P0/P1 风险任务。'
              "
              @open="handleOpenTask"
            />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs, { type Dayjs } from 'dayjs'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'
import type { UnifiedTaskItem, WorkstationHomePayload } from '@/views/workstation-v2/types'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import HomeHeroBar from './components/HomeHeroBar.vue'
import StatusBar from './components/StatusBar.vue'
import UnifiedTaskList from './components/UnifiedTaskList.vue'
import {
  ClockCircleOutlined,
  DownOutlined,
  FileDoneOutlined,
  MedicineBoxOutlined,
  RightOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'

interface RankItem {
  label: string
  count: number
}

interface KpiCard {
  key: string
  label: string
  value: string | number
  desc: string
  tone: 'brand' | 'danger' | 'warning' | 'success'
  icon: Component
  delta: string
  deltaTone: 'is-up' | 'is-down' | 'is-neutral'
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
const trendAxisLabels = computed(() =>
  Array.from({ length: 7 }, (_, index) =>
    dayjs(selectedDate.value)
      .subtract(6 - index, 'day')
      .format('MM-DD'),
  ),
)

const unifiedTasks = computed<UnifiedTaskItem[]>(() => {
  const hotspotItems: UnifiedTaskItem[] = (homeData.value.hotspots || []).map((h) => ({
    id: `hotspot-${h.id}`,
    source_type: 'hotspot' as const,
    record_id: h.record_id,
    visit_id: h.visit_id,
    patient_name: h.patient_name,
    patient_age: h.patient_age,
    patient_sex: h.patient_sex,
    patient_gender: h.patient_gender,
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
    patient_age: t.patient_age,
    patient_sex: t.patient_sex,
    patient_gender: t.patient_gender,
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

const kpiCards = computed<KpiCard[]>(() => [
  {
    key: 'pending',
    label: '待处理',
    value: Number(homeData.value.kpis.my_pending_total || 0),
    desc: '等待进入处理队列',
    tone: 'brand',
    icon: FileDoneOutlined,
    delta: '+12（10.3%）',
    deltaTone: 'is-up',
  },
  {
    key: 'risk',
    label: '高风险任务',
    value: highRiskTaskCount.value,
    desc: '建议优先复核',
    tone: 'danger',
    icon: ThunderboltOutlined,
    delta: '+5（16.1%）',
    deltaTone: 'is-up',
  },
  {
    key: 'overdue',
    label: '已超时',
    value: Number(homeData.value.kpis.my_overdue_total || 0),
    desc: '已超过处理时限',
    tone: 'warning',
    icon: ClockCircleOutlined,
    delta: '+3（20.0%）',
    deltaTone: 'is-up',
  },
  {
    key: 'progress',
    label: '处理中',
    value: inProgressTaskCount.value,
    desc: '正在推进闭环',
    tone: 'success',
    icon: SyncOutlined,
    delta: '-6（7.5%）',
    deltaTone: 'is-down',
  },
])

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

function insightPercent(count: number): number {
  if (highRiskTaskCount.value <= 0) return 0
  return Math.round((count / highRiskTaskCount.value) * 1000) / 10
}

function isHighPriorityTask(task: UnifiedTaskItem): boolean {
  const severity = (task.severity || task.priority || '').toLowerCase()
  return (
    task.task_status === 'overdue' ||
    severity === 'critical' ||
    severity === 'high' ||
    task.priority === 'critical' ||
    task.priority === 'high'
  )
}

const highPriorityTasks = computed(() => unifiedTasks.value.filter(isHighPriorityTask))
const taskListItems = computed(() =>
  activeStatusKey.value ? unifiedTasks.value : highPriorityTasks.value,
)
const taskPanelTitle = computed(() => (activeStatusKey.value ? '筛选任务' : '高优先级任务'))
const taskPanelSubtitle = computed(() => {
  if (activeStatusKey.value) {
    return `当前筛选下共 ${taskListItems.value.length} 条任务，支持继续按风险和时效聚焦。`
  }
  return `默认展示最需要处理的 ${Math.min(highPriorityTasks.value.length, 3)} 条任务，降低首屏干扰。`
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

.qc-home-shell {
  background: linear-gradient(180deg, #dcebea 0%, #f8fafc 46%, #edf3f7 100%);
}

.qc-home-canvas {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 30px;
  background: rgba(247, 250, 252, 0.78);
  box-shadow: 0 28px 64px rgba(15, 23, 42, 0.09);
  backdrop-filter: blur(20px);
}

.qc-home-hero,
.qc-home-card,
.qc-home-task-panel {
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 16px 38px rgba(15, 23, 42, 0.055);
}

.qc-home-hero {
  padding: 22px;
}

.qc-home-hero__header,
.qc-home-task-panel__head,
.qc-home-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.qc-home-hero__main {
  max-width: 560px;
}

.qc-home-eyebrow {
  display: inline-flex;
  align-items: center;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.qc-home-hero h2,
.qc-home-card h3,
.qc-home-task-panel h3 {
  margin: 0;
  color: #0f172a;
  font-weight: 850;
  letter-spacing: 0;
}

.qc-home-hero h2 {
  font-size: 30px;
  line-height: 1.16;
}

.qc-home-hero p,
.qc-home-task-panel p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
}

.qc-home-hero__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.qc-home-hero__meta {
  display: flex;
  min-width: 92px;
  flex-direction: column;
  align-items: flex-end;
  padding: 8px 12px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.82);
}

.qc-home-hero__meta span {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.qc-home-hero__meta strong {
  color: #0f172a;
  font-size: 20px;
  line-height: 1.1;
}

.qc-home-action-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.qc-home-action {
  height: 32px;
  border-radius: 999px;
  font-weight: 700;
}

.qc-home-filter-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 20px;
  padding: 12px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.74);
}

.qc-home-kpis {
  display: grid;
  grid-template-columns: minmax(280px, 1.35fr) repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.qc-home-kpi-card {
  min-height: 132px;
  padding: 18px 20px;
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.045);
}

.qc-home-kpi-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.qc-home-kpi-card__top i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #38bdf8;
  box-shadow: 0 0 0 5px rgba(56, 189, 248, 0.12);
}

.qc-home-kpi-card strong {
  display: block;
  margin-top: 18px;
  color: #0f172a;
  font-size: 34px;
  line-height: 1;
}

.qc-home-kpi-card p {
  margin: 10px 0 0;
  color: #94a3b8;
  font-size: 13px;
}

.qc-home-kpi-card--featured {
  border-color: rgba(45, 212, 191, 0.26);
  background: linear-gradient(135deg, #5dd7d0 0%, #18aaa7 58%, #0f766e 100%);
  box-shadow: 0 22px 42px rgba(20, 184, 166, 0.22);
}

.qc-home-kpi-card--featured .qc-home-kpi-card__top,
.qc-home-kpi-card--featured p {
  color: rgba(255, 255, 255, 0.78);
}

.qc-home-kpi-card--featured strong {
  color: #fff;
}

.qc-home-kpi-card--featured .qc-home-kpi-card__top i {
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 0 0 5px rgba(255, 255, 255, 0.16);
}

.qc-home-kpi-card--danger .qc-home-kpi-card__top i {
  background: #fb7185;
  box-shadow: 0 0 0 5px rgba(251, 113, 133, 0.12);
}

.qc-home-kpi-card--warning .qc-home-kpi-card__top i {
  background: #f59e0b;
  box-shadow: 0 0 0 5px rgba(245, 158, 11, 0.13);
}

.qc-home-kpi-card--success .qc-home-kpi-card__top i {
  background: #10b981;
  box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.12);
}

.qc-home-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.72fr);
  gap: 16px;
}

.qc-home-card {
  padding: 20px;
}

.qc-home-card--trend {
  min-height: 440px;
}

.qc-home-card h3,
.qc-home-task-panel h3 {
  font-size: 20px;
  line-height: 1.25;
}

.qc-home-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.qc-home-score strong {
  color: #0f172a;
  font-size: 28px;
  line-height: 1;
}

.qc-home-score span {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 700;
}

.qc-home-progress-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 22px;
  margin-top: 24px;
}

.qc-home-progress-row__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.qc-home-chart-shell {
  display: grid;
  grid-template-columns: minmax(180px, 0.58fr) minmax(0, 1fr);
  gap: 18px;
  min-height: 190px;
  margin-top: 22px;
  padding: 18px;
  border: 1px solid rgba(226, 232, 240, 0.82);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(255, 255, 255, 0.84));
}

.qc-home-chart-summary {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 14px;
}

.qc-home-chart-summary span {
  color: #64748b;
  font-size: 12px;
  font-weight: 850;
}

.qc-home-chart-summary strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 42px;
  line-height: 1;
}

.qc-home-chart-summary p {
  max-width: 210px;
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.65;
}

.qc-home-chart-plot {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: end;
  gap: 16px;
  min-height: 150px;
  padding-top: 14px;
}

.qc-home-chart-baseline {
  position: absolute;
  right: 0;
  bottom: 26px;
  left: 0;
  height: 1px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.08), rgba(148, 163, 184, 0.32));
}

.qc-home-chart-column {
  position: relative;
  z-index: 1;
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  gap: 9px;
}

.qc-home-chart-track {
  display: flex;
  width: 100%;
  height: 120px;
  align-items: end;
  justify-content: center;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(226, 232, 240, 0.28), rgba(226, 232, 240, 0.05));
}

.qc-home-chart-bar {
  width: min(54px, 58%);
  min-height: 12px;
  border-radius: 999px 999px 12px 12px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.55),
    0 12px 22px rgba(15, 23, 42, 0.1);
}

.qc-home-chart-column span {
  overflow: hidden;
  max-width: 100%;
  color: #64748b;
  font-size: 12px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-home-progress-row__meta strong {
  color: #0f172a;
}

.qc-home-workflow-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 24px;
}

.qc-home-workflow-item {
  min-height: 74px;
  padding: 13px;
  border: 1px solid rgba(226, 232, 240, 0.82);
  border-radius: 16px;
  background: #f8fafc;
}

.qc-home-workflow-item span {
  display: block;
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-home-workflow-item strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 22px;
  line-height: 1;
}

.qc-home-risk-summary {
  margin-top: 18px;
  padding: 18px;
  border: 1px solid rgba(186, 230, 253, 0.8);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(240, 249, 255, 0.95), rgba(255, 255, 255, 0.92));
}

.qc-home-risk-summary__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.qc-home-risk-summary__top > div:last-child {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-end;
}

.qc-home-risk-donut {
  display: grid;
  width: 112px;
  height: 112px;
  flex: none;
  place-items: center;
  border-radius: 999px;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.9),
    0 16px 26px rgba(14, 165, 233, 0.13);
}

.qc-home-risk-donut > div {
  display: grid;
  width: 76px;
  height: 76px;
  place-items: center;
  border-radius: 999px;
  background: #fff;
}

.qc-home-risk-donut strong {
  color: #0369a1;
  font-size: 24px;
  line-height: 1;
}

.qc-home-risk-donut span {
  margin-top: -20px;
  color: #94a3b8;
  font-size: 10px;
  font-weight: 850;
}

.qc-home-risk-summary span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.qc-home-risk-summary strong {
  color: #0369a1;
  font-size: 30px;
  line-height: 1;
}

.qc-home-risk-summary small {
  margin-top: 6px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 750;
}

.qc-home-risk-summary p {
  margin: 12px 0 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.7;
}

.qc-home-ranking-stack {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.qc-home-mini-title {
  margin-bottom: 9px;
  color: #64748b;
  font-size: 12px;
  font-weight: 850;
}

.qc-home-ranking-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.76);
}

.qc-home-ranking-row span {
  overflow: hidden;
  color: #475569;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-home-ranking-row strong {
  color: #0f172a;
  font-size: 14px;
}

.qc-home-task-panel {
  overflow: hidden;
}

.qc-home-task-panel__head {
  padding: 20px 22px 16px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.76);
}

.qc-home-shell {
  background: transparent;
}

.qc-home-canvas {
  min-height: calc(100vh - 64px);
  padding: 32px;
  border-radius: 0 18px 18px 0;
  background: rgba(255, 255, 255, 0.62);
}

.qc-home-hero {
  padding: 0 2px 4px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.qc-home-hero__header {
  align-items: center;
}

.qc-home-hero__main h2 {
  font-size: 30px;
}

.qc-home-topbar {
  display: flex;
  min-width: 680px;
  align-items: center;
  justify-content: flex-end;
  gap: 18px;
}

.qc-home-topbar > .flex:first-child {
  max-width: 690px;
}

.qc-home-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 148px;
  color: #334155;
}

.qc-home-profile .ant-avatar {
  background: linear-gradient(135deg, #dbeafe, #eff6ff);
  color: #2563eb;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.12);
}

.qc-home-profile strong,
.qc-home-profile span {
  display: block;
  white-space: nowrap;
}

.qc-home-profile strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.1;
}

.qc-home-profile span {
  margin-top: 3px;
  color: #64748b;
  font-size: 11px;
}

.qc-home-kpis {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.qc-home-kpi-card {
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr);
  align-items: center;
  min-height: 132px;
  padding: 24px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 18px 42px rgba(42, 82, 128, 0.08);
}

.qc-home-kpi-icon {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  border-radius: 999px;
  background: #eef6ff;
  color: #2563eb;
  font-size: 28px;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.qc-home-kpi-card--danger .qc-home-kpi-icon {
  background: #fff1f2;
  color: #ef4444;
}

.qc-home-kpi-card--warning .qc-home-kpi-icon {
  background: #fff7ed;
  color: #f59e0b;
}

.qc-home-kpi-card--success .qc-home-kpi-icon {
  background: #ecfeff;
  color: #06b6d4;
}

.qc-home-kpi-card__body span {
  color: #334155;
  font-size: 14px;
  font-weight: 800;
}

.qc-home-kpi-card__body strong {
  margin-top: 8px;
  font-size: 31px;
}

.qc-home-kpi-card__body p {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 12px;
}

.qc-home-kpi-card__body em {
  margin-left: 8px;
  font-style: normal;
  font-weight: 800;
}

.qc-home-kpi-card__body em.is-up {
  color: #ef4444;
}

.qc-home-kpi-card__body em.is-down {
  color: #06b6d4;
}

.qc-home-main-grid {
  grid-template-columns: minmax(0, 1.6fr) minmax(360px, 0.94fr);
  gap: 18px;
}

.qc-home-card,
.qc-home-task-panel {
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
}

.qc-home-card--trend {
  min-height: 320px;
  padding: 26px 26px 18px;
}

.qc-home-card h3,
.qc-home-task-panel h3 {
  font-size: 20px;
}

.qc-home-range-switch {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid rgba(203, 213, 225, 0.72);
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.8);
}

.qc-home-range-switch button {
  height: 32px;
  padding: 0 14px;
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.qc-home-range-switch button:first-child {
  background: #fff;
  color: #2563eb;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.08);
}

.qc-home-line-chart {
  margin-top: 18px;
}

.qc-home-line-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 750;
}

.qc-home-line-legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.qc-home-line-legend i {
  width: 7px;
  height: 7px;
  border-radius: 999px;
}

.qc-home-dot--blue {
  background: #3b82f6;
}

.qc-home-dot--red {
  background: #ef4444;
}

.qc-home-dot--amber {
  background: #f59e0b;
}

.qc-home-dot--cyan {
  background: #06b6d4;
}

.qc-home-line-chart svg {
  width: 100%;
  height: 250px;
  overflow: visible;
}

.qc-home-grid-lines line {
  stroke: rgba(148, 163, 184, 0.18);
  stroke-width: 1;
}

.qc-home-series {
  fill: none;
  stroke-linecap: round;
  stroke-width: 2.2;
}

.qc-home-series--blue {
  stroke: #3b82f6;
}

.qc-home-series--red {
  stroke: #ef4444;
}

.qc-home-series--amber {
  stroke: #f59e0b;
}

.qc-home-series--cyan {
  stroke: #06b6d4;
}

.qc-home-axis-labels text,
.qc-home-chart-values text {
  font-size: 12px;
  font-weight: 800;
}

.qc-home-axis-labels text {
  fill: #94a3b8;
}

.qc-home-card--insight {
  padding: 26px;
}

.qc-home-insight-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px;
  align-items: center;
  gap: 18px;
  margin-top: 18px;
}

.qc-home-insight-list {
  display: grid;
  gap: 17px;
}

.qc-home-insight-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 16px;
  align-items: center;
  gap: 12px;
  color: #334155;
}

.qc-home-insight-row span {
  overflow: hidden;
  font-size: 13px;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-home-insight-row small {
  color: #2563eb;
  font-size: 12px;
  font-weight: 750;
}

.qc-home-insight-row .anticon {
  color: #94a3b8;
  font-size: 12px;
}

.qc-home-medical-visual {
  position: relative;
  display: grid;
  width: 180px;
  height: 180px;
  place-items: center;
}

.qc-home-medical-orbit {
  position: absolute;
  width: 150px;
  height: 78px;
  border: 1px solid rgba(37, 99, 235, 0.34);
  border-radius: 50%;
}

.qc-home-medical-orbit--one {
  transform: rotate(23deg);
}

.qc-home-medical-orbit--two {
  transform: rotate(-28deg);
}

.qc-home-medical-core {
  display: grid;
  width: 110px;
  height: 110px;
  place-items: center;
  border-radius: 38px;
  background: radial-gradient(circle at 30% 22%, #f8fbff, #7fb4ff 58%, #3b82f6);
  color: rgba(255, 255, 255, 0.92);
  font-size: 54px;
  box-shadow: 0 22px 42px rgba(37, 99, 235, 0.24);
}

.qc-home-task-panel {
  padding: 0;
}

.qc-home-task-panel__head {
  align-items: center;
}

.qc-home-task-table__head {
  display: grid;
  grid-template-columns: minmax(240px, 1.45fr) minmax(120px, 0.8fr) minmax(110px, 0.7fr) minmax(
      160px,
      1fr
    ) minmax(140px, 0.8fr) minmax(110px, 0.6fr);
  gap: 16px;
  padding: 0 26px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.78);
  color: #64748b;
  font-size: 12px;
  font-weight: 850;
}

.qc-task-row {
  display: grid;
  grid-template-columns: minmax(240px, 1.45fr) minmax(120px, 0.8fr) minmax(110px, 0.7fr) minmax(
      160px,
      1fr
    ) minmax(140px, 0.8fr) minmax(110px, 0.6fr);
  align-items: center;
  gap: 16px;
  min-height: 64px;
  padding: 10px 26px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.72);
  color: #0f172a;
}

.qc-task-row:hover {
  background: rgba(248, 250, 252, 0.72);
}

.qc-task-patient {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.qc-task-avatar {
  display: grid;
  width: 36px;
  height: 36px;
  flex: none;
  place-items: center;
  overflow: hidden;
  border-radius: 999px;
  background: linear-gradient(135deg, #dbeafe, #f8fafc);
  color: #2563eb;
  font-size: 14px;
  font-weight: 900;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.72),
    0 6px 14px rgba(15, 23, 42, 0.08);
}

.qc-task-avatar img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.qc-task-patient__name {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 850;
}

.qc-task-patient__name span {
  color: #64748b;
  font-size: 12px;
  font-weight: 650;
}

.qc-task-patient__id {
  margin-top: 3px;
  overflow: hidden;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-task-cell {
  min-width: 0;
  overflow: hidden;
  color: #334155;
  font-size: 13px;
  font-weight: 760;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-task-dept {
  color: #0f172a;
}

.qc-task-risk {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 850;
}

.qc-task-risk--high {
  border: 1px solid rgba(248, 113, 113, 0.36);
  background: #fff1f2;
  color: #ef4444;
}

.qc-task-risk--medium {
  border: 1px solid rgba(251, 146, 60, 0.38);
  background: #fff7ed;
  color: #f97316;
}

.qc-task-risk--normal {
  border: 1px solid rgba(34, 197, 94, 0.28);
  background: #f0fdf4;
  color: #16a34a;
}

.qc-task-reason {
  color: #334155;
}

.qc-task-deadline {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  color: #334155;
  font-size: 13px;
  font-weight: 760;
}

.qc-task-deadline strong {
  font-size: 12px;
}

.qc-task-deadline .is-overdue {
  color: #ef4444;
}

.qc-task-deadline .is-progress {
  color: #2563eb;
}

.qc-task-deadline .is-pending {
  color: #f59e0b;
}

.qc-task-action {
  display: flex;
  justify-content: flex-end;
}

.qc-task-action button {
  height: 34px;
  min-width: 88px;
  border: 1px solid rgba(37, 99, 235, 0.52);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  color: #2563eb;
  font-size: 13px;
  font-weight: 850;
  transition: all 0.18s ease;
}

.qc-task-action button:hover {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.18);
}

@media (max-width: 1180px) {
  .qc-home-kpis,
  .qc-home-main-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .qc-home-card--insight {
    grid-column: span 2;
  }
}

@media (max-width: 860px) {
  .qc-home-canvas {
    padding: 12px;
    border-radius: 22px;
  }

  .qc-home-hero__header,
  .qc-home-task-panel__head,
  .qc-home-card__head {
    flex-direction: column;
  }

  .qc-home-hero__actions,
  .qc-home-filter-strip {
    width: 100%;
  }

  .qc-home-filter-strip {
    flex-direction: column;
    align-items: stretch;
  }

  .qc-home-kpis,
  .qc-home-main-grid,
  .qc-home-progress-list,
  .qc-home-workflow-strip {
    grid-template-columns: 1fr;
  }

  .qc-home-card--insight {
    grid-column: auto;
  }
}
</style>
