<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">事中监控</h2>
      <span class="text-sm text-slate-400">实时预警和编码建议</span>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">质量总数</div>
        <div class="flex items-baseline gap-1">
          <WarningOutlined class="text-yellow-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">6</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">严重预警</div>
        <div class="flex items-baseline gap-1">
          <CloseCircleOutlined class="text-red-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">3</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">待处理建议</div>
        <div class="flex items-baseline gap-1">
          <InfoCircleOutlined class="text-blue-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">8</span>
          <span class="text-sm text-slate-400">条</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">今日新增</div>
        <div class="flex items-baseline gap-1">
          <RiseOutlined class="text-green-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">15</span>
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
            <tr v-for="item in mockData" :key="item.id" class="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30">
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ item.caseNo }}</td>
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
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import {
  ArrowLeftOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  RiseOutlined
} from '@ant-design/icons-vue'

const cmiChartRef = ref<HTMLElement | null>(null)
const costChartRef = ref<HTMLElement | null>(null)
const filterType = ref('all')

let cmiChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null

const mockData = [
  // 严重预警 - 费用超标严重
  { id: 1, caseNo: '#2026010101', dept: '心内科', diagnosis: '急性心肌梗死', drg: 'FM19', ratio: 1.35, status: 'warning', los: 12, estCost: 85000 },
  { id: 2, caseNo: '#2026010108', dept: '神经外科', diagnosis: '颅内动脉瘤', drg: 'IC15', ratio: 1.28, status: 'warning', los: 18, estCost: 125000 },
  { id: 3, caseNo: '#2026010115', dept: '骨科', diagnosis: '股骨颈骨折', drg: 'IB19', ratio: 1.22, status: 'warning', los: 15, estCost: 65000 },
  
  // 一般预警 - 轻度超标
  { id: 4, caseNo: '#2026010103', dept: '骨科', diagnosis: '腰椎间盘突出', drg: 'EB13', ratio: 1.08, status: 'warning', los: 8, estCost: 38000 },
  { id: 5, caseNo: '#2026010105', dept: '神经内科', diagnosis: '急性脑梗死', drg: 'BR23', ratio: 1.05, status: 'warning', los: 10, estCost: 42000 },
  { id: 6, caseNo: '#2026010112', dept: '消化内科', diagnosis: '上消化道出血', drg: 'GD21', ratio: 1.03, status: 'warning', los: 7, estCost: 28000 },
  
  // 正常 - 费用控制良好
  { id: 7, caseNo: '#2026010102', dept: '呼吸科', diagnosis: '社区获得性肺炎', drg: 'BW15', ratio: 0.92, status: 'normal', los: 6, estCost: 18000 },
  { id: 8, caseNo: '#2026010104', dept: '普外科', diagnosis: '急性阑尾炎', drg: 'GD15', ratio: 0.85, status: 'normal', los: 4, estCost: 12000 },
  { id: 9, caseNo: '#2026010106', dept: '泌尿外科', diagnosis: '肾结石', drg: 'KB19', ratio: 0.88, status: 'normal', los: 5, estCost: 22000 },
  { id: 10, caseNo: '#2026010107', dept: '妇产科', diagnosis: '剖宫产', drg: 'MD15', ratio: 0.78, status: 'normal', los: 5, estCost: 15000 },
  { id: 11, caseNo: '#2026010109', dept: '儿科', diagnosis: '支气管肺炎', drg: 'BP11', ratio: 0.82, status: 'normal', los: 4, estCost: 8500 },
  { id: 12, caseNo: '#2026010110', dept: '肿瘤科', diagnosis: '肺癌化疗', drg: 'RA19', ratio: 0.95, status: 'normal', los: 6, estCost: 35000 },
  { id: 13, caseNo: '#2026010111', dept: '心内科', diagnosis: '心律失常', drg: 'FM15', ratio: 0.91, status: 'normal', los: 5, estCost: 25000 },
  { id: 14, caseNo: '#2026010113', dept: '呼吸科', diagnosis: '慢阻肺急性加重', drg: 'BW21', ratio: 0.89, status: 'normal', los: 7, estCost: 22000 },
  { id: 15, caseNo: '#2026010114', dept: '内分泌科', diagnosis: '糖尿病酮症酸中毒', drg: 'KB15', ratio: 0.95, status: 'normal', los: 6, estCost: 18000 }
]

onMounted(() => {
  if (cmiChartRef.value) {
    cmiChart = echarts.init(cmiChartRef.value)
    cmiChart.setOption({
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
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
        data: [1.0, 1.05, 1.03, 1.08, 1.12, 1.09, 1.15],
        type: 'line',
        smooth: true,
        lineStyle: { color: '#3b82f6', width: 3 },
        itemStyle: { color: '#3b82f6' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
          { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
        ])}
      }]
    })
  }

  if (costChartRef.value) {
    costChart = echarts.init(costChartRef.value)
    costChart.setOption({
      grid: { left: 60, right: 20, top: 40, bottom: 50 },
      xAxis: {
        type: 'category',
        data: ['心内科', '呼吸科', '骨科', '普外科', '神经内科', '神经外科', '消化内科', '泸尿外科'],
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
          data: [
            { value: 0.92, itemStyle: { color: '#22c55e' } },
            { value: 0.89, itemStyle: { color: '#22c55e' } },
            { value: 1.15, itemStyle: { color: '#ef4444' } },
            { value: 0.85, itemStyle: { color: '#22c55e' } },
            { value: 1.05, itemStyle: { color: '#ef4444' } },
            { value: 1.28, itemStyle: { color: '#ef4444' } },
            { value: 0.95, itemStyle: { color: '#22c55e' } },
            { value: 0.88, itemStyle: { color: '#22c55e' } }
          ],
          barWidth: '40%'
        },
        {
          type: 'line',
          data: [1, 1, 1, 1, 1, 1, 1, 1],
          lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
          symbol: 'none',
          markLine: {
            silent: true,
            lineStyle: { color: '#f59e0b', type: 'dashed' },
            data: [{ yAxis: 1 }]
          }
        }
      ]
    })
  }
})

onUnmounted(() => {
  cmiChart?.dispose()
  costChart?.dispose()
})
</script>
