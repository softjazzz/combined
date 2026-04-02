<template>
  <!-- 整个页面采用纯正的 SaaS 灰色画板底色 -->
  <div class="min-h-[calc(100vh-64px)] bg-[#F4F5F7] flex flex-col font-sans antialiased">
    <!-- 顶部紧凑控制栏 (Control Bar) -->
    <div
      class="bg-white border-b border-slate-200 px-6 py-3 shrink-0 shadow-sm z-10 flex flex-wrap gap-4 items-center justify-between"
    >
      <HomeHeroBar
        v-model:keyword="keyword"
        v-model:selected-date="selectedDate"
        v-model:department-filter="departmentFilter"
        v-model:workflow-filter="workflowFilter"
        :department-options="departmentOptions"
        :loading="loading"
        :disabled-future-date="disabledFutureDate"
        @refresh="fetchHome()"
      />
    </div>

    <!-- 主工作区：居中单卡片设计 (A4 Island) -->
    <div class="flex-1 px-6 py-6 overflow-y-auto">
      <div class="mx-auto max-w-[1400px] flex flex-col gap-4">
        <!-- 状态过滤器 (Status Tabs) -->
        <StatusBar
          :kpis="homeData.kpis"
          :active-key="activeStatusKey"
          @select="handleStatusSelect"
        />

        <!-- 任务列表画板 -->
        <div
          class="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden min-h-[400px] flex flex-col"
        >
          <UnifiedTaskList
            :tasks="unifiedTasks"
            :format-date-time="formatDateTime"
            @open="handleOpenTask"
          />
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
      const s = (t.severity || '').toLowerCase()
      return s === 'critical' || s === 'high'
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
  router.push({
    path: '/workstation-v4',
    query: {
      source: 'dashboard',
      record_id: recordId,
      action: action as WorkstationLaunchAction,
      from_stage: fromStage as WorkflowStageKey,
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

async function syncFiltersToQuery() {
  const nextQuery = {
    ...route.query,
    date: selectedDate.value.format('YYYY-MM-DD'),
    department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
    workflow: workflowFilter.value !== 'all' ? workflowFilter.value : undefined,
    keyword: keyword.value.trim() || undefined,
  }
  await router.replace({ path: route.path, query: nextQuery })
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
