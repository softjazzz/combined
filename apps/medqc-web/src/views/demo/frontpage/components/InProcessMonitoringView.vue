<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">事中监控</h2>
      <span class="text-sm text-slate-400">实时预警和编码建议</span>
      <span v-if="loading" class="ml-2">
        <LoadingOutlined class="text-blue-500 animate-spin" />
      </span>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">质量总数</div>
        <div class="flex items-baseline gap-1">
          <WarningOutlined class="text-yellow-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.total_alerts }}</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">严重预警</div>
        <div class="flex items-baseline gap-1">
          <CloseCircleOutlined class="text-red-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.severe_alerts }}</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">待处理建议</div>
        <div class="flex items-baseline gap-1">
          <InfoCircleOutlined class="text-blue-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.pending_suggestions }}</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">今日新增</div>
        <div class="flex items-baseline gap-1">
          <RiseOutlined class="text-green-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.today_new }}</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <!-- CMI Trend Chart -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">CMI 实时趋势 (近7日)</h3>
        <div ref="cmiChartRef" class="h-64"></div>
      </div>
      
      <!-- Cost Consumption Ratio Chart -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">费用消耗指数 (标杆值 < 1.0)</h3>
        <div ref="costChartRef" class="h-64"></div>
      </div>
    </div>

    <!-- DRG Forecast Table -->
    <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
      <div class="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">DRG 预警</h3>
        <a-select v-model:value="filterType" class="w-32" size="small">
          <a-select-option value="all">全部</a-select-option>
          <a-select-option value="warning">预警</a-select-option>
          <a-select-option value="normal">正常</a-select-option>
        </a-select>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left font-medium">病案号</th>
              <th class="px-4 py-3 text-left font-medium">科室</th>
              <th class="px-4 py-3 text-left font-medium">主诊断</th>
              <th class="px-4 py-3 text-left font-medium">预测DRG</th>
              <th class="px-4 py-3 text-left font-medium">费用消耗比</th>
              <th class="px-4 py-3 text-left font-medium">状态</th>
              <th class="px-4 py-3 text-left font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredAlerts" :key="item.id" class="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30">
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ item.case_no }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ item.dept }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ item.diagnosis }}</td>
              <td class="px-4 py-3 font-medium text-slate-700 dark:text-slate-300">{{ item.drg }}</td>
              <td class="px-4 py-3">
                <span :class="item.ratio > 1 ? 'text-red-600' : 'text-green-600'">{{ item.ratio }}</span>
              </td>
              <td class="px-4 py-3">
                <span v-if="item.status === 'warning'" class="px-2 py-1 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded text-xs">预警</span>
                <span v-else class="px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded text-xs">正常</span>
              </td>
              <td class="px-4 py-3">
                <button class="text-blue-500 hover:text-blue-600 text-xs">查看详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import {
  ArrowLeftOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  RiseOutlined,
  LoadingOutlined
} from '@ant-design/icons-vue'
import { panelApi } from '@/api/panel'
import type { DrgAlert, MonitoringStats, CmiTrend, DeptCostIndex } from '@/api/panel'

const cmiChartRef = ref<HTMLElement | null>(null)
const costChartRef = ref<HTMLElement | null>(null)
const filterType = ref('all')
const loading = ref(false)

let cmiChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null

// ==================== 响应式数据 ====================

const stats = ref<MonitoringStats>({
  total_alerts: 0,
  severe_alerts: 0,
  pending_suggestions: 0,
  today_new: 0,
})

const drgAlerts = ref<DrgAlert[]>([])

const filteredAlerts = computed(() => {
  if (filterType.value === 'all') return drgAlerts.value
  return drgAlerts.value.filter(a => a.status === filterType.value)
})

// ==================== 数据加载 ====================

async function loadData() {
  loading.value = true
  try {
    // 并行加载所有数据
    const [statsData, alertsData, cmiData, costData] = await Promise.all([
      panelApi.getMonitoringStats(),
      panelApi.getDrgAlerts(),
      panelApi.getCmiTrend(7),
      panelApi.getDeptCostIndex(),
    ])

    stats.value = statsData
    drgAlerts.value = alertsData

    // 渲染图表
    renderCmiChart(cmiData)
    renderCostChart(costData)
  } catch (error) {
    console.error('加载事中监控数据失败:', error)
    // 降级：使用 fallback 图表
    renderFallbackCharts()
  } finally {
    loading.value = false
  }
}

// ==================== 图表渲染 ====================

function renderCmiChart(data: CmiTrend) {
  if (!cmiChartRef.value) return
  cmiChart = echarts.init(cmiChartRef.value)
  cmiChart.setOption({
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.labels,
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#94a3b8' }
    },
    yAxis: {
      type: 'value',
      min: 0.8,
      max: 1.2,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8' }
    },
    series: [{
      data: data.values,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#3b82f6', width: 3 },
      itemStyle: { color: '#3b82f6' },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
        { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
      ])},
      markLine: {
        silent: true,
        lineStyle: { color: '#f59e0b', type: 'dashed' },
        data: [{ yAxis: data.benchmark }],
        label: { formatter: '标杆值' }
      }
    }]
  })
}

function renderCostChart(data: DeptCostIndex) {
  if (!costChartRef.value) return
  costChart = echarts.init(costChartRef.value)
  costChart.setOption({
    grid: { left: 60, right: 20, top: 40, bottom: 50 },
    xAxis: {
      type: 'category',
      data: data.departments,
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#94a3b8', rotate: 15 }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1.5,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8' }
    },
    series: [
      {
        type: 'bar',
        data: data.values.map(v => ({
          value: v,
          itemStyle: { color: v > data.benchmark ? '#ef4444' : '#22c55e' }
        })),
        barWidth: '40%'
      },
      {
        type: 'line',
        data: data.departments.map(() => data.benchmark),
        lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
        symbol: 'none',
      }
    ]
  })
}

function renderFallbackCharts() {
  // CMI fallback
  renderCmiChart({
    labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    values: [1.0, 1.05, 1.03, 1.08, 1.12, 1.09, 1.15],
    benchmark: 1.0
  })
  // Cost fallback
  renderCostChart({
    departments: ['心内科', '呼吸科', '骨科', '普外科', '神经内科', '神经外科', '消化内科', '泌尿外科'],
    values: [0.92, 0.89, 1.15, 0.85, 1.05, 1.28, 0.95, 0.88],
    benchmark: 1.0
  })
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  cmiChart?.dispose()
  costChart?.dispose()
})
</script>
