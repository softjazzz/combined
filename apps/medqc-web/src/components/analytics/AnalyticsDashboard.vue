<template>
  <div class="analytics-dashboard">
    <!-- 页面头部 -->
    <div class="dashboard-header mb-6">
      <div class="flex justify-between items-center">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">360度数据分析</h1>
          <p class="text-gray-600 mt-1">全方位质控数据洞察与智能分析</p>
        </div>
        <div class="flex space-x-3">
          <a-range-picker
            v-model:value="dateRange"
            @change="onDateRangeChange"
            :ranges="dateRanges"
            class="w-80"
          />
          <a-select
            v-model:value="selectedDepartment"
            @change="onDepartmentChange"
            placeholder="选择科室"
            class="w-40"
            allow-clear
          >
            <a-select-option value="">全部科室</a-select-option>
            <a-select-option v-for="dept in departments" :key="dept" :value="dept">
              {{ dept }}
            </a-select-option>
          </a-select>
          <a-button type="primary" @click="refreshData" :loading="loading">
            <ReloadOutlined />
            刷新数据
          </a-button>
        </div>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <div class="metrics-overview mb-6">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="8" :lg="6" v-for="metric in coreMetrics" :key="metric.key">
          <a-card class="metric-card" :class="getMetricCardClass(metric)">
            <div class="flex items-center justify-between">
              <div class="flex-1">
                <div class="metric-label text-gray-600 text-sm">{{ metric.label }}</div>
                <div class="metric-value text-2xl font-bold mt-1" :style="{ color: metric.color }">
                  {{ formatMetricValue(metric.value, metric.unit) }}
                </div>
                <div class="metric-change flex items-center mt-2">
                  <component 
                    :is="metric.trend === 'up' ? 'ArrowUpOutlined' : metric.trend === 'down' ? 'ArrowDownOutlined' : 'MinusOutlined'"
                    :class="getTrendClass(metric.trend)"
                    class="text-xs mr-1"
                  />
                  <span :class="getTrendClass(metric.trend)" class="text-xs">
                    {{ Math.abs(metric.change || 0).toFixed(1) }}%
                  </span>
                  <span class="text-gray-500 text-xs ml-1">vs 上期</span>
                </div>
              </div>
              <div class="metric-icon p-3 rounded-lg" :style="{ backgroundColor: metric.color + '20' }">
                <component :is="metric.icon" :style="{ color: metric.color }" class="text-xl" />
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 主要分析区域 -->
    <a-row :gutter="[24, 24]">
      <!-- 左侧：图表分析 -->
      <a-col :xs="24" :lg="16">
        <!-- 质量趋势分析 -->
        <a-card title="质量趋势分析" class="mb-6" :loading="loading">
          <template #extra>
            <a-radio-group v-model:value="trendGranularity" @change="onTrendGranularityChange">
              <a-radio-button value="day">日</a-radio-button>
              <a-radio-button value="week">周</a-radio-button>
              <a-radio-button value="month">月</a-radio-button>
            </a-radio-group>
          </template>
          <div class="h-80">
            <LineChart
              :data="trendChartData"
              :options="trendChartOptions"
              :height="300"
            />
          </div>
        </a-card>

        <!-- 科室对比分析 -->
        <a-card title="科室对比分析" class="mb-6" :loading="loading">
          <template #extra>
            <a-select v-model:value="comparisonMetric" @change="onComparisonMetricChange" class="w-32">
              <a-select-option value="avg_score">平均评分</a-select-option>
              <a-select-option value="grade_a_rate">优秀率</a-select-option>
              <a-select-option value="total_records">病案数量</a-select-option>
            </a-select>
          </template>
          <div class="h-80">
            <BarChart
              :data="comparisonChartData"
              :type="getBarChartType(comparisonMetric)"
              height="300px"
            />
          </div>
        </a-card>

        <!-- 绩效雷达图 -->
        <a-card title="绩效雷达分析" class="mb-6" :loading="loading">
          <template #extra>
            <a-select
              v-model:value="selectedDoctor"
              @change="onDoctorChange"
              placeholder="选择医生"
              class="w-40"
              allow-clear
            >
              <a-select-option value="">全部医生</a-select-option>
              <a-select-option v-for="doctor in topDoctors" :key="doctor.id" :value="doctor.id">
                {{ doctor.name }}
              </a-select-option>
            </a-select>
          </template>
          <div class="h-80">
            <RadarChartEcharts
              :data="radarChartEchartsData"
              :indicators="radarChartIndicators"
              :height="300"
              title="医生绩效对比"
            />
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：洞察和报表 -->
      <a-col :xs="24" :lg="8">
        <!-- 智能洞察 -->
        <a-card title="智能洞察" class="mb-6" :loading="loading">
          <template #extra>
            <a-tooltip title="AI自动分析生成">
              <BulbOutlined class="text-yellow-500" />
            </a-tooltip>
          </template>
          <div class="space-y-4">
            <div
              v-for="insight in insights"
              :key="insight.title"
              class="insight-item p-4 rounded-lg border"
              :class="getInsightClass(insight.type)"
            >
              <div class="flex items-start">
                <div class="insight-icon mr-3 mt-1">
                  <component :is="getInsightIcon(insight.type)" :class="getInsightIconClass(insight.type)" />
                </div>
                <div class="flex-1">
                  <h4 class="font-semibold text-sm mb-1">{{ insight.title }}</h4>
                  <p class="text-xs text-gray-600 mb-2">{{ insight.description }}</p>
                  <div class="recommendation bg-gray-50 p-2 rounded text-xs">
                    <strong>建议：</strong>{{ insight.recommendation }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="insights.length === 0" class="text-center text-gray-500 py-8">
            <BulbOutlined class="text-2xl mb-2" />
            <p>暂无智能洞察</p>
          </div>
        </a-card>

        <!-- 报表生成 -->
        <a-card title="智能报表" class="mb-6">
          <template #extra>
            <a-button type="link" @click="showReportModal = true" size="small">
              <PlusOutlined />
              生成报表
            </a-button>
          </template>
          <div class="space-y-3">
            <div
              v-for="template in reportTemplates"
              :key="template.id"
              class="report-template-item p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
              @click="generateReport(template.id)"
            >
              <div class="flex items-center justify-between">
                <div class="flex-1">
                  <h4 class="font-medium text-sm">{{ template.template_name }}</h4>
                  <p class="text-xs text-gray-500 mt-1">{{ template.description }}</p>
                </div>
                <div class="flex items-center space-x-2">
                  <a-tag :color="getReportTypeColor(template.template_type)" size="small">
                    {{ getReportTypeLabel(template.template_type) }}
                  </a-tag>
                  <FileTextOutlined class="text-gray-400" />
                </div>
              </div>
            </div>
          </div>
        </a-card>

        <!-- 最近报表 -->
        <a-card title="最近报表">
          <div class="space-y-3">
            <div
              v-for="report in recentReports"
              :key="report.id"
              class="report-item p-3 border rounded-lg"
            >
              <div class="flex items-center justify-between">
                <div class="flex-1">
                  <h4 class="font-medium text-sm">{{ report.report_name }}</h4>
                  <p class="text-xs text-gray-500 mt-1">
                    {{ formatDate(report.created_at) }}
                  </p>
                </div>
                <div class="flex items-center space-x-2">
                  <a-tag :color="getReportStatusColor(report.status)" size="small">
                    {{ getReportStatusLabel(report.status) }}
                  </a-tag>
                  <a-dropdown>
                    <a-button type="text" size="small">
                      <MoreOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item @click="downloadReport(report.id)" :disabled="report.status !== 'completed'">
                          <DownloadOutlined />
                          下载
                        </a-menu-item>
                        <a-menu-item @click="viewReport(report.id)" :disabled="report.status !== 'completed'">
                          <EyeOutlined />
                          查看
                        </a-menu-item>
                        <a-menu-item @click="deleteReport(report.id)">
                          <DeleteOutlined />
                          删除
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </div>
              </div>
              <div v-if="report.status === 'generating'" class="mt-2">
                <a-progress :percent="report.progress" size="small" />
              </div>
            </div>
          </div>
          <div v-if="recentReports.length === 0" class="text-center text-gray-500 py-8">
            <FileTextOutlined class="text-2xl mb-2" />
            <p>暂无报表</p>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 报表生成弹窗 -->
    <a-modal
      v-model:open="showReportModal"
      title="生成报表"
      width="600px"
      @ok="handleGenerateReport"
      :confirm-loading="generatingReport"
    >
      <a-form :model="reportForm" layout="vertical">
        <a-form-item label="报表模板" required>
          <a-select v-model:value="reportForm.template_id" placeholder="选择报表模板">
            <a-select-option v-for="template in reportTemplates" :key="template.id" :value="template.id">
              {{ template.template_name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="时间范围" required>
          <a-range-picker
            v-model:value="reportForm.date_range"
            style="width: 100%"
            :ranges="dateRanges"
          />
        </a-form-item>
        <a-form-item label="科室筛选">
          <a-select
            v-model:value="reportForm.department"
            placeholder="选择科室（可选）"
            allow-clear
          >
            <a-select-option v-for="dept in departments" :key="dept" :value="dept">
              {{ dept }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="输出格式">
          <a-select v-model:value="reportForm.output_format" placeholder="选择输出格式">
            <a-select-option value="pdf">PDF</a-select-option>
            <a-select-option value="excel">Excel</a-select-option>
            <a-select-option value="word">Word</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  BulbOutlined,
  TrophyOutlined,
  FileTextOutlined,
  BarChartOutlined,
  TeamOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  DownloadOutlined,
  EyeOutlined,
  DeleteOutlined,
  MoreOutlined
} from '@ant-design/icons-vue'
import LineChart from '../charts/LineChart.vue'
import BarChart from '../charts/BarChart.vue'
import RadarChartEcharts from '../charts/RadarChartEcharts.vue'
import { analyticsEngine } from '../../lib/analytics-engine'
import { reportEngine } from '../../lib/report-engine'
import type { 
  AnalyticsInsight, 
  TimeRange, 
  DepartmentComparison,
  DoctorPerformance,
  TrendAnalysis 
} from '../../lib/analytics-engine'
import type { ReportTemplate, ReportInstance } from '../../lib/report-engine'

// 响应式数据
const loading = ref(false)
const dateRange = ref<[Dayjs, Dayjs]>([dayjs().subtract(30, 'days'), dayjs()])
const selectedDepartment = ref<string>('')
const trendGranularity = ref<'day' | 'week' | 'month'>('day')
const comparisonMetric = ref<string>('avg_score')
const selectedDoctor = ref<string>('')

// 数据状态
const coreMetrics = ref<any[]>([])
const insights = ref<AnalyticsInsight[]>([])
const trendChartData = ref<any>([])
const comparisonChartData = ref<any>([])
const radarChartData = ref<any>({})
const departments = ref<string[]>([])
const topDoctors = ref<any[]>([])
const reportTemplates = ref<ReportTemplate[]>([])
const recentReports = ref<ReportInstance[]>([])

// ECharts 雷达图数据
const radarChartEchartsData = ref<Array<{
  name: string
  value: number[]
  color?: string
}>>([])

const radarChartIndicators = ref<Array<{
  name: string
  max: number
  min?: number
}>>([
  { name: '质量评分', max: 100, min: 0 },
  { name: '工作效率', max: 100, min: 0 },
  { name: '生产力', max: 100, min: 0 },
  { name: '一致性', max: 100, min: 0 },
  { name: '及时性', max: 100, min: 0 }
])

// 报表相关
const showReportModal = ref(false)
const generatingReport = ref(false)
const reportForm = ref({
  template_id: '',
  date_range: null as [Dayjs, Dayjs] | null,
  department: '',
  output_format: 'pdf'
})

// 计算属性
const timeRange = computed<TimeRange>(() => ({
  start: dateRange.value[0].format('YYYY-MM-DD'),
  end: dateRange.value[1].format('YYYY-MM-DD'),
  granularity: trendGranularity.value
}))

const dateRanges = computed(() => ({
  '今天': [dayjs(), dayjs()],
  '昨天': [dayjs().subtract(1, 'day'), dayjs().subtract(1, 'day')],
  '最近7天': [dayjs().subtract(7, 'days'), dayjs()],
  '最近30天': [dayjs().subtract(30, 'days'), dayjs()],
  '本月': [dayjs().startOf('month'), dayjs().endOf('month')],
  '上月': [dayjs().subtract(1, 'month').startOf('month'), dayjs().subtract(1, 'month').endOf('month')]
}))

// 图表配置
const trendChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      beginAtZero: true,
      max: 100
    }
  },
  plugins: {
    legend: {
      display: true,
      position: 'top'
    },
    tooltip: {
      mode: 'index',
      intersect: false
    }
  }
}))

const comparisonChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y',
  scales: {
    x: {
      beginAtZero: true
    }
  },
  plugins: {
    legend: {
      display: false
    }
  }
}))

// radarChartOptions 已移除，ECharts 组件不需要这些选项

// 方法
const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadCoreMetrics(),
      loadTrendData(),
      loadComparisonData(),
      loadRadarData(),
      loadInsights(),
      loadReportTemplates(),
      loadRecentReports()
    ])
  } catch (error) {
    console.error('刷新数据失败:', error)
    message.error('刷新数据失败')
  } finally {
    loading.value = false
  }
}

const loadCoreMetrics = async () => {
  // 模拟核心指标数据
  coreMetrics.value = [
    {
      key: 'total_records',
      label: '总病案数',
      value: 1247,
      unit: '份',
      change: 12.5,
      trend: 'up',
      color: '#1890ff',
      icon: 'FileTextOutlined'
    },
    {
      key: 'avg_score',
      label: '平均评分',
      value: 87.5,
      unit: '分',
      change: 3.2,
      trend: 'up',
      color: '#52c41a',
      icon: 'TrophyOutlined'
    },
    {
      key: 'grade_a_rate',
      label: '优秀率',
      value: 65.2,
      unit: '%',
      change: 2.8,
      trend: 'up',
      color: '#722ed1',
      icon: 'CheckCircleOutlined'
    },
    {
      key: 'avg_processing_time',
      label: '平均处理时间',
      value: 4.2,
      unit: '小时',
      change: -8.5,
      trend: 'down',
      color: '#faad14',
      icon: 'ClockCircleOutlined'
    }
  ]
}

const loadTrendData = async () => {
  try {
    // 临时使用模拟数据来测试图表显示
    const mockTrends = [
      { period: '2024-01-01', recordCount: 45, averageScore: 82.5, passRate: 65.2 },
      { period: '2024-01-02', recordCount: 52, averageScore: 84.1, passRate: 67.8 },
      { period: '2024-01-03', recordCount: 48, averageScore: 86.3, passRate: 70.1 },
      { period: '2024-01-04', recordCount: 55, averageScore: 85.7, passRate: 68.9 },
      { period: '2024-01-05', recordCount: 49, averageScore: 87.2, passRate: 72.3 },
      { period: '2024-01-06', recordCount: 51, averageScore: 88.5, passRate: 74.1 },
      { period: '2024-01-07', recordCount: 47, averageScore: 86.8, passRate: 71.5 }
    ]
    
    trendChartData.value = mockTrends
    console.log('趋势数据已加载:', trendChartData.value)
  } catch (error) {
    console.error('加载趋势数据失败:', error)
    trendChartData.value = []
  }
}

const loadComparisonData = async () => {
  try {
    // 临时使用模拟数据来测试图表显示
    const mockComparison = [
      { department: '内科', total_records: 120, avg_score: 85.5, grade_a_rate: 68.2 },
      { department: '外科', total_records: 98, avg_score: 82.3, grade_a_rate: 65.1 },
      { department: '儿科', total_records: 75, avg_score: 88.7, grade_a_rate: 72.4 },
      { department: '妇产科', total_records: 88, avg_score: 86.9, grade_a_rate: 70.5 },
      { department: '急诊科', total_records: 156, avg_score: 79.8, grade_a_rate: 58.9 }
    ]
    
    // 转换为 ECharts BarChart 组件期望的格式
    comparisonChartData.value = mockComparison.map((dept, index) => ({
      department: dept.department,
      recordCount: dept.total_records || 0,
      averageScore: dept.avg_score || 0,
      passRate: dept.grade_a_rate || 0,
      color: `hsla(${200 + index * 30}, 70%, 50%, 0.8)`
    }))
    
    console.log('科室对比数据已加载:', comparisonChartData.value)
  } catch (error) {
    console.error('加载对比数据失败:', error)
    comparisonChartData.value = []
  }
}

const loadRadarData = async () => {
  try {
    // 临时使用模拟数据来测试图表显示
    const mockPerformance = [
      { doctor_name: '张医生', quality_score: 85, efficiency_score: 78, productivity_score: 92, avg_score: 86, overall_score: 85 },
      { doctor_name: '李医生', quality_score: 78, efficiency_score: 85, productivity_score: 88, avg_score: 82, overall_score: 83 },
      { doctor_name: '王医生', quality_score: 92, efficiency_score: 76, productivity_score: 85, avg_score: 88, overall_score: 85 },
      { doctor_name: '刘医生', quality_score: 88, efficiency_score: 82, productivity_score: 79, avg_score: 85, overall_score: 84 }
    ]
    
    radarChartData.value = {
      labels: ['质量评分', '工作效率', '生产力', '一致性', '及时性'],
      datasets: mockPerformance.map((doctor, index) => ({
        label: doctor.doctor_name,
        data: [
          doctor.quality_score,
          doctor.efficiency_score,
          doctor.productivity_score,
          doctor.avg_score,
          doctor.overall_score
        ],
        borderColor: `hsla(${index * 72}, 70%, 50%, 1)`,
        backgroundColor: `hsla(${index * 72}, 70%, 50%, 0.2)`,
        pointBackgroundColor: `hsla(${index * 72}, 70%, 50%, 1)`
      }))
    }
    
    // 同时更新 ECharts 格式的数据
    radarChartEchartsData.value = mockPerformance.map((doctor, index) => ({
      name: doctor.doctor_name,
      value: [
        doctor.quality_score,
        doctor.efficiency_score,
        doctor.productivity_score,
        doctor.avg_score,
        doctor.overall_score
      ],
      color: `hsla(${index * 72}, 70%, 50%, 1)`
    }))
    
    console.log('雷达图数据已加载:', radarChartEchartsData.value)
  } catch (error) {
    console.error('加载雷达数据失败:', error)
    radarChartEchartsData.value = []
  }
}

const loadInsights = async () => {
  try {
    insights.value = await analyticsEngine.generateInsights(timeRange.value, selectedDepartment.value)
  } catch (error) {
    console.error('加载洞察数据失败:', error)
  }
}

const loadReportTemplates = async () => {
  try {
    reportTemplates.value = await reportEngine.getReportTemplates()
  } catch (error) {
    console.error('加载报表模板失败:', error)
  }
}

const loadRecentReports = async () => {
  try {
    recentReports.value = await reportEngine.getReportInstances({ limit: 10 })
  } catch (error) {
    console.error('加载最近报表失败:', error)
  }
}

// 事件处理
const onDateRangeChange = () => {
  refreshData()
}

const onDepartmentChange = () => {
  refreshData()
}

const onTrendGranularityChange = () => {
  loadTrendData()
}

const onComparisonMetricChange = () => {
  loadComparisonData()
}

const onDoctorChange = () => {
  loadRadarData()
}

// 报表相关方法
const generateReport = async (templateId: string) => {
  reportForm.value.template_id = templateId
  reportForm.value.date_range = dateRange.value
  reportForm.value.department = selectedDepartment.value
  showReportModal.value = true
}

const handleGenerateReport = async () => {
  if (!reportForm.value.template_id || !reportForm.value.date_range) {
    message.error('请填写必要信息')
    return
  }

  generatingReport.value = true
  try {
    await reportEngine.generateReport(reportForm.value.template_id, {
      period_start: reportForm.value.date_range[0].format('YYYY-MM-DD'),
      period_end: reportForm.value.date_range[1].format('YYYY-MM-DD'),
      filters: reportForm.value.department ? { department: reportForm.value.department } : undefined,
      output_format: reportForm.value.output_format
    })
    
    message.success('报表生成任务已提交，请稍后查看')
    showReportModal.value = false
    loadRecentReports()
  } catch (error) {
    console.error('生成报表失败:', error)
    message.error('生成报表失败')
  } finally {
    generatingReport.value = false
  }
}

const downloadReport = async (reportId: string) => {
  try {
    // 实现报表下载逻辑
    message.success('报表下载已开始')
  } catch (error) {
    console.error('下载报表失败:', error)
    message.error('下载报表失败')
  }
}

const viewReport = async (reportId: string) => {
  try {
    // 实现报表查看逻辑
    message.info('报表查看功能开发中')
  } catch (error) {
    console.error('查看报表失败:', error)
    message.error('查看报表失败')
  }
}

const deleteReport = async (reportId: string) => {
  try {
    await reportEngine.deleteReportInstance(reportId)
    message.success('报表已删除')
    loadRecentReports()
  } catch (error) {
    console.error('删除报表失败:', error)
    message.error('删除报表失败')
  }
}

// 辅助方法
const formatMetricValue = (value: number, unit: string): string => {
  if (unit === '%') {
    return `${value.toFixed(1)}%`
  }
  if (unit === '分') {
    return `${value.toFixed(1)}分`
  }
  if (unit === '小时') {
    return `${value.toFixed(1)}h`
  }
  return value.toLocaleString()
}

const getTrendClass = (trend: string): string => {
  if (trend === 'up') return 'text-green-500'
  if (trend === 'down') return 'text-red-500'
  return 'text-gray-500'
}

const getMetricCardClass = (metric): string => {
  if (metric.trend === 'up') return 'border-l-4 border-green-500'
  if (metric.trend === 'down') return 'border-l-4 border-red-500'
  return 'border-l-4 border-gray-300'
}

const getInsightClass = (type: string): string => {
  const classes = {
    achievement: 'border-green-200 bg-green-50',
    warning: 'border-yellow-200 bg-yellow-50',
    opportunity: 'border-blue-200 bg-blue-50',
    risk: 'border-red-200 bg-red-50'
  }
  return classes[type as keyof typeof classes] || 'border-gray-200 bg-gray-50'
}

const getInsightIcon = (type: string): string => {
  const icons = {
    achievement: 'CheckCircleOutlined',
    warning: 'ExclamationCircleOutlined',
    opportunity: 'BulbOutlined',
    risk: 'ExclamationCircleOutlined'
  }
  return icons[type as keyof typeof icons] || 'BulbOutlined'
}

const getInsightIconClass = (type: string): string => {
  const classes = {
    achievement: 'text-green-500',
    warning: 'text-yellow-500',
    opportunity: 'text-blue-500',
    risk: 'text-red-500'
  }
  return classes[type as keyof typeof classes] || 'text-gray-500'
}

const getReportTypeColor = (type: string): string => {
  const colors = {
    qc_summary: 'blue',
    performance: 'green',
    trend: 'purple',
    comparison: 'orange'
  }
  return colors[type as keyof typeof colors] || 'default'
}

const getReportTypeLabel = (type: string): string => {
  const labels = {
    qc_summary: '质控总结',
    performance: '绩效分析',
    trend: '趋势分析',
    comparison: '对比分析'
  }
  return labels[type as keyof typeof labels] || type
}

const getReportStatusColor = (status: string): string => {
  const colors = {
    pending: 'default',
    generating: 'processing',
    completed: 'success',
    failed: 'error'
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getReportStatusLabel = (status: string): string => {
  const labels = {
    pending: '待生成',
    generating: '生成中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status as keyof typeof labels] || status
}

const getComparisonMetricLabel = (metric: string): string => {
  const labels = {
    avg_score: '平均评分',
    grade_a_rate: '优秀率',
    total_records: '病案数量'
  }
  return labels[metric as keyof typeof labels] || metric
}

const getBarChartType = (metric: string): 'recordCount' | 'averageScore' | 'passRate' => {
  switch (metric) {
    case 'avg_score':
      return 'averageScore'
    case 'grade_a_rate':
      return 'passRate'
    case 'total_records':
      return 'recordCount'
    default:
      return 'recordCount'
  }
}

const formatDate = (dateString: string): string => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

// 生命周期
onMounted(() => {
  refreshData()
})

// 监听器
watch(dateRange, () => {
  refreshData()
})

watch(selectedDepartment, () => {
  refreshData()
})
</script>

<style scoped>
.analytics-dashboard {
  padding: 24px;
  background: #f0f2f5;
  min-height: 100vh;
}

.dashboard-header {
  background: white;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.metric-card {
  transition: all 0.3s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.insight-item {
  transition: all 0.3s ease;
}

.insight-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.report-template-item {
  transition: all 0.3s ease;
}

.report-template-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.report-item {
  transition: all 0.3s ease;
}

.report-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style> 