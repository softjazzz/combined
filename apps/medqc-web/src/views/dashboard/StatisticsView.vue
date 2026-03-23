<template>
  <div class="statistics-container p-8 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">
        统计分析
      </h1>
      <p class="text-gray-600">
        医疗质控系统数据统计与分析报告
      </p>
    </div>

    <!-- 时间范围选择 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold text-gray-800">
          数据统计
        </h2>
        <div class="flex items-center space-x-4">
          <a-range-picker
            v-model:value="dateRange"
            :presets="datePresets"
            class="rounded-lg"
            @change="handleDateChange"
          />
          <a-button
            type="primary"
            :loading="loading"
            class="rounded-lg"
            @click="handleRefresh"
          >
            <ReloadOutlined />
            刷新数据
          </a-button>
        </div>
      </div>
    </div>

    <!-- 统计概览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              总病案数
            </p>
            <p class="text-3xl font-bold text-gray-800">
              {{ statistics.totalRecords }}
            </p>
            <div class="flex items-center mt-2">
              <ArrowUpOutlined class="text-green-500 text-xs mr-1" />
              <span class="text-green-500 text-sm">+12.5%</span>
              <span class="text-gray-500 text-sm ml-2">较上月</span>
            </div>
          </div>
          <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
            <FileTextOutlined class="text-blue-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              质控通过率
            </p>
            <p class="text-3xl font-bold text-gray-800">
              {{ statistics.passRate }}%
            </p>
            <div class="flex items-center mt-2">
              <ArrowUpOutlined class="text-green-500 text-xs mr-1" />
              <span class="text-green-500 text-sm">+3.2%</span>
              <span class="text-gray-500 text-sm ml-2">较上月</span>
            </div>
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
              平均处理时间
            </p>
            <p class="text-3xl font-bold text-gray-800">
              {{ statistics.avgProcessTime }}h
            </p>
            <div class="flex items-center mt-2">
              <ArrowDownOutlined class="text-red-500 text-xs mr-1" />
              <span class="text-red-500 text-sm">-8.1%</span>
              <span class="text-gray-500 text-sm ml-2">较上月</span>
            </div>
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
              AI准确率
            </p>
            <p class="text-3xl font-bold text-gray-800">
              {{ statistics.aiAccuracy }}%
            </p>
            <div class="flex items-center mt-2">
              <ArrowUpOutlined class="text-green-500 text-xs mr-1" />
              <span class="text-green-500 text-sm">+1.8%</span>
              <span class="text-gray-500 text-sm ml-2">较上月</span>
            </div>
          </div>
          <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
            <RobotOutlined class="text-purple-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-8">
      <!-- 质控趋势图 -->
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-xl font-semibold text-gray-800">
            质控趋势分析
          </h3>
          <a-select
            v-model:value="trendPeriod"
            style="width: 120px"
            :options="periodOptions"
            @change="handleTrendPeriodChange"
          />
        </div>
        <div class="h-80 bg-gray-50 rounded-lg flex items-center justify-center">
          <div class="text-center">
            <BarChartOutlined class="text-4xl text-gray-400 mb-4" />
            <p class="text-gray-500">
              质控趋势图表
            </p>
            <p class="text-sm text-gray-400">
              图表组件开发中...
            </p>
          </div>
        </div>
      </div>

      <!-- 科室分布图 -->
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-xl font-semibold text-gray-800">
            科室分布统计
          </h3>
          <a-button
            type="text"
            @click="handleExportChart"
          >
            <DownloadOutlined />
            导出
          </a-button>
        </div>
        <div class="h-80 bg-gray-50 rounded-lg flex items-center justify-center">
          <div class="text-center">
            <PieChartOutlined class="text-4xl text-gray-400 mb-4" />
            <p class="text-gray-500">
              科室分布饼图
            </p>
            <p class="text-sm text-gray-400">
              图表组件开发中...
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 详细统计表格 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
      <div class="flex items-center justify-between mb-6">
        <h3 class="text-xl font-semibold text-gray-800">
          科室详细统计
        </h3>
        <div class="flex space-x-2">
          <a-button
            class="rounded-lg"
            @click="handleExportTable"
          >
            <DownloadOutlined />
            导出表格
          </a-button>
          <a-button
            type="primary"
            class="rounded-lg"
            @click="handleGenerateReport"
          >
            <FileTextOutlined />
            生成报告
          </a-button>
        </div>
      </div>

      <a-table
        :columns="tableColumns"
        :data-source="departmentStats"
        :loading="tableLoading"
        :pagination="false"
        row-key="department"
        class="rounded-lg"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'passRate'">
            <div class="flex items-center">
              <a-progress 
                :percent="record.passRate" 
                size="small" 
                :stroke-color="getProgressColor(record.passRate)"
                class="flex-1 mr-2"
              />
              <span class="text-sm font-medium">{{ record.passRate }}%</span>
            </div>
          </template>
          <template v-if="column.key === 'trend'">
            <div class="flex items-center">
              <component 
                :is="record.trend > 0 ? ArrowUpOutlined : ArrowDownOutlined"
                :class="record.trend > 0 ? 'text-green-500' : 'text-red-500'"
                class="text-xs mr-1"
              />
              <span
                :class="record.trend > 0 ? 'text-green-500' : 'text-red-500'"
                class="text-sm"
              >
                {{ Math.abs(record.trend) }}%
              </span>
            </div>
          </template>
          <template v-if="column.key === 'action'">
            <div class="flex space-x-2">
              <a-button
                type="link"
                size="small"
                @click="handleViewDetail(record)"
              >
                <EyeOutlined />
                详情
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="handleDepartmentReport(record)"
              >
                <FileTextOutlined />
                报告
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import {
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  RobotOutlined,
  BarChartOutlined,
  PieChartOutlined,
  DownloadOutlined,
  EyeOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const tableLoading = ref(false)
const dateRange = ref([dayjs().subtract(30, 'day'), dayjs()])
const trendPeriod = ref('month')

// 统计数据
const statistics = ref({
  totalRecords: 1247,
  passRate: 94.2,
  avgProcessTime: 2.8,
  aiAccuracy: 96.5
})

// 科室统计数据
const departmentStats = ref([
  {
    department: '内科',
    totalRecords: 342,
    passedRecords: 325,
    passRate: 95.0,
    avgTime: 2.5,
    trend: 3.2
  },
  {
    department: '外科',
    totalRecords: 298,
    passedRecords: 276,
    passRate: 92.6,
    avgTime: 3.1,
    trend: -1.8
  },
  {
    department: '儿科',
    totalRecords: 186,
    passedRecords: 178,
    passRate: 95.7,
    avgTime: 2.2,
    trend: 5.1
  },
  {
    department: '妇产科',
    totalRecords: 234,
    passedRecords: 218,
    passRate: 93.2,
    avgTime: 2.9,
    trend: 2.3
  },
  {
    department: '急诊科',
    totalRecords: 187,
    passedRecords: 169,
    passRate: 90.4,
    avgTime: 3.8,
    trend: -2.1
  }
])

// 日期预设选项
const datePresets = [
  { label: '最近7天', value: [dayjs().subtract(7, 'day'), dayjs()] },
  { label: '最近30天', value: [dayjs().subtract(30, 'day'), dayjs()] },
  { label: '最近3个月', value: [dayjs().subtract(3, 'month'), dayjs()] },
  { label: '最近6个月', value: [dayjs().subtract(6, 'month'), dayjs()] }
]

// 时间周期选项
const periodOptions = [
  { value: 'week', label: '按周' },
  { value: 'month', label: '按月' },
  { value: 'quarter', label: '按季度' }
]

interface DepartmentStatsRow {
  department: string
  totalRecords: number
  passedRecords: number
  passRate: number
  avgTime: number
  trend: number
}

// 表格列配置
const tableColumns = [
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 120
  },
  {
    title: '总病案数',
    dataIndex: 'totalRecords',
    key: 'totalRecords',
    width: 120,
    sorter: (a: DepartmentStatsRow, b: DepartmentStatsRow) => a.totalRecords - b.totalRecords
  },
  {
    title: '通过数',
    dataIndex: 'passedRecords',
    key: 'passedRecords',
    width: 100
  },
  {
    title: '通过率',
    dataIndex: 'passRate',
    key: 'passRate',
    width: 200,
    sorter: (a: DepartmentStatsRow, b: DepartmentStatsRow) => a.passRate - b.passRate
  },
  {
    title: '平均处理时间(h)',
    dataIndex: 'avgTime',
    key: 'avgTime',
    width: 150,
    sorter: (a: DepartmentStatsRow, b: DepartmentStatsRow) => a.avgTime - b.avgTime
  },
  {
    title: '趋势',
    dataIndex: 'trend',
    key: 'trend',
    width: 100
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
    fixed: 'right'
  }
]

// 工具函数
const getProgressColor = (percent: number) => {
  if (percent >= 95) return '#52c41a'
  if (percent >= 90) return '#faad14'
  return '#ff4d4f'
}

// 事件处理函数
const handleDateChange = (dates: [Dayjs, Dayjs] | null) => {
  if (dates) {
    fetchStatistics()
  }
}

const handleRefresh = () => {
  fetchStatistics()
  fetchDepartmentStats()
}

const handleTrendPeriodChange = () => {
  message.info(`切换到${trendPeriod.value === 'week' ? '按周' : trendPeriod.value === 'month' ? '按月' : '按季度'}统计`)
}

const handleExportChart = () => {
  message.info('导出图表')
}

const handleExportTable = () => {
  message.info('导出表格数据')
}

const handleGenerateReport = () => {
  message.info('生成统计报告')
}

const handleViewDetail = (record: DepartmentStatsRow) => {
  message.info(`查看${record.department}详细统计`)
}

const handleDepartmentReport = (record: DepartmentStatsRow) => {
  message.info(`生成${record.department}报告`)
}

// 数据获取函数
const fetchStatistics = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    // 模拟数据更新
    statistics.value = {
      totalRecords: Math.floor(Math.random() * 500) + 1000,
      passRate: Math.floor(Math.random() * 10) + 90,
      avgProcessTime: Math.round((Math.random() * 2 + 2) * 10) / 10,
      aiAccuracy: Math.floor(Math.random() * 5) + 95
    }
  } catch (error) {
    message.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
}

const fetchDepartmentStats = async () => {
  tableLoading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 800))
    // 数据已在初始化时设置
  } catch (error) {
    message.error('获取科室统计数据失败')
  } finally {
    tableLoading.value = false
  }
}

onMounted(() => {
  fetchStatistics()
  fetchDepartmentStats()
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

:deep(.ant-progress-inner) {
  background-color: #f0f0f0;
}
</style>
