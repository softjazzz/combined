<template>
  <div class="realtime-qc-dashboard">
    <!-- 仪表板头部 -->
    <div class="dashboard-header">
      <div class="header-left">
        <div class="status-indicator">
          <div 
            class="status-dot"
            :class="{
              'status-active': isMonitoring,
              'status-inactive': !isMonitoring
            }"
          ></div>
          <h2 class="dashboard-title">实时质控监控</h2>
        </div>
        <div class="system-health">
          <span class="health-label">系统状态:</span>
          <span 
            class="health-status"
            :class="`health-${systemHealth}`"
          >
            {{ getHealthText(systemHealth) }}
          </span>
        </div>
      </div>
      
      <div class="header-right">
        <div class="control-buttons">
          <button
            v-if="!isMonitoring"
            @click="startMonitoring"
            class="btn-start"
            :disabled="isStarting"
          >
            <i class="fas fa-play mr-2"></i>
            {{ isStarting ? '启动中...' : '启动监控' }}
          </button>
          <button
            v-else
            @click="stopMonitoring"
            class="btn-stop"
            :disabled="isStopping"
          >
            <i class="fas fa-stop mr-2"></i>
            {{ isStopping ? '停止中...' : '停止监控' }}
          </button>
          <button
            @click="refreshDashboard"
            class="btn-refresh"
            :disabled="isRefreshing"
          >
            <i class="fas fa-sync-alt" :class="{ 'fa-spin': isRefreshing }"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- 监控统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-users text-blue-500"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ monitorStatus.connectedUsers }}</div>
          <div class="stat-label">在线用户</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-cog fa-spin text-orange-500" v-if="monitorStatus.activeAnalyses > 0"></i>
          <i class="fas fa-cog text-gray-400" v-else></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ monitorStatus.activeAnalyses }}</div>
          <div class="stat-label">活跃分析</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-chart-line text-green-500"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ monitorStatus.totalAnalysesToday }}</div>
          <div class="stat-label">今日分析</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-clock text-purple-500"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ formatResponseTime(monitorStatus.averageResponseTime) }}</div>
          <div class="stat-label">平均响应</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-exclamation-triangle text-red-500" v-if="criticalIssues.length > 0"></i>
          <i class="fas fa-shield-alt text-green-500" v-else></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ criticalIssues.length }}</div>
          <div class="stat-label">严重问题</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-server" :class="getSystemLoadClass()"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ Math.round(monitorStatus.systemLoad) }}%</div>
          <div class="stat-label">系统负载</div>
        </div>
      </div>
    </div>

    <!-- 预警面板 -->
    <div class="alerts-section">
      <div class="section-header">
        <h3 class="section-title">
          <i class="fas fa-bell mr-2"></i>
          实时预警
        </h3>
        <div class="alert-summary">
          <span class="alert-count critical" v-if="criticalIssues.length > 0">
            {{ criticalIssues.length }} 严重
          </span>
          <span class="alert-count warning" v-if="warningIssues.length > 0">
            {{ warningIssues.length }} 警告
          </span>
          <span class="alert-count info" v-if="alertQueue.length === 0">
            无预警
          </span>
        </div>
      </div>

      <div class="alerts-container">
        <div v-if="alertQueue.length === 0" class="no-alerts">
          <i class="fas fa-check-circle text-green-500 text-4xl mb-3"></i>
          <p class="text-gray-600">当前无质控预警</p>
        </div>

        <div v-else class="alerts-list">
          <div
            v-for="(alert, index) in alertQueue.slice(0, 10)"
            :key="index"
            class="alert-item"
            :class="`alert-${alert.severity}`"
          >
            <div class="alert-icon">
              <i :class="getAlertIcon(alert.severity)"></i>
            </div>
            <div class="alert-content">
              <div class="alert-message">{{ alert.message }}</div>
              <div class="alert-meta">
                <span class="alert-type">{{ alert.type }}</span>
                <span class="alert-time">刚刚</span>
              </div>
            </div>
            <div class="alert-actions">
              <button
                @click="dismissAlert(index)"
                class="btn-dismiss"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 实时分析结果 -->
    <div class="results-section">
      <div class="section-header">
        <h3 class="section-title">
          <i class="fas fa-chart-bar mr-2"></i>
          最近分析结果
        </h3>
        <div class="results-controls">
          <select v-model="resultFilter" class="filter-select">
            <option value="all">全部</option>
            <option value="critical">严重问题</option>
            <option value="error">错误</option>
            <option value="warning">警告</option>
            <option value="info">信息</option>
          </select>
        </div>
      </div>

      <div class="results-container">
        <div v-if="filteredResults.length === 0" class="no-results">
          <i class="fas fa-search text-gray-400 text-4xl mb-3"></i>
          <p class="text-gray-600">暂无分析结果</p>
        </div>

        <div v-else class="results-list">
          <div
            v-for="result in filteredResults.slice(0, 20)"
            :key="result.id"
            class="result-item"
            :class="`result-${result.alertLevel}`"
          >
            <div class="result-header">
              <div class="result-info">
                <span class="result-id">{{ result.recordId.slice(-8) }}</span>
                <span class="result-level" :class="`level-${result.alertLevel}`">
                  {{ getLevelText(result.alertLevel) }}
                </span>
                <span class="result-time">{{ formatTime(result.timestamp) }}</span>
              </div>
              <div class="result-metrics">
                <span class="metric">
                  <i class="fas fa-clock"></i>
                  {{ result.processingTime }}ms
                </span>
                <span class="metric">
                  <i class="fas fa-percentage"></i>
                  {{ Math.round(result.confidence * 100) }}%
                </span>
              </div>
            </div>

            <div class="result-content">
              <div class="result-issues" v-if="result.issues.length > 0">
                <div class="issues-summary">
                  发现 {{ result.issues.length }} 个问题:
                </div>
                <div class="issues-list">
                  <span
                    v-for="(issue, idx) in result.issues.slice(0, 3)"
                    :key="idx"
                    class="issue-tag"
                    :class="`issue-${issue.severity}`"
                  >
                    {{ issue.message }}
                  </span>
                  <span v-if="result.issues.length > 3" class="more-issues">
                    +{{ result.issues.length - 3 }} 更多
                  </span>
                </div>
              </div>

              <div class="result-suggestions" v-if="result.suggestions.length > 0">
                <div class="suggestions-summary">建议:</div>
                <div class="suggestions-list">
                  <div
                    v-for="(suggestion, idx) in result.suggestions.slice(0, 2)"
                    :key="idx"
                    class="suggestion-item"
                  >
                    {{ suggestion }}
                  </div>
                </div>
              </div>
            </div>

            <div class="result-actions">
              <button
                @click="viewResultDetails(result)"
                class="btn-view-details"
              >
                <i class="fas fa-eye mr-1"></i>
                详情
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 系统性能图表 -->
    <div class="performance-section">
      <div class="section-header">
        <h3 class="section-title">
          <i class="fas fa-tachometer-alt mr-2"></i>
          系统性能
        </h3>
      </div>

      <div class="performance-charts">
        <div class="chart-container">
          <div class="chart-title">响应时间趋势</div>
          <div class="chart-placeholder">
            <div class="performance-bar">
              <div 
                class="performance-fill"
                :style="{ width: getPerformanceWidth() }"
              ></div>
            </div>
            <div class="performance-text">
              {{ formatResponseTime(monitorStatus.averageResponseTime) }} 平均响应时间
            </div>
          </div>
        </div>

        <div class="chart-container">
          <div class="chart-title">系统负载</div>
          <div class="chart-placeholder">
            <div class="load-gauge">
              <div 
                class="load-indicator"
                :style="{ transform: `rotate(${getLoadRotation()}deg)` }"
              ></div>
            </div>
            <div class="load-text">
              {{ Math.round(monitorStatus.systemLoad) }}% 当前负载
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRealTimeQC } from '@/composables/useRealTimeQC'
import type { RealTimeQCResult, QCIssue, QCAlertLevel } from '@/composables/useRealTimeQC'
import { message } from 'ant-design-vue'

// 使用实时质控组合式函数
const {
  isMonitoring,
  monitorStatus,
  activeAnalyses,
  recentResults,
  qcRules,
  alertQueue,
  criticalIssues,
  warningIssues,
  systemHealth,
  startRealTimeMonitoring,
  stopRealTimeMonitoring
} = useRealTimeQC()

// 组件状态
const isStarting = ref(false)
const isStopping = ref(false)
const isRefreshing = ref(false)
const resultFilter = ref<string>('all')

// 计算属性
const filteredResults = computed(() => {
  if (resultFilter.value === 'all') {
    return recentResults.value
  }
  return recentResults.value.filter(result => result.alertLevel === resultFilter.value)
})

// 方法
const startMonitoring = async () => {
  isStarting.value = true
  try {
    await startRealTimeMonitoring()
  } catch (error) {
    console.error('启动监控失败:', error)
  } finally {
    isStarting.value = false
  }
}

const stopMonitoring = async () => {
  isStopping.value = true
  try {
    stopRealTimeMonitoring()
  } catch (error) {
    console.error('停止监控失败:', error)
  } finally {
    isStopping.value = false
  }
}

const refreshDashboard = async () => {
  isRefreshing.value = true
  try {
    // 刷新数据
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('仪表板已刷新')
  } catch (error) {
    console.error('刷新失败:', error)
  } finally {
    isRefreshing.value = false
  }
}

const dismissAlert = (index: number) => {
  alertQueue.value.splice(index, 1)
}

const viewResultDetails = (result: RealTimeQCResult) => {
  // 显示结果详情
  console.log('查看结果详情:', result)
  message.info('结果详情功能开发中')
}

// 工具函数
const getHealthText = (health: string): string => {
  const texts = {
    good: '良好',
    fair: '一般',
    poor: '较差'
  }
  return texts[health as keyof typeof texts] || '未知'
}

const formatResponseTime = (time: number): string => {
  if (time < 1000) return `${Math.round(time)}ms`
  return `${(time / 1000).toFixed(1)}s`
}

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const getSystemLoadClass = (): string => {
  const load = monitorStatus.value.systemLoad
  if (load > 80) return 'text-red-500'
  if (load > 60) return 'text-orange-500'
  return 'text-green-500'
}

const getAlertIcon = (severity: QCAlertLevel): string => {
  const icons = {
    critical: 'fas fa-exclamation-circle text-red-500',
    error: 'fas fa-exclamation-triangle text-orange-500',
    warning: 'fas fa-exclamation text-yellow-500',
    info: 'fas fa-info-circle text-blue-500'
  }
  return icons[severity]
}

const getLevelText = (level: QCAlertLevel): string => {
  const texts = {
    critical: '严重',
    error: '错误',
    warning: '警告',
    info: '信息'
  }
  return texts[level]
}

const getPerformanceWidth = (): string => {
  const time = monitorStatus.value.averageResponseTime
  const maxTime = 5000 // 5秒为最大值
  const percentage = Math.min((time / maxTime) * 100, 100)
  return `${percentage}%`
}

const getLoadRotation = (): number => {
  // 将负载百分比转换为角度 (0-180度)
  return (monitorStatus.value.systemLoad / 100) * 180
}

// 生命周期
onMounted(() => {
  console.log('实时质控仪表板已加载')
})

onUnmounted(() => {
  if (isMonitoring.value) {
    stopRealTimeMonitoring()
  }
})
</script>

<style scoped>
.realtime-qc-dashboard {
  @apply p-6 space-y-6 bg-gray-50 min-h-screen;
}

/* 仪表板头部 */
.dashboard-header {
  @apply flex items-center justify-between bg-white rounded-xl p-6 shadow-sm border border-gray-200;
}

.header-left {
  @apply flex items-center space-x-6;
}

.status-indicator {
  @apply flex items-center space-x-3;
}

.status-dot {
  @apply w-3 h-3 rounded-full;
}

.status-active {
  @apply bg-green-500 animate-pulse;
}

.status-inactive {
  @apply bg-gray-400;
}

.dashboard-title {
  @apply text-2xl font-bold text-gray-800;
}

.system-health {
  @apply flex items-center space-x-2;
}

.health-label {
  @apply text-sm text-gray-600;
}

.health-status {
  @apply text-sm font-medium px-2 py-1 rounded-full;
}

.health-good {
  @apply bg-green-100 text-green-800;
}

.health-fair {
  @apply bg-yellow-100 text-yellow-800;
}

.health-poor {
  @apply bg-red-100 text-red-800;
}

.header-right {
  @apply flex items-center space-x-3;
}

.control-buttons {
  @apply flex items-center space-x-2;
}

.btn-start {
  @apply px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.btn-stop {
  @apply px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.btn-refresh {
  @apply p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors duration-200 disabled:opacity-50;
}

/* 统计卡片网格 */
.stats-grid {
  @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4;
}

.stat-card {
  @apply bg-white rounded-xl p-6 shadow-sm border border-gray-200 flex items-center space-x-4;
}

.stat-icon {
  @apply text-2xl;
}

.stat-content {
  @apply flex-1;
}

.stat-value {
  @apply text-2xl font-bold text-gray-800;
}

.stat-label {
  @apply text-sm text-gray-600;
}

/* 预警面板 */
.alerts-section {
  @apply bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden;
}

.section-header {
  @apply flex items-center justify-between p-6 bg-gray-50 border-b border-gray-200;
}

.section-title {
  @apply text-lg font-semibold text-gray-800 flex items-center;
}

.alert-summary {
  @apply flex items-center space-x-3;
}

.alert-count {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.alert-count.critical {
  @apply bg-red-100 text-red-800;
}

.alert-count.warning {
  @apply bg-yellow-100 text-yellow-800;
}

.alert-count.info {
  @apply bg-green-100 text-green-800;
}

.alerts-container {
  @apply p-6;
}

.no-alerts {
  @apply text-center py-12;
}

.alerts-list {
  @apply space-y-3;
}

.alert-item {
  @apply flex items-start space-x-3 p-4 rounded-lg border-l-4;
}

.alert-critical {
  @apply bg-red-50 border-red-500;
}

.alert-error {
  @apply bg-orange-50 border-orange-500;
}

.alert-warning {
  @apply bg-yellow-50 border-yellow-500;
}

.alert-info {
  @apply bg-blue-50 border-blue-500;
}

.alert-icon {
  @apply text-lg mt-0.5;
}

.alert-content {
  @apply flex-1;
}

.alert-message {
  @apply font-medium text-gray-800 mb-1;
}

.alert-meta {
  @apply flex items-center space-x-2 text-sm text-gray-600;
}

.alert-type {
  @apply px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs;
}

.alert-actions {
  @apply flex items-center;
}

.btn-dismiss {
  @apply p-1 text-gray-400 hover:text-red-600 rounded transition-colors duration-200;
}

/* 分析结果面板 */
.results-section {
  @apply bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden;
}

.results-controls {
  @apply flex items-center space-x-3;
}

.filter-select {
  @apply px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.results-container {
  @apply p-6;
}

.no-results {
  @apply text-center py-12;
}

.results-list {
  @apply space-y-4;
}

.result-item {
  @apply border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow duration-200;
}

.result-critical {
  @apply border-red-300 bg-red-50;
}

.result-error {
  @apply border-orange-300 bg-orange-50;
}

.result-warning {
  @apply border-yellow-300 bg-yellow-50;
}

.result-info {
  @apply border-blue-300 bg-blue-50;
}

.result-header {
  @apply flex items-center justify-between mb-3;
}

.result-info {
  @apply flex items-center space-x-3;
}

.result-id {
  @apply font-mono text-sm bg-gray-100 px-2 py-1 rounded;
}

.result-level {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.level-critical {
  @apply bg-red-100 text-red-800;
}

.level-error {
  @apply bg-orange-100 text-orange-800;
}

.level-warning {
  @apply bg-yellow-100 text-yellow-800;
}

.level-info {
  @apply bg-blue-100 text-blue-800;
}

.result-time {
  @apply text-sm text-gray-500 font-mono;
}

.result-metrics {
  @apply flex items-center space-x-3 text-sm text-gray-600;
}

.metric {
  @apply flex items-center space-x-1;
}

.result-content {
  @apply space-y-3;
}

.result-issues {
  @apply space-y-2;
}

.issues-summary {
  @apply text-sm font-medium text-gray-700;
}

.issues-list {
  @apply flex flex-wrap gap-2;
}

.issue-tag {
  @apply px-2 py-1 text-xs rounded-full;
}

.issue-critical {
  @apply bg-red-100 text-red-800;
}

.issue-error {
  @apply bg-orange-100 text-orange-800;
}

.issue-warning {
  @apply bg-yellow-100 text-yellow-800;
}

.issue-info {
  @apply bg-blue-100 text-blue-800;
}

.more-issues {
  @apply px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full;
}

.result-suggestions {
  @apply space-y-2;
}

.suggestions-summary {
  @apply text-sm font-medium text-gray-700;
}

.suggestions-list {
  @apply space-y-1;
}

.suggestion-item {
  @apply text-sm text-gray-600 pl-4 border-l-2 border-green-300;
}

.result-actions {
  @apply flex items-center justify-end mt-3 pt-3 border-t border-gray-200;
}

.btn-view-details {
  @apply px-3 py-1.5 text-sm bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg transition-colors duration-200 flex items-center;
}

/* 性能图表 */
.performance-section {
  @apply bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden;
}

.performance-charts {
  @apply p-6 grid grid-cols-1 md:grid-cols-2 gap-6;
}

.chart-container {
  @apply space-y-4;
}

.chart-title {
  @apply text-lg font-semibold text-gray-800;
}

.chart-placeholder {
  @apply bg-gray-50 rounded-lg p-6 text-center;
}

.performance-bar {
  @apply w-full h-4 bg-gray-200 rounded-full overflow-hidden mb-3;
}

.performance-fill {
  @apply h-full bg-gradient-to-r from-green-500 to-blue-500 transition-all duration-500;
}

.performance-text {
  @apply text-sm text-gray-600;
}

.load-gauge {
  @apply relative w-24 h-12 mx-auto mb-3;
  background: conic-gradient(from 0deg, #ef4444 0deg 60deg, #f59e0b 60deg 120deg, #10b981 120deg 180deg);
  border-radius: 120px 120px 0 0;
}

.load-indicator {
  @apply absolute top-0 left-1/2 w-1 h-12 bg-gray-800 origin-bottom transform -translate-x-1/2 transition-transform duration-500;
}

.load-text {
  @apply text-sm text-gray-600;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .realtime-qc-dashboard {
    @apply p-4 space-y-4;
  }

  .dashboard-header {
    @apply flex-col space-y-4 items-start;
  }

  .header-left {
    @apply flex-col space-y-3 items-start;
  }

  .stats-grid {
    @apply grid-cols-1;
  }

  .result-header {
    @apply flex-col space-y-2 items-start;
  }

  .performance-charts {
    @apply grid-cols-1;
  }
}
</style>
