<template>
  <div class="data-analytics">
    <div class="header">
      <h2>数据分析中心</h2>
      <div class="controls">
        <a-select v-model:value="timeRange" @change="refreshData" style="width: 120px; margin-right: 16px">
          <a-select-option value="7d">最近7天</a-select-option>
          <a-select-option value="30d">最近30天</a-select-option>
          <a-select-option value="90d">最近90天</a-select-option>
        </a-select>
        <a-select v-model:value="granularity" @change="refreshData" style="width: 100px; margin-right: 16px">
          <a-select-option value="day">按天</a-select-option>
          <a-select-option value="week">按周</a-select-option>
          <a-select-option value="month">按月</a-select-option>
        </a-select>
        <a-button type="primary" @click="refreshData" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </div>
    </div>

    <!-- 概览指标 -->
    <a-row :gutter="16" class="overview-metrics">
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="总违规数"
            :value="overview.total_violations"
            :value-style="{ color: '#1890ff' }"
          >
            <template #prefix><ExclamationCircleOutlined /></template>
          </a-statistic>
          <div class="metric-trend">
            <span :class="getTrendClass(trendAnalysis?.total_trend?.trend)">
              {{ getTrendText(trendAnalysis?.total_trend?.trend) }}
              {{ (trendAnalysis?.total_trend?.slope || 0).toFixed(2) }}
            </span>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="涉及就诊数"
            :value="overview.unique_visits"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix><UserOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="触发规则数"
            :value="overview.unique_rules"
            :value-style="{ color: '#722ed1' }"
          >
            <template #prefix><SettingOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="异常天数"
            :value="anomalyData?.anomalies?.length || 0"
            :value-style="{ color: anomalyData?.anomalies?.length > 0 ? '#ff4d4f' : '#52c41a' }"
          >
            <template #prefix><AlertOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 趋势图表 -->
    <a-row :gutter="16" class="charts-row">
      <a-col :span="16">
        <a-card title="违规趋势分析" class="trend-chart-card">
          <div class="chart-controls">
            <a-radio-group v-model:value="chartType" @change="updateChart">
              <a-radio-button value="line">折线图</a-radio-button>
              <a-radio-button value="bar">柱状图</a-radio-button>
              <a-radio-button value="area">面积图</a-radio-button>
            </a-radio-group>
            <a-switch 
              v-model:checked="showMovingAverage" 
              @change="updateChart"
              checked-children="移动平均"
              un-checked-children="原始数据"
            />
          </div>
          <div ref="trendChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="严重程度分布" class="severity-chart-card">
          <div ref="severityChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 详细分析 -->
    <a-row :gutter="16" class="analysis-row">
      <a-col :span="12">
        <a-card title="规则类型分析">
          <div class="rule-type-analysis">
            <div v-for="item in ruleTypeAnalysis" :key="item.rule_type" class="rule-type-item">
              <div class="rule-type-header">
                <span class="rule-type-name">{{ item.rule_type }}</span>
                <span class="rule-type-count">{{ item.total_violations }}</span>
              </div>
              <div class="rule-type-bar">
                <div class="severity-segment block" :style="{ width: `${item.severity_breakdown.block / item.total_violations * 100}%` }"></div>
                <div class="severity-segment warn" :style="{ width: `${item.severity_breakdown.warn / item.total_violations * 100}%` }"></div>
                <div class="severity-segment info" :style="{ width: `${item.severity_breakdown.info / item.total_violations * 100}%` }"></div>
              </div>
              <div class="rule-type-stats">
                <span class="stat">规则数: {{ item.unique_rules }}</span>
                <span class="stat">占比: {{ (item.violation_rate * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="时间分布模式">
          <div ref="hourlyChartRef" class="chart-container"></div>
          <div class="time-insights">
            <a-alert 
              v-if="timePatterns?.peak_hour"
              :message="`高峰时段: ${timePatterns.peak_hour}:00 - ${(parseInt(timePatterns.peak_hour) + 1)}:00`"
              type="info"
              show-icon
            />
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 异常检测 -->
    <a-card title="异常检测分析" class="anomaly-card">
      <div class="anomaly-controls">
        <span>敏感度:</span>
        <a-slider 
          v-model:value="anomalySensitivity" 
          :min="1" 
          :max="3" 
          :step="0.1"
          :tooltip-formatter="(value) => `${value}σ`"
          @change="refreshAnomalyData"
          style="width: 200px; margin: 0 16px"
        />
        <a-button @click="refreshAnomalyData" size="small">
          <template #icon><SearchOutlined /></template>
          重新检测
        </a-button>
      </div>
      <div v-if="anomalyData?.anomalies?.length > 0" class="anomaly-list">
        <h4>检测到 {{ anomalyData.anomalies.length }} 个异常点:</h4>
        <div class="anomaly-items">
          <div v-for="anomaly in anomalyData.anomalies" :key="anomaly.date" class="anomaly-item">
            <a-tag :color="anomaly.severity === 'high' ? 'red' : 'blue'">
              {{ anomaly.date }}
            </a-tag>
            <span class="anomaly-value">{{ anomaly.violations }} 次违规</span>
            <span class="anomaly-score">Z-Score: {{ anomaly.z_score.toFixed(2) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="no-anomalies">
        <a-empty description="未检测到异常数据点" />
      </div>
    </a-card>

    <!-- 规则效率排行 -->
    <a-card title="规则效率排行" class="rule-efficiency-card">
      <a-table 
        :dataSource="ruleEfficiency" 
        :columns="ruleEfficiencyColumns"
        :pagination="{ pageSize: 10 }"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'efficiency_score'">
            <a-progress 
              :percent="Math.min(record.efficiency_score * 20, 100)" 
              size="small"
              :format="() => record.efficiency_score.toFixed(2)"
            />
          </template>
          <template v-if="column.key === 'rule_type'">
            <a-tag>{{ record.rule_type }}</a-tag>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import AnalyticsService from '@/services/analyticsService'
import {
  ReloadOutlined,
  ExclamationCircleOutlined,
  UserOutlined,
  SettingOutlined,
  AlertOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const timeRange = ref('30d')
const granularity = ref('day')
const chartType = ref('line')
const showMovingAverage = ref(false)
const anomalySensitivity = ref(2.0)

// 数据状态
const overview = ref<any>({})
const trendsData = ref<any[]>([])
const trendAnalysis = ref<any>(null)
const violationAnalysis = ref<any>({})
const ruleTypeAnalysis = ref<any[]>([])
const timePatterns = ref<any>(null)
const anomalyData = ref<any>(null)
const ruleEfficiency = ref<any[]>([])

// 图表引用
const trendChartRef = ref<HTMLDivElement>()
const severityChartRef = ref<HTMLDivElement>()
const hourlyChartRef = ref<HTMLDivElement>()

// 图表实例
let trendChart: echarts.ECharts | null = null
let severityChart: echarts.ECharts | null = null
let hourlyChart: echarts.ECharts | null = null

// 表格列定义
const ruleEfficiencyColumns = [
  { title: '规则编码', dataIndex: 'code', key: 'code' },
  { title: '规则名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '类型', dataIndex: 'rule_type', key: 'rule_type' },
  { title: '违规次数', dataIndex: 'violations', key: 'violations' },
  { title: '涉及就诊', dataIndex: 'unique_visits', key: 'unique_visits' },
  { title: '效率评分', dataIndex: 'efficiency_score', key: 'efficiency_score' }
]

// 获取数据
const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchTrendsData(),
      fetchViolationAnalysis(),
      fetchAnomalyData()
    ])
    
    await nextTick()
    initCharts()
  } catch (error) {
    message.error('数据加载失败')
    console.error('Failed to fetch analytics data:', error)
  } finally {
    loading.value = false
  }
}

const fetchTrendsData = async () => {
  try {
    const days = parseInt(timeRange.value)
    const data = await AnalyticsService.getTrendsAnalysis({
      days,
      granularity: granularity.value,
      includeAnalysis: true
    })

    trendsData.value = data.trends || []
    trendAnalysis.value = data.analysis
    overview.value = {
      total_violations: data.analysis?.summary?.total_violations || 0,
      unique_visits: trendsData.value.reduce((sum, item) => sum + item.unique_visits, 0),
      unique_rules: Math.max(...trendsData.value.map(item => item.unique_rules), 0)
    }
  } catch (error) {
    console.error('Failed to fetch trends data:', error)
    throw error
  }
}

const fetchViolationAnalysis = async () => {
  try {
    const data = await AnalyticsService.getViolationAnalysis({
      timeRange: timeRange.value,
      groupBy: 'rule_type'
    })

    violationAnalysis.value = data
    ruleTypeAnalysis.value = data.by_rule_type || []
    timePatterns.value = data.temporal_patterns
    ruleEfficiency.value = data.rule_efficiency || []
  } catch (error) {
    console.error('Failed to fetch violation analysis:', error)
    throw error
  }
}

const fetchAnomalyData = async () => {
  try {
    const days = parseInt(timeRange.value)
    const data = await AnalyticsService.detectAnomalies({
      days,
      sensitivity: anomalySensitivity.value
    })

    anomalyData.value = data
  } catch (error) {
    console.error('Failed to fetch anomaly data:', error)
    throw error
  }
}

const refreshAnomalyData = async () => {
  await fetchAnomalyData()
}

// 图表初始化和更新
const initCharts = () => {
  initTrendChart()
  initSeverityChart()
  initHourlyChart()
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  
  trendChart = echarts.init(trendChartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!trendChart || !trendsData.value.length) return
  
  const dates = trendsData.value.map(item => item.date)
  const blockData = trendsData.value.map(item => item.block)
  const warnData = trendsData.value.map(item => item.warn)
  const infoData = trendsData.value.map(item => item.info)
  const totalData = trendsData.value.map(item => item.total)
  
  const series: any[] = [
    {
      name: '阻断',
      type: chartType.value,
      data: blockData,
      color: '#ff4d4f',
      areaStyle: chartType.value === 'area' ? {} : undefined
    },
    {
      name: '警告',
      type: chartType.value,
      data: warnData,
      color: '#faad14',
      areaStyle: chartType.value === 'area' ? {} : undefined
    },
    {
      name: '提醒',
      type: chartType.value,
      data: infoData,
      color: '#1890ff',
      areaStyle: chartType.value === 'area' ? {} : undefined
    }
  ]
  
  if (showMovingAverage.value && trendAnalysis.value?.moving_averages) {
    series.push({
      name: '7日均线',
      type: 'line',
      data: trendAnalysis.value.moving_averages.total_7day,
      color: '#722ed1',
      lineStyle: { type: 'dashed' }
    })
  }
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: series.map(s => s.name)
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: {
      type: 'value'
    },
    series
  }
  
  trendChart.setOption(option)
}

const initSeverityChart = () => {
  if (!severityChartRef.value || !violationAnalysis.value.severity_distribution) return
  
  if (severityChart) {
    severityChart.dispose()
  }
  
  severityChart = echarts.init(severityChartRef.value)
  
  const data = [
    { name: '阻断', value: violationAnalysis.value.severity_distribution.block.count, itemStyle: { color: '#ff4d4f' } },
    { name: '警告', value: violationAnalysis.value.severity_distribution.warn.count, itemStyle: { color: '#faad14' } },
    { name: '提醒', value: violationAnalysis.value.severity_distribution.info.count, itemStyle: { color: '#1890ff' } }
  ]
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    series: [{
      name: '严重程度',
      type: 'pie',
      radius: '70%',
      data,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  }
  
  severityChart.setOption(option)
}

const initHourlyChart = () => {
  if (!hourlyChartRef.value || !timePatterns.value?.hourly_distribution) return
  
  if (hourlyChart) {
    hourlyChart.dispose()
  }
  
  hourlyChart = echarts.init(hourlyChartRef.value)
  
  const hours = timePatterns.value.hourly_distribution.map((item: any) => `${item.hour}:00`)
  const counts = timePatterns.value.hourly_distribution.map((item: any) => item.count)
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: hours
    },
    yAxis: {
      type: 'value'
    },
    series: [{
      name: '违规次数',
      type: 'bar',
      data: counts,
      itemStyle: {
        color: '#1890ff'
      }
    }]
  }
  
  hourlyChart.setOption(option)
}

// 工具函数
const getTrendClass = (trend: string) => {
  return {
    'trend-up': trend === 'increasing',
    'trend-down': trend === 'decreasing',
    'trend-stable': trend === 'stable'
  }
}

const getTrendText = (trend: string) => {
  const trendMap: Record<string, string> = {
    increasing: '↗ 上升',
    decreasing: '↘ 下降',
    stable: '→ 平稳'
  }
  return trendMap[trend] || '→ 平稳'
}

// 生命周期
onMounted(() => {
  refreshData()
  
  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    trendChart?.resize()
    severityChart?.resize()
    hourlyChart?.resize()
  })
})
</script>

<style scoped>
.data-analytics {
  padding: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.overview-metrics {
  margin-bottom: 24px;
}

.metric-trend {
  margin-top: 8px;
  font-size: 12px;
}

.trend-up {
  color: #ff4d4f;
}

.trend-down {
  color: #52c41a;
}

.trend-stable {
  color: #1890ff;
}

.charts-row {
  margin-bottom: 24px;
}

.chart-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-container {
  height: 300px;
}

.analysis-row {
  margin-bottom: 24px;
}

.rule-type-analysis {
  max-height: 300px;
  overflow-y: auto;
}

.rule-type-item {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
}

.rule-type-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.rule-type-name {
  font-weight: 500;
}

.rule-type-count {
  color: #1890ff;
  font-weight: 600;
}

.rule-type-bar {
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  margin-bottom: 8px;
}

.severity-segment {
  height: 100%;
}

.severity-segment.block {
  background-color: #ff4d4f;
}

.severity-segment.warn {
  background-color: #faad14;
}

.severity-segment.info {
  background-color: #1890ff;
}

.rule-type-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #666;
}

.time-insights {
  margin-top: 16px;
}

.anomaly-card {
  margin-bottom: 24px;
}

.anomaly-controls {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.anomaly-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.anomaly-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

.anomaly-value {
  font-weight: 500;
}

.anomaly-score {
  font-size: 12px;
  color: #666;
}

.no-anomalies {
  text-align: center;
  padding: 40px;
}

.rule-efficiency-card {
  margin-bottom: 24px;
}
</style>
