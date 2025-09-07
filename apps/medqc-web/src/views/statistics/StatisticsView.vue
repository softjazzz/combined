<template>
  <div class="page-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">统计分析</h1>
      <div class="header-actions">
        <a-space>
          <a-select v-model:value="selectedPeriod" @change="onPeriodChange" style="width: 120px">
            <a-select-option value="week">最近一周</a-select-option>
            <a-select-option value="month">最近一月</a-select-option>
            <a-select-option value="quarter">最近一季</a-select-option>
          </a-select>
          <a-button type="primary" :icon="h(ReloadOutlined)" @click="refreshData" :loading="loading">
            刷新数据
          </a-button>
          <a-button :icon="h(DownloadOutlined)" @click="exportReport" :loading="exporting">
        导出报表
      </a-button>
        </a-space>
      </div>
    </div>
    
    <!-- 统计概览卡片 -->
    <div class="stats-overview mb-6">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="8" :lg="6" v-for="card in overviewCards" :key="card.title">
          <a-card class="stats-card">
            <div class="stats-card-content">
              <div class="stats-icon" :style="{ backgroundColor: card.color + '20' }">
                <component :is="getIcon(card.icon)" :style="{ color: card.color }" />
              </div>
              <div class="stats-info">
                <div class="stats-title">{{ card.title }}</div>
                <div class="stats-value">{{ card.value }}</div>
                <div class="stats-change" :class="card.change?.type">
                  <component :is="card.change?.type === 'increase' ? ArrowUpOutlined : ArrowDownOutlined" />
                  {{ card.change?.value }}%
                </div>
              </div>
      </div>
    </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 图表区域 -->
    <div class="charts-section">
      <a-row :gutter="[24, 24]">
        <!-- 趋势分析 -->
        <a-col :xs="24" :lg="16">
          <a-card title="质控趋势分析" class="chart-card">
            <template #extra>
              <a-space>
                <a-radio-group v-model:value="trendType" @change="onTrendTypeChange" size="small">
                  <a-radio-button value="all">全部</a-radio-button>
                  <a-radio-button value="score">评分</a-radio-button>
                  <a-radio-button value="count">数量</a-radio-button>
                </a-radio-group>
              </a-space>
            </template>
            <div v-if="loading" class="loading-container">
              <a-spin size="large" />
            </div>
            <LineChart
              v-else
              :data="trendData"
              title=""
              height="350px"
              :show-data-zoom="trendData.length > 10"
            />
          </a-card>
        </a-col>

        <!-- 总体评分仪表盘 -->
        <a-col :xs="24" :lg="8">
          <a-card title="总体评分" class="chart-card">
            <div v-if="loading" class="loading-container">
              <a-spin size="large" />
            </div>
            <GaugeChart
              v-else
              :value="overview.averageScore"
              title=""
              height="350px"
            />
          </a-card>
        </a-col>

        <!-- 部门对比 -->
        <a-col :xs="24" :lg="12">
          <a-card title="部门对比分析" class="chart-card">
            <template #extra>
              <a-select v-model:value="departmentChartType" @change="onDepartmentChartTypeChange" size="small" style="width: 100px">
                <a-select-option value="recordCount">病案数</a-select-option>
                <a-select-option value="averageScore">评分</a-select-option>
                <a-select-option value="passRate">通过率</a-select-option>
              </a-select>
            </template>
            <div v-if="loading" class="loading-container">
              <a-spin size="large" />
            </div>
            <BarChart
              v-else
              :data="departmentStats"
              :type="departmentChartType"
              title=""
              height="350px"
            />
          </a-card>
        </a-col>

        <!-- 评分分布 -->
        <a-col :xs="24" :lg="12">
          <a-card title="评分分布" class="chart-card">
            <div v-if="loading" class="loading-container">
              <a-spin size="large" />
            </div>
            <PieChart
              v-else
              :data="scoreDistributionData"
              title=""
              height="350px"
            />
          </a-card>
        </a-col>

        <!-- 问题类型统计 -->
        <a-col :xs="24" :lg="12">
          <a-card title="问题类型统计" class="chart-card">
            <div v-if="loading" class="loading-container">
              <a-spin size="large" />
            </div>
            <PieChart
              v-else
              :data="issueStatsData"
              title=""
              height="350px"
              :radius="['30%', '60%']"
            />
          </a-card>
        </a-col>

        <!-- 详细统计表格 -->
        <a-col :xs="24" :lg="12">
          <a-card title="部门详细统计" class="chart-card">
            <a-table
              :columns="tableColumns"
              :data-source="departmentStats"
              :pagination="false"
              size="small"
              :loading="loading"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'averageScore'">
                  <a-progress
                    :percent="record.averageScore"
                    :stroke-color="record.averageScore >= 80 ? '#52c41a' : record.averageScore >= 60 ? '#faad14' : '#ff4d4f'"
                    size="small"
                  />
                </template>
                <template v-else-if="column.key === 'passRate'">
                  <a-tag :color="record.passRate >= 80 ? 'green' : record.passRate >= 60 ? 'orange' : 'red'">
                    {{ record.passRate }}%
                  </a-tag>
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  DownloadOutlined,
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  PlusOutlined
} from '@ant-design/icons-vue'
import LineChart from '@/components/charts/LineChart.vue'
import BarChart from '@/components/charts/BarChart.vue'
import PieChart from '@/components/charts/PieChart.vue'
import GaugeChart from '@/components/charts/GaugeChart.vue'
import {
  getStatisticsOverview,
  getTrendData,
  getDepartmentStats,
  getQCScoreDistribution,
  getQCIssueStats,
  exportStatisticsReport,
  type StatisticsOverview,
  type TrendData,
  type DepartmentStats,
  type QCScoreDistribution,
  type QCIssueStats
} from '@/api/statistics-api'
import type { DashboardCard } from '@/types'

// 响应式数据
const loading = ref(true)
const exporting = ref(false)
const selectedPeriod = ref<'week' | 'month' | 'quarter'>('month')
const trendType = ref('all')
const departmentChartType = ref<'recordCount' | 'averageScore' | 'passRate'>('recordCount')

// 统计数据
const overview = ref<StatisticsOverview>({
  totalRecords: 0,
  pendingRecords: 0,
  analyzingRecords: 0,
  completedRecords: 0,
  averageScore: 0,
  passRate: 0,
  todayUploads: 0,
  weeklyTrend: '+0%'
})

const trendData = ref<TrendData[]>([])
const departmentStats = ref<DepartmentStats[]>([])
const scoreDistribution = ref<QCScoreDistribution[]>([])
const issueStats = ref<QCIssueStats[]>([])

// 计算属性
const overviewCards = computed<DashboardCard[]>(() => [
  {
    title: '总病案数',
    value: overview.value.totalRecords.toLocaleString(),
    change: {
      value: parseFloat(overview.value.weeklyTrend.replace(/[+%]/g, '')),
      type: overview.value.weeklyTrend.startsWith('+') ? 'increase' : 'decrease'
    },
    icon: 'FileTextOutlined',
    color: '#1890ff'
  },
  {
    title: '待分析',
    value: overview.value.pendingRecords,
    change: {
      value: 2.1,
      type: 'decrease'
    },
    icon: 'ClockCircleOutlined',
    color: '#faad14'
  },
  {
    title: '分析中',
    value: overview.value.analyzingRecords,
    change: {
      value: 1.8,
      type: 'increase'
    },
    icon: 'SyncOutlined',
    color: '#13c2c2'
  },
  {
    title: '平均评分',
    value: `${overview.value.averageScore}分`,
    change: {
      value: 3.2,
      type: 'increase'
    },
    icon: 'TrophyOutlined',
    color: '#52c41a'
  },
  {
    title: '通过率',
    value: `${overview.value.passRate}%`,
    change: {
      value: 1.5,
      type: 'increase'
    },
    icon: 'CheckCircleOutlined',
    color: '#722ed1'
  },
  {
    title: '今日新增',
    value: overview.value.todayUploads,
    change: {
      value: 8.3,
      type: 'increase'
    },
    icon: 'PlusOutlined',
    color: '#f5222d'
  }
])

const scoreDistributionData = computed(() => 
  scoreDistribution.value.map(item => ({
    name: item.scoreRange,
    value: item.count,
    percentage: item.percentage
  }))
)

const issueStatsData = computed(() => 
  issueStats.value.map(item => ({
    name: item.category,
    value: item.issueCount,
    percentage: item.percentage
  }))
)

// 表格列配置
const tableColumns = [
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 100
  },
  {
    title: '病案数',
    dataIndex: 'recordCount',
    key: 'recordCount',
    width: 80,
    sorter: (a: DepartmentStats, b: DepartmentStats) => a.recordCount - b.recordCount
  },
  {
    title: '平均评分',
    dataIndex: 'averageScore',
    key: 'averageScore',
    width: 120,
    sorter: (a: DepartmentStats, b: DepartmentStats) => a.averageScore - b.averageScore
  },
  {
    title: '通过率',
    dataIndex: 'passRate',
    key: 'passRate',
    width: 100,
    sorter: (a: DepartmentStats, b: DepartmentStats) => a.passRate - b.passRate
  }
]

// 图标映射
const getIcon = (iconName: string) => {
  const iconMap: Record<string, any> = {
    FileTextOutlined,
    ClockCircleOutlined,
    SyncOutlined,
    TrophyOutlined,
    CheckCircleOutlined,
    PlusOutlined
  }
  return iconMap[iconName] || FileTextOutlined
}

// 方法
const loadData = async () => {
  try {
    loading.value = true
    
    const [
      overviewData,
      trendDataResult,
      departmentStatsResult,
      scoreDistributionResult,
      issueStatsResult
    ] = await Promise.all([
      getStatisticsOverview(),
      getTrendData(selectedPeriod.value),
      getDepartmentStats(),
      getQCScoreDistribution(),
      getQCIssueStats()
    ])

    overview.value = overviewData
    trendData.value = trendDataResult
    departmentStats.value = departmentStatsResult
    scoreDistribution.value = scoreDistributionResult
    issueStats.value = issueStatsResult
  } catch (error) {
    console.error('加载统计数据失败:', error)
    message.error('加载统计数据失败')
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  loadData()
}

const onPeriodChange = () => {
  loadData()
}

const onTrendTypeChange = () => {
  // 可以根据趋势类型过滤数据
  console.log('趋势类型变更:', trendType.value)
}

const onDepartmentChartTypeChange = () => {
  // 图表类型变更时的处理
  console.log('部门图表类型变更:', departmentChartType.value)
}

const exportReport = async () => {
  try {
    exporting.value = true
    
    // 准备导出数据
    const exportData = {
      overview: overview.value,
      trendData: trendData.value,
      departmentStats: departmentStats.value,
      scoreDistribution: scoreDistribution.value,
      issueStats: issueStats.value,
      exportTime: new Date().toISOString()
    }
    
    // 导入导出工具
    const { exportToExcel } = await import('@/utils/export')
    await exportToExcel(exportData)
    
    message.success('报表导出成功')
  } catch (error) {
    console.error('导出报表失败:', error)
    message.error('导出报表失败')
  } finally {
    exporting.value = false
  }
}

// 生命周期
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-container {
  @apply p-6;
}

.page-header {
  @apply flex items-center justify-between mb-6;
}

.page-title {
  @apply text-2xl font-bold text-gray-900;
}

.header-actions {
  @apply flex items-center gap-4;
}

.stats-overview {
  @apply mb-6;
}

.stats-card {
  @apply h-full transition-all duration-200 hover:shadow-lg;
}

.stats-card-content {
  @apply flex items-center;
}

.stats-icon {
  @apply w-12 h-12 rounded-lg flex items-center justify-center mr-4;
}

.stats-info {
  @apply flex-1;
}

.stats-title {
  @apply text-gray-600 text-sm mb-1;
}

.stats-value {
  @apply text-2xl font-bold text-gray-900 mb-1;
}

.stats-change {
  @apply text-sm flex items-center gap-1;
}

.stats-change.increase {
  @apply text-green-600;
}

.stats-change.decrease {
  @apply text-red-600;
}

.charts-section {
  @apply space-y-6;
}

.chart-card {
  @apply h-full;
}

.loading-container {
  @apply flex items-center justify-center h-80;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .page-header {
    @apply flex-col items-start gap-4;
  }
  
  .header-actions {
    @apply w-full justify-end;
  }
}
</style> 