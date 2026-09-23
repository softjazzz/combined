<template>
  <div class="my-tasks-container p-8 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">
        我的任务
      </h1>
      <p class="text-gray-600">
        管理和处理分配给我的质控任务
      </p>
    </div>

    <div
      v-if="invalidTaskQuery"
      data-testid="task-todo-invalid"
      role="alert"
      class="flex items-center justify-between gap-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 mb-8 text-sm text-red-700"
    >
      <span>任务范围链接无效，未加载无范围任务列表。</span>
      <a-button
        size="small"
        @click="void clearInvalidTaskScope()"
      >
        清除无效范围
      </a-button>
    </div>
    <div
      v-else-if="activeTodo"
      data-testid="task-todo-scope"
      class="flex items-center justify-between gap-4 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 mb-8 text-sm text-blue-800"
    >
      <span>待办范围：{{ todoScopeLabel }} · {{ sceneScopeLabel }} · 基准 {{ formatDate(todoAsOf || '') }}</span>
      <a-button
        data-testid="clear-task-todo"
        size="small"
        @click="void clearTodoScope()"
      >
        清除待办范围
      </a-button>
    </div>

    <!-- 任务统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              未开始任务
            </p>
            <p
              data-testid="pending-task-count"
              class="text-3xl font-bold text-orange-600"
            >
              {{ formatStatValue(pendingTaskCount) }}
            </p>
          </div>
          <div class="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
            <ClockCircleOutlined class="text-orange-600 text-xl" />
          </div>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              进行中
            </p>
            <p class="text-3xl font-bold text-blue-600">
              {{ formatStatValue(taskStats?.in_progress ?? null) }}
            </p>
          </div>
          <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
            <SyncOutlined class="text-blue-600 text-xl" />
          </div>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              已完成
            </p>
            <p class="text-3xl font-bold text-green-600">
              {{ formatStatValue(taskStats?.completed ?? null) }}
            </p>
          </div>
          <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
            <CheckCircleOutlined class="text-green-600 text-xl" />
          </div>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              完成率
            </p>
            <p class="text-3xl font-bold text-purple-600">
              {{ formatStatValue(completionRate, '%') }}
            </p>
          </div>
          <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
            <TrophyOutlined class="text-purple-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="statsError"
      data-testid="task-stats-error"
      role="alert"
      class="flex items-center justify-between gap-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 mb-8 text-sm text-red-700"
    >
      <span>任务统计暂不可用：{{ statsError }}</span>
      <a-button
        data-testid="retry-task-stats"
        size="small"
        :loading="statsLoading"
        @click="fetchStats"
      >
        <ReloadOutlined />
        重试
      </a-button>
    </div>

    <!-- 快捷操作 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <h2 class="text-xl font-semibold text-gray-800 mb-4">
        快捷操作
      </h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <a-button
          data-testid="start-task-action"
          type="primary"
          size="large"
          class="rounded-lg h-16"
          @click="handleStartTask"
        >
          <PlayCircleOutlined class="text-lg" />
          <span class="ml-2">开始任务</span>
        </a-button>
        <a-button
          data-testid="pending-task-action"
          size="large"
          class="rounded-lg h-16"
          @click="handleViewByStatus('assigned')"
        >
          <ClockCircleOutlined class="text-lg" />
          <span class="ml-2">未开始任务</span>
        </a-button>
        <a-button
          data-testid="completed-task-action"
          size="large"
          class="rounded-lg h-16"
          @click="handleViewByStatus('completed')"
        >
          <CheckCircleOutlined class="text-lg" />
          <span class="ml-2">已完成任务</span>
        </a-button>
        <a-button
          size="large"
          class="rounded-lg h-16"
          @click="handleTaskReport"
        >
          <BarChartOutlined class="text-lg" />
          <span class="ml-2">任务报告</span>
        </a-button>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 mb-8">
      <ProQueryBar>
        <template #filters>
          <a-select
            :value="activeScene"
            placeholder="全部场景"
            allow-clear
            class="rounded-lg min-w-32"
            :options="sceneOptions"
            @change="handleSceneChange"
          />

          <a-select
            v-model:value="selectedStatus"
            placeholder="选择状态"
            allow-clear
            class="rounded-lg min-w-36"
            :options="statusOptions"
          />

          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索任务名称"
            allow-clear
            class="rounded-lg min-w-60"
            @search="handleFilter"
          />

          <a-range-picker
            v-model:value="dateRange"
            class="rounded-lg"
          />
        </template>
        <template #actions>
          <ProTableToolbar>
            <a-button
              type="primary"
              class="rounded-lg"
              @click="handleFilter"
            >
              <FilterOutlined />
              筛选
            </a-button>
            <a-button
              class="rounded-lg"
              @click="handleResetFilter"
            >
              <ReloadOutlined />
              重置
            </a-button>
          </ProTableToolbar>
        </template>
      </ProQueryBar>
    </div>

    <!-- 任务列表 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-xl font-semibold text-gray-800">
          任务列表
        </h2>
        <a-button
          data-testid="refresh-task-list"
          type="primary"
          :loading="loading"
          class="rounded-lg"
          @click="handleRefresh"
        >
          <ReloadOutlined />
          刷新
        </a-button>
      </div>

      <div
        v-if="listError"
        data-testid="task-list-error"
        role="alert"
        class="flex items-center justify-between gap-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 mb-5 text-sm text-red-700"
      >
        <span>任务列表暂不可用：{{ listError }}</span>
        <a-button
          data-testid="retry-task-list"
          size="small"
          :loading="loading"
          @click="fetchTasks"
        >
          重试
        </a-button>
      </div>

      <ProStandardTable
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        class="rounded-lg"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor((record as TaskItem).status)">
              {{ getStatusText((record as TaskItem).status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'scene'">
            {{ sceneLabel((record as TaskItem).scene) }}
          </template>
          <template v-if="column.key === 'progress'">
            <a-progress
              :percent="(record as TaskItem).progress"
              size="small"
              :status="(record as TaskItem).progress >= 100 ? 'success' : 'active'"
            />
          </template>
          <template v-if="column.key === 'action'">
            <div class="flex space-x-2">
              <a-button
                v-if="(record as TaskItem).status === 'assigned'"
                type="link"
                size="small"
                :loading="startingTaskIds.has((record as TaskItem).id)"
                :disabled="startingTaskIds.has((record as TaskItem).id)"
                @click="handleStartWork(record as TaskItem)"
              >
                <PlayCircleOutlined />
                开始
              </a-button>
              <a-button
                v-if="(record as TaskItem).status === 'in_progress'"
                type="link"
                size="small"
                @click="handleContinueWork(record as TaskItem)"
              >
                <EditOutlined />
                继续
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="handleViewDetail(record as TaskItem)"
              >
                <EyeOutlined />
                详情
              </a-button>
            </div>
          </template>
        </template>
      </ProStandardTable>
    </div>

    <TaskDetailDrawer
      v-model:open="detailDrawerVisible"
      :task-id="detailTaskId"
      tab="received"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { useRoute, useRouter } from 'vue-router'
import { getTaskList, getTaskStats, updateTask } from '@/api/tasks'
import type {
  TaskItem,
  TaskSceneFilter,
  TaskStats,
  TaskStatus,
  TaskTodo,
} from '@/api/tasks'
import TaskDetailDrawer from '@/components/qc/TaskDetailDrawer.vue'
import {
  ClockCircleOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  TrophyOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  FilterOutlined,
  ReloadOutlined,
  EditOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import ProQueryBar from '@/components/pro/ProQueryBar.vue'
import ProTableToolbar from '@/components/pro/ProTableToolbar.vue'
import ProStandardTable from '@/components/pro/ProStandardTable.vue'

const router = useRouter()
const route = useRoute()

// 响应式数据
const loading = ref(false)
const selectedStatus = ref<TaskStatus | undefined>(undefined)
const searchKeyword = ref('')
type DateRange = [Dayjs, Dayjs] | null
const dateRange = ref<DateRange>(null)
const tasks = ref<TaskItem[]>([])
const startingTaskIds = ref(new Set<string>())
const listError = ref('')
const initialTaskQuery = parseTaskQuery(route.query.todo, route.query.as_of, route.query.scene)
const activeTodo = ref<TaskTodo | undefined>(initialTaskQuery.todo)
const todoAsOf = ref<string | undefined>(initialTaskQuery.asOf)
const activeScene = ref<TaskSceneFilter | undefined>(initialTaskQuery.scene)
const invalidTaskQuery = ref(initialTaskQuery.invalid)
let syncingTodoRoute = false
let listRequestId = 0

// 统计
const taskStats = ref<TaskStats | null>(null)
const statsLoading = ref(false)
const statsError = ref('')
let statsRequestId = 0

const pendingTaskCount = computed(() =>
  taskStats.value ? (taskStats.value.by_status.assigned ?? 0) : null,
)

// 完成率
const completionRate = computed(() => {
  if (!taskStats.value) return null
  const total = taskStats.value.total
  if (!total) return 0
  return Math.round((taskStats.value.completed / total) * 1000) / 10
})

const todoScopeLabel = computed(() => {
  const labels: Record<TaskTodo, string> = {
    assigned: '未开始任务',
    in_progress: '进行中任务',
    due_soon: '24 小时内到期',
  }
  return activeTodo.value ? labels[activeTodo.value] : ''
})

const sceneScopeLabel = computed(() =>
  activeScene.value ? sceneLabel(activeScene.value) : '全部场景',
)

// 详情抽屉
const detailDrawerVisible = ref(false)
const detailTaskId = ref<string | null>(null)

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条任务`,
})

// 状态选项
const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'assigned', label: '已分配' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

const sceneOptions: Array<{ label: string; value: TaskSceneFilter }> = [
  { label: '运行', value: 'running' },
  { label: '终末', value: 'final' },
  { label: '门急诊', value: 'outpatient' },
  { label: '未标注', value: 'unclassified' },
]

// 表格列配置
const columns: TableColumnsType<TaskItem> = [
  { title: '任务编号', dataIndex: 'task_number', key: 'taskNumber', width: 140 },
  { title: '任务名称', dataIndex: 'task_name', key: 'taskName', width: 200 },
  { title: '场景', dataIndex: 'scene', key: 'scene', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '进度', dataIndex: 'progress', key: 'progress', width: 140 },
  {
    title: '总病历',
    dataIndex: 'total_records',
    key: 'totalRecords',
    width: 90,
    align: 'center' as const,
  },
  {
    title: '已完成',
    dataIndex: 'completed_records',
    key: 'completedRecords',
    width: 90,
    align: 'center' as const,
  },
  { title: '截止时间', dataIndex: 'deadline', key: 'deadline', width: 150 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const },
]

// 工具函数
const getStatusColor = (status: string) => {
  const map: Record<string, string> = {
    draft: 'default',
    sampling: 'cyan',
    assigned: 'orange',
    in_progress: 'blue',
    completed: 'green',
    cancelled: 'red',
  }
  return map[status] || 'default'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    draft: '草稿',
    sampling: '抽样中',
    assigned: '已分配',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[status] || status
}

const sceneLabel = (scene?: TaskSceneFilter | null) => {
  const labels: Record<TaskSceneFilter, string> = {
    running: '运行',
    final: '终末',
    outpatient: '门急诊',
    unclassified: '未标注',
  }
  return scene ? labels[scene] : '未标注'
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function parseTaskTodo(value: unknown): TaskTodo | undefined {
  return value === 'assigned' || value === 'in_progress' || value === 'due_soon'
    ? value
    : undefined
}

function parseAsOf(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) || Number.isNaN(Date.parse(value))) return undefined
  return value
}

function parseScene(value: unknown): TaskSceneFilter | undefined {
  return value === 'running' ||
    value === 'final' ||
    value === 'outpatient' ||
    value === 'unclassified'
    ? value
    : undefined
}

function parseTaskQuery(todoValue: unknown, asOfValue: unknown, sceneValue: unknown) {
  const todo = parseTaskTodo(todoValue)
  const asOf = parseAsOf(asOfValue)
  const scene = parseScene(sceneValue)
  const hasTodo = todoValue !== undefined
  const hasAsOf = asOfValue !== undefined
  const hasScene = sceneValue !== undefined
  return {
    todo,
    asOf: todo ? asOf : undefined,
    scene,
    invalid: (hasTodo && !todo) || (hasAsOf && (!todo || !asOf)) || (hasScene && !scene),
  }
}

function syncTaskScopeFromRoute(todoValue: unknown, asOfValue: unknown, sceneValue: unknown) {
  const nextQuery = parseTaskQuery(todoValue, asOfValue, sceneValue)
  activeTodo.value = nextQuery.todo
  todoAsOf.value = nextQuery.asOf
  activeScene.value = nextQuery.scene
  invalidTaskQuery.value = nextQuery.invalid
}

function clearLocalFilters() {
  selectedStatus.value = undefined
  searchKeyword.value = ''
  dateRange.value = null
  pagination.value.current = 1
}

function queryWithoutTodo() {
  const query = { ...route.query }
  delete query.todo
  delete query.as_of
  return query
}

function queryWithoutTaskScope() {
  const query = queryWithoutTodo()
  delete query.scene
  return query
}

function invalidateTaskList() {
  listRequestId += 1
  tasks.value = []
  pagination.value.total = 0
  listError.value = ''
  loading.value = false
}

function invalidateTaskStats() {
  statsRequestId += 1
  taskStats.value = null
  statsError.value = ''
  statsLoading.value = false
}

async function clearTodoRoute() {
  if (route.query.todo === undefined && route.query.as_of === undefined) return
  invalidateTaskList()
  syncingTodoRoute = true
  syncTaskScopeFromRoute(undefined, undefined, route.query.scene)
  try {
    await router.replace({ query: queryWithoutTodo() })
  } finally {
    syncingTodoRoute = false
  }
}

async function clearTaskScopeRoute() {
  if (
    route.query.todo === undefined &&
    route.query.as_of === undefined &&
    route.query.scene === undefined
  ) {
    return
  }
  invalidateTaskList()
  invalidateTaskStats()
  syncingTodoRoute = true
  syncTaskScopeFromRoute(undefined, undefined, undefined)
  try {
    await router.replace({ query: queryWithoutTaskScope() })
  } finally {
    syncingTodoRoute = false
  }
}

const formatStatValue = (value: number | null, suffix = '') => {
  if (statsLoading.value) return '加载中'
  if (value === null) return '不可用'
  return `${value}${suffix}`
}

// ====== 数据获取 ======

const fetchStats = async () => {
  const requestId = ++statsRequestId
  if (invalidTaskQuery.value && route.query.scene !== undefined && !activeScene.value) {
    taskStats.value = null
    statsLoading.value = false
    return
  }
  statsLoading.value = true
  statsError.value = ''
  try {
    const res = await getTaskStats(
      activeScene.value
        ? { tab: 'received', scene: activeScene.value }
        : { tab: 'received' },
    )
    if (requestId !== statsRequestId) return
    if (res.success && res.data) {
      taskStats.value = res.data
    } else {
      taskStats.value = null
      statsError.value = res.message || '获取任务统计失败'
    }
  } catch {
    if (requestId !== statsRequestId) return
    taskStats.value = null
    statsError.value = '网络异常或服务器不可用'
  } finally {
    if (requestId === statsRequestId) {
      statsLoading.value = false
    }
  }
}

const fetchTasks = async () => {
  const requestId = ++listRequestId
  listError.value = ''
  if (invalidTaskQuery.value) {
    tasks.value = []
    pagination.value.total = 0
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await getTaskList({
      tab: 'received',
      todo: activeTodo.value,
      as_of: activeTodo.value ? todoAsOf.value : undefined,
      scene: activeScene.value,
      keyword: searchKeyword.value || undefined,
      status: selectedStatus.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })

    if (requestId !== listRequestId) return
    if (res.success && res.data) {
      const data = res.data
      tasks.value = data.items || []
      pagination.value.total = data.total || 0
    } else {
      tasks.value = []
      pagination.value.total = 0
      listError.value = res.message || '获取任务列表失败'
      message.error(listError.value)
    }
  } catch {
    if (requestId !== listRequestId) return
    tasks.value = []
    pagination.value.total = 0
    listError.value = '网络异常或服务器不可用'
    message.error(listError.value)
  } finally {
    if (requestId === listRequestId) loading.value = false
  }
}

// ====== 事件处理 ======

const handleStartTask = () => {
  const pending = tasks.value.find((t) => t.status === 'assigned')
  if (pending) {
    handleStartWork(pending)
  } else {
    message.info('暂无待处理任务')
  }
}

const handleViewByStatus = async (status: TaskStatus) => {
  if (statsLoading.value) {
    message.warning('任务统计正在加载，请稍后重试')
    return
  }
  const statusCount =
    status === 'assigned'
      ? pendingTaskCount.value
      : status === 'completed' && taskStats.value
        ? taskStats.value.completed
        : taskStats.value?.by_status[status] ?? null
  if (statusCount === null) {
    message.warning('任务统计暂不可用，请重试')
    return
  }
  if (statusCount === 0) {
    message.info('没有待处理的事项')
    return
  }
  clearLocalFilters()
  await clearTodoRoute()
  selectedStatus.value = status
  handleFilter()
}

const handleTaskReport = () => {
  router.push('/statistics')
}

const handleFilter = () => {
  pagination.value.current = 1
  fetchTasks()
}

const handleSceneChange = async (scene?: TaskSceneFilter) => {
  invalidateTaskList()
  invalidateTaskStats()
  clearLocalFilters()
  const query = { ...route.query }
  if (scene) query.scene = scene
  else delete query.scene
  syncingTodoRoute = true
  syncTaskScopeFromRoute(route.query.todo, route.query.as_of, scene)
  try {
    await router.replace({ query })
  } finally {
    syncingTodoRoute = false
  }
  void fetchTasks()
  void fetchStats()
}

const clearTodoScope = async () => {
  pagination.value.current = 1
  await clearTodoRoute()
  fetchTasks()
}

const clearInvalidTaskScope = async () => {
  clearLocalFilters()
  await clearTaskScopeRoute()
  void fetchTasks()
  void fetchStats()
}

const handleResetFilter = async () => {
  clearLocalFilters()
  await clearTaskScopeRoute()
  void fetchTasks()
  void fetchStats()
}

const handleRefresh = () => {
  fetchTasks()
  fetchStats()
}

const handleStartWork = async (record: TaskItem) => {
  if (record.status !== 'assigned' || startingTaskIds.value.has(record.id)) return
  startingTaskIds.value.add(record.id)
  try {
    const res = await updateTask(record.id, { status: 'in_progress' })
    if (res.success && res.data?.id === record.id && res.data.status === 'in_progress') {
      message.success(`任务「${record.task_name}」已开始`)
    } else {
      const reason = res.success ? '操作结果未确认' : res.message || '操作结果未确认'
      message.error(`${reason}，请核对刷新后的任务状态`)
    }
  } catch {
    message.error('操作结果未确认，请核对刷新后的任务状态')
  } finally {
    await Promise.all([fetchTasks(), fetchStats()])
    startingTaskIds.value.delete(record.id)
  }
}

const handleContinueWork = (record: TaskItem) => {
  // 跳转到工作站（带上任务上下文）
  router.push({ path: '/workstation-v5', query: { taskId: record.id } })
}

const handleViewDetail = (record: TaskItem) => {
  detailTaskId.value = record.id
  detailDrawerVisible.value = true
}

const handleTableChange = (pag: TablePaginationConfig) => {
  if (pag.current) pagination.value.current = pag.current
  if (pag.pageSize) pagination.value.pageSize = pag.pageSize
  fetchTasks()
}

watch(
  [() => route.query.todo, () => route.query.as_of, () => route.query.scene],
  ([todoValue, asOfValue, sceneValue], previousValues) => {
    if (syncingTodoRoute) return
    invalidateTaskList()
    const sceneChanged = sceneValue !== previousValues?.[2]
    if (sceneChanged) invalidateTaskStats()
    syncTaskScopeFromRoute(todoValue, asOfValue, sceneValue)
    clearLocalFilters()
    void fetchTasks()
    if (sceneChanged) void fetchStats()
  },
)

onMounted(() => {
  fetchTasks()
  fetchStats()
})
</script>

<style scoped>
:deep(.ant-table-thead > tr > th) {
  background-color: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f8fafc;
}

:deep(.ant-btn-link) {
  padding: 0 4px;
}
</style>
