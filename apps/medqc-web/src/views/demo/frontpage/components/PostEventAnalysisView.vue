<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">事后分析</h2>
      <span class="text-sm text-slate-400">基于大数据的病案质量分析与趋势预测</span>
    </div>

    <!-- Time Range Selector -->
    <div class="flex items-center gap-4 mb-6">
      <a-range-picker v-model:value="dateRange" class="w-80" />
      <a-select v-model:value="analysisType" class="w-40">
        <a-select-option value="quality">质量分析</a-select-option>
        <a-select-option value="cost">费用分析</a-select-option>
        <a-select-option value="drg">DRG分析</a-select-option>
      </a-select>
      <button class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
        生成报告
      </button>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-5 gap-4 mb-6">
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">病案总数</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">1,258</div>
        <div class="text-xs text-green-600 mt-1">↑ 12.5%</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">平均CMI</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">1.08</div>
        <div class="text-xs text-green-600 mt-1">↑ 3.2%</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">编码准确率</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">96.8%</div>
        <div class="text-xs text-green-600 mt-1">↑ 1.5%</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">平均住院日</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">8.5</div>
        <div class="text-xs text-red-600 mt-1">↓ 0.8天</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">费用消耗指数</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">0.95</div>
        <div class="text-xs text-green-600 mt-1">↓ 0.05</div>
      </div>
    </div>

    <!-- Charts Grid -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <!-- Quality Trend -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">质量趋势分析</h3>
        <div ref="qualityTrendRef" class="h-64"></div>
      </div>
      
      <!-- Department Comparison -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">科室对比分析</h3>
        <div ref="deptComparisonRef" class="h-64"></div>
      </div>

      <!-- DRG Distribution -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">DRG 分组占比</h3>
        <div ref="drgPieRef" class="h-64"></div>
      </div>

      <!-- Cost Analysis -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">费用结构分析</h3>
        <div ref="costStructureRef" class="h-64"></div>
      </div>
    </div>

    <!-- Issue Summary -->
    <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
      <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">问题汇总与建议</h3>
      <div class="space-y-3">
        <div class="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30">
          <ExclamationCircleOutlined class="text-red-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-red-700 dark:text-red-300 mb-1">编码准确性问题</div>
            <div class="text-sm text-red-600/80 dark:text-red-400/80">发现23例主诊断编码与临床诊断不符，建议加强编码培训</div>
          </div>
        </div>
        
        <div class="flex items-start gap-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/30">
          <WarningOutlined class="text-yellow-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-yellow-700 dark:text-yellow-300 mb-1">费用消耗异常</div>
            <div class="text-sm text-yellow-600/80 dark:text-yellow-400/80">骨科和神经内科费用消耗指数偏高，需关注成本控制</div>
          </div>
        </div>
        
        <div class="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-900/30">
          <InfoCircleOutlined class="text-blue-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-blue-700 dark:text-blue-300 mb-1">优化建议</div>
            <div class="text-sm text-blue-600/80 dark:text-blue-400/80">建议优化心内科和呼吸科的诊疗路径，可提升CMI约5%</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import {
  ArrowLeftOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'

const qualityTrendRef = ref<HTMLElement | null>(null)
const deptComparisonRef = ref<HTMLElement | null>(null)
const drgPieRef = ref<HTMLElement | null>(null)
const costStructureRef = ref<HTMLElement | null>(null)

const dateRange = ref<any>(null)
const analysisType = ref('quality')

let qualityChart: echarts.ECharts | null = null
let deptChart: echarts.ECharts | null = null
let drgChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null

onMounted(() => {
  if (qualityTrendRef.value) {
    qualityChart = echarts.init(qualityTrendRef.value)
    qualityChart.setOption({
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      legend: { top: 0, textStyle: { color: '#94a3b8' } },
      xAxis: {
        type: 'category',
        data: ['1月', '2月', '3月', '4月', '5月', '6月'],
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: [
        {
          name: '编码准确率',
          data: [94.5, 95.2, 95.8, 96.1, 96.5, 96.8],
          type: 'line',
          smooth: true,
          lineStyle: { color: '#3b82f6', width: 2 },
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: 'CMI',
          data: [1.02, 1.03, 1.05, 1.06, 1.07, 1.08],
          type: 'line',
          smooth: true,
          lineStyle: { color: '#22c55e', width: 2 },
          itemStyle: { color: '#22c55e' }
        }
      ]
    })
  }

  if (deptComparisonRef.value) {
    deptChart = echarts.init(deptComparisonRef.value)
    deptChart.setOption({
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      legend: { top: 0, textStyle: { color: '#94a3b8' } },
      xAxis: {
        type: 'category',
        data: ['心内科', '呼吸科', '骨科', '普外科', '神经内科'],
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: [
        {
          name: 'CMI',
          data: [1.15, 0.98, 1.25, 0.85, 1.32],
          type: 'bar',
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: '费用消耗指数',
          data: [0.92, 0.95, 1.08, 0.88, 1.02],
          type: 'bar',
          itemStyle: { color: '#22c55e' }
        }
      ]
    })
  }

  if (drgPieRef.value) {
    drgChart = echarts.init(drgPieRef.value)
    drgChart.setOption({
      legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        data: [
          { value: 125, name: 'FM19', itemStyle: { color: '#3b82f6' } },
          { value: 98, name: 'BW15', itemStyle: { color: '#22c55e' } },
          { value: 87, name: 'IB19', itemStyle: { color: '#f59e0b' } },
          { value: 76, name: 'GD15', itemStyle: { color: '#ef4444' } },
          { value: 65, name: 'BR23', itemStyle: { color: '#8b5cf6' } },
          { value: 120, name: '其他', itemStyle: { color: '#94a3b8' } }
        ],
        label: { color: '#64748b' }
      }]
    })
  }

  if (costStructureRef.value) {
    costChart = echarts.init(costStructureRef.value)
    costChart.setOption({
      grid: { left: 80, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'category',
        data: ['药品费', '检查费', '治疗费', '手术费', '材料费', '床位费'],
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: [{
        type: 'bar',
        data: [3500, 2800, 2200, 4500, 3200, 800],
        itemStyle: { color: '#3b82f6' },
        barWidth: '50%'
      }]
    })
  }
})

onUnmounted(() => {
  qualityChart?.dispose()
  deptChart?.dispose()
  drgChart?.dispose()
  costChart?.dispose()
})
</script>
