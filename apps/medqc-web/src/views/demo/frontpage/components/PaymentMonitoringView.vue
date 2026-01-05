<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">付费监测</h2>
      <span class="text-sm text-slate-400">DRG/DIP 付费预测与盈亏分析</span>
    </div>

    <!-- Summary Cards -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">本月总费用</div>
        <div class="flex items-baseline gap-1">
          <DollarOutlined class="text-blue-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">1,258</span>
          <span class="text-sm text-slate-400">万元</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">预计医保支付</div>
        <div class="flex items-baseline gap-1">
          <PayCircleOutlined class="text-green-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">1,006</span>
          <span class="text-sm text-slate-400">万元</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">预计盈余</div>
        <div class="flex items-baseline gap-1">
          <RiseOutlined class="text-green-500 text-lg" />
          <span class="text-2xl font-bold text-green-600">+125</span>
          <span class="text-sm text-slate-400">万元</span>
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">亏损病例</div>
        <div class="flex items-baseline gap-1">
          <FallOutlined class="text-red-500 text-lg" />
          <span class="text-2xl font-bold text-red-600">23</span>
          <span class="text-sm text-slate-400">例</span>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <!-- Payment Trend Chart -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">付费趋势 (近30日)</h3>
        <div ref="paymentTrendRef" class="h-64"></div>
      </div>
      
      <!-- DRG Distribution Chart -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">DRG 分组分布 (Top 10)</h3>
        <div ref="drgDistributionRef" class="h-64"></div>
      </div>
    </div>

    <!-- Payment Details Table -->
    <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
      <div class="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">付费明细</h3>
        <div class="flex gap-2">
          <a-select v-model:value="deptFilter" class="w-32" size="small">
            <a-select-option value="all">全部科室</a-select-option>
            <a-select-option value="cardiology">心内科</a-select-option>
            <a-select-option value="respiratory">呼吸科</a-select-option>
          </a-select>
          <a-select v-model:value="statusFilter" class="w-32" size="small">
            <a-select-option value="all">全部状态</a-select-option>
            <a-select-option value="profit">盈余</a-select-option>
            <a-select-option value="loss">亏损</a-select-option>
          </a-select>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left font-medium">病案号</th>
              <th class="px-4 py-3 text-left font-medium">科室</th>
              <th class="px-4 py-3 text-left font-medium">DRG分组</th>
              <th class="px-4 py-3 text-left font-medium">实际费用</th>
              <th class="px-4 py-3 text-left font-medium">医保支付</th>
              <th class="px-4 py-3 text-left font-medium">盈亏</th>
              <th class="px-4 py-3 text-left font-medium">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in paymentData" :key="item.id" class="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30">
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ item.caseNo }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ item.dept }}</td>
              <td class="px-4 py-3 font-medium text-slate-700 dark:text-slate-300">{{ item.drg }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">¥{{ item.actualCost.toLocaleString() }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">¥{{ item.payment.toLocaleString() }}</td>
              <td class="px-4 py-3">
                <span :class="item.profit >= 0 ? 'text-green-600' : 'text-red-600'">
                  {{ item.profit >= 0 ? '+' : '' }}¥{{ item.profit.toLocaleString() }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span v-if="item.profit >= 0" class="px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded text-xs">盈余</span>
                <span v-else class="px-2 py-1 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded text-xs">亏损</span>
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
  DollarOutlined,
  PayCircleOutlined,
  RiseOutlined,
  FallOutlined
} from '@ant-design/icons-vue'

const paymentTrendRef = ref<HTMLElement | null>(null)
const drgDistributionRef = ref<HTMLElement | null>(null)
const deptFilter = ref('all')
const statusFilter = ref('all')

let paymentChart: echarts.ECharts | null = null
let distributionChart: echarts.ECharts | null = null

const paymentData = [
  { id: 1, caseNo: '#2026010101', dept: '心内科', drg: 'FM19', actualCost: 28500, payment: 32000, profit: 3500 },
  { id: 2, caseNo: '#2026010102', dept: '呼吸科', drg: 'BW15', actualCost: 15200, payment: 14800, profit: -400 },
  { id: 3, caseNo: '#2026010103', dept: '骨科', drg: 'IB19', actualCost: 45000, payment: 48000, profit: 3000 },
  { id: 4, caseNo: '#2026010104', dept: '普外科', drg: 'GD15', actualCost: 12800, payment: 15000, profit: 2200 },
  { id: 5, caseNo: '#2026010105', dept: '神经内科', drg: 'BR23', actualCost: 38000, payment: 36500, profit: -1500 }
]

onMounted(() => {
  if (paymentTrendRef.value) {
    paymentChart = echarts.init(paymentTrendRef.value)
    paymentChart.setOption({
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      legend: { top: 0, textStyle: { color: '#94a3b8' } },
      xAxis: {
        type: 'category',
        data: Array.from({ length: 30 }, (_, i) => `${i + 1}日`),
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8', interval: 4 }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8', formatter: '{value}万' }
      },
      series: [
        {
          name: '实际费用',
          data: Array.from({ length: 30 }, () => Math.random() * 50 + 30),
          type: 'line',
          smooth: true,
          lineStyle: { color: '#3b82f6', width: 2 },
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: '医保支付',
          data: Array.from({ length: 30 }, () => Math.random() * 45 + 35),
          type: 'line',
          smooth: true,
          lineStyle: { color: '#22c55e', width: 2 },
          itemStyle: { color: '#22c55e' }
        }
      ]
    })
  }

  if (drgDistributionRef.value) {
    distributionChart = echarts.init(drgDistributionRef.value)
    distributionChart.setOption({
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'category',
        data: ['FM19', 'BW15', 'IB19', 'GD15', 'BR23', 'HC15', 'EB13', 'JB19', 'KB15', 'RB23'],
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: [{
        type: 'bar',
        data: [125, 98, 87, 76, 65, 54, 43, 32, 21, 15],
        itemStyle: { color: '#3b82f6' },
        barWidth: '50%'
      }]
    })
  }
})

onUnmounted(() => {
  paymentChart?.dispose()
  distributionChart?.dispose()
})
</script>
