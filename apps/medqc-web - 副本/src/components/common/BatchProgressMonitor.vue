<template>
  <div class="batch-progress-monitor">
    <!-- 监控面板头部 -->
    <div class="monitor-header">
      <div class="header-left">
        <i class="fas fa-tasks text-xl text-blue-600" />
        <h3 class="text-lg font-semibold text-gray-800">
          批量任务监控
        </h3>
        <span class="task-count">{{ activeTasks.length }} 个活跃任务</span>
      </div>
      <div class="header-right">
        <button
          class="btn-refresh"
          :disabled="isRefreshing"
          @click="refreshTasks"
        >
          <i
            class="fas fa-sync-alt"
            :class="{ 'fa-spin': isRefreshing }"
          />
        </button>
        <button
          class="btn-minimize"
          @click="toggleMinimize"
        >
          <i
            class="fas"
            :class="isMinimized ? 'fa-chevron-down' : 'fa-chevron-up'"
          />
        </button>
      </div>
    </div>

    <!-- 任务列表 -->
    <div
      v-if="!isMinimized"
      class="task-list"
    >
      <div
        v-if="activeTasks.length === 0"
        class="empty-state"
      >
        <i class="fas fa-check-circle text-4xl text-green-500 mb-3" />
        <p class="text-gray-600">
          暂无活跃的批量任务
        </p>
      </div>

      <div
        v-for="task in activeTasks"
        :key="task.id"
        class="task-item"
        :class="{
          'task-pending': task.status === 'pending',
          'task-processing': task.status === 'processing',
          'task-completed': task.status === 'completed',
          'task-failed': task.status === 'failed',
        }"
      >
        <!-- 任务基本信息 -->
        <div class="task-info">
          <div class="task-header">
            <div class="task-title">
              <i :class="getTaskIcon(task.task_type)" />
              <span class="task-name">{{ getTaskName(task.task_type) }}</span>
              <span
                class="task-status-badge"
                :class="getStatusClass(task.status)"
              >
                {{ getStatusText(task.status) }}
              </span>
            </div>
            <div class="task-meta">
              <span class="task-time">{{ formatTime(task.created_at) }}</span>
              <span
                v-if="task.started_at"
                class="task-duration"
              >
                {{ formatDuration(task.started_at, task.completed_at) }}
              </span>
            </div>
          </div>

          <!-- 进度条 -->
          <div class="progress-section">
            <div class="progress-bar">
              <div
                class="progress-fill"
                :class="getProgressClass(task.status)"
                :style="{ width: task.progress_percentage + '%' }"
              />
            </div>
            <div class="progress-text">
              <span class="progress-percentage">{{ Math.round(task.progress_percentage) }}%</span>
              <span class="progress-items">
                {{ task.processed_items }}/{{ task.total_items }}
              </span>
            </div>
          </div>

          <!-- 详细统计 -->
          <div class="task-stats">
            <div class="stat-item">
              <span class="stat-label">总数</span>
              <span class="stat-value">{{ task.total_items }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">已处理</span>
              <span class="stat-value text-blue-600">{{ task.processed_items }}</span>
            </div>
            <div
              v-if="task.failed_items > 0"
              class="stat-item"
            >
              <span class="stat-label">失败</span>
              <span class="stat-value text-red-600">{{ task.failed_items }}</span>
            </div>
            <div
              v-if="task.status === 'processing'"
              class="stat-item"
            >
              <span class="stat-label">预计剩余</span>
              <span class="stat-value">{{ estimateRemainingTime(task) }}</span>
            </div>
          </div>

          <!-- 错误信息 -->
          <div
            v-if="task.error_details && task.status === 'failed'"
            class="error-section"
          >
            <div class="error-header">
              <i class="fas fa-exclamation-triangle text-red-500" />
              <span class="error-title">错误详情</span>
            </div>
            <div class="error-content">
              {{ formatErrorDetails(task.error_details) }}
            </div>
          </div>
        </div>

        <!-- 任务操作 -->
        <div class="task-actions">
          <button
            v-if="task.status === 'failed'"
            class="btn-retry"
            :disabled="isRetrying"
            @click="retryTask(task.id)"
          >
            <i class="fas fa-redo" />
            <span>重试</span>
          </button>
          <button
            v-if="task.status === 'processing'"
            class="btn-cancel"
            :disabled="isCancelling"
            @click="cancelTask(task.id)"
          >
            <i class="fas fa-stop" />
            <span>取消</span>
          </button>
          <button
            class="btn-details"
            @click="viewTaskDetails(task)"
          >
            <i class="fas fa-info-circle" />
            <span>详情</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 历史任务快速访问 -->
    <div
      v-if="!isMinimized && recentTasks.length > 0"
      class="recent-tasks"
    >
      <div class="recent-header">
        <h4 class="text-sm font-medium text-gray-700">
          最近完成
        </h4>
        <button
          class="btn-view-all"
          @click="viewAllTasks"
        >
          查看全部
        </button>
      </div>
      <div class="recent-list">
        <div
          v-for="task in recentTasks.slice(0, 3)"
          :key="task.id"
          class="recent-item"
          @click="viewTaskDetails(task)"
        >
          <div class="recent-info">
            <i :class="getTaskIcon(task.task_type)" />
            <span class="recent-name">{{ getTaskName(task.task_type) }}</span>
            <span class="recent-time">{{ formatRelativeTime(task.completed_at!) }}</span>
          </div>
          <div class="recent-result">
            <span class="recent-success">{{ task.total_items - task.failed_items }}</span>
            <span
              v-if="task.failed_items > 0"
              class="recent-failed"
            >{{ task.failed_items }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useBatchMonitor } from '@/composables/useBatchMonitor'
// 移除 date-fns 依赖，使用原生 JavaScript 日期处理

// 批量任务接口
interface BatchTask {
  id: string
  user_id: string
  task_type: 'upload' | 'analysis' | 'export'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  total_items: number
  processed_items: number
  failed_items: number
  progress_percentage: number
  error_details?: Record<string, unknown>
  metadata?: Record<string, unknown>
  created_at: string
  started_at?: string
  completed_at?: string
}

// 组件属性
const props = defineProps<{
  autoRefresh?: boolean
  refreshInterval?: number
  showRecentTasks?: boolean
  maxRecentTasks?: number
}>()

// 默认配置
const autoRefresh = props.autoRefresh ?? true
const refreshInterval = props.refreshInterval ?? 5000 // 5秒
const showRecentTasks = props.showRecentTasks ?? true
const maxRecentTasks = props.maxRecentTasks ?? 5

// 响应式数据
const isMinimized = ref(false)
const isRefreshing = ref(false)
const isRetrying = ref(false)
const isCancelling = ref(false)

// 使用批量监控组合式函数
const {
  activeTasks,
  recentTasks,
  refreshTasks: refreshTasksComposable,
  subscribeToTasks,
  retryTask: retryTaskComposable,
  cancelTask: cancelTaskComposable,
} = useBatchMonitor()

// 自动刷新定时器
let refreshTimer: NodeJS.Timeout | null = null

// 计算属性
const totalActiveTasks = computed(() => activeTasks.value.length)

// 方法
const toggleMinimize = () => {
  isMinimized.value = !isMinimized.value
}

const refreshTasks = async () => {
  if (isRefreshing.value) return

  isRefreshing.value = true
  try {
    await refreshTasksComposable()
  } finally {
    isRefreshing.value = false
  }
}

const retryTask = async (taskId: string) => {
  if (isRetrying.value) return

  isRetrying.value = true
  try {
    await retryTaskComposable(taskId)
  } finally {
    isRetrying.value = false
  }
}

const cancelTask = async (taskId: string) => {
  if (isCancelling.value) return

  isCancelling.value = true
  try {
    await cancelTaskComposable(taskId)
  } finally {
    isCancelling.value = false
  }
}

const viewTaskDetails = (task: BatchTask) => {
  // 触发事件，让父组件处理详情显示
  emit('view-details', task)
}

const viewAllTasks = () => {
  // 触发事件，让父组件处理全部任务显示
  emit('view-all-tasks')
}

// 工具函数
const getTaskIcon = (taskType: string): string => {
  const icons = {
    upload: 'fas fa-upload text-blue-500',
    analysis: 'fas fa-brain text-purple-500',
    export: 'fas fa-download text-green-500',
  }
  return icons[taskType as keyof typeof icons] || 'fas fa-tasks text-gray-500'
}

const getTaskName = (taskType: string): string => {
  const names = {
    upload: '批量上传',
    analysis: '批量分析',
    export: '批量导出',
  }
  return names[taskType as keyof typeof names] || '未知任务'
}

const getStatusText = (status: string): string => {
  const texts = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return texts[status as keyof typeof texts] || status
}

const getStatusClass = (status: string): string => {
  const classes = {
    pending: 'status-pending',
    processing: 'status-processing',
    completed: 'status-completed',
    failed: 'status-failed',
  }
  return classes[status as keyof typeof classes] || ''
}

const getProgressClass = (status: string): string => {
  const classes = {
    pending: 'progress-pending',
    processing: 'progress-processing',
    completed: 'progress-completed',
    failed: 'progress-failed',
  }
  return classes[status as keyof typeof classes] || ''
}

const formatTime = (dateString: string): string => {
  const date = new Date(dateString)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffMinutes = Math.ceil(diffTime / (1000 * 60))
  const diffHours = Math.ceil(diffTime / (1000 * 60 * 60))
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffMinutes < 60) {
    return `${diffMinutes}分钟前`
  } else if (diffHours < 24) {
    return `${diffHours}小时前`
  } else {
    return `${diffDays}天前`
  }
}

const formatDuration = (startTime: string, endTime?: string): string => {
  const start = new Date(startTime)
  const end = endTime ? new Date(endTime) : new Date()
  const duration = Math.floor((end.getTime() - start.getTime()) / 1000)

  if (duration < 60) return `${duration}秒`
  if (duration < 3600) return `${Math.floor(duration / 60)}分钟`
  return `${Math.floor(duration / 3600)}小时${Math.floor((duration % 3600) / 60)}分钟`
}

const estimateRemainingTime = (task: BatchTask): string => {
  if (!task.started_at || task.processed_items === 0) return '计算中...'

  const elapsed = Date.now() - new Date(task.started_at).getTime()
  const avgTimePerItem = elapsed / task.processed_items
  const remainingItems = task.total_items - task.processed_items
  const remainingTime = Math.floor((avgTimePerItem * remainingItems) / 1000)

  if (remainingTime < 60) return `约${remainingTime}秒`
  if (remainingTime < 3600) return `约${Math.floor(remainingTime / 60)}分钟`
  return `约${Math.floor(remainingTime / 3600)}小时`
}

const formatErrorDetails = (errorDetails: unknown): string => {
  if (typeof errorDetails === 'string') return errorDetails
  if (errorDetails && typeof errorDetails === 'object') {
    const details = errorDetails as Record<string, unknown>
    return typeof details.message === 'string'
      ? details.message
      : JSON.stringify(errorDetails, null, 2)
  }
  return '未知错误'
}

// 事件定义
const emit = defineEmits<{
  'view-details': [task: BatchTask]
  'view-all-tasks': []
}>()

// 生命周期
onMounted(async () => {
  // 初始加载任务
  await refreshTasks()

  // 订阅实时更新
  subscribeToTasks()

  // 设置自动刷新
  if (autoRefresh) {
    refreshTimer = setInterval(refreshTasks, refreshInterval)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.batch-progress-monitor {
  @apply bg-white rounded-xl border border-gray-200 overflow-hidden;
}

.monitor-header {
  @apply flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-200;
}

.header-left {
  @apply flex items-center space-x-3;
}

.task-count {
  @apply px-2 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded-full;
}

.header-right {
  @apply flex items-center space-x-2;
}

.btn-refresh,
.btn-minimize {
  @apply p-2 text-gray-600 hover:text-blue-600 hover:bg-white rounded-lg transition-colors duration-200;
}

.task-list {
  @apply divide-y divide-gray-100;
}

.empty-state {
  @apply flex flex-col items-center justify-center py-12 text-center;
}

.task-item {
  @apply p-4 hover:bg-gray-50 transition-colors duration-200;
}

.task-item.task-pending {
  @apply border-l-4 border-gray-400;
}

.task-item.task-processing {
  @apply border-l-4 border-blue-500 bg-blue-50/30;
}

.task-item.task-completed {
  @apply border-l-4 border-green-500;
}

.task-item.task-failed {
  @apply border-l-4 border-red-500 bg-red-50/30;
}

.task-info {
  @apply space-y-3;
}

.task-header {
  @apply flex items-start justify-between;
}

.task-title {
  @apply flex items-center space-x-2;
}

.task-name {
  @apply font-medium text-gray-800;
}

.task-status-badge {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.status-pending {
  @apply bg-gray-100 text-gray-700;
}

.status-processing {
  @apply bg-blue-100 text-blue-700;
}

.status-completed {
  @apply bg-green-100 text-green-700;
}

.status-failed {
  @apply bg-red-100 text-red-700;
}

.task-meta {
  @apply flex items-center space-x-2 text-sm text-gray-500;
}

.task-time,
.task-duration {
  @apply font-mono;
}

.progress-section {
  @apply space-y-2;
}

.progress-bar {
  @apply w-full h-2 bg-gray-200 rounded-full overflow-hidden;
}

.progress-fill {
  @apply h-full transition-all duration-300;
}

.progress-pending {
  @apply bg-gray-400;
}

.progress-processing {
  @apply bg-blue-500;
}

.progress-completed {
  @apply bg-green-500;
}

.progress-failed {
  @apply bg-red-500;
}

.progress-text {
  @apply flex items-center justify-between text-sm;
}

.progress-percentage {
  @apply font-semibold text-gray-700;
}

.progress-items {
  @apply text-gray-500 font-mono;
}

.task-stats {
  @apply flex items-center space-x-4;
}

.stat-item {
  @apply flex flex-col items-center;
}

.stat-label {
  @apply text-xs text-gray-500;
}

.stat-value {
  @apply text-sm font-semibold text-gray-800;
}

.error-section {
  @apply mt-3 p-3 bg-red-50 border border-red-200 rounded-lg;
}

.error-header {
  @apply flex items-center space-x-2 mb-2;
}

.error-title {
  @apply text-sm font-medium text-red-800;
}

.error-content {
  @apply text-sm text-red-700 font-mono whitespace-pre-wrap;
}

.task-actions {
  @apply flex items-center justify-end space-x-2 mt-3 pt-3 border-t border-gray-100;
}

.btn-retry,
.btn-cancel,
.btn-details {
  @apply px-3 py-1.5 text-sm font-medium rounded-lg transition-colors duration-200 flex items-center space-x-1;
}

.btn-retry {
  @apply bg-orange-100 text-orange-700 hover:bg-orange-200;
}

.btn-cancel {
  @apply bg-red-100 text-red-700 hover:bg-red-200;
}

.btn-details {
  @apply bg-gray-100 text-gray-700 hover:bg-gray-200;
}

.recent-tasks {
  @apply border-t border-gray-200 bg-gray-50;
}

.recent-header {
  @apply flex items-center justify-between p-3 border-b border-gray-200;
}

.btn-view-all {
  @apply text-sm text-blue-600 hover:text-blue-700 font-medium;
}

.recent-list {
  @apply divide-y divide-gray-200;
}

.recent-item {
  @apply flex items-center justify-between p-3 hover:bg-gray-100 cursor-pointer transition-colors duration-200;
}

.recent-info {
  @apply flex items-center space-x-2;
}

.recent-name {
  @apply text-sm font-medium text-gray-700;
}

.recent-time {
  @apply text-xs text-gray-500;
}

.recent-result {
  @apply flex items-center space-x-2 text-sm;
}

.recent-success {
  @apply text-green-600 font-medium;
}

.recent-failed {
  @apply text-red-600 font-medium;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .monitor-header {
    @apply flex-col space-y-3 items-start;
  }

  .header-right {
    @apply w-full justify-end;
  }

  .task-header {
    @apply flex-col space-y-2 items-start;
  }

  .task-stats {
    @apply grid grid-cols-2 gap-2 w-full;
  }

  .task-actions {
    @apply flex-col space-y-2 space-x-0;
  }

  .btn-retry,
  .btn-cancel,
  .btn-details {
    @apply w-full justify-center;
  }
}
</style>
