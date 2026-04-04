<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
          <ArrowLeftOutlined class="text-lg" />
        </button>
        <h2 class="text-xl font-semibold text-slate-800 dark:text-white">
          付费监测
        </h2>
        <span class="text-sm text-slate-400">DRG/DIP 付费预测与盈亏分析</span>
      </div>
      <a-dropdown>
        <template #overlay>
          <a-menu @click="handleExport">
            <a-menu-item key="excel">
              <FileExcelOutlined /> 导出 Excel
            </a-menu-item>
            <a-menu-item key="pdf">
              <FilePdfOutlined /> 导出 PDF
            </a-menu-item>
            <a-menu-item key="word">
              <FileWordOutlined /> 导出 Word
            </a-menu-item>
          </a-menu>
        </template>
        <button
          class="rounded-lg bg-blue-500 px-4 py-2 text-sm text-white transition-colors hover:bg-blue-600"
        >
          <DownloadOutlined /> 导出报告
        </button>
      </a-dropdown>
    </div>

    <!-- 数据集管理面板 -->
    <DatasetUploadPanel
      class="mb-4"
      @data-changed="handleDatasetChanged"
    />

    <div
      v-if="!drgMockEnabled && !hasUploadedData"
      class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700"
    >
      当前处于真实优先模式。`payment` 页仍保留 Mock 数据兜底，便于演示。
    </div>

    <!-- Summary Cards -->
    <div class="grid grid-cols-4 gap-4 mb-4">
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
      >
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
          本月总费用
        </div>
        <div class="flex items-baseline gap-1">
          <DollarOutlined class="text-blue-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">{{
            formatWan(overview.actualCost)
          }}</span>
          <span class="text-sm text-slate-400">万元</span>
        </div>
      </div>

      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
      >
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
          预计医保支付
        </div>
        <div class="flex items-baseline gap-1">
          <PayCircleOutlined class="text-green-500 text-lg" />
          <span class="text-2xl font-bold text-slate-800 dark:text-white">{{
            formatWan(overview.payment)
          }}</span>
          <span class="text-sm text-slate-400">万元</span>
        </div>
      </div>

      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
      >
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
          预计盈亏
        </div>
        <div class="flex items-baseline gap-1">
          <RiseOutlined class="text-green-500 text-lg" />
          <span
            :class="overview.profit >= 0 ? 'text-green-600' : 'text-red-600'"
            class="text-2xl font-bold"
          >
            {{ formatWanSigned(overview.profit) }}
          </span>
          <span class="text-sm text-slate-400">万元</span>
        </div>
      </div>

      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
      >
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
          亏损病例
        </div>
        <div class="flex items-baseline gap-1">
          <FallOutlined class="text-red-500 text-lg" />
          <span class="text-2xl font-bold text-red-600">{{ overview.lossCases }}</span>
          <span class="text-sm text-slate-400">例</span>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-3 gap-4 mb-6">
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
              医保支付率自动核算
            </div>
            <div class="text-sm text-slate-700 dark:text-slate-200">
              整体口径 = 预计医保支付 / 实际费用
            </div>
          </div>
          <a-tag color="processing">
            总体
          </a-tag>
        </div>
        <div class="flex items-baseline gap-2 mb-2">
          <span class="text-3xl font-bold text-slate-800 dark:text-white">{{ overview.paymentRate.toFixed(1) }}%</span>
          <span class="text-sm text-slate-400">按全部病例自动汇总</span>
        </div>
        <a-progress
          :percent="Math.min(100, overview.paymentRate)"
          :stroke-color="
            overview.paymentRate >= 100
              ? '#22c55e'
              : overview.paymentRate >= 90
                ? '#3b82f6'
                : '#ef4444'
          "
          :show-info="false"
          size="small"
        />
      </div>

      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
              科室支付率筛选
            </div>
            <div class="text-sm text-slate-700 dark:text-slate-200">
              切换科室后自动重算支付率与盈亏
            </div>
          </div>
          <a-tag color="blue">
            {{ selectedDeptLabel }}
          </a-tag>
        </div>
        <a-select
          v-model:value="deptFilter"
          class="w-full mb-3"
          size="small"
        >
          <a-select-option
            v-for="option in activeDeptOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </a-select-option>
        </a-select>
        <div class="flex items-baseline gap-2 mb-2">
          <span class="text-3xl font-bold text-slate-800 dark:text-white">{{ selectedDeptOverview.paymentRate.toFixed(1) }}%</span>
          <span class="text-sm text-slate-400">{{ selectedDeptOverview.caseCount }} 例病例</span>
        </div>
        <a-progress
          :percent="Math.min(100, selectedDeptOverview.paymentRate)"
          :stroke-color="
            selectedDeptOverview.paymentRate >= 100
              ? '#22c55e'
              : selectedDeptOverview.paymentRate >= 90
                ? '#3b82f6'
                : '#ef4444'
          "
          :show-info="false"
          size="small"
        />
      </div>

      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
              实时模拟分组与费用控制提示
            </div>
            <div class="text-sm text-slate-700 dark:text-slate-200">
              按成本消耗率分组，支付率单独核算
            </div>
          </div>
          <a-tag :color="activeGroupRule ? activeGroupRule.color : 'processing'">
            {{ selectedGroupLabel }}
          </a-tag>
        </div>
        <div class="grid grid-cols-3 gap-2">
          <div
            v-for="rule in paymentMonitoringRules"
            :key="rule.groupType"
            class="rounded-lg border p-3 transition-colors"
            :class="
              groupFilter === rule.groupType
                ? 'border-blue-300 bg-blue-50/70 dark:bg-blue-900/20'
                : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-700/30'
            "
          >
            <div class="flex items-center justify-between gap-2 mb-1">
              <a-tag
                :color="rule.color"
                class="m-0"
              >
                {{ rule.title }}
              </a-tag>
              <span class="text-xs text-slate-400">{{ getGroupCaseCount(rule.groupType) }} 例</span>
            </div>
            <div class="text-xs text-slate-500 dark:text-slate-400 leading-5">
              {{ rule.trigger }}
            </div>
            <div class="mt-1 text-xs text-slate-500 dark:text-slate-300 leading-5">
              {{ rule.suggestion }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <div class="flex items-start justify-between gap-4 mb-4">
          <div>
            <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">
              付费趋势 (近30日)
            </h3>
            <p class="text-xs text-slate-400 mt-1">
              实际费用、医保支付与支付率同屏展示
            </p>
          </div>
          <a-tag color="blue">
            静态可重复数据
          </a-tag>
        </div>
        <div
          ref="paymentTrendRef"
          class="h-64"
        />
      </div>

      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <div class="flex items-start justify-between gap-4 mb-4">
          <div>
            <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">
              DRG 分组分布 (按当前筛选)
            </h3>
            <p class="text-xs text-slate-400 mt-1">
              分组结果随科室、组别和状态联动更新
            </p>
          </div>
          <a-tag :color="getGroupTagColor(groupFilter)">
            当前：{{ selectedGroupLabel }}
          </a-tag>
        </div>
        <div
          ref="drgDistributionRef"
          class="h-64"
        />
      </div>
    </div>

    <!-- Payment Details Table -->
    <div
      class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700"
    >
      <div
        class="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
      >
        <div>
          <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">
            付费明细
          </h3>
          <div class="text-xs text-slate-400 mt-1">
            按科室、组别和状态联动筛选
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <a-segmented
            v-model:value="groupFilter"
            :options="paymentMonitoringGroupOptions"
          />
          <a-select
            v-model:value="statusFilter"
            class="w-32"
            size="small"
          >
            <a-select-option value="all">
              全部状态
            </a-select-option>
            <a-select-option value="profit">
              盈余
            </a-select-option>
            <a-select-option value="loss">
              亏损
            </a-select-option>
          </a-select>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm min-w-[1100px]">
          <thead class="bg-slate-50 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left font-medium">
                病案号
              </th>
              <th class="px-4 py-3 text-left font-medium">
                科室
              </th>
              <th class="px-4 py-3 text-left font-medium">
                DRG分组
              </th>
              <th class="px-4 py-3 text-left font-medium">
                实际费用
              </th>
              <th class="px-4 py-3 text-left font-medium">
                医保支付
              </th>
              <th class="px-4 py-3 text-left font-medium">
                医保支付率
              </th>
              <th class="px-4 py-3 text-left font-medium">
                盈亏
              </th>
              <th class="px-4 py-3 text-left font-medium">
                监测分组
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in filteredRows"
              :key="item.id"
              class="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30"
            >
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                {{ item.caseNo }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ item.deptName }}
              </td>
              <td class="px-4 py-3 font-medium text-slate-700 dark:text-slate-300">
                {{ item.drg }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                ¥{{ item.actualCost.toLocaleString() }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                ¥{{ item.payment.toLocaleString() }}
              </td>
              <td class="px-4 py-3">
                <div class="flex flex-col">
                  <span
                    :class="
                      calcPaymentRate(item) >= 100
                        ? 'text-green-600'
                        : calcPaymentRate(item) >= 90
                          ? 'text-blue-600'
                          : 'text-red-600'
                    "
                  >
                    {{ calcPaymentRate(item).toFixed(1) }}%
                  </span>
                  <span class="text-xs text-slate-400">成本消耗率 {{ calcCostRate(item).toFixed(1) }}%</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <span
                  :class="item.payment - item.actualCost >= 0 ? 'text-green-600' : 'text-red-600'"
                >
                  {{ item.payment - item.actualCost >= 0 ? '+' : '' }}¥{{
                    Math.abs(item.payment - item.actualCost).toLocaleString()
                  }}
                </span>
              </td>
              <td class="px-4 py-3">
                <a-tag :color="getGroupTagColor(resolveGroupType(item))">
                  {{ getPaymentGroupLabel(resolveGroupType(item)) }}
                </a-tag>
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td
                colspan="8"
                class="px-4 py-10 text-center text-slate-400"
              >
                当前筛选下暂无数据
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import {
  ArrowLeftOutlined,
  DollarOutlined,
  PayCircleOutlined,
  RiseOutlined,
  FallOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  FileWordOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import {
  calcCostRate,
  calcPaymentRate,
  filterPaymentMonitoringRows,
  getPaymentGroupColor,
  getPaymentGroupLabel,
  getPaymentMonitoringOverview,
  paymentMonitoringDeptOptions,
  paymentMonitoringGroupOptions,
  paymentMonitoringRows,
  paymentMonitoringRules,
  paymentMonitoringTrend,
  resolveGroupType,
  type PaymentGroupType,
  type PaymentMonitoringRow,
  type PaymentMonitoringOption,
} from '@/data/drg/mock-payment-monitoring'
import { isDrgMockModeEnabled, onDrgMockModeChange } from '@/utils/drgMockMode'
import { exportDrgMockReport, type DrgExportFormat } from '@/utils/drgMockExport'
import { useDrgDatasetStore } from '@/stores/drgDataset'
import { mapCaseRecordsToPaymentMonitoringRows } from '@/utils/drg-aggregation'
import DatasetUploadPanel from '@/components/drg/DatasetUploadPanel.vue'

const drgDatasetStore = useDrgDatasetStore()
const hasUploadedData = computed(() => drgDatasetStore.hasUploadedData)

// 数据源：优先从上传数据 Store 映射，无上传数据时回退到原始 Mock
const activeRows = computed<PaymentMonitoringRow[]>(() => {
  if (hasUploadedData.value) {
    return mapCaseRecordsToPaymentMonitoringRows(drgDatasetStore.records)
  }
  return paymentMonitoringRows
})

// 动态科室选项（上传数据时从实际数据生成）
const activeDeptOptions = computed<PaymentMonitoringOption[]>(() => {
  if (!hasUploadedData.value) return paymentMonitoringDeptOptions
  const depts = [...new Set(activeRows.value.map((r) => r.deptKey))]
  return [
    { label: '全部科室', value: 'all' },
    ...depts.map((d) => {
      const row = activeRows.value.find((r) => r.deptKey === d)
      return { label: row?.deptName || d, value: d }
    }),
  ]
})

const paymentTrendRef = ref<HTMLElement | null>(null)
const drgDistributionRef = ref<HTMLElement | null>(null)
const deptFilter = ref('all')
const statusFilter = ref<'all' | 'profit' | 'loss'>('all')
const groupFilter = ref<PaymentGroupType>('all')
const drgMockEnabled = ref(isDrgMockModeEnabled())

let paymentChart: echarts.ECharts | null = null
let distributionChart: echarts.ECharts | null = null
let unsubscribeDrgMockMode: (() => void) | null = null

const overview = computed(() => getPaymentMonitoringOverview(activeRows.value))
const selectedDeptRows = computed(() =>
  filterPaymentMonitoringRows(activeRows.value, { deptKey: deptFilter.value }),
)
const selectedDeptOverview = computed(() => getPaymentMonitoringOverview(selectedDeptRows.value))
const filteredRows = computed(() =>
  filterPaymentMonitoringRows(activeRows.value, {
    deptKey: deptFilter.value,
    groupType: groupFilter.value,
    status: statusFilter.value,
  }),
)
const chartRows = computed(() =>
  [...filteredRows.value].sort((left, right) => right.actualCost - left.actualCost).slice(0, 10),
)

const selectedDeptLabel = computed(() => {
  return (
    paymentMonitoringDeptOptions.find((option) => option.value === deptFilter.value)?.label ||
    '全部科室'
  )
})

const selectedGroupLabel = computed(() => {
  return (
    paymentMonitoringGroupOptions.find((option) => option.value === groupFilter.value)?.label ||
    '全部组别'
  )
})

const activeGroupRule = computed(() => {
  if (groupFilter.value === 'all') return null
  return paymentMonitoringRules.find((rule) => rule.groupType === groupFilter.value) || null
})

function getGroupTagColor(groupType: PaymentGroupType): 'processing' | 'warning' | 'error' {
  if (groupType === 'all') return 'processing'
  return getPaymentGroupColor(groupType)
}

function formatWan(value: number): string {
  return (value / 10000).toLocaleString('zh-CN', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

function formatWanSigned(value: number): string {
  const prefix = value >= 0 ? '+' : '-'
  return `${prefix}${formatWan(Math.abs(value))}`
}

function getGroupCaseCount(groupType: Exclude<PaymentGroupType, 'all'>): number {
  return selectedDeptRows.value.filter((row) => resolveGroupType(row) === groupType).length
}

function buildExportPayload() {
  const now = new Date().toLocaleString('zh-CN')
  return {
    title: 'DRG/DIP 付费监测演示报告',
    filenameBase: `drg_payment_${Date.now()}`,
    meta: [
      ['导出时间', now],
      ['数据模式', drgMockEnabled.value ? 'Mock 演示模式' : '真实优先模式（当前页导出为演示快照）'],
      ['科室筛选', selectedDeptLabel.value],
      ['监测分组', selectedGroupLabel.value],
      [
        '盈亏筛选',
        statusFilter.value === 'all'
          ? '全部状态'
          : statusFilter.value === 'profit'
            ? '盈余'
            : '亏损',
      ],
    ] as Array<[string, string]>,
    kpis: [
      ['病例数', String(overview.value.caseCount)],
      ['预计医保支付率', `${overview.value.paymentRate.toFixed(1)}%`],
      ['本月总费用', `${formatWan(overview.value.actualCost)} 万元`],
      ['预计医保支付', `${formatWan(overview.value.payment)} 万元`],
      ['预计盈亏', `${formatWanSigned(overview.value.profit)} 万元`],
      ['亏损病例', `${overview.value.lossCases}`],
    ] as Array<[string, string]>,
    sections: [
      {
        title: '付费明细',
        columns: [
          '病案号',
          '科室',
          'DRG',
          '实际费用(元)',
          '医保支付(元)',
          '医保支付率(%)',
          '成本消耗率(%)',
          '盈亏(元)',
          '监测分组',
        ],
        rows: filteredRows.value.map((row) => [
          row.caseNo,
          row.deptName,
          row.drg,
          row.actualCost,
          row.payment,
          calcPaymentRate(row).toFixed(1),
          calcCostRate(row).toFixed(1),
          row.payment - row.actualCost,
          getPaymentGroupLabel(resolveGroupType(row)),
        ]),
      },
    ],
  }
}

function handleExport({ key }: MenuInfo) {
  const keyStr = String(key)
  if (keyStr !== 'excel' && keyStr !== 'pdf' && keyStr !== 'word') return
  exportDrgMockReport(keyStr as DrgExportFormat, buildExportPayload())
  message.success(`${keyStr.toUpperCase()} 报告导出成功`)
}

function renderPaymentTrendChart() {
  if (!paymentTrendRef.value) return

  paymentChart?.dispose()
  paymentChart = echarts.init(paymentTrendRef.value)
  paymentChart.setOption({
    grid: { left: 56, right: 56, top: 44, bottom: 30 },
    legend: { top: 0, textStyle: { color: '#94a3b8' } },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: paymentMonitoringTrend.map((point) => `${point.day}日`),
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#94a3b8', interval: 4 },
    },
    yAxis: [
      {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8', formatter: '{value}万' },
      },
      {
        type: 'value',
        min: 70,
        max: 105,
        axisLine: { show: false },
        splitLine: { show: false },
        axisLabel: { color: '#94a3b8', formatter: '{value}%' },
      },
    ],
    series: [
      {
        name: '实际费用',
        data: paymentMonitoringTrend.map((point) => point.actualCost),
        type: 'line',
        smooth: true,
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
      },
      {
        name: '医保支付',
        data: paymentMonitoringTrend.map((point) => point.payment),
        type: 'line',
        smooth: true,
        lineStyle: { color: '#22c55e', width: 2 },
        itemStyle: { color: '#22c55e' },
      },
      {
        name: '支付率',
        data: paymentMonitoringTrend.map((point) => point.paymentRate),
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#f59e0b' },
      },
    ],
  })
}

function renderDistributionChart() {
  if (!drgDistributionRef.value) return

  distributionChart?.dispose()
  distributionChart = echarts.init(drgDistributionRef.value)
  const rows = chartRows.value

  distributionChart.setOption({
    grid: { left: 72, right: 24, top: 24, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const item = Array.isArray(params) ? params[0] : params
        const row = rows[item.dataIndex] as PaymentMonitoringRow | undefined
        if (!row) return ''
        const groupType = resolveGroupType(row)
        return [
          `${row.drg} · ${row.deptName}`,
          `监测分组：${getPaymentGroupLabel(groupType)}`,
          `实际费用：${formatWan(row.actualCost)} 万元`,
          `医保支付：${formatWan(row.payment)} 万元`,
          `成本消耗率：${calcCostRate(row).toFixed(1)}%`,
        ].join('<br/>')
      },
    },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8', formatter: '{value}万' },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.drg),
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#94a3b8' },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((row) => Number((row.actualCost / 10000).toFixed(1))),
        barWidth: '52%',
        itemStyle: {
          color: (params: any) => {
            const row = rows[params.dataIndex] as PaymentMonitoringRow | undefined
            if (!row) return '#3b82f6'
            const groupType = resolveGroupType(row)
            if (groupType === 'high') return '#ef4444'
            if (groupType === 'low') return '#f59e0b'
            return '#3b82f6'
          },
        },
      },
    ],
  })
}

watch([deptFilter, statusFilter, groupFilter], () => {
  renderDistributionChart()
})

onMounted(() => {
  drgMockEnabled.value = isDrgMockModeEnabled()
  unsubscribeDrgMockMode = onDrgMockModeChange((enabled) => {
    drgMockEnabled.value = enabled
  })
  renderPaymentTrendChart()
  renderDistributionChart()
})

/** 数据集变更（上传/清除）后刷新图表 */
function handleDatasetChanged() {
  deptFilter.value = 'all'
  groupFilter.value = 'all'
  statusFilter.value = 'all'
  renderDistributionChart()
}

onUnmounted(() => {
  unsubscribeDrgMockMode?.()
  paymentChart?.dispose()
  distributionChart?.dispose()
})
</script>
