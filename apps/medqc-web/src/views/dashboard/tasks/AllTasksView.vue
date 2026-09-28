<template>
  <div class="all-tasks-container p-8 bg-gray-50 min-h-screen">
    <!-- CreateTaskDrawer -->
    <CreateTaskDrawer
      :key="createDrawerKey"
      v-model:open="showCreateDrawer"
      :initial-template-config="taskTemplateSeed"
      @created="onTaskCreated"
      @save-template="handleSaveTaskTemplate"
    />
    <TaskTemplateDrawer
      v-model:open="showTaskTemplateDrawer"
      :seed-config="taskTemplateSeed"
      @apply="handleApplyTaskTemplate"
    />
    <TaskDetailDrawer
      :key="detailRefreshKey"
      v-model:open="detailDrawerVisible"
      :task-id="detailTaskId"
      tab="all"
    />
    <TaskAnalysisDrawer
      v-model:open="analysisDrawerVisible"
      :task-id="analysisTaskId"
      @view-detail="handleAnalysisDetail"
    />
    <TaskEditDrawer
      v-model:open="editDrawerVisible"
      :task-id="editTaskId"
      @saved="handleTaskSaved"
    />
    <TaskScheduleDrawer
      v-model:open="scheduleDrawerVisible"
      @view-task="handleScheduleTaskDetail"
    />
    <a-modal
      v-model:open="analysisPickerOpen"
      title="选择分析任务"
      :ok-button-props="{ disabled: !analysisSelection }"
      @ok="confirmAnalysisSelection"
    >
      <a-select
        v-model:value="analysisSelection"
        aria-label="当前页任务"
        placeholder="选择当前页任务"
        style="width: 100%"
        :options="tasks.map(task => ({ value: task.id, label: task.task_name }))"
      />
    </a-modal>
    <a-modal
      :open="assignDialogVisible"
      :title="batchAssigningTasks.length ? '批量分配质控任务' : '分配质控任务'"
      :confirm-loading="assignSubmitting"
      :ok-button-props="{ disabled: assignLoading || !!assignError || assignRecoveryRequired || !selectedAssigneeIds.length || !assigneeCandidates.length || assignFallbackMissing }"
      :cancel-button-props="{ disabled: assignSubmitting }"
      :mask-closable="!assignSubmitting"
      :closable="!assignSubmitting"
      ok-text="确认分配"
      @ok="submitAssignment"
      @cancel="closeAssignDialog"
    >
      <p class="mb-4 text-sm text-gray-600">
        {{ batchAssigningTasks.length ? `已选择 ${batchAssigningTasks.length} 个任务` : assigningTask?.task_name }}
        <span
          v-if="assigningMethod"
          data-testid="assign-method-label"
        > · 分配方式：{{ ASSIGN_METHOD_LABELS[assigningMethod] }}</span>
      </p>
      <div
        v-if="batchAssigningTasks.length"
        data-testid="batch-assign-contract"
        class="mb-3 text-xs text-gray-600"
      >
        各任务沿用创建时保存的分配策略并独立提交；成功项会从选择中移除，失败项保留以便调整后重试
      </div>
      <div
        v-if="assigningMethod === 'by_department'"
        data-testid="assign-department-hint"
        class="mb-3 text-xs text-amber-700"
      >
        受领人按其账号科室匹配病历科室，历史任务缺科室将无法分配
      </div>
      <div
        v-if="!batchAssigningTasks.length && assigningMethod === 'by_original_reviewer'"
        class="mb-3"
      >
        <label class="mb-1 block text-sm text-gray-700">无原质控员时</label>
        <a-radio-group
          v-model:value="assignFallback"
          data-testid="assign-fallback-group"
          :disabled="assignSubmitting"
        >
          <a-radio value="by_ratio">
            按比例分给选定人员
          </a-radio>
          <a-radio value="reject">
            拒绝分配
          </a-radio>
        </a-radio-group>
      </div>
      <div
        v-if="assignLoading"
        data-testid="assign-loading"
      >
        正在读取质控员目录…
      </div>
      <div
        v-else-if="assignError"
        data-testid="assign-error"
        role="alert"
        class="text-red-700"
      >
        {{ assignError }}
        <a-button
          size="small"
          :disabled="assignSubmitting"
          @click="loadAssigneeOptions"
        >
          重试
        </a-button>
      </div>
      <div
        v-else-if="!assigneeCandidates.length"
        data-testid="assign-empty"
        role="status"
        class="text-gray-600"
      >
        暂无可分配的质控员
      </div>
      <div v-else>
        <label class="mb-2 block text-sm text-gray-700">质控员</label>
        <a-select
          v-model:value="selectedAssigneeIds"
          data-testid="assign-candidates"
          mode="multiple"
          class="w-full"
          placeholder="选择质控员"
          :options="assigneeCandidates.map((person) => ({ value: person.user_id, label: person.department ? `${person.user_name} · ${person.department}` : person.user_name }))"
        />
      </div>
      <div
        v-if="assignSubmitError"
        data-testid="assign-submit-error"
        role="alert"
        class="mt-3 text-sm text-red-700"
      >
        {{ assignSubmitError }}
      </div>
    </a-modal>

    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">
        全部任务
      </h1>
      <p class="text-gray-600">
        管理和监控系统中的所有质控任务
      </p>
    </div>

    <TaskAssignmentResult
      v-if="lastAssignResult"
      class="mb-8"
      :result="lastAssignResult.result"
      :task-name="lastAssignResult.taskName"
      @close="lastAssignResult = null"
    />

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
          data-testid="batch-assign-button"
          :disabled="!selectedBatchTasks.length || assignRecoveryRequired"
          @click="handleBatchAssign"
        >
          <TeamOutlined class="text-lg" />
          <span class="ml-2">批量分配{{ selectedBatchTasks.length ? `（${selectedBatchTasks.length}）` : '' }}</span>
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
          :disabled="loading || !tasks.length"
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
            data-testid="task-schedules"
            @click="scheduleDrawerVisible = true"
          >
            <ClockCircleOutlined />
            定时计划
          </a-button>
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
            data-testid="task-export"
            class="rounded-lg"
            :loading="exporting"
            :disabled="loading || !!listError || exporting"
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
        row-key="id"
        :row-selection="batchRowSelection"
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
                type="link"
                size="small"
                data-testid="task-row-analysis"
                @click="openTaskAnalysis((record as DashboardTaskItem).id)"
              >
                <BarChartOutlined />
                分析
              </a-button>
              <a-button
                v-if="canAssign(record as DashboardTaskItem)"
                data-testid="task-row-assign"
                type="link"
                size="small"
                @click="handleAssign(record as DashboardTaskItem)"
              >
                <UserAddOutlined />
                分配
              </a-button>
              <a-button
                data-testid="task-row-edit"
                type="link"
                size="small"
                :disabled="record.status === 'completed' || record.status === 'cancelled'"
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
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { getTaskList, getTaskStats, deleteTask, assignTask, assignTasksBatch, getTaskAssigneeOptions } from '@/api/tasks'
import type {
  AssignFallback,
  TaskAssignableMethod,
  TaskAssigneeOption,
  TaskAssignResult,
  TaskItem,
  TaskSceneFilter,
  TaskStats,
  TaskStatus,
  TaskTemplateConfig,
} from '@/api/tasks'
import CreateTaskDrawer from '@/components/qc/CreateTaskDrawer.vue'
import TaskTemplateDrawer from '@/components/qc/TaskTemplateDrawer.vue'
import TaskAnalysisDrawer from '@/components/qc/TaskAnalysisDrawer.vue'
import TaskEditDrawer from '@/components/qc/TaskEditDrawer.vue'
import TaskScheduleDrawer from '@/components/qc/TaskScheduleDrawer.vue'
import { exportTasksCsv } from '@/api/taskExports'
import TaskAssignmentResult from '@/components/qc/TaskAssignmentResult.vue'
import { describeTaskAssignError } from '@/utils/taskAssignment'
import TaskDetailDrawer from '@/components/qc/TaskDetailDrawer.vue'
import { useAuthStore } from '@/stores/auth'
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
const selectedDepartment = ref<string | undefined>(undefined)
type DateRange = [Dayjs, Dayjs] | null
type DashboardTaskItem = TaskItem & {
  priority?: string
  assignee?: string
}
const dateRange = ref<DateRange>(null)
const tasks = ref<DashboardTaskItem[]>([])
const showCreateDrawer = ref(false)
const showTaskTemplateDrawer = ref(false)
const taskTemplateSeed = ref<TaskTemplateConfig | null>(null)
const createDrawerKey = ref(0)
const detailDrawerVisible = ref(false)
const detailTaskId = ref<string | null>(null)
const analysisDrawerVisible = ref(false)
const analysisTaskId = ref<string | null>(null)
const analysisPickerOpen = ref(false)
const analysisSelection = ref<string>()
const editDrawerVisible = ref(false)
const editTaskId = ref<string | null>(null)
const scheduleDrawerVisible = ref(false)
const exporting = ref(false)
let exportRequestId = 0
const appliedFilters = ref<{ scene?: TaskSceneFilter; keyword?: string; status?: TaskStatus }>({})
const authStore = useAuthStore()
const detailRefreshKey = ref(0)
const assignDialogVisible = ref(false)
const assigningTask = ref<DashboardTaskItem | null>(null)
const batchAssigningTasks = ref<DashboardTaskItem[]>([])
const selectedBatchTaskIds = ref<string[]>([])
const assignLoading = ref(false)
const assignError = ref('')
const assignSubmitError = ref('')
const assignSubmitting = ref(false)
const assignRecoveryRequired = ref(false)
const assigneeCandidates = ref<TaskAssigneeOption[]>([])
const selectedAssigneeIds = ref<string[]>([])
const assignFallback = ref<AssignFallback | undefined>(undefined)
const lastAssignResult = ref<{ taskName: string; result: TaskAssignResult } | null>(null)
let assignRequestId = 0

const ASSIGN_METHOD_LABELS: Record<TaskAssignableMethod, string> = {
  by_ratio: '按比例均分',
  by_original_reviewer: '原质控员',
  by_department: '按科室',
}
const isAssignableMethod = (method: unknown): method is TaskAssignableMethod =>
  method === 'by_ratio' || method === 'by_original_reviewer' || method === 'by_department'
const assigningMethod = computed<TaskAssignableMethod | null>(() => {
  if (batchAssigningTasks.value.length) return null
  const method = assigningTask.value?.assign_method
  return isAssignableMethod(method) ? method : null
})
const assignFallbackMissing = computed(() =>
  !batchAssigningTasks.value.length &&
  assigningMethod.value === 'by_original_reviewer' &&
  assignFallback.value !== 'by_ratio' && assignFallback.value !== 'reject',
)
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
  { title: '操作', key: 'action', width: 310, fixed: 'right' as const },
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
  taskTemplateSeed.value = null
  createDrawerKey.value += 1
  showCreateDrawer.value = true
}

const onTaskCreated = (task: TaskItem) => {
  taskTemplateSeed.value = null
  message.success(`任务「${task?.task_name || ''}」已创建`)
  fetchTasks()
  fetchStats()
}

const handleTaskTemplate = () => {
  taskTemplateSeed.value = null
  showTaskTemplateDrawer.value = true
}

const handleSaveTaskTemplate = (config: TaskTemplateConfig) => {
  taskTemplateSeed.value = config
  showCreateDrawer.value = false
  showTaskTemplateDrawer.value = true
}

const handleApplyTaskTemplate = (config: TaskTemplateConfig) => {
  taskTemplateSeed.value = config
  showTaskTemplateDrawer.value = false
  createDrawerKey.value += 1
  showCreateDrawer.value = true
}

const handleTaskAnalysis = () => {
  analysisSelection.value = undefined
  analysisPickerOpen.value = true
}

const openTaskAnalysis = (taskId: string) => {
  analysisTaskId.value = taskId
  analysisDrawerVisible.value = true
  analysisPickerOpen.value = false
}

const confirmAnalysisSelection = () => {
  if (!analysisSelection.value || !tasks.value.some(task => task.id === analysisSelection.value)) {
    message.warning('任务列表已变化，请重新选择任务')
    return
  }
  openTaskAnalysis(analysisSelection.value)
}

const handleAnalysisDetail = (taskId: string) => {
  if (!analysisDrawerVisible.value || taskId !== analysisTaskId.value) return
  analysisDrawerVisible.value = false
  detailTaskId.value = taskId
  detailDrawerVisible.value = true
}

watch(() => authStore.user?.id, () => {
  taskTemplateSeed.value = null
  showTaskTemplateDrawer.value = false
  showCreateDrawer.value = false
  createDrawerKey.value += 1
  analysisDrawerVisible.value = false
  analysisPickerOpen.value = false
  analysisTaskId.value = null
  analysisSelection.value = undefined
  editDrawerVisible.value = false
  editTaskId.value = null
  scheduleDrawerVisible.value = false
  exportRequestId += 1
  exporting.value = false
})

watch([selectedScene, searchKeyword, selectedStatus, selectedDepartment, dateRange], () => {
  exportRequestId += 1
  exporting.value = false
})

onBeforeUnmount(() => {
  exportRequestId += 1
  listRequestId += 1
  statsRequestId += 1
})

const clearBatchSelection = () => {
  if (assignDialogVisible.value) return
  selectedBatchTaskIds.value = []
}

const handleSearch = () => {
  clearBatchSelection()
  pagination.value.current = 1
  fetchTasks()
}

const handleReset = () => {
  clearBatchSelection()
  searchKeyword.value = ''
  selectedStatus.value = undefined
  selectedScene.value = undefined
  selectedDepartment.value = undefined
  dateRange.value = null
  pagination.value.current = 1
  void fetchTasks()
  void fetchStats()
}

const handleSceneChange = (scene?: TaskSceneFilter) => {
  clearBatchSelection()
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

const handleExport = async () => {
  if (exporting.value || loading.value || listError.value) return
  if (selectedDepartment.value || dateRange.value) {
    message.warning('科室和日期筛选尚未接通，请清空这两个条件后导出')
    return
  }
  const requestId = ++exportRequestId
  const actorId = authStore.user?.id
  exporting.value = true
  try {
    const result = await exportTasksCsv({ ...appliedFilters.value })
    if (requestId !== exportRequestId || actorId !== authStore.user?.id) return
    if (result.success === false) {
      message.error(result.message || '任务导出失败')
      return
    }
    const url = URL.createObjectURL(result.blob)
    const link = document.createElement('a')
    try {
      link.href = url
      link.download = result.filename || '质控任务.csv'
      link.click()
      message.success('任务列表已导出')
    } finally {
      URL.revokeObjectURL(url)
    }
  } catch {
    if (requestId === exportRequestId) message.error('任务导出失败，请稍后重试')
  } finally {
    if (requestId === exportRequestId) exporting.value = false
  }
}

const handleViewDetail = (record: DashboardTaskItem) => {
  detailTaskId.value = record.id
  detailDrawerVisible.value = true
}

const canAssign = (record: DashboardTaskItem) => !!authStore.user?.id
  && record.creator_id === authStore.user.id
  && isAssignableMethod(record.assign_method)
  && record.status === 'sampling'
  && !assignRecoveryRequired.value

const savedFallback = (record: DashboardTaskItem): AssignFallback | undefined => {
  const fallback = record.assignee_config?.fallback
  return fallback === 'by_ratio' || fallback === 'reject' ? fallback : undefined
}

const canBatchAssign = (record: DashboardTaskItem) => canAssign(record)
  && (record.assign_method !== 'by_original_reviewer' || !!savedFallback(record))

const selectedBatchTasks = computed(() => {
  const selected = new Set(selectedBatchTaskIds.value)
  return tasks.value.filter((task) => selected.has(task.id) && canBatchAssign(task))
})

const batchRowSelection = computed<TableProps<DashboardTaskItem>['rowSelection']>(() => ({
  selectedRowKeys: selectedBatchTaskIds.value,
  getCheckboxProps: (record) => ({ disabled: !canBatchAssign(record) }),
  onChange: (keys) => {
    const normalized = keys.map(String)
    if (normalized.length > 20) {
      message.warning('单次最多批量分配 20 个任务')
      return
    }
    selectedBatchTaskIds.value = normalized
  },
}))

const handleAssign = (record: DashboardTaskItem) => {
  if (!canAssign(record) || assignSubmitting.value) return
  assignRequestId += 1
  batchAssigningTasks.value = []
  assigningTask.value = record
  assignDialogVisible.value = true
  selectedAssigneeIds.value = []
  assigneeCandidates.value = []
  assignSubmitError.value = ''
  // 以创建时保存的处理方式预填；缺失时须在此显式选择
  assignFallback.value = savedFallback(record)
  void loadAssigneeOptions()
}

const handleBatchAssign = () => {
  if (assignSubmitting.value || assignRecoveryRequired.value || !selectedBatchTasks.value.length) return
  assignRequestId += 1
  assigningTask.value = null
  batchAssigningTasks.value = [...selectedBatchTasks.value]
  assignDialogVisible.value = true
  selectedAssigneeIds.value = []
  assigneeCandidates.value = []
  assignFallback.value = undefined
  assignSubmitError.value = ''
  void loadAssigneeOptions()
}

const closeAssignDialog = () => {
  if (assignSubmitting.value) return
  assignRequestId += 1
  assignDialogVisible.value = false
  assigningTask.value = null
  batchAssigningTasks.value = []
  assigneeCandidates.value = []
  selectedAssigneeIds.value = []
  assignFallback.value = undefined
  assignError.value = ''
  assignSubmitError.value = ''
  assignLoading.value = false
  if (assignRecoveryRequired.value) {
    void fetchTasks()
    void fetchStats()
  }
}

const loadAssigneeOptions = async () => {
  if (!assignDialogVisible.value) return
  const requestId = ++assignRequestId
  assignLoading.value = true
  assignError.value = ''
  assigneeCandidates.value = []
  selectedAssigneeIds.value = []
  try {
    const result = await getTaskAssigneeOptions()
    if (requestId !== assignRequestId || !assignDialogVisible.value) return
    if (!result.success || !Array.isArray(result.data)) {
      assignError.value = result.message || '质控员目录暂不可用'
      return
    }
    assigneeCandidates.value = result.data
  } catch {
    if (requestId !== assignRequestId || !assignDialogVisible.value) return
    assignError.value = '质控员目录暂不可用'
  } finally {
    if (requestId === assignRequestId) assignLoading.value = false
  }
}

const submitAssignment = async () => {
  if (assignSubmitting.value || assignLoading.value || assignError.value || assignRecoveryRequired.value) return
  if (batchAssigningTasks.value.length) {
    await submitBatchAssignment()
    return
  }
  if (!assigningTask.value || !canAssign(assigningTask.value)) return
  const method = assigningMethod.value
  if (!method || assignFallbackMissing.value) return
  const selected = assigneeCandidates.value.filter((person) => selectedAssigneeIds.value.includes(person.user_id))
  if (!selected.length) return
  const taskId = assigningTask.value.id
  const taskName = assigningTask.value.task_name
  assignSubmitting.value = true
  assignSubmitError.value = ''
  try {
    const result = await assignTask(taskId, {
      method,
      assignees: selected.map((person) => ({
        user_id: person.user_id,
        user_name: person.user_name,
        ...(person.department ? { department: person.department } : {}),
      })),
      ...(method === 'by_original_reviewer' && assignFallback.value ? { fallback: assignFallback.value } : {}),
    })
    // 已知策略业务码在写入前判定，未落库，可调整人员后重试
    const businessError = result.success ? undefined : describeTaskAssignError(result.errorDetail, result.status)
    if (businessError) {
      assignSubmitError.value = businessError
      return
    }
    if (!result.success || typeof result.data?.total_assigned !== 'number') {
      assignRecoveryRequired.value = true
      assignSubmitError.value = `分配未确认，请核对任务状态后再操作。${result.message || ''}`
      return
    }
    assignSubmitting.value = false
    lastAssignResult.value = { taskName, result: result.data }
    closeAssignDialog()
    message.success(result.message || '任务已分配')
    await Promise.all([fetchTasks(), fetchStats()])
    if (detailDrawerVisible.value && detailTaskId.value === taskId) {
      detailRefreshKey.value += 1
      await nextTick()
    }
  } catch {
    assignRecoveryRequired.value = true
    assignSubmitError.value = '分配结果未知，请刷新任务列表核对后再操作。'
  } finally {
    assignSubmitting.value = false
  }
}

async function submitBatchAssignment() {
  const targets = batchAssigningTasks.value.filter(canBatchAssign)
  const selected = assigneeCandidates.value.filter((person) => selectedAssigneeIds.value.includes(person.user_id))
  if (!targets.length || !selected.length || targets.length > 20) return
  assignSubmitting.value = true
  assignSubmitError.value = ''
  try {
    const result = await assignTasksBatch({
      tasks: targets.map((task) => ({
        task_id: task.id,
        method: task.assign_method as TaskAssignableMethod,
        ...(task.assign_method === 'by_original_reviewer' && savedFallback(task)
          ? { fallback: savedFallback(task) }
          : {}),
      })),
      assignees: selected.map((person) => ({
        user_id: person.user_id,
        user_name: person.user_name,
        ...(person.department ? { department: person.department } : {}),
      })),
    })
    const data = result.data
    const expectedIds = new Set(targets.map((task) => task.id))
    const responseItems = Array.isArray(data?.items) ? data.items : []
    const responseIds = responseItems.map((item) => item.task_id)
    const actualSuccessCount = responseItems.filter((item) => item.success).length
    if (!result.success || !data || !Array.isArray(data.items)
      || data.total !== targets.length || data.items.length !== data.total
      || responseIds.length !== new Set(responseIds).size
      || responseIds.some((taskId) => !expectedIds.has(taskId))
      || data.success_count !== actualSuccessCount
      || data.failed_count !== data.total - actualSuccessCount) {
      assignRecoveryRequired.value = true
      assignSubmitError.value = `批量分配结果未确认，请刷新任务列表核对后再操作。${result.message || ''}`
      return
    }
    const successIds = new Set(data.items.filter((item) => item.success).map((item) => item.task_id))
    const failedItems = data.items.filter((item) => !item.success)
    selectedBatchTaskIds.value = selectedBatchTaskIds.value.filter((id) => !successIds.has(id))
    batchAssigningTasks.value = targets.filter((task) => !successIds.has(task.id))
    if (data.success_count) {
      await Promise.all([fetchTasks(), fetchStats()])
    }
    if (!failedItems.length) {
      selectedBatchTaskIds.value = []
      message.success(result.message || `已分配 ${data.success_count} 个任务`)
      assignSubmitting.value = false
      closeAssignDialog()
      return
    }
    const names = new Map(targets.map((task) => [task.id, task.task_name]))
    const failureText = failedItems
      .map((item) => `${names.get(item.task_id) || item.task_id}：${item.message || '分配失败'}`)
      .join('；')
    assignSubmitError.value = `已成功 ${data.success_count} 个，失败 ${data.failed_count} 个。${failureText}`
    message.warning('部分任务分配失败，失败项已保留')
  } catch {
    assignRecoveryRequired.value = true
    assignSubmitError.value = '批量分配结果未知，请刷新任务列表核对后再操作。'
  } finally {
    assignSubmitting.value = false
  }
}

const handleEdit = (record: DashboardTaskItem) => {
  if (record.status === 'completed' || record.status === 'cancelled') return
  editTaskId.value = record.id
  editDrawerVisible.value = true
}

const handleTaskSaved = async (taskId: string) => {
  if (!editDrawerVisible.value || taskId !== editTaskId.value) return
  editDrawerVisible.value = false
  detailRefreshKey.value += 1
  await Promise.all([fetchTasks(), fetchStats()])
}

const handleScheduleTaskDetail = (taskId: string) => {
  if (!scheduleDrawerVisible.value) return
  detailTaskId.value = taskId
  detailRefreshKey.value += 1
  detailDrawerVisible.value = true
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
  clearBatchSelection()
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
  exportRequestId += 1
  exporting.value = false
  const filters = {
    scene: selectedScene.value,
    keyword: searchKeyword.value || undefined,
    status: selectedStatus.value || undefined,
  }
  loading.value = true
  listError.value = ''
  tasks.value = []
  pagination.value.total = 0
  try {
    const res = await getTaskList({
      ...filters,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })

    if (requestId !== listRequestId) return
    if (res.success && res.data) {
      appliedFilters.value = filters
      const data = res.data
      tasks.value = data.items || []
      pagination.value.total = data.total || 0
      if (!assignDialogVisible.value) assignRecoveryRequired.value = false
      const assignableIds = new Set(tasks.value.filter(canBatchAssign).map((task) => task.id))
      selectedBatchTaskIds.value = selectedBatchTaskIds.value.filter((id) => assignableIds.has(id))
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
