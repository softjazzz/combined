<template>
  <div class="qc-trend-chart">
    <!-- 图表控制栏 -->
    <div class="chart-controls mb-4">
      <div class="flex justify-between items-center">
        <div class="flex items-center space-x-4">
          <a-radio-group
            v-model:value="chartType"
            button-style="solid"
            size="small"
          >
            <a-radio-button value="line">
              趋势图
            </a-radio-button>
            <a-radio-button value="bar">
              柱状图
            </a-radio-button>
            <a-radio-button value="area">
              面积图
            </a-radio-button>
          </a-radio-group>
          
          <a-select 
            v-model:value="selectedMetric" 
            style="width: 120px" 
            size="small"
            @change="handleMetricChange"
          >
            <a-select-option value="all">
              全部指标
            </a-select-option>
            <a-select-option value="count">
              病案数量
            </a-select-option>
            <a-select-option value="score">
              平均评分
            </a-select-option>
            <a-select-option value="pass_rate">
              通过率
            </a-select-option>
          </a-select>
        </div>
        
        <div class="flex items-center space-x-2">
          <a-tooltip title="刷新数据">
            <a-button 
              type="text" 
              size="small" 
              :icon="h(ReloadOutlined)"
              :loading="loading"
              @click="refreshData"
            />
          </a-tooltip>
          
          <a-tooltip title="导出图表">
            <a-button 
              type="text" 
              size="small" 
              :icon="h(DownloadOutlined)"
              @click="exportChart"
            />
          </a-tooltip>
          
          <a-tooltip title="查看详情">
            <a-button 
              type="text" 
              size="small" 
              :icon="h(EyeOutlined)"
              @click="showDetail"
            />
          </a-tooltip>
        </div>
      </div>
    </div>

    <!-- 图表容器 -->
    <div
      class="chart-container"
      :style="{ height: props.height + 'px' }"
    >
      <div
        v-if="loading"
        class="chart-loading"
      >
        <a-spin size="large" />
        <p class="mt-4 text-gray-500">
          正在加载数据...
        </p>
      </div>
      
      <div
        v-else-if="error"
        class="chart-error"
      >
        <ExclamationCircleOutlined class="text-4xl text-red-500 mb-4" />
        <p class="text-gray-600 mb-4">
          {{ error }}
        </p>
        <a-button
          type="primary"
          @click="refreshData"
        >
          重新加载
        </a-button>
      </div>
      
      <div
        v-else
        class="chart-content"
      >
        <!-- 简化的图表展示 -->
        <div class="chart-display">
          <div class="chart-header mb-4">
            <h3 class="text-lg font-semibold text-gray-800">
              质控趋势分析
            </h3>
            <p class="text-sm text-gray-600">
              {{ getDateRange() }}
            </p>
          </div>
          
          <!-- 数据可视化 -->
          <div class="chart-visualization">
            <div class="grid grid-cols-12 gap-1 mb-4">
              <div 
                v-for="(item, index) in chartData" 
                :key="index"
                class="chart-bar"
                @click="selectDataPoint(item)"
              >
                <div class="bar-container">
                  <!-- 病案数量柱状图 -->
                  <div 
                    v-if="selectedMetric === 'all' || selectedMetric === 'count'"
                    class="bar count-bar"
                    :style="{ 
                      height: (item.count / maxCount * 100) + '%',
                      backgroundColor: '#2b6cf6'
                    }"
                    :title="`${item.date}: ${item.count}个病案`"
                  />
                  
                  <!-- 评分柱状图 -->
                  <div 
                    v-if="selectedMetric === 'all' || selectedMetric === 'score'"
                    class="bar score-bar"
                    :style="{ 
                      height: (item.score / 100 * 100) + '%',
                      backgroundColor: '#52c41a'
                    }"
                    :title="`${item.date}: ${item.score}分`"
                  />
                  
                  <!-- 通过率柱状图 -->
                  <div 
                    v-if="selectedMetric === 'all' || selectedMetric === 'pass_rate'"
                    class="bar pass-rate-bar"
                    :style="{ 
                      height: (item.pass_rate / 100 * 100) + '%',
                      backgroundColor: '#faad14'
                    }"
                    :title="`${item.date}: ${item.pass_rate}%`"
                  />
                </div>
                
                <div class="bar-label">
                  {{ item.date.split('-')[1] }}月
                </div>
              </div>
            </div>
          </div>
          
          <!-- 趋势线图 -->
          <div
            v-if="chartType === 'line'"
            class="trend-lines"
          >
            <svg
              width="100%"
              height="100"
              class="trend-svg"
            >
              <!-- 病案数量趋势线 -->
              <polyline
                v-if="selectedMetric === 'all' || selectedMetric === 'count'"
                :points="getLinePoints('count')"
                stroke="#2b6cf6"
                stroke-width="2"
                fill="none"
              />
              
              <!-- 评分趋势线 -->
              <polyline
                v-if="selectedMetric === 'all' || selectedMetric === 'score'"
                :points="getLinePoints('score')"
                stroke="#52c41a"
                stroke-width="2"
                fill="none"
              />
              
              <!-- 通过率趋势线 -->
              <polyline
                v-if="selectedMetric === 'all' || selectedMetric === 'pass_rate'"
                :points="getLinePoints('pass_rate')"
                stroke="#faad14"
                stroke-width="2"
                fill="none"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表说明 -->
    <div class="chart-legend mt-4">
      <div class="flex flex-wrap gap-4 text-sm">
        <div
          v-for="item in legendItems"
          :key="item.name"
          class="flex items-center"
        >
          <div 
            class="w-3 h-3 rounded-full mr-2"
            :style="{ backgroundColor: item.color }"
          />
          <span class="text-gray-600">{{ item.name }}</span>
          <span class="ml-2 font-medium">{{ item.value }}</span>
        </div>
      </div>
    </div>

    <!-- 数据详情抽屉 -->
    <a-drawer
      v-model:open="detailDrawerVisible"
      title="数据详情"
      placement="right"
      width="600"
    >
      <div class="data-detail">
        <a-table
          :columns="detailColumns"
          :data-source="detailData"
          :pagination="false"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'trend'">
              <div class="flex items-center">
                <component
                  :is="Number(record.trend) > 0 ? ArrowUpOutlined : ArrowDownOutlined"
                  :class="Number(record.trend) > 0 ? 'text-green-500' : 'text-red-500'"
                  class="mr-1"
                />
                <span :class="Number(record.trend) > 0 ? 'text-green-500' : 'text-red-500'">
                  {{ Math.abs(Number(record.trend)) }}%
                </span>
              </div>
            </template>
          </template>
        </a-table>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  ExclamationCircleOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined
} from '@ant-design/icons-vue'

interface Props {
  period: string
  height?: number
  autoRefresh?: boolean
}

interface ChartDataItem {
  date: string
  count: number
  score: number
  pass_rate: number
}

const props = withDefaults(defineProps<Props>(), {
  period: 'month',
  height: 400,
  autoRefresh: false
})

// 响应式数据
const loading = ref(false)
const error = ref('')
const detailDrawerVisible = ref(false)
const selectedDataPoint = ref<ChartDataItem | null>(null)

// 图表配置
const chartType = ref('line')
const selectedMetric = ref('all')

// 模拟数据
const chartData = ref<ChartDataItem[]>([
  { date: '2024-01', count: 156, score: 85.2, pass_rate: 92.3 },
  { date: '2024-02', count: 189, score: 87.1, pass_rate: 94.1 },
  { date: '2024-03', count: 234, score: 88.5, pass_rate: 95.2 },
  { date: '2024-04', count: 198, score: 86.8, pass_rate: 93.7 },
  { date: '2024-05', count: 267, score: 89.2, pass_rate: 96.1 },
  { date: '2024-06', count: 301, score: 90.1, pass_rate: 97.2 },
  { date: '2024-07', count: 278, score: 88.9, pass_rate: 95.8 },
  { date: '2024-08', count: 245, score: 87.6, pass_rate: 94.5 },
  { date: '2024-09', count: 289, score: 89.8, pass_rate: 96.7 },
  { date: '2024-10', count: 324, score: 91.2, pass_rate: 98.1 },
  { date: '2024-11', count: 298, score: 90.5, pass_rate: 97.4 },
  { date: '2024-12', count: 312, score: 91.8, pass_rate: 98.6 }
])

// 计算属性
const maxCount = computed(() => Math.max(...chartData.value.map(item => item.count)))

// 图例数据
const legendItems = computed(() => {
  const latest = chartData.value[chartData.value.length - 1]
  if (!latest) return []
  
  return [
    { name: '病案数量', value: `${latest.count}`, color: '#2b6cf6' },
    { name: '平均评分', value: `${latest.score}分`, color: '#52c41a' },
    { name: '通过率', value: `${latest.pass_rate}%`, color: '#faad14' }
  ]
})

// 详情表格配置
const detailColumns = [
  { title: '时间', dataIndex: 'date', key: 'date' },
  { title: '病案数量', dataIndex: 'count', key: 'count' },
  { title: '平均评分', dataIndex: 'score', key: 'score' },
  { title: '通过率(%)', dataIndex: 'pass_rate', key: 'pass_rate' },
  { title: '趋势', key: 'trend' }
]

const detailData = computed(() => {
  return chartData.value.map((item, index) => ({
    ...item,
    trend: index > 0 ? 
      ((item.score - chartData.value[index - 1].score) / chartData.value[index - 1].score * 100).toFixed(1) : '0'
  }))
})

// 方法
const getDateRange = () => {
  const first = chartData.value[0]?.date
  const last = chartData.value[chartData.value.length - 1]?.date
  return `${first} 至 ${last}`
}

const getLinePoints = (metric: string) => {
  const width = 100 // SVG宽度百分比
  const height = 100 // SVG高度
  const points = chartData.value.map((item: ChartDataItem, index: number) => {
    const x = (index / (chartData.value.length - 1)) * width
    let y = 0
    
    if (metric === 'count') {
      y = height - (item.count / maxCount.value * height)
    } else if (metric === 'score') {
      y = height - (item.score / 100 * height)
    } else if (metric === 'pass_rate') {
      y = height - (item.pass_rate / 100 * height)
    }
    
    return `${x},${y}`
  })
  
  return points.join(' ')
}

const selectDataPoint = (item: ChartDataItem) => {
  selectedDataPoint.value = item
  message.info(`选中数据点: ${item.date}`)
}

const refreshData = async () => {
  loading.value = true
  error.value = ''
  
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 模拟数据变化
    chartData.value = chartData.value.map(item => ({
      ...item,
      count: item.count + Math.floor(Math.random() * 20 - 10),
      score: Math.min(100, Math.max(0, item.score + Math.random() * 4 - 2)),
      pass_rate: Math.min(100, Math.max(0, item.pass_rate + Math.random() * 2 - 1))
    }))
    
    message.success('数据刷新成功')
  } catch (err) {
    error.value = '数据加载失败'
    message.error('数据刷新失败')
  } finally {
    loading.value = false
  }
}

const exportChart = () => {
  // 简化的导出功能
  const data = chartData.value.map(item => ({
    日期: item.date,
    病案数量: item.count,
    平均评分: item.score,
    通过率: item.pass_rate
  }))
  
  console.log('导出数据:', data)
  message.success('图表数据已导出到控制台')
}

const showDetail = () => {
  detailDrawerVisible.value = true
}

const handleMetricChange = () => {
  // 指标变化处理
}

// 生命周期
onMounted(() => {
  // 初始化
})
</script>

<style scoped>
.qc-trend-chart {
  @apply w-full;
}

.chart-container {
  @apply relative w-full bg-white rounded-lg border;
}

.chart-loading,
.chart-error {
  @apply flex flex-col items-center justify-center h-full;
}

.chart-content {
  @apply w-full h-full p-4;
}

.chart-controls {
  @apply flex justify-between items-center p-3 bg-gray-50 rounded-lg;
}

.chart-display {
  @apply w-full h-full;
}

.chart-visualization {
  @apply relative;
}

.chart-bar {
  @apply cursor-pointer transition-all duration-200 hover:opacity-80;
}

.bar-container {
  @apply relative h-32 flex items-end justify-center space-x-1;
}

.bar {
  @apply w-full max-w-6 rounded-t transition-all duration-300;
  min-height: 4px;
}

.bar-label {
  @apply text-xs text-gray-500 text-center mt-1;
}

.trend-lines {
  @apply mt-4;
}

.trend-svg {
  @apply w-full;
}

.chart-legend {
  @apply p-3 bg-gray-50 rounded-lg;
}

.data-detail {
  @apply space-y-4;
}

:deep(.ant-radio-button-wrapper) {
  @apply border-gray-300;
}

:deep(.ant-radio-button-wrapper-checked) {
  @apply bg-blue-500 border-blue-500;
}
</style> 
