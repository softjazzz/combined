<template>
  <div class="performance-monitor">
    <div class="header">
      <h2>质控引擎性能监控</h2>
      <div class="controls">
        <a-select v-model:value="timeRange" @change="refreshStats" style="width: 120px; margin-right: 16px">
          <a-select-option value="1h">最近1小时</a-select-option>
          <a-select-option value="24h">最近24小时</a-select-option>
          <a-select-option value="7d">最近7天</a-select-option>
        </a-select>
        <a-button type="primary" @click="refreshStats" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
        <a-button @click="runBenchmark" :loading="benchmarkLoading" style="margin-left: 8px">
          <template #icon><ThunderboltOutlined /></template>
          性能测试
        </a-button>
      </div>
    </div>

    <!-- 健康状态 -->
    <a-card title="系统健康状态" class="health-card" :class="healthStatus.status">
      <div class="health-indicators">
        <div class="indicator">
          <div class="status-dot" :class="healthStatus.status"></div>
          <span class="status-text">{{ getStatusText(healthStatus.status) }}</span>
        </div>
        <div class="indicator">
          <DatabaseOutlined />
          <span>数据库延迟: {{ healthStatus.database?.latency_ms || 0 }}ms</span>
        </div>
        <div class="indicator">
          <ClockCircleOutlined />
          <span>最后更新: {{ formatTime(healthStatus.timestamp) }}</span>
        </div>
      </div>
    </a-card>

    <!-- 性能指标 -->
    <a-row :gutter="16" class="metrics-row">
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="总评估次数"
            :value="performanceStats.total_evaluations"
            :value-style="{ color: '#1890ff' }"
          >
            <template #prefix><BarChartOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="平均执行时间"
            :value="performanceStats.avg_execution_time_ms"
            suffix="ms"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix><ClockCircleOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="缓存命中率"
            :value="(performanceStats.cache_hit_rate * 100).toFixed(1)"
            suffix="%"
            :value-style="{ color: '#722ed1' }"
          >
            <template #prefix><DatabaseOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="错误率"
            :value="(performanceStats.error_rate * 100).toFixed(2)"
            suffix="%"
            :value-style="{ color: performanceStats.error_rate > 0.01 ? '#ff4d4f' : '#52c41a' }"
          >
            <template #prefix><ExclamationCircleOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 详细指标 -->
    <a-row :gutter="16" class="details-row">
      <a-col :span="12">
        <a-card title="规则分布">
          <div class="chart-container">
            <div class="rule-stats">
              <div class="stat-item">
                <span class="label">按严重程度:</span>
                <div class="severity-bars">
                  <div v-for="(count, severity) in detailedMetrics.rule_distribution?.by_severity" :key="severity" class="severity-bar">
                    <span class="severity-label" :class="severity">{{ severity }}</span>
                    <div class="bar">
                      <div class="fill" :style="{ width: `${(count / detailedMetrics.rule_distribution?.total_active * 100)}%` }"></div>
                    </div>
                    <span class="count">{{ count }}</span>
                  </div>
                </div>
              </div>
              <div class="stat-item">
                <span class="label">按类型:</span>
                <div class="type-list">
                  <div v-for="(count, type) in detailedMetrics.rule_distribution?.by_type" :key="type" class="type-item">
                    <span class="type-name">{{ type }}</span>
                    <span class="type-count">{{ count }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="违规趋势">
          <div class="violation-trend">
            <div v-if="Object.keys(detailedMetrics.violation_trend || {}).length === 0" class="no-data">
              暂无违规数据
            </div>
            <div v-else class="trend-chart">
              <div v-for="(data, date) in detailedMetrics.violation_trend" :key="date" class="trend-item">
                <span class="date">{{ formatDate(date) }}</span>
                <div class="trend-bar">
                  <div class="warn-bar" :style="{ width: `${data.warn * 10}px` }" title="警告"></div>
                  <div class="block-bar" :style="{ width: `${data.block * 10}px` }" title="阻断"></div>
                </div>
                <span class="count">{{ data.total }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 基准测试结果 -->
    <a-card v-if="benchmarkResult" title="性能基准测试结果" class="benchmark-card">
      <div class="benchmark-summary">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic
              title="吞吐量"
              :value="benchmarkResult.results?.throughput_contexts_per_second"
              suffix="次/秒"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="平均批次时间"
              :value="benchmarkResult.results?.avg_batch_time_ms"
              suffix="ms"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="违规检出率"
              :value="(benchmarkResult.results?.violation_rate * 100).toFixed(1)"
              suffix="%"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="测试上下文"
              :value="benchmarkResult.test_parameters?.test_contexts"
              suffix="个"
            />
          </a-col>
        </a-row>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const benchmarkLoading = ref(false)
const timeRange = ref('24h')
const healthStatus = ref<any>({})
const performanceStats = ref<any>({})
const detailedMetrics = ref<any>({})
const benchmarkResult = ref<any>(null)

// 获取性能统计
const refreshStats = async () => {
  loading.value = true
  try {
    // 并行获取所有数据
    const [healthRes, statsRes, metricsRes] = await Promise.all([
      fetch('/api/supabase/functions/rule-performance-monitor/health'),
      fetch(`/api/supabase/functions/rule-performance-monitor/stats?time_range=${timeRange.value}`),
      fetch('/api/supabase/functions/rule-performance-monitor/metrics')
    ])

    if (healthRes.ok) {
      healthStatus.value = await healthRes.json()
    }
    if (statsRes.ok) {
      performanceStats.value = await statsRes.json()
    }
    if (metricsRes.ok) {
      detailedMetrics.value = await metricsRes.json()
    }
  } catch (error) {
    message.error('获取性能数据失败')
    console.error('Failed to fetch performance data:', error)
  } finally {
    loading.value = false
  }
}

// 运行基准测试
const runBenchmark = async () => {
  benchmarkLoading.value = true
  try {
    const response = await fetch('/api/supabase/functions/rule-performance-monitor/benchmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        test_contexts: 100,
        concurrent_requests: 5
      })
    })

    if (response.ok) {
      benchmarkResult.value = await response.json()
      message.success('基准测试完成')
    } else {
      message.error('基准测试失败')
    }
  } catch (error) {
    message.error('基准测试失败')
    console.error('Benchmark failed:', error)
  } finally {
    benchmarkLoading.value = false
  }
}

// 工具函数
const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    healthy: '健康',
    degraded: '降级',
    unhealthy: '异常'
  }
  return statusMap[status] || '未知'
}

const formatTime = (timestamp: string) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleTimeString()
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString()
}

// 生命周期
onMounted(() => {
  refreshStats()
  // 每30秒自动刷新
  setInterval(refreshStats, 30000)
})
</script>

<style scoped>
.performance-monitor {
  padding: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.health-card {
  margin-bottom: 24px;
}

.health-card.healthy {
  border-color: #52c41a;
}

.health-card.degraded {
  border-color: #faad14;
}

.health-card.unhealthy {
  border-color: #ff4d4f;
}

.health-indicators {
  display: flex;
  gap: 24px;
  align-items: center;
}

.indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status-dot.healthy {
  background-color: #52c41a;
}

.status-dot.degraded {
  background-color: #faad14;
}

.status-dot.unhealthy {
  background-color: #ff4d4f;
}

.metrics-row {
  margin-bottom: 24px;
}

.details-row {
  margin-bottom: 24px;
}

.rule-stats .stat-item {
  margin-bottom: 16px;
}

.severity-bars .severity-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.severity-label {
  width: 60px;
  font-size: 12px;
}

.severity-label.warn {
  color: #faad14;
}

.severity-label.block {
  color: #ff4d4f;
}

.bar {
  flex: 1;
  height: 16px;
  background-color: #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
}

.bar .fill {
  height: 100%;
  background-color: #1890ff;
  transition: width 0.3s;
}

.type-list .type-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.violation-trend .trend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.trend-bar {
  display: flex;
  gap: 2px;
}

.warn-bar {
  height: 16px;
  background-color: #faad14;
  min-width: 2px;
}

.block-bar {
  height: 16px;
  background-color: #ff4d4f;
  min-width: 2px;
}

.benchmark-card {
  margin-top: 24px;
}

.no-data {
  text-align: center;
  color: #999;
  padding: 40px;
}
</style>
