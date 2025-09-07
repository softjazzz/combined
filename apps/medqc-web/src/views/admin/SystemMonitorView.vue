<template>
  <div class="system-monitor">
    <div class="monitor-header">
      <h1>系统监控面板</h1>
      <div class="header-actions">
        <a-button @click="refreshData" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
        <a-switch 
          v-model:checked="autoRefresh" 
          checked-children="自动刷新" 
          un-checked-children="手动刷新"
        />
      </div>
    </div>

    <!-- 系统概览 -->
    <div class="overview-section">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="metric-card">
            <a-statistic
              title="系统状态"
              :value="systemStatus"
              :value-style="{ color: systemStatus === '正常' ? '#3f8600' : '#cf1322' }"
            >
              <template #prefix>
                <component :is="systemStatus === '正常' ? CheckCircleOutlined : ExclamationCircleOutlined" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="metric-card">
            <a-statistic
              title="平均响应时间"
              :value="performanceStats.averageResponseTime"
              suffix="ms"
              :value-style="{ color: performanceStats.averageResponseTime < 2000 ? '#3f8600' : '#faad14' }"
            >
              <template #prefix><ClockCircleOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="metric-card">
            <a-statistic
              title="缓存命中率"
              :value="performanceStats.cacheHitRate * 100"
              suffix="%"
              :precision="1"
              :value-style="{ color: performanceStats.cacheHitRate > 0.7 ? '#3f8600' : '#faad14' }"
            >
              <template #prefix><DatabaseOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="metric-card">
            <a-statistic
              title="错误率"
              :value="errorStats.errorRate * 100"
              suffix="%"
              :precision="2"
              :value-style="{ color: errorStats.errorRate < 0.05 ? '#3f8600' : '#cf1322' }"
            >
              <template #prefix><WarningOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 服务健康状态 -->
    <div class="services-section">
      <a-card title="服务健康状态" class="section-card">
        <a-row :gutter="[16, 16]">
          <a-col 
            v-for="service in serviceHealth" 
            :key="service.name"
            :xs="24" :sm="12" :lg="8"
          >
            <div class="service-item" :class="`service-${service.status}`">
              <div class="service-header">
                <div class="service-name">{{ service.name }}</div>
                <a-tag :color="getServiceStatusColor(service.status)">
                  {{ getServiceStatusText(service.status) }}
                </a-tag>
              </div>
              <div class="service-metrics">
                <div class="metric">
                  <span class="metric-label">响应时间:</span>
                  <span class="metric-value">{{ service.responseTime }}ms</span>
                </div>
                <div class="metric">
                  <span class="metric-label">最后检查:</span>
                  <span class="metric-value">{{ formatTime(service.lastCheck) }}</span>
                </div>
                <div v-if="service.error" class="service-error">
                  <span class="error-label">错误:</span>
                  <span class="error-message">{{ service.error }}</span>
                </div>
              </div>
            </div>
          </a-col>
        </a-row>
      </a-card>
    </div>

    <!-- 性能图表 -->
    <div class="charts-section">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :lg="12">
          <a-card title="响应时间趋势" class="chart-card">
            <div ref="responseTimeChart" class="chart-container"></div>
          </a-card>
        </a-col>
        
        <a-col :xs="24" :lg="12">
          <a-card title="错误统计" class="chart-card">
            <div ref="errorChart" class="chart-container"></div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 错误日志 -->
    <div class="errors-section">
      <a-card title="最近错误" class="section-card">
        <a-table
          :columns="errorColumns"
          :data-source="recentErrors"
          :pagination="{ pageSize: 10 }"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'severity'">
              <a-tag :color="getErrorSeverityColor(record.severity)">
                {{ record.severity }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'timestamp'">
              {{ formatDateTime(record.timestamp) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button size="small" @click="viewErrorDetails(record)">
                详情
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 错误详情模态框 -->
    <a-modal
      v-model:open="showErrorModal"
      title="错误详情"
      :width="800"
      :footer="null"
    >
      <div v-if="selectedError" class="error-details">
        <a-descriptions :column="1" bordered>
          <a-descriptions-item label="错误类型">
            <a-tag :color="getErrorSeverityColor(selectedError.severity)">
              {{ selectedError.type }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="严重程度">
            {{ selectedError.severity }}
          </a-descriptions-item>
          <a-descriptions-item label="错误消息">
            {{ selectedError.message }}
          </a-descriptions-item>
          <a-descriptions-item label="用户消息">
            {{ selectedError.userMessage }}
          </a-descriptions-item>
          <a-descriptions-item label="发生时间">
            {{ formatDateTime(selectedError.timestamp) }}
          </a-descriptions-item>
          <a-descriptions-item label="页面URL">
            {{ selectedError.url }}
          </a-descriptions-item>
          <a-descriptions-item v-if="selectedError.stack" label="错误堆栈">
            <pre class="error-stack">{{ selectedError.stack }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  ReloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  WarningOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { globalErrorHandler } from '@/lib/error-handler'
import { apiFallbackManager } from '@/lib/api-fallback'
import { optimizedQCAnalysisService } from '@/lib/qc-analysis-optimized'
import { formatDateTime } from '@/utils/date'

// 响应式数据
const loading = ref(false)
const autoRefresh = ref(true)
const refreshTimer = ref<NodeJS.Timeout | null>(null)

// 系统状态数据
const systemStatus = ref('正常')
const performanceStats = ref({
  averageResponseTime: 0,
  cacheHitRate: 0,
  totalRequests: 0
})
const errorStats = ref({
  totalErrors: 0,
  errorRate: 0,
  errorsByType: {} as Record<string, number>,
  errorsBySeverity: {} as Record<string, number>
})
const serviceHealth = ref<any[]>([])
const recentErrors = ref<any[]>([])

// 图表相关
const responseTimeChart = ref<HTMLElement>()
const errorChart = ref<HTMLElement>()

// 错误详情
const showErrorModal = ref(false)
const selectedError = ref<any>(null)

// 表格列定义
const errorColumns = [
  { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
  { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
  { title: '严重程度', dataIndex: 'severity', key: 'severity', width: 100 },
  { title: '消息', dataIndex: 'message', key: 'message', ellipsis: true },
  { title: '操作', key: 'actions', width: 80 }
]

// 方法
const refreshData = async () => {
  loading.value = true
  
  try {
    // 获取性能统计
    const perfStats = optimizedQCAnalysisService.getPerformanceStats()
    performanceStats.value = {
      averageResponseTime: perfStats.optimizer.averageResponseTime,
      cacheHitRate: perfStats.optimizer.cacheHitRate,
      totalRequests: perfStats.optimizer.totalRequests
    }

    // 获取错误统计
    const errStats = globalErrorHandler.getStats()
    errorStats.value = {
      totalErrors: errStats.totalErrors,
      errorRate: errStats.totalErrors > 0 ? errStats.totalErrors / (errStats.totalErrors + performanceStats.value.totalRequests) : 0,
      errorsByType: errStats.errorsByType,
      errorsBySeverity: errStats.errorsBySeverity
    }

    // 获取服务健康状态
    const healthMap = apiFallbackManager.getServiceHealth()
    serviceHealth.value = Array.from(healthMap.values()).map(health => ({
      name: getServiceDisplayName(health.service),
      status: health.status,
      responseTime: health.responseTime,
      lastCheck: health.lastCheck,
      error: health.error
    }))

    // 获取最近错误
    recentErrors.value = errStats.recentErrors.slice(0, 20).map((error, index) => ({
      key: index,
      ...error
    }))

    // 更新系统状态
    updateSystemStatus()

    console.log('📊 系统监控数据已更新')
  } catch (error) {
    console.error('获取监控数据失败:', error)
    message.error('获取监控数据失败')
  } finally {
    loading.value = false
  }
}

const updateSystemStatus = () => {
  const hasUnhealthyServices = serviceHealth.value.some(s => s.status !== 'healthy')
  const highErrorRate = errorStats.value.errorRate > 0.1
  const slowResponse = performanceStats.value.averageResponseTime > 5000

  if (hasUnhealthyServices || highErrorRate || slowResponse) {
    systemStatus.value = '异常'
  } else {
    systemStatus.value = '正常'
  }
}

const getServiceDisplayName = (serviceName: string): string => {
  const nameMap: Record<string, string> = {
    'deepseek-api': 'AI分析服务',
    'supabase-db': '数据库服务',
    'file-storage': '文件存储服务'
  }
  return nameMap[serviceName] || serviceName
}

const getServiceStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    healthy: 'green',
    degraded: 'orange',
    unavailable: 'red'
  }
  return colorMap[status] || 'default'
}

const getServiceStatusText = (status: string): string => {
  const textMap: Record<string, string> = {
    healthy: '正常',
    degraded: '降级',
    unavailable: '不可用'
  }
  return textMap[status] || status
}

const getErrorSeverityColor = (severity: string): string => {
  const colorMap: Record<string, string> = {
    critical: 'red',
    high: 'orange',
    medium: 'gold',
    low: 'blue'
  }
  return colorMap[severity] || 'default'
}

const formatTime = (timestamp: number): string => {
  if (!timestamp) return '未知'
  const now = Date.now()
  const diff = now - timestamp
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${Math.floor(diff / 86400000)}天前`
}

const viewErrorDetails = (error) => {
  selectedError.value = error
  showErrorModal.value = true
}

const startAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
  
  if (autoRefresh.value) {
    refreshTimer.value = setInterval(() => {
      refreshData()
    }, 30000) // 每30秒刷新一次
  }
}

// 生命周期
onMounted(() => {
  refreshData()
  startAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
})

// 监听自动刷新开关
watch(() => autoRefresh.value, () => {
  startAutoRefresh()
})
</script>

<style scoped>
.system-monitor {
  padding: 24px;
  background: #f0f2f5;
  min-height: 100vh;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 0 8px;
}

.monitor-header h1 {
  margin: 0;
  color: #1a1a1a;
  font-size: 28px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.overview-section,
.services-section,
.charts-section,
.errors-section {
  margin-bottom: 24px;
}

.metric-card {
  text-align: center;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.section-card,
.chart-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.service-item {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #d9d9d9;
  background: white;
}

.service-healthy {
  border-color: #52c41a;
  background: #f6ffed;
}

.service-degraded {
  border-color: #faad14;
  background: #fffbe6;
}

.service-unavailable {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.service-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.service-name {
  font-weight: 500;
  font-size: 16px;
}

.service-metrics {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.metric-label {
  color: #666;
}

.metric-value {
  font-weight: 500;
}

.service-error {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: #fff2f0;
  border-radius: 4px;
  border: 1px solid #ffccc7;
}

.error-label {
  color: #cf1322;
  font-weight: 500;
  font-size: 12px;
}

.error-message {
  color: #a8071a;
  font-size: 12px;
  word-break: break-all;
}

.chart-container {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  background: #fafafa;
  border-radius: 4px;
}

.error-details .error-stack {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .system-monitor {
    padding: 16px;
  }
  
  .monitor-header {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }
  
  .monitor-header h1 {
    font-size: 24px;
  }
  
  .service-metrics {
    gap: 6px;
  }
  
  .metric {
    font-size: 13px;
  }
}
</style>
