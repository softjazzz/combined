<template>
  <div class="all-tasks-container p-8 bg-gray-50 min-h-screen">
    <!-- CreateTaskDrawer -->
    <CreateTaskDrawer
      v-model:open="showCreateDrawer"
      @created="onTaskCreated"
    />
    <TaskDetailDrawer
      v-model:open="detailDrawerVisible"
      :task-id="detailTaskId"
      tab="all"
    />

    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">
        全部任务
      </h1>
      <p class="text-gray-600">
        管理和监控系统中的所有质控任务
      </p>
    </div>

    <!-- 任务统计概览 -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              总任务数
            </p>
            <p class="text-3xl font-bold text-gray-800">
              {{ formatStatValue(taskStats?.total ?? null) }}
            </p>
          </div>
          <div class="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center">
            <ProjectOutlined class="text-gray-600 text-xl" />
          </div>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              草稿
            </p>
            <p class="text-3xl font-bold text-orange-600">
              {{ formatStatValue(taskStats?.draft ?? null) }}
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
              已取消
            </p>
            <p class="text-3xl font-bold text-red-600">
              {{ formatStatValue(taskStats?.cancelled ?? null) }}
            </p>
          </div>
          <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
            <ExclamationCircleOutlined class="text-red-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="statsError"
      data-testid="all-task-stats-error"
      role="alert"
      class="flex items-center justify-between gap-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 mb-8 text-sm text-red-700"
    >
      <span>任务统计暂不可用：{{ statsError }}</span>
      <a-button
        size="small"
        :loading="statsLoading"
        @click="fetchStats"
      >
        重试
      </a-button>
    </div>

    <!-- 管理操作区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <h2 class="text-xl font-semibold text-gray-800 mb-4">
        任务管理
      </h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <a-button
          type="primary"
          size="large"
          class="rounded-lg h-16"
          @click="handleCreateTask"
        >
          <PlusOutlined class="text-lg" />
          <span class="ml-2">创建任务</span>
        </a-button>
        <a-button
          size="large"
          class="rounded-lg h-16"
          @click="handleBatchAssign"
        >
          <TeamOutlined class="text-lg" />
          <span class="ml-2">批量分配</span>
        </a-button>
        <a-button
          size="large"
          class="rounded-lg h-16"
          @click="handleTaskTemplate"
        >
          <FileOutlined class="text-lg" />
          <span class="ml-2">任务模板</span>
        </a-button>
        <a-button
          size="large"
          class="rounded-lg h-16"
          @click="handleTaskAnalysis"
        >
          <BarChartOutlined class="text-lg" />
          <span class="ml-2">任务分析</span>
        </a-button>
      </div>
    </div>

    <!-- 搜索和筛选区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <div class="grid grid-cols-1 md:grid-cols-6 gap-4">
        <a-select
          data-testid="all-task-scene"
          :value="selectedScene"
          placeholder="全部场景"
          allow-clear
          class="rounded-lg"
          :options="sceneOptions"
          @change="handleSceneChange"
        />

        <a-input
          v-model:value="searchKeyword"
          placeholder="搜索任务名称、编号"
          class="rounded-lg"
        >
          <template #prefix>
            <SearchOutlined class="text-gray-400" />
          </template>
        </a-input>

        <a-select
          v-model:value="selectedStatus"
          placeholder="选择状态"
          class="rounded-lg"
          :options="statusOptions"
        />

        <a-select
          v-model:value="selectedAssignee"
          placeholder="选择负责人"
          class="rounded-lg"
          :options="assigneeOptions"
        />

        <a-select
          v-model:value="selectedDepartment"
          placeholder="选择科室"
          class="rounded-lg"
          :options="departmentOptions"
        />

        <a-range-picker
          v-model:value="dateRange"
          :placeholder="['开始日期', '结束日期']"
          class="rounded-lg"
        />

        <div class="flex space-x-2">
          <a-button
            type="primary"
            class="rounded-lg"
            @click="handleSearch"
          >
            <SearchOutlined />
            搜索
          </a-button>
          <a-button
            class="rounded-lg"
            @click="handleReset"
          >
            <ReloadOutlined />
            重置
          </a-button>
        </div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-xl font-semibold text-gray-800">
          任务列表
        </h2>
        <div class="flex space-x-2">
          <a-button
            type="primary"
            :loading="loading"
            class="rounded-lg"
            @click="handleRefresh"
          >
            <ReloadOutlined />
            刷新
          </a-button>
          <a-button
            class="rounded-lg"
            @click="handleExport"
          >
            <DownloadOutlined />
            导出
          </a-button>
        </div>
      </div>

      <div
        v-if="listError"
        data-testid="all-task-list-error"
        role="alert"
        class="flex items-center justify-between gap-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 mb-5 text-sm text-red-700"
      >
        <span>任务列表暂不可用：{{ listError }}</span>
        <a-button
          size="small"
          :loading="loading"
          @click="fetchTasks"
        >
          重试
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        row-key="id"
        class="rounded-lg"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'priority'">
            <a-tag :color="getPriorityColor((record as DashboardTaskItem).priority)">
              {{ getPriorityText((record as DashboardTaskItem).priority) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor((record as DashboardTaskItem).status)">
              {{ getStatusText((record as DashboardTaskItem).status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'scene'">
            {{ sceneLabel((record as DashboardTaskItem).scene) }}
          </template>
          <template v-if="column.key === 'progress'">
            <a-progress
              :percent="(record as DashboardTaskItem).progress"
              size="small"
            />
          </template>
          <template v-if="column.key === 'assignee'">
            <div class="flex items-center">
              <a-avatar
                size="small"
                class="mr-2"
              >
                {{ (record as DashboardTaskItem).assignee?.charAt(0) }}
              </a-avatar>
              {{ (record as DashboardTaskItem).assignee || '未分配' }}
            </div>
          </template>
          <template v-if="column.key === 'action'">
            <div class="flex space-x-2">
              <a-button
                type="link"
                size="small"
                @click="handleViewDetail(record as DashboardTaskItem)"
              >
                <EyeOutlined />
                详情
              </a-button>
              <a-button
                v-if="!(record as DashboardTaskItem).assignee"
                type="link"
                size="small"
                @click="handleAssign(record as DashboardTaskItem)"
              >
                <UserAddOutlined />
                分配
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="handleEdit(record as DashboardTaskItem)"
              >
                <EditOutlined />
                编辑
              </a-button>
              <a-button
                type="link"
                size="small"
                danger
                @click="handleDelete(record as DashboardTaskItem)"
              >
                <DeleteOutlined />
                删除
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { getTaskList, getTaskStats, deleteTask, cancelTask } from '@/api/tasks'
import type { TaskItem, TaskSceneFilter, TaskStats, TaskStatus } from '@/api/tasks'
import CreateTaskDrawer from '@/components/qc/CreateTaskDrawer.vue'
import TaskDetailDrawer from '@/components/qc/TaskDetailDrawer.vue'
import {
  ProjectOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  TeamOutlined,
  FileOutlined,
  BarChartOutlined,
  SearchOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  UserAddOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const searchKeyword = ref('')
const selectedStatus = ref<TaskStatus | undefined>(undefined)
const selectedScene = ref<TaskSceneFilter | undefined>(undefined)
const selectedAssignee = ref<string | undefined>(undefined)
const selectedDepartment = ref<string | undefined>(undefined)
type DateRange = [Dayjs, Dayjs] | null
type DashboardTaskItem = TaskItem & {
  priority?: string
  assignee?: string
}
const dateRange = ref<DateRange>(null)
const tasks = ref<DashboardTaskItem[]>([])
const selectedRowKeys = ref<string[]>([])
const showCreateDrawer = ref(false)
const detailDrawerVisible = ref(false)
const detailTaskId = ref<string | null>(null)
const listError = ref('')
let listRequestId = 0

// 任务统计
const taskStats = ref<TaskStats | null>(null)
const statsLoading = ref(false)
const statsError = ref('')
let statsRequestId = 0

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条任务`,
})

// 行选择配置
const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
}))

// 选项配置
const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'sampling', label: '抽样中' },
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

const assigneeOptions = [
  { value: 'zhang_san', label: '张三' },
  { value: 'li_si', label: '李四' },
  { value: 'wang_wu', label: '王五' },
]

const departmentOptions = [
  { value: 'internal', label: '内科' },
  { value: 'surgery', label: '外科' },
  { value: 'pediatrics', label: '儿科' },
  { value: 'obstetrics', label: '妇产科' },
]

// 表格列配置
const columns: TableColumnsType<TaskItem> = [
  { title: '任务编号', dataIndex: 'task_number', key: 'taskNumber', width: 140 },
  { title: '任务名称', dataIndex: 'task_name', key: 'taskName', width: 200 },
  { title: '场景', dataIndex: 'scene', key: 'scene', width: 90 },
  { title: '任务类型', dataIndex: 'task_type', key: 'taskType', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '进度', dataIndex: 'progress', key: 'progress', width: 120 },
  { title: '总病历', dataIndex: 'total_records', key: 'totalRecords', width: 90 },
  { title: '已完成', dataIndex: 'completed_records', key: 'completedRecords', width: 90 },
  { title: '创建人', dataIndex: 'creator_name', key: 'creatorName', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'createTime', width: 150 },
  { title: '截止时间', dataIndex: 'deadline', key: 'deadline', width: 150 },
  { title: '操作', key: 'action', width: 250, fixed: 'right' as const },
]

// 工具函数
const getPriorityColor = (priority: string) => {
  const colorMap: Record<string, string> = {
    high: 'red',
    medium: 'orange',
    low: 'green',
  }
  return colorMap[priority] || 'default'
}

const getPriorityText = (priority: string) => {
  const textMap: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低',
  }
  return textMap[priority] || priority
}

const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    draft: 'default',
    sampling: 'cyan',
    assigned: 'orange',
    in_progress: 'blue',
    completed: 'green',
    cancelled: 'red',
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    draft: '草稿',
    sampling: '抽样中',
    assigned: '已分配',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return textMap[status] || status
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

const formatStatValue = (value: number | null) => {
  if (statsLoading.value) return '加载中'
  return value === null ? '不可用' : String(value)
}

// 事件处理函数
const handleCreateTask = async () => {
  showCreateDrawer.value = true
}

const onTaskCreated = (task: TaskItem) => {
  message.success(`任务「${task?.task_name || ''}」已创建`)
  fetchTasks()
  fetchStats()
}

const handleBatchAssign = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要分配的任务')
    return
  }
  message.info(`批量分配 ${selectedRowKeys.value.length} 个任务`)
}

const handleTaskTemplate = () => {
  message.info('管理任务模板')
}

const handleTaskAnalysis = () => {
  message.info('查看任务分析')
}

const handleSearch = () => {
  pagination.value.current = 1
  fetchTasks()
}

const handleReset = () => {
  searchKeyword.value = ''
  selectedStatus.value = undefined
  selectedScene.value = undefined
  selectedAssignee.value = undefined
  selectedDepartment.value = undefined
  dateRange.value = null
  pagination.value.current = 1
  void fetchTasks()
  void fetchStats()
}

const handleSceneChange = (scene?: TaskSceneFilter) => {
  selectedScene.value = scene
  pagination.value.current = 1
  listRequestId += 1
  statsRequestId += 1
  tasks.value = []
  pagination.value.total = 0
  taskStats.value = null
  listError.value = ''
  statsError.value = ''
  void fetchTasks()
  void fetchStats()
}

const handleRefresh = () => {
  fetchTasks()
  fetchStats()
}

const handleExport = () => {
  message.info('导出任务数据')
}

const handleViewDetail = (record: DashboardTaskItem) => {
  detailTaskId.value = record.id
  detailDrawerVisible.value = true
}

const handleAssign = (record: DashboardTaskItem) => {
  message.info(`分配任务: ${record.task_name}`)
}

const handleEdit = (record: DashboardTaskItem) => {
  message.info(`编辑任务: ${record.task_name}`)
}

const handleDelete = async (record: DashboardTaskItem) => {
  try {
    const res = await deleteTask(record.id)
    if (res.success) {
      message.success('任务已删除')
      await fetchTasks()
      await fetchStats()
    } else {
      message.error(res.message || '删除失败')
    }
  } catch (e) {
    message.error('删除失败')
  }
}

const handleTableChange = (pag: any) => {
  pagination.value = { ...pagination.value, ...pag }
  fetchTasks()
}

// 获取任务统计
const fetchStats = async () => {
  const requestId = ++statsRequestId
  statsLoading.value = true
  statsError.value = ''
  taskStats.value = null
  try {
    const res = await getTaskStats(selectedScene.value ? { scene: selectedScene.value } : undefined)
    if (requestId !== statsRequestId) return
    if (res.success && res.data) {
      taskStats.value = res.data
    } else {
      statsError.value = res.message || '获取任务统计失败'
    }
  } catch {
    if (requestId !== statsRequestId) return
    statsError.value = '网络异常或服务器不可用'
  } finally {
    if (requestId === statsRequestId) statsLoading.value = false
  }
}

// 获取任务列表数据
const fetchTasks = async () => {
  const requestId = ++listRequestId
  loading.value = true
  listError.value = ''
  tasks.value = []
  pagination.value.total = 0
  try {
    const res = await getTaskList({
      scene: selectedScene.value,
      keyword: searchKeyword.value || undefined,
      status: selectedStatus.value || undefined,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })

    if (requestId !== listRequestId) return
    if (res.success && res.data) {
      const data = res.data
      tasks.value = data.items || []
      pagination.value.total = data.total || 0
    } else {
      listError.value = res.message || '获取任务列表失败'
      message.error(listError.value)
    }
  } catch {
    if (requestId !== listRequestId) return
    listError.value = '网络异常或服务器不可用'
    message.error(listError.value)
  } finally {
    if (requestId === listRequestId) loading.value = false
  }
}

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
