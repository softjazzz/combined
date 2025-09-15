<template>
  <div class="advanced-analytics">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1>高级数据分析</h1>
        <p>智慧医保质控系统 - 深度数据洞察与预测分析</p>
      </div>
      <div class="header-actions">
        <a-space>
          <a-select v-model:value="timeRange" @change="refreshAllData" style="width: 120px">
            <a-select-option value="7d">最近7天</a-select-option>
            <a-select-option value="30d">最近30天</a-select-option>
            <a-select-option value="90d">最近90天</a-select-option>
            <a-select-option value="180d">最近半年</a-select-option>
          </a-select>
          <a-button type="primary" @click="exportReport" :loading="exporting">
            <template #icon><DownloadOutlined /></template>
            导出报告
          </a-button>
          <a-button @click="refreshAllData" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新数据
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <div class="metrics-grid">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="6" v-for="metric in coreMetrics" :key="metric.key">
          <a-card class="metric-card" :class="metric.trend">
            <div class="metric-content">
              <div class="metric-icon" :style="{ backgroundColor: metric.color + '20' }">
                <component :is="metric.icon" :style="{ color: metric.color }" />
              </div>
              <div class="metric-info">
                <div class="metric-title">{{ metric.title }}</div>
                <div class="metric-value">{{ metric.value }}</div>
                <div class="metric-change">
                  <component :is="metric.trendIcon" />
                  {{ metric.change }}
                </div>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 主要分析区域 -->
    <div class="analysis-section">
      <a-row :gutter="[24, 24]">
        <!-- 趋势预测分析 -->
        <a-col :xs="24" :lg="16">
          <a-card title="趋势预测分析" class="chart-card">
            <template #extra>
              <a-space>
                <a-select v-model:value="predictionModel" @change="updatePredictions" size="small">
                  <a-select-option value="linear">线性回归</a-select-option>
                  <a-select-option value="moving_average">移动平均</a-select-option>
                  <a-select-option value="seasonal">季节性模式</a-select-option>
                </a-select>
                <a-tooltip title="预测准确度">
                  <a-tag :color="getConfidenceColor(predictionConfidence)">
                    置信度: {{ (predictionConfidence * 100).toFixed(1) }}%
                  </a-tag>
                </a-tooltip>
              </a-space>
            </template>
            <div class="prediction-chart-container">
              <div ref="predictionChartRef" class="chart-container"></div>
            </div>
          </a-card>
        </a-col>

        <!-- 实时监控面板 -->
        <a-col :xs="24" :lg="8">
          <a-card title="实时监控" class="monitoring-card">
            <div class="monitoring-content">
              <div class="status-indicator">
                <div class="status-light" :class="systemStatus.level"></div>
                <div class="status-text">
                  <div class="status-title">系统状态: {{ systemStatus.text }}</div>
                  <div class="status-time">最后更新: {{ systemStatus.lastUpdate }}</div>
                </div>
              </div>
              
              <div class="alert-list">
                <h4>风险预警</h4>
                <div v-if="alerts.length === 0" class="no-alerts">
                  <a-empty description="暂无风险预警" :image="false" />
                </div>
                <div v-else class="alert-items">
                  <div v-for="alert in alerts" :key="alert.id" class="alert-item" :class="alert.level">
                    <div class="alert-icon">
                      <ExclamationCircleOutlined v-if="alert.level === 'high'" />
                      <WarningOutlined v-else-if="alert.level === 'medium'" />
                      <InfoCircleOutlined v-else />
                    </div>
                    <div class="alert-content">
                      <div class="alert-title">{{ alert.title }}</div>
                      <div class="alert-description">{{ alert.description }}</div>
                      <div class="alert-time">{{ alert.time }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 多维度分析 -->
    <div class="multi-dimension-analysis">
      <a-row :gutter="[24, 24]">
        <!-- 科室对比分析 -->
        <a-col :xs="24" :lg="12">
          <a-card title="科室绩效对比" class="comparison-card">
            <template #extra>
              <a-radio-group v-model:value="comparisonMetric" @change="updateComparisonChart" size="small">
                <a-radio-button value="violation_rate">违规率</a-radio-button>
                <a-radio-button value="quality_score">质控评分</a-radio-button>
                <a-radio-button value="improvement">改进幅度</a-radio-button>
              </a-radio-group>
            </template>
            <div ref="comparisonChartRef" class="chart-container"></div>
          </a-card>
        </a-col>

        <!-- 规则效率分析 -->
        <a-col :xs="24" :lg="12">
          <a-card title="规则效率分析" class="efficiency-card">
            <template #extra>
              <a-tooltip title="效率评分 = 违规检出数 / 规则复杂度">
                <InfoCircleOutlined />
              </a-tooltip>
            </template>
            <div ref="efficiencyChartRef" class="chart-container"></div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 异常检测与智能分析 -->
    <div class="anomaly-detection">
      <a-card title="异常检测与智能分析" class="anomaly-card">
        <div class="anomaly-controls">
          <a-space>
            <span>检测敏感度:</span>
            <a-slider 
              v-model:value="anomalySensitivity" 
              :min="1" 
              :max="3" 
              :step="0.1"
              :tooltip-formatter="(value) => `${value}σ`"
              @change="runAnomalyDetection"
              style="width: 200px"
            />
            <a-button @click="runAnomalyDetection" size="small">
              <template #icon><SearchOutlined /></template>
              重新检测
            </a-button>
            <a-switch 
              v-model:checked="autoDetection" 
              checked-children="自动检测"
              un-checked-children="手动检测"
            />
          </a-space>
        </div>

        <div class="anomaly-results">
          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :lg="16">
              <div ref="anomalyChartRef" class="chart-container"></div>
            </a-col>
            <a-col :xs="24" :lg="8">
              <div class="anomaly-insights">
                <h4>异常洞察</h4>
                <div v-if="anomalyInsights.length === 0" class="no-insights">
                  <a-empty description="未发现异常模式" :image="false" />
                </div>
                <div v-else class="insight-list">
                  <div v-for="insight in anomalyInsights" :key="insight.id" class="insight-item">
                    <a-tag :color="insight.severity === 'high' ? 'red' : 'orange'">
                      {{ insight.type }}
                    </a-tag>
                    <div class="insight-content">
                      <div class="insight-title">{{ insight.title }}</div>
                      <div class="insight-description">{{ insight.description }}</div>
                      <div class="insight-recommendation">
                        <strong>建议:</strong> {{ insight.recommendation }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </a-col>
          </a-row>
        </div>
      </a-card>
    </div>

    <!-- 导出报告模态框 -->
    <a-modal
      v-model:open="exportModalVisible"
      title="导出数据报告"
      @ok="handleExport"
      :confirm-loading="exporting"
      width="600px"
    >
      <div class="export-form">
        <a-form layout="vertical">
          <a-form-item label="报告模板">
            <a-select v-model:value="selectedTemplate" placeholder="选择报告模板">
              <a-select-option v-for="template in reportTemplates" :key="template.id" :value="template.id">
                {{ template.name }} - {{ template.description }}
              </a-select-option>
            </a-select>
          </a-form-item>
          
          <a-form-item label="导出格式">
            <a-radio-group v-model:value="exportFormat">
              <a-radio value="excel">Excel (.xlsx)</a-radio>
              <a-radio value="csv">CSV (.csv)</a-radio>
              <a-radio value="pdf">PDF (.pdf)</a-radio>
            </a-radio-group>
          </a-form-item>
          
          <a-form-item label="时间范围">
            <a-range-picker v-model:value="exportDateRange" />
          </a-form-item>
          
          <a-form-item label="包含内容">
            <a-checkbox-group v-model:value="exportOptions">
              <a-checkbox value="summary">汇总统计</a-checkbox>
              <a-checkbox value="trends">趋势分析</a-checkbox>
              <a-checkbox value="predictions">预测数据</a-checkbox>
              <a-checkbox value="anomalies">异常检测</a-checkbox>
              <a-checkbox value="recommendations">改进建议</a-checkbox>
            </a-checkbox-group>
          </a-form-item>
        </a-form>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import {
  DownloadOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  SearchOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const exporting = ref(false)
const timeRange = ref('30d')
const predictionModel = ref('linear')
const predictionConfidence = ref(0.75)
const comparisonMetric = ref('violation_rate')
const anomalySensitivity = ref(2.0)
const autoDetection = ref(true)

// 导出相关
const exportModalVisible = ref(false)
const selectedTemplate = ref('')
const exportFormat = ref('excel')
const exportDateRange = ref([])
const exportOptions = ref(['summary', 'trends'])

// 数据状态
const coreMetrics = ref([
  {
    key: 'total_violations',
    title: '总违规数',
    value: '1,234',
    change: '+12.5%',
    trend: 'increasing',
    color: '#ff4d4f',
    icon: ExclamationCircleOutlined,
    trendIcon: ArrowUpOutlined
  },
  {
    key: 'avg_quality_score',
    title: '平均质控评分',
    value: '87.3',
    change: '+2.1%',
    trend: 'increasing',
    color: '#52c41a',
    icon: ArrowUpOutlined,
    trendIcon: ArrowUpOutlined
  },
  {
    key: 'high_risk_departments',
    title: '高风险科室',
    value: '3',
    change: '-1',
    trend: 'decreasing',
    color: '#faad14',
    icon: WarningOutlined,
    trendIcon: ArrowDownOutlined
  },
  {
    key: 'prediction_accuracy',
    title: '预测准确度',
    value: '75.2%',
    change: '0%',
    trend: 'stable',
    color: '#1890ff',
    icon: InfoCircleOutlined,
    trendIcon: MinusOutlined
  }
])

const systemStatus = ref({
  level: 'normal',
  text: '正常',
  lastUpdate: '2分钟前'
})

const alerts = ref([
  {
    id: 1,
    level: 'high',
    title: '心内科违规率异常',
    description: '今日违规率较昨日上升45%，建议立即关注',
    time: '5分钟前'
  },
  {
    id: 2,
    level: 'medium',
    title: '新规则命中率低',
    description: '规则YB001近7天命中率仅为2.1%，建议优化',
    time: '1小时前'
  }
])

const anomalyInsights = ref([
  {
    id: 1,
    type: '趋势异常',
    severity: 'high',
    title: '违规数量突增',
    description: '检测到昨日违规数量较平均水平高出3.2σ',
    recommendation: '建议检查是否有新的医疗政策变化或系统异常'
  }
])

const reportTemplates = ref([
  { id: 'violations_summary', name: '违规汇总报告', description: '按时间范围统计的违规数据汇总' },
  { id: 'department_performance', name: '科室质控绩效报告', description: '各科室质控表现对比分析' },
  { id: 'doctor_quality_profile', name: '医生质控档案', description: '医生个人质控表现详细档案' }
])

// 图表引用
const predictionChartRef = ref<HTMLDivElement>()
const comparisonChartRef = ref<HTMLDivElement>()
const efficiencyChartRef = ref<HTMLDivElement>()
const anomalyChartRef = ref<HTMLDivElement>()

// 图表实例
let predictionChart: echarts.ECharts | null = null
let comparisonChart: echarts.ECharts | null = null
let efficiencyChart: echarts.ECharts | null = null
let anomalyChart: echarts.ECharts | null = null

// 方法
const refreshAllData = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadPredictionData(),
      loadComparisonData(),
      loadEfficiencyData(),
      loadAnomalyData()
    ])
    
    await nextTick()
    initAllCharts()
  } catch (error) {
    message.error('数据加载失败')
    console.error('Failed to refresh data:', error)
  } finally {
    loading.value = false
  }
}

const loadPredictionData = async () => {
  // 加载预测数据的逻辑
}

const loadComparisonData = async () => {
  // 加载对比数据的逻辑
}

const loadEfficiencyData = async () => {
  // 加载效率数据的逻辑
}

const loadAnomalyData = async () => {
  // 加载异常检测数据的逻辑
}

const initAllCharts = () => {
  initPredictionChart()
  initComparisonChart()
  initEfficiencyChart()
  initAnomalyChart()
}

const initPredictionChart = () => {
  if (!predictionChartRef.value) return
  
  if (predictionChart) {
    predictionChart.dispose()
  }
  
  predictionChart = echarts.init(predictionChartRef.value)
  updatePredictions()
}

const updatePredictions = () => {
  if (!predictionChart) return
  
  // 预测图表配置
  const option = {
    title: {
      text: '违规趋势预测',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['历史数据', '预测数据', '置信区间']
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '历史数据',
        type: 'line',
        data: [120, 132, 101, 134, 90, 230, 210]
      },
      {
        name: '预测数据',
        type: 'line',
        data: [null, null, null, null, null, 230, 240],
        lineStyle: {
          type: 'dashed'
        }
      }
    ]
  }
  
  predictionChart.setOption(option)
}

const initComparisonChart = () => {
  if (!comparisonChartRef.value) return
  
  if (comparisonChart) {
    comparisonChart.dispose()
  }
  
  comparisonChart = echarts.init(comparisonChartRef.value)
  updateComparisonChart()
}

const updateComparisonChart = () => {
  if (!comparisonChart) return
  
  // 科室对比图表配置
  const option = {
    title: {
      text: '科室绩效对比'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: ['心内科', '神经科', '骨科', '外科', '儿科']
    },
    yAxis: {
      type: 'value'
    },
    series: [{
      name: comparisonMetric.value,
      type: 'bar',
      data: [2.3, 1.8, 3.1, 2.7, 1.5],
      itemStyle: {
        color: '#1890ff'
      }
    }]
  }
  
  comparisonChart.setOption(option)
}

const initEfficiencyChart = () => {
  if (!efficiencyChartRef.value) return
  
  if (efficiencyChart) {
    efficiencyChart.dispose()
  }
  
  efficiencyChart = echarts.init(efficiencyChartRef.value)
  
  // 规则效率图表配置
  const option = {
    title: {
      text: '规则效率分析'
    },
    tooltip: {
      trigger: 'item'
    },
    series: [{
      name: '规则效率',
      type: 'pie',
      radius: '70%',
      data: [
        { value: 35, name: '高效规则' },
        { value: 45, name: '中效规则' },
        { value: 20, name: '低效规则' }
      ]
    }]
  }
  
  efficiencyChart.setOption(option)
}

const initAnomalyChart = () => {
  if (!anomalyChartRef.value) return
  
  if (anomalyChart) {
    anomalyChart.dispose()
  }
  
  anomalyChart = echarts.init(anomalyChartRef.value)
  
  // 异常检测图表配置
  const option = {
    title: {
      text: '异常检测结果'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '正常数据',
        type: 'line',
        data: [45, 52, 48, 61, 55, 42, 38]
      },
      {
        name: '异常点',
        type: 'scatter',
        data: [[3, 85], [5, 15]],
        symbolSize: 15,
        itemStyle: {
          color: '#ff4d4f'
        }
      }
    ]
  }
  
  anomalyChart.setOption(option)
}

const runAnomalyDetection = () => {
  // 运行异常检测的逻辑
  message.info('正在运行异常检测...')
}

const exportReport = () => {
  exportModalVisible.value = true
}

const handleExport = async () => {
  exporting.value = true
  try {
    // 导出报告的逻辑
    await new Promise(resolve => setTimeout(resolve, 2000)) // 模拟导出过程
    message.success('报告导出成功')
    exportModalVisible.value = false
  } catch (error) {
    message.error('报告导出失败')
  } finally {
    exporting.value = false
  }
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return 'green'
  if (confidence >= 0.6) return 'orange'
  return 'red'
}

// 生命周期
onMounted(() => {
  refreshAllData()
  
  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    predictionChart?.resize()
    comparisonChart?.resize()
    efficiencyChart?.resize()
    anomalyChart?.resize()
  })
})
</script>

<style scoped>
.advanced-analytics {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #262626;
}

.header-content p {
  margin: 4px 0 0 0;
  color: #8c8c8c;
}

.metrics-grid {
  margin-bottom: 24px;
}

.metric-card {
  height: 120px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.metric-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  font-size: 24px;
}

.metric-info {
  flex: 1;
}

.metric-title {
  font-size: 14px;
  color: #8c8c8c;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 4px;
}

.metric-change {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.metric-card.increasing .metric-change {
  color: #ff4d4f;
}

.metric-card.decreasing .metric-change {
  color: #52c41a;
}

.metric-card.stable .metric-change {
  color: #1890ff;
}

.analysis-section,
.multi-dimension-analysis,
.anomaly-detection {
  margin-bottom: 24px;
}

.chart-card,
.monitoring-card,
.comparison-card,
.efficiency-card,
.anomaly-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chart-container {
  height: 400px;
  width: 100%;
}

.prediction-chart-container .chart-container {
  height: 350px;
}

.monitoring-content {
  padding: 16px 0;
}

.status-indicator {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 8px;
}

.status-light {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 12px;
}

.status-light.normal {
  background: #52c41a;
}

.status-light.warning {
  background: #faad14;
}

.status-light.error {
  background: #ff4d4f;
}

.status-title {
  font-weight: 500;
  color: #262626;
}

.status-time {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 4px;
}

.alert-list h4 {
  margin-bottom: 16px;
  color: #262626;
}

.no-alerts {
  text-align: center;
  padding: 20px;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  border-left: 4px solid;
}

.alert-item.high {
  background: #fff2f0;
  border-left-color: #ff4d4f;
}

.alert-item.medium {
  background: #fffbe6;
  border-left-color: #faad14;
}

.alert-item.low {
  background: #f6ffed;
  border-left-color: #52c41a;
}

.alert-icon {
  margin-right: 12px;
  margin-top: 2px;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: 500;
  color: #262626;
  margin-bottom: 4px;
}

.alert-description {
  font-size: 13px;
  color: #595959;
  margin-bottom: 4px;
}

.alert-time {
  font-size: 12px;
  color: #8c8c8c;
}

.anomaly-controls {
  margin-bottom: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
}

.anomaly-insights {
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
  height: 400px;
  overflow-y: auto;
}

.insight-item {
  margin-bottom: 16px;
  padding: 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.insight-content {
  margin-top: 8px;
}

.insight-title {
  font-weight: 500;
  color: #262626;
  margin-bottom: 4px;
}

.insight-description {
  font-size: 13px;
  color: #595959;
  margin-bottom: 8px;
}

.insight-recommendation {
  font-size: 13px;
  color: #1890ff;
}

.export-form {
  padding: 16px 0;
}
</style>
