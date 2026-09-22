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
                v-if="
                  (record as TaskItem).status === 'draft' ||
                    (record as TaskItem).status === 'assigned'
                "
                type="link"
                size="small"
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

    <!-- 任务详情抽屉 -->
    <a-drawer
      v-model:open="detailDrawerVisible"
      :title="detailTask?.task_name || '任务详情'"
      :width="560"
      :header-style="{ borderBottom: '1px solid #e2e8f0' }"
      :body-style="{ padding: '20px' }"
    >
      <template v-if="detailTask">
        <div class="space-y-4">
          <!-- 基本信息 -->
          <div class="bg-slate-50 rounded-lg p-4 border border-slate-100">
            <h4 class="text-sm font-bold text-slate-500 mb-3">
              基本信息
            </h4>
            <div class="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span class="text-slate-400">编号：</span><span class="font-medium">{{ detailTask.task_number }}</span>
              </div>
              <div>
                <span class="text-slate-400">类型：</span><span class="font-medium">{{
                  detailTask.task_type === 'one_time' ? '一次性' : '定时'
                }}</span>
              </div>
              <div>
                <span class="text-slate-400">状态：</span><a-tag :color="getStatusColor(detailTask.status)">
                  {{ getStatusText(detailTask.status) }}
                </a-tag>
              </div>
              <div>
                <span class="text-slate-400">创建人：</span><span class="font-medium">{{ detailTask.creator_name }}</span>
              </div>
              <div>
                <span class="text-slate-400">截止：</span><span class="font-medium">{{ detailTask.deadline || '无' }}</span>
              </div>
              <div>
                <span class="text-slate-400">创建时间：</span><span class="font-medium">{{ formatDate(detailTask.created_at) }}</span>
              </div>
            </div>
          </div>

          <!-- 进度信息 -->
          <div
            v-if="detailProgress"
            class="bg-blue-50 rounded-lg p-4 border border-blue-100"
          >
            <h4 class="text-sm font-bold text-blue-700 mb-3">
              进度详情
            </h4>
            <a-progress
              :percent="detailProgress.progress_pct"
              :status="detailProgress.progress_pct >= 100 ? 'success' : 'active'"
              class="mb-3"
            />
            <div class="grid grid-cols-3 gap-3 text-sm text-center">
              <div class="bg-white rounded-lg p-2 border border-blue-100">
                <div class="text-lg font-bold text-slate-700">
                  {{ detailProgress.pending_count }}
                </div>
                <div class="text-xs text-slate-400">
                  待处理
                </div>
              </div>
              <div class="bg-white rounded-lg p-2 border border-blue-100">
                <div class="text-lg font-bold text-blue-600">
                  {{ detailProgress.working_count }}
                </div>
                <div class="text-xs text-slate-400">
                  进行中
                </div>
              </div>
              <div class="bg-white rounded-lg p-2 border border-blue-100">
                <div class="text-lg font-bold text-green-600">
                  {{ detailProgress.done_count }}
                </div>
                <div class="text-xs text-slate-400">
                  已完成
                </div>
              </div>
            </div>
            <div class="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <span class="text-slate-400">平均分：</span><span class="font-bold">{{ detailProgress.avg_score ?? '-' }}</span>
              </div>
              <div>
                <span class="text-slate-400">总缺陷：</span><span class="font-bold text-red-500">{{ detailProgress.total_defects }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { useRouter } from 'vue-router'
import { getTaskList, getTaskStats, getTaskProgress, updateTask } from '@/api/tasks'
import type { TaskItem, TaskStats, TaskProgress, TaskStatus } from '@/api/tasks'
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

// 响应式数据
const loading = ref(false)
const selectedStatus = ref<TaskStatus | undefined>(undefined)
const searchKeyword = ref('')
type DateRange = [Dayjs, Dayjs] | null
const dateRange = ref<DateRange>(null)
const tasks = ref<TaskItem[]>([])

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

// 详情抽屉
const detailDrawerVisible = ref(false)
const detailTask = ref<TaskItem | null>(null)
const detailProgress = ref<TaskProgress | null>(null)

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

// 表格列配置
const columns: TableColumnsType<TaskItem> = [
  { title: '任务编号', dataIndex: 'task_number', key: 'taskNumber', width: 140 },
  { title: '任务名称', dataIndex: 'task_name', key: 'taskName', width: 200 },
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

const formatStatValue = (value: number | null, suffix = '') => {
  if (statsLoading.value) return '加载中'
  if (value === null) return '不可用'
  return `${value}${suffix}`
}

// ====== 数据获取 ======

const fetchStats = async () => {
  const requestId = ++statsRequestId
  statsLoading.value = true
  statsError.value = ''
  try {
    const res = await getTaskStats({ tab: 'received' })
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
  loading.value = true
  try {
    const res = await getTaskList({
      tab: 'received',
      keyword: searchKeyword.value || undefined,
      status: selectedStatus.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })

    if (res.success && res.data) {
      const data = res.data
      tasks.value = data.items || []
      pagination.value.total = data.total || 0
    } else {
      message.error(res.message || '获取任务列表失败')
    }
  } catch (error) {
    message.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

// ====== 事件处理 ======

const handleStartTask = () => {
  // 跳转到第一个待处理任务
  const pending = tasks.value.find((t) => t.status === 'draft' || t.status === 'assigned')
  if (pending) {
    handleStartWork(pending)
  } else {
    message.info('暂无待处理任务')
  }
}

const handleViewByStatus = (status: TaskStatus) => {
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
  selectedStatus.value = status
  searchKeyword.value = ''
  dateRange.value = null
  handleFilter()
}

const handleTaskReport = () => {
  router.push('/statistics')
}

const handleFilter = () => {
  pagination.value.current = 1
  fetchTasks()
}

const handleResetFilter = () => {
  selectedStatus.value = undefined
  searchKeyword.value = ''
  dateRange.value = null
  pagination.value.current = 1
  fetchTasks()
}

const handleRefresh = () => {
  fetchTasks()
  fetchStats()
}

const handleStartWork = async (record: TaskItem) => {
  try {
    if (record.status === 'draft' || record.status === 'assigned') {
      const res = await updateTask(record.id, { status: 'in_progress' })
      if (res.success) {
        message.success(`任务「${record.task_name}」已开始`)
        fetchTasks()
        fetchStats()
      } else {
        message.error(res.message || '操作失败')
      }
    }
  } catch (e) {
    message.error('操作失败')
  }
}

const handleContinueWork = (record: TaskItem) => {
  // 跳转到工作站（带上任务上下文）
  router.push({ path: '/workstation-v5', query: { taskId: record.id } })
}

const handleViewDetail = async (record: TaskItem) => {
  detailTask.value = record
  detailProgress.value = null
  detailDrawerVisible.value = true

  // 异步加载进度详情
  try {
    const res = await getTaskProgress(record.id)
    if (res.success && res.data) {
      detailProgress.value = res.data as TaskProgress
    }
  } catch (e) {
    console.error('获取进度失败:', e)
  }
}

const handleTableChange = (pag: TablePaginationConfig) => {
  if (pag.current) pagination.value.current = pag.current
  if (pag.pageSize) pagination.value.pageSize = pag.pageSize
  fetchTasks()
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
