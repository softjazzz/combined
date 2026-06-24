<template>
  <div class="min-h-screen bg-slate-50/50 p-6 lg:p-8 font-sans relative overflow-x-hidden">
    <!-- Background Gradients -->
    <div class="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-blue-50/50 via-slate-50/30 to-transparent pointer-events-none z-0" />
    <div class="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-gradient-to-br from-blue-100/20 to-purple-100/20 rounded-full blur-3xl pointer-events-none z-0" />

    <div class="relative z-10 max-w-[1920px] mx-auto">
      <!-- Page Header -->
      <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 class="text-2xl font-bold text-slate-800 tracking-tight">
            统计分析
          </h1>
          <p class="text-slate-500 text-sm mt-1">
            全方位的质控数据监控与效能分析看板
          </p>
          <p class="text-xs text-slate-400 mt-2">
            一期已接入真实概览、部门分布、评分分布、问题分类、趋势图和报表导出。
          </p>
        </div>
        <div class="flex items-center gap-3 bg-white p-1.5 rounded-xl border border-slate-200 shadow-sm">
          <a-select
            v-model:value="selectedPeriod"
            class="w-32"
            :bordered="false"
            @change="onPeriodChange"
          >
            <a-select-option value="week">
              最近一周
            </a-select-option>
            <a-select-option value="month">
              最近一月
            </a-select-option>
            <a-select-option value="quarter">
              最近一季
            </a-select-option>
          </a-select>
          <div class="w-px h-4 bg-slate-200" />
          <a-button
            type="text"
            :icon="h(ReloadOutlined)"
            :loading="loading"
            class="!text-slate-600 hover:!text-blue-600"
            @click="refreshData"
          >
            刷新
          </a-button>
          <a-button
            type="primary"
            :icon="h(DownloadOutlined)"
            :loading="exporting"
            class="!bg-slate-900 !border-slate-900 hover:!bg-blue-600 hover:!border-blue-600 !rounded-lg !font-medium !shadow-md !shadow-slate-200"
            @click="exportReport"
          >
            导出报表
          </a-button>
        </div>
      </div>
      
      <!-- Stats Overview Grid -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <div 
          v-for="card in overviewCards" 
          :key="card.title"
          class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm hover:shadow-md hover:border-blue-100 transition-all duration-300 group"
        >
          <div class="flex items-start justify-between mb-3">
            <div
              class="w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
              :style="{ backgroundColor: card.color + '15' }"
            >
              <component
                :is="getIcon(String(card.icon || ''))"
                class="text-lg"
                :style="{ color: card.color }"
              />
            </div>
            <div
              v-if="card.change"
              class="text-xs font-medium px-1.5 py-0.5 rounded flex items-center gap-0.5"
              :class="card.change?.type === 'increase' ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'"
            >
              <component
                :is="card.change?.type === 'increase' ? ArrowUpOutlined : ArrowDownOutlined"
                class="text-[10px]"
              />
              {{ card.change?.value }}%
            </div>
          </div>
          <div>
            <div class="text-slate-500 text-xs font-medium mb-1">
              {{ card.title }}
            </div>
            <div class="text-xl font-bold text-slate-800 tracking-tight group-hover:text-blue-600 transition-colors">
              {{ card.value }}
            </div>
          </div>
        </div>
      </div>

      <!-- Charts Section -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <!-- Trend Analysis (Full Width) -->
        <div class="lg:col-span-12 bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-base font-bold text-slate-800 flex items-center gap-2">
              <span class="w-1 h-4 bg-blue-600 rounded-full" />
              质控趋势分析
            </h3>
            <a-radio-group
              v-model:value="trendType"
              size="small"
              button-style="solid"
              @change="onTrendTypeChange"
            >
              <a-radio-button value="all">
                综合
              </a-radio-button>
              <a-radio-button value="score">
                评分
              </a-radio-button>
              <a-radio-button value="count">
                数量
              </a-radio-button>
            </a-radio-group>
          </div>
          <div class="h-[360px] w-full bg-slate-50/50 rounded-xl border border-slate-50 p-4">
            <div
              v-if="loading"
              class="flex items-center justify-center h-full text-slate-400"
            >
              <a-spin />
            </div>
            <LineChart
              v-else-if="trendData.length > 0"
              :data="trendData"
              title=""
              height="100%"
              :show-data-zoom="trendData.length > 10"
            />
            <div
              v-else
              class="h-full flex items-center justify-center text-slate-400 text-sm"
            >
              暂无趋势数据
            </div>
          </div>
        </div>

        <!-- Row 2: Department Stats & Score Distribution -->
        <div class="lg:col-span-12 grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- Department Contrast -->
          <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-base font-bold text-slate-800 flex items-center gap-2">
                <span class="w-1 h-4 bg-indigo-600 rounded-full" />
                部门对比分析
              </h3>
              <a-select
                v-model:value="departmentChartType"
                size="small"
                class="w-24"
                @change="onDepartmentChartTypeChange"
              >
                <a-select-option value="recordCount">
                  病案数
                </a-select-option>
                <a-select-option value="averageScore">
                  评分
                </a-select-option>
                <a-select-option value="passRate">
                  通过率
                </a-select-option>
              </a-select>
            </div>
            <div class="h-[300px]">
              <BarChart
                v-if="!loading"
                :data="departmentStats"
                :type="departmentChartType"
                title=""
                height="100%"
              />
              <a-spin
                v-else
                class="flex justify-center items-center h-full"
              />
            </div>
          </div>

          <!-- Score Distribution -->
          <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
            <h3 class="text-base font-bold text-slate-800 mb-6 flex items-center gap-2">
              <span class="w-1 h-4 bg-emerald-600 rounded-full" />
              评分分布
            </h3>
            <div class="h-[300px]">
              <PieChart
                v-if="!loading"
                :data="scoreDistributionData"
                title=""
                height="100%"
              />
              <a-spin
                v-else
                class="flex justify-center items-center h-full"
              />
            </div>
          </div>
        </div>

        <!-- Row 3: Issue Stats & Detail Table -->
        <div class="lg:col-span-12 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Issue Stats -->
          <div class="lg:col-span-1 bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
            <h3 class="text-base font-bold text-slate-800 mb-6 flex items-center gap-2">
              <span class="w-1 h-4 bg-orange-500 rounded-full" />
              问题类型统计
            </h3>
            <div class="h-[300px]">
              <PieChart
                v-if="!loading && issueStatsData.length > 0"
                :data="issueStatsData"
                title=""
                height="100%"
                :radius="['40%', '70%']"
              />
              <div
                v-else-if="!loading"
                class="h-full flex items-center justify-center text-slate-400 text-sm"
              >
                暂无问题分类数据
              </div>
              <a-spin
                v-else
                class="flex justify-center items-center h-full"
              />
            </div>
          </div>

          <!-- Detail Table -->
          <div class="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-base font-bold text-slate-800 flex items-center gap-2">
                <span class="w-1 h-4 bg-slate-600 rounded-full" />
                部门详细统计
              </h3>
              <a-button
                type="link"
                size="small"
                class="!text-slate-500 hover:!text-blue-600"
              >
                查看更多
              </a-button>
            </div>
            <a-table
              :columns="tableColumns"
              :data-source="departmentStats"
              :pagination="{ pageSize: 5 }"
              size="middle"
              :loading="loading"
              class="ant-table-modern"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'averageScore'">
                  <div class="flex items-center gap-2">
                    <span class="font-mono font-medium text-slate-700">{{ record.averageScore }}</span>
                    <div class="flex-1 min-w-[60px]">
                      <a-progress
                        :percent="record.averageScore"
                        :stroke-color="record.averageScore >= 80 ? '#10b981' : record.averageScore >= 60 ? '#f59e0b' : '#ef4444'"
                        :show-info="false"
                        size="small"
                        class="!m-0"
                      />
                    </div>
                  </div>
                </template>
                <template v-else-if="column.key === 'passRate'">
                  <span 
                    class="px-2 py-0.5 rounded-full text-xs font-bold"
                    :class="record.passRate >= 80 ? 'bg-emerald-50 text-emerald-600' : record.passRate >= 60 ? 'bg-orange-50 text-orange-600' : 'bg-red-50 text-red-600'"
                  >
                    {{ record.passRate }}%
                  </span>
                </template>
                <template v-else-if="column.key === 'department'">
                  <span class="font-medium text-slate-700">{{ record.department }}</span>
                </template>
              </template>
            </a-table>
          </div>
        </div>
      </div>
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
// Removed GaugeChart import as it's no longer used
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

function parseTrendChange(
  value: string,
): DashboardCard['change'] | undefined {
  const normalized = value.trim()
  if (!normalized || normalized === '0%' || normalized === '+0%' || normalized === '-0%') {
    return undefined
  }

  const numeric = Number.parseFloat(normalized.replace(/[+%]/g, ''))
  if (Number.isNaN(numeric)) {
    return undefined
  }

  return {
    value: numeric,
    type: normalized.startsWith('-') ? 'decrease' : 'increase',
  }
}

// 计算属性
const overviewCards = computed<DashboardCard[]>(() => [
  {
    title: '总病案数',
    value: overview.value.totalRecords.toLocaleString(),
    change: parseTrendChange(overview.value.weeklyTrend),
    icon: 'FileTextOutlined',
    color: '#1890ff'
  },
  {
    title: '待分析',
    value: overview.value.pendingRecords,
    icon: 'ClockCircleOutlined',
    color: '#faad14'
  },
  {
    title: '分析中',
    value: overview.value.analyzingRecords,
    icon: 'SyncOutlined',
    color: '#13c2c2'
  },
  {
    title: '平均评分',
    value: `${overview.value.averageScore}分`,
    icon: 'TrophyOutlined',
    color: '#52c41a'
  },
  {
    title: '通过率',
    value: `${overview.value.passRate}%`,
    icon: 'CheckCircleOutlined',
    color: '#722ed1'
  },
  {
    title: '今日新增',
    value: overview.value.todayUploads,
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
    width: 100,
    sorter: (a: DepartmentStats, b: DepartmentStats) => a.recordCount - b.recordCount
  },
  {
    title: '平均评分',
    dataIndex: 'averageScore',
    key: 'averageScore',
    width: 150,
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
  const iconMap: Record<string, unknown> = {
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
  loading.value = true

  const results = await Promise.allSettled([
    getStatisticsOverview(),
    getTrendData(selectedPeriod.value),
    getDepartmentStats(),
    getQCScoreDistribution(),
    getQCIssueStats()
  ])

  const failedModules: string[] = []

  if (results[0].status === 'fulfilled') {
    overview.value = results[0].value
  } else {
    failedModules.push('概览')
    overview.value = {
      totalRecords: 0,
      pendingRecords: 0,
      analyzingRecords: 0,
      completedRecords: 0,
      averageScore: 0,
      passRate: 0,
      todayUploads: 0,
      weeklyTrend: '0%'
    }
    console.error('加载统计概览失败:', results[0].reason)
  }

  if (results[1].status === 'fulfilled') {
    trendData.value = results[1].value
  } else {
    failedModules.push('趋势')
    trendData.value = []
    console.error('加载趋势数据失败:', results[1].reason)
  }

  if (results[2].status === 'fulfilled') {
    departmentStats.value = results[2].value
  } else {
    failedModules.push('科室统计')
    departmentStats.value = []
    console.error('加载科室统计失败:', results[2].reason)
  }

  if (results[3].status === 'fulfilled') {
    scoreDistribution.value = results[3].value
  } else {
    failedModules.push('评分分布')
    scoreDistribution.value = []
    console.error('加载评分分布失败:', results[3].reason)
  }

  if (results[4].status === 'fulfilled') {
    issueStats.value = results[4].value
  } else {
    failedModules.push('问题分类')
    issueStats.value = []
    console.error('加载问题分类失败:', results[4].reason)
  }

  if (failedModules.length === 5) {
    message.error('统计数据加载失败')
  } else if (failedModules.length > 0) {
    message.warning(`部分模块加载失败：${failedModules.join('、')}`)
  }

  loading.value = false
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

    const result = await exportStatisticsReport('excel')
    window.open(result.downloadUrl, '_blank', 'noopener')
    message.success(`报表导出成功${result.count ? `，共 ${result.count} 条记录` : ''}`)
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
.font-sans {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}

:deep(.ant-table-modern) .ant-table-thead > tr > th {
  background: transparent;
  border-bottom: 1px solid #f1f5f9;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
}

:deep(.ant-table-modern) .ant-table-tbody > tr > td {
  border-bottom: 1px solid #f8fafc;
  padding: 12px 8px;
}

:deep(.ant-table-modern) .ant-table-tbody > tr:last-child > td {
  border-bottom: none;
}
</style>
