<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">
        事后分析
      </h2>
      <span class="text-sm text-slate-400">基于大数据的病案质量分析与趋势预测</span>
    </div>

    <!-- 五级层级维度选择 -->
    <div
      class="flex items-center gap-4 mb-4 bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
    >
      <span class="text-sm font-medium text-slate-600 dark:text-slate-400">分析维度:</span>
      <a-radio-group
        v-model:value="analysisDimension"
        button-style="solid"
        size="small"
        @change="handleDimensionChange"
      >
        <a-radio-button value="hospital">
          全院概览
        </a-radio-button>
        <a-radio-button value="department">
          科室分析
        </a-radio-button>
        <a-radio-button value="ward">
          病区分析
        </a-radio-button>
        <a-radio-button value="chief_group">
          主诊医师组
        </a-radio-button>
        <a-radio-button value="person">
          个人
        </a-radio-button>
      </a-radio-group>
      <span class="ml-auto text-xs text-slate-400">当前: {{ dimensionLabel }}</span>
    </div>

    <!-- 数据集管理面板 -->
    <DatasetUploadPanel
      class="mb-4"
      @data-changed="handleDatasetChanged"
    />

    <!-- Time Range Selector -->
    <div class="flex items-center gap-4 mb-6">
      <div
        v-if="useDemoData || hasUploadedDataset"
        class="text-orange-500 text-sm flex items-center gap-2"
      >
        <WarningOutlined />
        <span>{{ drgModeHintText }}</span>
      </div>
      <a-range-picker
        v-if="!useDemoData && !hasUploadedDataset && batchId"
        v-model:value="dateRange"
        class="w-80"
      />
      <a-select
        v-model:value="analysisType"
        class="w-40"
      >
        <a-select-option value="quality">
          质量分析
        </a-select-option>
        <a-select-option value="cost">
          费用分析
        </a-select-option>
        <a-select-option value="drg">
          DRG分析
        </a-select-option>
      </a-select>
      <a-dropdown>
        <template #overlay>
          <a-menu
            @click="
              (info) => {
                void handleExport(info)
              }
            "
          >
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
          class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center gap-2"
        >
          <DownloadOutlined />
          导出报告
        </button>
      </a-dropdown>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-1 gap-4 mb-6 md:grid-cols-2 xl:grid-cols-4">
      <div
        v-for="card in kpiCards"
        :key="card.label"
        :class="['rounded-xl p-4 border bg-white dark:bg-slate-800', card.cardClass]"
      >
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">
          {{ card.label }}
        </div>
        <div
          class="text-2xl font-bold"
          :class="card.valueClass"
        >
          {{ card.value }}
        </div>
        <div
          class="text-xs mt-1"
          :class="card.hintClass"
        >
          {{ card.hint }}
        </div>
      </div>
    </div>

    <!-- Backend Generated Advanced Charts -->
    <div
      v-if="stats.charts && Object.keys(stats.charts).length > 0"
      class="flex flex-col gap-4 mb-6"
    >
      <div class="grid grid-cols-2 gap-4">
        <div
          v-show="stats.charts.profit_waterfall"
          class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
        >
          <div
            ref="waterfallRef"
            class="h-80 w-full"
          />
        </div>
        <div
          v-show="stats.charts.dept_profit_ranking"
          class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
        >
          <div
            ref="deptRankingRef"
            class="h-80 w-full"
          />
        </div>
      </div>
      <div
        v-show="stats.charts.drg_scatter"
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <div
          ref="drgScatterRef"
          class="h-96 w-full"
        />
      </div>
    </div>

    <!-- Fallback Charts Grid (Demo Data) -->
    <div
      v-else
      class="grid grid-cols-2 gap-4 mb-6"
    >
      <!-- Quality Trend -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
          {{ chartTitles.trend }}
        </h3>
        <div
          ref="qualityTrendRef"
          class="h-64"
        />
      </div>

      <!-- Department Comparison -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
          {{ chartTitles.comparison }}
        </h3>
        <div
          ref="deptComparisonRef"
          class="h-64"
        />
      </div>

      <!-- DRG Distribution -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
          DRG 分组占比
        </h3>
        <div
          ref="drgPieRef"
          class="h-64"
        />
      </div>

      <!-- Cost Analysis -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
      >
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
          费用结构分析
        </h3>
        <div
          ref="costStructureRef"
          class="h-64"
        />
      </div>
    </div>

    <!-- 超费原因分析 (新增) -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <OverCostAnalysisCard
        :batch-id="useDemoData || hasUploadedDataset ? undefined : batchId"
        :session-id="useDemoData || hasUploadedDataset ? undefined : sessionId"
        :dimension="analysisDimension"
        :dimension-label="dimensionLabel"
      />
    </div>

    <!-- AI Insights Summary -->
    <div
      v-if="stats.ai_insights && stats.ai_insights.length > 0"
      class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
    >
      <div class="flex items-center gap-2 mb-4">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">
          AI 智能洞察
        </h3>
        <a-tag color="blue">
          模型分析
        </a-tag>
      </div>
      <div class="space-y-3">
        <div
          v-for="(insight, idx) in stats.ai_insights"
          :key="idx"
          class="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-900/30"
        >
          <InfoCircleOutlined class="text-blue-500 text-lg mt-0.5" />
          <div class="flex-1 text-sm text-blue-700 dark:text-blue-300">
            {{ insight }}
          </div>
        </div>
      </div>
    </div>

    <!-- Legacy Issue Summary (Fallback) -->
    <div
      v-else
      class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
    >
      <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
        问题汇总与建议
      </h3>
      <div class="space-y-3">
        <div
          class="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30"
        >
          <ExclamationCircleOutlined class="text-red-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-red-700 dark:text-red-300 mb-1">
              编码准确性问题
            </div>
            <div class="text-sm text-red-600/80 dark:text-red-400/80">
              发现23例主诊断编码与临床诊断不符，建议加强编码培训
            </div>
          </div>
        </div>

        <div
          class="flex items-start gap-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/30"
        >
          <WarningOutlined class="text-yellow-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-yellow-700 dark:text-yellow-300 mb-1">
              费用消耗异常
            </div>
            <div class="text-sm text-yellow-600/80 dark:text-yellow-400/80">
              骨科和神经内科费用消耗指数偏高，需关注成本控制
            </div>
          </div>
        </div>

        <div
          class="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-900/30"
        >
          <InfoCircleOutlined class="text-blue-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-blue-700 dark:text-blue-300 mb-1">
              优化建议
            </div>
            <div class="text-sm text-blue-600/80 dark:text-blue-400/80">
              建议优化心内科和呼吸科的诊疗路径，可提升CMI约5%
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Drill Down Modal -->
  <DrillDownModal
    v-model:open="drillVisible"
    :title="drillTitle"
    :dimension="drillDimension"
    :value="drillValue"
    :session-id="useDemoData || hasUploadedDataset ? undefined : sessionId"
    :batch-id="useDemoData || hasUploadedDataset ? undefined : batchId"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import DrillDownModal from './DrillDownModal.vue'
import OverCostAnalysisCard from './OverCostAnalysisCard.vue'
import {
  ArrowLeftOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { isDrgMockModeEnabled, onDrgMockModeChange } from '@/utils/drgMockMode'
import { exportDrgMockReport, type DrgExportFormat } from '@/utils/drgMockExport'
import { useDrgDatasetStore } from '@/stores/drgDataset'
import { buildPostEventDatasetStats, type PostEventDimension } from '@/utils/drg-aggregation'
import DatasetUploadPanel from '@/components/drg/DatasetUploadPanel.vue'

const props = defineProps<{
  sessionId?: string // 新增：session_id
  batchId?: string
}>()

const qualityTrendRef = ref<HTMLElement | null>(null)
const deptComparisonRef = ref<HTMLElement | null>(null)
const drgPieRef = ref<HTMLElement | null>(null)
const costStructureRef = ref<HTMLElement | null>(null)

// Advanced Backend Chart Refs
const waterfallRef = ref<HTMLElement | null>(null)
const deptRankingRef = ref<HTMLElement | null>(null)
const drgScatterRef = ref<HTMLElement | null>(null)

const dateRange = ref<any>(null)
const analysisType = ref('quality')
const analysisDimension = ref<'hospital' | 'department' | 'ward' | 'chief_group' | 'person'>(
  'hospital',
)
const drgMockEnabled = ref(isDrgMockModeEnabled())
const drgDatasetStore = useDrgDatasetStore()
const hasUploadedDataset = computed(() => drgDatasetStore.hasUploadedData)
const useDemoData = computed(() => drgMockEnabled.value || !props.sessionId)
const drgModeHintText = computed(() =>
  hasUploadedDataset.value
    ? `当前使用模板上传数据（${drgDatasetStore.meta?.validCount ?? drgDatasetStore.records.length} 例）`
    : drgMockEnabled.value
      ? '当前已开启 Mock 演示模式，展示前端演示数据'
      : '当前缺少 session_id，自动展示演示数据',
)
let unsubscribeDrgMockMode: (() => void) | null = null

// 维度标签映射
const dimensionLabelMap: Record<string, string> = {
  hospital: '全院概览',
  department: '科室分析',
  ward: '病区分析',
  chief_group: '主诊医师组',
  person: '个人',
}

// 计算属性：当前维度名称
const dimensionLabel = computed(() => dimensionLabelMap[analysisDimension.value])

// 计算属性：图表标题根据维度变化
const chartTitles = computed(() => {
  const titles: Record<string, { trend: string; comparison: string }> = {
    hospital: { trend: '全院质量趋势', comparison: '科室绩效对比' },
    department: { trend: '科室质量趋势', comparison: '科室内病区对比' },
    ward: { trend: '病区质量趋势', comparison: '病区绩效排名' },
    chief_group: { trend: '主诊医师组趋势', comparison: '主诊医师组对比' },
    person: { trend: '个人绩效趋势', comparison: '个人CMI对比' },
  }
  return titles[analysisDimension.value]
})

const safeNumber = (value: unknown, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const formatInteger = (value: unknown) => Math.round(safeNumber(value)).toLocaleString('zh-CN')
const formatDecimal = (value: unknown, digits = 2) => safeNumber(value).toFixed(digits)
const formatPercent = (value: unknown, digits = 2) =>
  `${(safeNumber(value) * 100).toFixed(digits)}%`
const formatCurrency = (value: unknown) =>
  `¥${safeNumber(value).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`

const kpiCards = computed(() => {
  const summary = stats.value.summary as Record<string, any>
  const insuranceProfit = safeNumber(summary.insurance_profit ?? summary.total_profit)
  const profitClass = insuranceProfit >= 0 ? 'text-green-600' : 'text-red-500'
  const profitHintClass = insuranceProfit >= 0 ? 'text-green-600' : 'text-red-500'
  const mortality = safeNumber(summary.low_risk_mortality_rate)
  const mortalityClass = mortality > 0.1 ? 'text-red-600' : 'text-slate-800 dark:text-white'
  const mortalityHintClass = mortality > 0.1 ? 'text-red-500' : 'text-slate-400'

  return [
    {
      label: '病组数',
      value: formatInteger(summary.drg_count ?? summary.total_records),
      hint: `入组率: ${formatPercent(summary.grouping_success_rate)}`,
      valueClass: 'text-slate-800 dark:text-white',
      hintClass: 'text-slate-400',
      cardClass: '',
    },
    {
      label: 'CMI',
      value: formatDecimal(summary.avg_cmi),
      hint: '基准: 1.00',
      valueClass: 'text-slate-800 dark:text-white',
      hintClass: 'text-green-600',
      cardClass: '',
    },
    {
      label: '费用消耗指数',
      value: formatDecimal(summary.cost_consumption_index),
      hint: '越低越优',
      valueClass: 'text-slate-800 dark:text-white',
      hintClass: 'text-slate-400',
      cardClass: '',
    },
    {
      label: '时间消耗指数',
      value: formatDecimal(summary.time_consumption_index),
      hint: '越低越优',
      valueClass: 'text-slate-800 dark:text-white',
      hintClass: 'text-slate-400',
      cardClass: '',
    },
    {
      label: '低风险死亡率',
      value: formatPercent(summary.low_risk_mortality_rate),
      hint: `${formatInteger(summary.low_risk_death_count)} / ${formatInteger(summary.low_risk_total_count)} 例`,
      valueClass: mortalityClass,
      hintClass: mortalityHintClass,
      cardClass:
        mortality > 0.1 ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' : '',
    },
    {
      label: '平均住院日',
      value: `${formatDecimal(summary.avg_length_of_stay, 1)} 天`,
      hint: '按出院病例口径',
      valueClass: 'text-slate-800 dark:text-white',
      hintClass: 'text-slate-400',
      cardClass: '',
    },
    {
      label: '平均住院费用',
      value: formatCurrency(summary.avg_inpatient_cost),
      hint: '含医保结算口径',
      valueClass: 'text-slate-800 dark:text-white',
      hintClass: 'text-slate-400',
      cardClass: '',
    },
    {
      label: '医保盈亏',
      value: formatCurrency(insuranceProfit),
      hint: insuranceProfit >= 0 ? '医保结余' : '医保亏损',
      valueClass: profitClass,
      hintClass: profitHintClass,
      cardClass: '',
    },
  ]
})

const updateDatasetDataForDimension = () => {
  if (!hasUploadedDataset.value) return
  stats.value = {
    ...stats.value,
    ...buildPostEventDatasetStats(
      drgDatasetStore.records,
      analysisDimension.value as PostEventDimension,
    ),
  } as any
  void updateCharts()
}

/** 数据集变更（上传/清除）后刷新 */
const handleDatasetChanged = () => {
  if (hasUploadedDataset.value) {
    updateDatasetDataForDimension()
  } else {
    initMockCharts()
  }
}

// 处理维度切换
const handleDimensionChange = () => {
  message.info(`切换到【${dimensionLabel.value}】维度，正在加载数据...`)
  if (hasUploadedDataset.value) {
    updateDatasetDataForDimension()
    return
  }
  // 重新加载数据（如果有 batchId）
  if (!useDemoData.value && props.batchId) {
    fetchStatistics()
  } else {
    // 演示模式：更新 mock 数据
    updateMockDataForDimension()
  }
}

// 根据维度更新 mock 数据
const updateMockDataForDimension = () => {
  const realisticSummaryByDimension: Record<string, any> = {
    hospital: {
      total_records: 32021,
      drg_count: 2863,
      grouping_success_rate: 0.9928,
      avg_cmi: 0.8193,
      total_weight: 26226.8,
      total_fee: 203190072,
      total_profit: -84868160,
      insurance_profit: -84868160,
      cost_consumption_index: 1.09,
      time_consumption_index: 0.97,
      low_risk_mortality_rate: 0,
      low_risk_death_count: 0,
      low_risk_total_count: 2953,
      avg_length_of_stay: 6.7,
      avg_inpatient_cost: 6346,
    },
    department: {
      total_records: 13801,
      drg_count: 12,
      grouping_success_rate: 0.995,
      avg_cmi: 0.8174,
      total_weight: 11284.6,
      total_fee: 31259932,
      total_profit: -12972741,
      insurance_profit: -12972741,
      cost_consumption_index: 1.05,
      time_consumption_index: 0.95,
      low_risk_mortality_rate: 0,
      low_risk_death_count: 0,
      low_risk_total_count: 1613,
      avg_length_of_stay: 6.3,
      avg_inpatient_cost: 4520,
    },
    ward: {
      total_records: 8398,
      drg_count: 20,
      grouping_success_rate: 0.993,
      avg_cmi: 0.8192,
      total_weight: 6878.6,
      total_fee: 48653000,
      total_profit: -20170000,
      insurance_profit: -20170000,
      cost_consumption_index: 1.12,
      time_consumption_index: 0.98,
      low_risk_mortality_rate: 0,
      low_risk_death_count: 0,
      low_risk_total_count: 980,
      avg_length_of_stay: 6.9,
      avg_inpatient_cost: 5793,
    },
    chief_group: {
      total_records: 6160,
      drg_count: 10,
      grouping_success_rate: 0.996,
      avg_cmi: 0.8183,
      total_weight: 5041.6,
      total_fee: 24682425,
      total_profit: -10516043,
      insurance_profit: -10516043,
      cost_consumption_index: 1.07,
      time_consumption_index: 0.96,
      low_risk_mortality_rate: 0,
      low_risk_death_count: 0,
      low_risk_total_count: 731,
      avg_length_of_stay: 6.4,
      avg_inpatient_cost: 4007,
    },
    person: {
      total_records: 4695,
      drg_count: 147,
      grouping_success_rate: 0.998,
      avg_cmi: 0.8182,
      total_weight: 3841.7,
      total_fee: 22936616,
      total_profit: -10043804,
      insurance_profit: -10043804,
      cost_consumption_index: 1.08,
      time_consumption_index: 0.97,
      low_risk_mortality_rate: 0,
      low_risk_death_count: 0,
      low_risk_total_count: 566,
      avg_length_of_stay: 6.5,
      avg_inpatient_cost: 4885,
    },
  }

  const realisticDataByDimension: Record<string, any[]> = {
    hospital: [
      {
        dept_name: '呼吸内科专业',
        total_profit: -6160751,
        avg_cmi: 0.8123,
        case_count: 2762,
        cost_rate: 0.98,
      },
      {
        dept_name: '心血管内科专业',
        total_profit: -9216297,
        avg_cmi: 0.8179,
        case_count: 2582,
        cost_rate: 1.26,
      },
      {
        dept_name: '普通外科专业',
        total_profit: -9793757,
        avg_cmi: 0.8217,
        case_count: 2465,
        cost_rate: 1.45,
      },
      {
        dept_name: '骨科专业',
        total_profit: -9284990,
        avg_cmi: 0.8227,
        case_count: 2169,
        cost_rate: 1.47,
      },
      {
        dept_name: '神经内科专业',
        total_profit: -5459072,
        avg_cmi: 0.8221,
        case_count: 2193,
        cost_rate: 1.02,
      },
      {
        dept_name: '儿科',
        total_profit: -2493697,
        avg_cmi: 0.8118,
        case_count: 2560,
        cost_rate: 0.31,
      },
    ],
    department: [
      {
        dept_name: 'J44.0',
        total_profit: -3345446,
        avg_cmi: 0.8144,
        case_count: 1577,
        cost_rate: 0.93,
      },
      {
        dept_name: 'J15.9',
        total_profit: -1547499,
        avg_cmi: 0.8085,
        case_count: 1013,
        cost_rate: 0.6,
      },
      {
        dept_name: 'H25.9:13.4100x001',
        total_profit: -1530339,
        avg_cmi: 0.8275,
        case_count: 788,
        cost_rate: 0.65,
      },
      {
        dept_name: 'Z51.1:99.2503',
        total_profit: -1377712,
        avg_cmi: 0.8285,
        case_count: 777,
        cost_rate: 0.73,
      },
      {
        dept_name: 'J18.0',
        total_profit: -558227,
        avg_cmi: 0.816,
        case_count: 569,
        cost_rate: 0.33,
      },
      {
        dept_name: 'I25.1',
        total_profit: -559077,
        avg_cmi: 0.8161,
        case_count: 391,
        cost_rate: 0.57,
      },
    ],
    ward: [
      {
        dept_name: '呼吸内科一病区',
        total_profit: -2080000,
        avg_cmi: 0.812,
        case_count: 936,
        cost_rate: 0.92,
      },
      {
        dept_name: '呼吸内科二病区',
        total_profit: -1860000,
        avg_cmi: 0.815,
        case_count: 884,
        cost_rate: 0.95,
      },
      {
        dept_name: '心血管内科一病区',
        total_profit: -2780000,
        avg_cmi: 0.818,
        case_count: 902,
        cost_rate: 1.23,
      },
      {
        dept_name: '心血管内科二病区',
        total_profit: -2650000,
        avg_cmi: 0.821,
        case_count: 846,
        cost_rate: 1.27,
      },
      {
        dept_name: '普外一病区',
        total_profit: -2330000,
        avg_cmi: 0.822,
        case_count: 788,
        cost_rate: 1.35,
      },
      {
        dept_name: '骨科一病区',
        total_profit: -2410000,
        avg_cmi: 0.823,
        case_count: 756,
        cost_rate: 1.4,
      },
    ],
    chief_group: [
      {
        dept_name: 'J44.0 慢阻肺组',
        total_profit: -3345446,
        avg_cmi: 0.8144,
        case_count: 1577,
        cost_rate: 0.93,
      },
      {
        dept_name: 'J15.9 肺炎组',
        total_profit: -1547499,
        avg_cmi: 0.8085,
        case_count: 1013,
        cost_rate: 0.6,
      },
      {
        dept_name: 'Z51.1:99.2503 化疗组',
        total_profit: -1377712,
        avg_cmi: 0.8285,
        case_count: 777,
        cost_rate: 0.73,
      },
      {
        dept_name: 'I25.1 冠心病组',
        total_profit: -559077,
        avg_cmi: 0.8161,
        case_count: 391,
        cost_rate: 0.57,
      },
      {
        dept_name: 'I25.1:88.5500 介入组',
        total_profit: -1037190,
        avg_cmi: 0.839,
        case_count: 335,
        cost_rate: 1.13,
      },
    ],
    person: [
      {
        dept_name: '李敏',
        total_profit: -1205897,
        avg_cmi: 0.8166,
        case_count: 563,
        cost_rate: 0.83,
      },
      {
        dept_name: '郭映江',
        total_profit: -892036,
        avg_cmi: 0.8168,
        case_count: 487,
        cost_rate: 0.86,
      },
      {
        dept_name: '曾晓楠',
        total_profit: -899343,
        avg_cmi: 0.8239,
        case_count: 475,
        cost_rate: 0.8,
      },
      {
        dept_name: '冯婉琳',
        total_profit: -1529308,
        avg_cmi: 0.8205,
        case_count: 472,
        cost_rate: 1.15,
      },
      {
        dept_name: '郭怀杰',
        total_profit: -1025240,
        avg_cmi: 0.8217,
        case_count: 466,
        cost_rate: 0.88,
      },
      {
        dept_name: '李昂',
        total_profit: -930408,
        avg_cmi: 0.8164,
        case_count: 427,
        cost_rate: 0.96,
      },
    ],
  }

  const monthly = [
    { date: '1月', count: 3371, avg_cmi: 0.693 },
    { date: '2月', count: 3100, avg_cmi: 0.8108 },
    { date: '3月', count: 2968, avg_cmi: 0.8693 },
    { date: '4月', count: 2655, avg_cmi: 0.8094 },
    { date: '5月', count: 2616, avg_cmi: 0.751 },
    { date: '6月', count: 2390, avg_cmi: 0.8103 },
    { date: '7月', count: 2369, avg_cmi: 0.8402 },
    { date: '8月', count: 2289, avg_cmi: 0.86 },
    { date: '9月', count: 2382, avg_cmi: 0.8601 },
    { date: '10月', count: 2436, avg_cmi: 0.8696 },
    { date: '11月', count: 2511, avg_cmi: 0.8402 },
    { date: '12月', count: 2901, avg_cmi: 0.86 },
  ]

  const realisticSelectedSummary =
    realisticSummaryByDimension[analysisDimension.value] || realisticSummaryByDimension.hospital
  const selectedRows =
    realisticDataByDimension[analysisDimension.value] || realisticDataByDimension.hospital
  stats.value = {
    ...stats.value,
    summary: {
      ...stats.value.summary,
      ...realisticSelectedSummary,
    },
    department_stats: selectedRows,
    doctor_stats: realisticDataByDimension.person,
    mdc_distribution: [
      { mdc: '正常病例', count: 23564 },
      { mdc: '偏低病例', count: 7626 },
      { mdc: '中途结算', count: 445 },
    ],
    drg_distribution: [],
    daily_trends: monthly,
    cost_structure: { drug: 3200, material: 2400, exam: 1800, treatment: 1600 },
    ai_insights: [
      '样本支付率约 58%，医保亏损为常态，超费控制应优先覆盖高频病种。',
      '呼吸、心血管、普外、骨科是主要费用贡献科室，建议作为分层治理首批对象。',
    ],
    charts: {},
  } as any

  updateCharts()
  return

  // eslint-disable-next-line no-unreachable
  const mockDataByDimension: Record<string, any[]> = {
    // 全院概览 - 各科室数据
    hospital: [
      {
        dept_name: '心内科',
        total_profit: 125000,
        avg_cmi: 1.35,
        case_count: 328,
        cost_rate: 0.92,
      },
      { dept_name: '骨科', total_profit: 98000, avg_cmi: 1.28, case_count: 256, cost_rate: 0.88 },
      {
        dept_name: '神经外科',
        total_profit: 85000,
        avg_cmi: 1.52,
        case_count: 145,
        cost_rate: 0.85,
      },
      { dept_name: '普外科', total_profit: 62000, avg_cmi: 1.15, case_count: 289, cost_rate: 0.95 },
      {
        dept_name: '呼吸科',
        total_profit: -15000,
        avg_cmi: 0.98,
        case_count: 186,
        cost_rate: 1.08,
      },
      {
        dept_name: '消化内科',
        total_profit: 45000,
        avg_cmi: 1.12,
        case_count: 167,
        cost_rate: 0.91,
      },
      {
        dept_name: '泌尿外科',
        total_profit: 38000,
        avg_cmi: 1.22,
        case_count: 134,
        cost_rate: 0.89,
      },
      { dept_name: '妇产科', total_profit: -8000, avg_cmi: 0.95, case_count: 215, cost_rate: 1.05 },
      { dept_name: '儿科', total_profit: 22000, avg_cmi: 0.88, case_count: 198, cost_rate: 0.96 },
      {
        dept_name: '肿瘤科',
        total_profit: 156000,
        avg_cmi: 1.68,
        case_count: 112,
        cost_rate: 0.82,
      },
    ],
    // 科室分析 - 项目/病种数据
    department: [
      {
        dept_name: '冠心病介入治疗',
        total_profit: 68000,
        avg_cmi: 1.85,
        case_count: 85,
        cost_rate: 0.78,
      },
      {
        dept_name: '心力衰竭治疗',
        total_profit: 32000,
        avg_cmi: 1.25,
        case_count: 126,
        cost_rate: 0.92,
      },
      {
        dept_name: '心律失常诊治',
        total_profit: 15000,
        avg_cmi: 1.15,
        case_count: 67,
        cost_rate: 0.95,
      },
      {
        dept_name: '高血压管理',
        total_profit: -5000,
        avg_cmi: 0.85,
        case_count: 145,
        cost_rate: 1.06,
      },
      {
        dept_name: '急性心梗溶栓',
        total_profit: 45000,
        avg_cmi: 1.95,
        case_count: 38,
        cost_rate: 0.75,
      },
      {
        dept_name: '心脏瓣膜病',
        total_profit: 28000,
        avg_cmi: 1.42,
        case_count: 52,
        cost_rate: 0.88,
      },
      { dept_name: '心包疾病', total_profit: 8000, avg_cmi: 1.08, case_count: 23, cost_rate: 0.94 },
      { dept_name: '心肌病', total_profit: -12000, avg_cmi: 1.32, case_count: 35, cost_rate: 1.12 },
    ],
    // 病区分析 - 护理单元数据
    ward: [
      {
        dept_name: '心内一区',
        total_profit: 52000,
        avg_cmi: 1.28,
        case_count: 156,
        cost_rate: 0.89,
      },
      {
        dept_name: '心内二区',
        total_profit: 38000,
        avg_cmi: 1.22,
        case_count: 142,
        cost_rate: 0.92,
      },
      { dept_name: '心内CCU', total_profit: 85000, avg_cmi: 1.85, case_count: 68, cost_rate: 0.78 },
      {
        dept_name: '骨科一区',
        total_profit: 45000,
        avg_cmi: 1.18,
        case_count: 128,
        cost_rate: 0.91,
      },
      {
        dept_name: '骨科二区',
        total_profit: 32000,
        avg_cmi: 1.15,
        case_count: 118,
        cost_rate: 0.94,
      },
      { dept_name: '神外ICU', total_profit: 68000, avg_cmi: 1.95, case_count: 45, cost_rate: 0.72 },
      {
        dept_name: '普外一区',
        total_profit: 28000,
        avg_cmi: 1.12,
        case_count: 145,
        cost_rate: 0.95,
      },
      {
        dept_name: '普外二区',
        total_profit: -8000,
        avg_cmi: 0.98,
        case_count: 132,
        cost_rate: 1.08,
      },
      {
        dept_name: '呼吸病区',
        total_profit: -15000,
        avg_cmi: 0.95,
        case_count: 186,
        cost_rate: 1.12,
      },
      {
        dept_name: '消化病区',
        total_profit: 22000,
        avg_cmi: 1.08,
        case_count: 167,
        cost_rate: 0.96,
      },
    ],
    // 主诊医师组 - 组内绩效数据
    chief_group: [
      {
        dept_name: 'FM19 心衰伴MCC',
        total_profit: 85000,
        avg_cmi: 1.85,
        case_count: 128,
        cost_rate: 0.82,
      },
      {
        dept_name: 'FB15 心脏手术',
        total_profit: 125000,
        avg_cmi: 2.45,
        case_count: 65,
        cost_rate: 0.72,
      },
      {
        dept_name: 'IC19 脑血管手术',
        total_profit: 98000,
        avg_cmi: 2.15,
        case_count: 78,
        cost_rate: 0.78,
      },
      {
        dept_name: 'BR23 呼吸感染',
        total_profit: -25000,
        avg_cmi: 0.88,
        case_count: 186,
        cost_rate: 1.18,
      },
      {
        dept_name: 'GD15 胃肠手术',
        total_profit: 45000,
        avg_cmi: 1.45,
        case_count: 95,
        cost_rate: 0.88,
      },
      {
        dept_name: 'EB13 骨折固定',
        total_profit: 38000,
        avg_cmi: 1.28,
        case_count: 142,
        cost_rate: 0.91,
      },
      {
        dept_name: 'KB19 肾脏手术',
        total_profit: 52000,
        avg_cmi: 1.65,
        case_count: 58,
        cost_rate: 0.85,
      },
      {
        dept_name: 'RB11 肺炎',
        total_profit: -18000,
        avg_cmi: 0.92,
        case_count: 215,
        cost_rate: 1.15,
      },
      {
        dept_name: 'HC15 肝胆手术',
        total_profit: 68000,
        avg_cmi: 1.78,
        case_count: 72,
        cost_rate: 0.82,
      },
      {
        dept_name: 'MD23 妇科手术',
        total_profit: 22000,
        avg_cmi: 1.18,
        case_count: 98,
        cost_rate: 0.94,
      },
    ],
    // 医生绩效 - 主治医师数据
    person: [
      {
        dept_name: '张明华 主任医师',
        total_profit: 158000,
        avg_cmi: 1.68,
        case_count: 185,
        cost_rate: 0.78,
      },
      {
        dept_name: '李建国 主任医师',
        total_profit: 125000,
        avg_cmi: 1.52,
        case_count: 168,
        cost_rate: 0.82,
      },
      {
        dept_name: '王志强 副主任医师',
        total_profit: 98000,
        avg_cmi: 1.45,
        case_count: 156,
        cost_rate: 0.85,
      },
      {
        dept_name: '刘伟 副主任医师',
        total_profit: 75000,
        avg_cmi: 1.32,
        case_count: 142,
        cost_rate: 0.88,
      },
      {
        dept_name: '陈晓东 主治医师',
        total_profit: 52000,
        avg_cmi: 1.18,
        case_count: 128,
        cost_rate: 0.92,
      },
      {
        dept_name: '赵敏 主治医师',
        total_profit: 38000,
        avg_cmi: 1.12,
        case_count: 118,
        cost_rate: 0.94,
      },
      {
        dept_name: '孙丽华 主治医师',
        total_profit: -8000,
        avg_cmi: 0.95,
        case_count: 105,
        cost_rate: 1.08,
      },
      {
        dept_name: '周军 主治医师',
        total_profit: 22000,
        avg_cmi: 1.05,
        case_count: 98,
        cost_rate: 0.96,
      },
      {
        dept_name: '吴晓燕 住院医师',
        total_profit: -15000,
        avg_cmi: 0.88,
        case_count: 86,
        cost_rate: 1.15,
      },
      {
        dept_name: '郑浩 住院医师',
        total_profit: 12000,
        avg_cmi: 0.98,
        case_count: 75,
        cost_rate: 0.98,
      },
    ],
  }
  const mockSummaryByDimension: Record<string, any> = {
    hospital: {
      total_records: 1286,
      drg_count: 126,
      grouping_success_rate: 0.982,
      avg_cmi: 1.18,
      total_weight: 1568.4,
      total_fee: 5680000,
      total_profit: 152000,
      insurance_profit: 152000,
      cost_consumption_index: 0.96,
      time_consumption_index: 0.93,
      low_risk_mortality_rate: 0.07,
      low_risk_death_count: 2,
      low_risk_total_count: 2860,
      avg_length_of_stay: 7.9,
      avg_inpatient_cost: 18650,
    },
    department: {
      total_records: 846,
      drg_count: 68,
      grouping_success_rate: 0.975,
      avg_cmi: 1.32,
      total_weight: 1242.8,
      total_fee: 4260000,
      total_profit: -36000,
      insurance_profit: -36000,
      cost_consumption_index: 1.02,
      time_consumption_index: 0.98,
      low_risk_mortality_rate: 0.09,
      low_risk_death_count: 3,
      low_risk_total_count: 3320,
      avg_length_of_stay: 9.1,
      avg_inpatient_cost: 21450,
    },
    ward: {
      total_records: 762,
      drg_count: 54,
      grouping_success_rate: 0.969,
      avg_cmi: 1.24,
      total_weight: 1065.2,
      total_fee: 3820000,
      total_profit: 42000,
      insurance_profit: 42000,
      cost_consumption_index: 0.98,
      time_consumption_index: 0.95,
      low_risk_mortality_rate: 0.06,
      low_risk_death_count: 2,
      low_risk_total_count: 3080,
      avg_length_of_stay: 8.4,
      avg_inpatient_cost: 19800,
    },
    chief_group: {
      total_records: 648,
      drg_count: 41,
      grouping_success_rate: 0.963,
      avg_cmi: 1.41,
      total_weight: 980.6,
      total_fee: 3360000,
      total_profit: 78000,
      insurance_profit: 78000,
      cost_consumption_index: 0.91,
      time_consumption_index: 0.89,
      low_risk_mortality_rate: 0.05,
      low_risk_death_count: 1,
      low_risk_total_count: 2140,
      avg_length_of_stay: 7.2,
      avg_inpatient_cost: 17600,
    },
    person: {
      total_records: 534,
      drg_count: 28,
      grouping_success_rate: 0.958,
      avg_cmi: 1.08,
      total_weight: 842.3,
      total_fee: 2980000,
      total_profit: -12000,
      insurance_profit: -12000,
      cost_consumption_index: 1.06,
      time_consumption_index: 1.04,
      low_risk_mortality_rate: 0.11,
      low_risk_death_count: 3,
      low_risk_total_count: 1820,
      avg_length_of_stay: 10.4,
      avg_inpatient_cost: 22800,
    },
  }

  const selectedSummary =
    mockSummaryByDimension[analysisDimension.value] || mockSummaryByDimension.hospital
  const mockChartMetaByDimension: Record<string, any> = {
    hospital: {
      mdc_distribution: [
        { mdc: 'MDC 05', count: 128 },
        { mdc: 'MDC 08', count: 112 },
        { mdc: 'MDC 11', count: 96 },
      ],
      drg_distribution: [],
      doctor_stats: mockDataByDimension.chief_group || [],
      daily_trends: [
        { date: '1月', count: 120, avg_cmi: 1.02 },
        { date: '2月', count: 135, avg_cmi: 1.05 },
        { date: '3月', count: 148, avg_cmi: 1.08 },
      ],
      cost_structure: { drug: 3500, material: 3200, exam: 2800, treatment: 2200 },
      ai_insights: [
        '全院病组数保持稳定，费用消耗指数较上月下降 0.03。',
        '心内科和骨科仍是贡献医保盈亏的核心科室，建议持续跟踪病组结构。',
      ],
    },
    department: {
      mdc_distribution: [
        { mdc: 'MDC 05', count: 84 },
        { mdc: 'MDC 08', count: 76 },
        { mdc: 'MDC 11', count: 69 },
      ],
      drg_distribution: [],
      doctor_stats: mockDataByDimension.chief_group || [],
      daily_trends: [
        { date: '1月', count: 66, avg_cmi: 1.18 },
        { date: '2月', count: 72, avg_cmi: 1.24 },
        { date: '3月', count: 78, avg_cmi: 1.29 },
      ],
      cost_structure: { drug: 2900, material: 3600, exam: 2200, treatment: 2400 },
      ai_insights: [
        '科级维度下，心脏介入相关病组费用消耗指数高于全院均值。',
        '慢病管理组的平均住院日偏长，是当前主要瓶颈。',
      ],
    },
    ward: {
      mdc_distribution: [
        { mdc: 'MDC 05', count: 72 },
        { mdc: 'MDC 08', count: 63 },
        { mdc: 'MDC 11', count: 58 },
      ],
      drg_distribution: [],
      doctor_stats: mockDataByDimension.chief_group || [],
      daily_trends: [
        { date: '1月', count: 58, avg_cmi: 1.15 },
        { date: '2月', count: 61, avg_cmi: 1.19 },
        { date: '3月', count: 66, avg_cmi: 1.22 },
      ],
      cost_structure: { drug: 2800, material: 3000, exam: 2100, treatment: 2300 },
      ai_insights: [
        '病区层面床位周转效率整体稳定，但呼吸病区住院日仍偏长。',
        '骨科一病区的医保盈亏表现优于病区平均值。',
      ],
    },
    chief_group: {
      mdc_distribution: [
        { mdc: 'MDC 05', count: 64 },
        { mdc: 'MDC 08', count: 52 },
        { mdc: 'MDC 11', count: 46 },
      ],
      drg_distribution: [],
      doctor_stats: mockDataByDimension.person || [],
      daily_trends: [
        { date: '1月', count: 48, avg_cmi: 1.32 },
        { date: '2月', count: 52, avg_cmi: 1.38 },
        { date: '3月', count: 57, avg_cmi: 1.41 },
      ],
      cost_structure: { drug: 2400, material: 2400, exam: 1900, treatment: 2100 },
      ai_insights: [
        '主诊组维度下，张明华主诊组在医保盈亏和CMI上均领先。',
        '建议围绕组内路径、编码和耗材选择进一步压缩时间消耗指数。',
      ],
    },
    person: {
      mdc_distribution: [
        { mdc: 'MDC 05', count: 44 },
        { mdc: 'MDC 08', count: 39 },
        { mdc: 'MDC 11', count: 35 },
      ],
      drg_distribution: [],
      doctor_stats: mockDataByDimension.person || [],
      daily_trends: [
        { date: '1月', count: 42, avg_cmi: 1.02 },
        { date: '2月', count: 45, avg_cmi: 1.05 },
        { date: '3月', count: 48, avg_cmi: 1.08 },
      ],
      cost_structure: { drug: 2600, material: 2500, exam: 2400, treatment: 2200 },
      ai_insights: [
        '个人维度下，低风险死亡率和住院日仍有改善空间。',
        '建议对高费用病例进行逐例复盘，优先压缩耗材与检查占比。',
      ],
    },
  }

  const selectedMeta =
    mockChartMetaByDimension[analysisDimension.value] || mockChartMetaByDimension.hospital
  stats.value = {
    ...stats.value,
    summary: {
      ...stats.value.summary,
      ...selectedSummary,
    },
    department_stats: mockDataByDimension[analysisDimension.value] || [],
    doctor_stats: selectedMeta.doctor_stats || [],
    mdc_distribution: selectedMeta.mdc_distribution || [],
    drg_distribution: selectedMeta.drg_distribution || [],
    daily_trends: selectedMeta.daily_trends || [],
    cost_structure: selectedMeta.cost_structure || stats.value.cost_structure,
    ai_insights: selectedMeta.ai_insights || [],
    charts: {},
  } as any
  updateCharts()
}

// Drill Down State
const drillVisible = ref(false)
const drillTitle = ref('')
const drillDimension = ref('')
const drillValue = ref('')

// Statistics Data
const stats = ref({
  summary: {
    total_records: 0,
    drg_count: 0,
    grouping_success_rate: 0,
    avg_cmi: 0,
    total_weight: 0,
    total_fee: 0,
    total_profit: 0,
    cost_consumption_index: 0,
    time_consumption_index: 0,
    low_risk_mortality_rate: 0,
    low_risk_death_count: 0,
    low_risk_total_count: 0,
    avg_length_of_stay: 0,
    avg_inpatient_cost: 0,
    insurance_profit: 0,
  },
  mdc_distribution: [] as any[],
  drg_distribution: [] as any[], // Top 10 High Risk/Cost DRGs
  department_stats: [] as any[],
  doctor_stats: [] as any[],
  daily_trends: [] as any[],
  cost_structure: { drug: 0, material: 0, exam: 0, treatment: 0 },
  charts: {} as Record<string, any>,
  ai_insights: [] as string[],
})

let qualityChart: echarts.ECharts | null = null
let deptChart: echarts.ECharts | null = null
let drgChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null

let waterfallChart: echarts.ECharts | null = null
let deptRankingChart: echarts.ECharts | null = null
let drgScatterChart: echarts.ECharts | null = null

const fetchStatistics = async () => {
  if (!props.sessionId) return // 需要 session_id

  try {
    const res = await axios.get('/api/v1/drg/statistics', {
      params: {
        session_id: props.sessionId, // 传递 session_id
        batch_id: props.batchId,
      },
    })
    const payload = res.data?.data ?? res.data
    if (payload && typeof payload === 'object') {
      stats.value = {
        ...stats.value,
        ...payload,
        summary: {
          ...stats.value.summary,
          ...(payload as any).summary,
        },
      } as any
    }
    updateCharts()
  } catch (e) {
    console.error('Failed to fetch statistics:', e)
  }
}

const updateCharts = async () => {
  await nextTick()

  // 如果后端的 charts 数据存在，则显示高级图表
  if (stats.value.charts && Object.keys(stats.value.charts).length > 0) {
    const c = stats.value.charts

    if (c.profit_waterfall && waterfallRef.value) {
      if (!waterfallChart) waterfallChart = echarts.init(waterfallRef.value)
      waterfallChart.setOption(c.profit_waterfall, true)
    }

    if (c.dept_profit_ranking && deptRankingRef.value) {
      if (!deptRankingChart) deptRankingChart = echarts.init(deptRankingRef.value)
      deptRankingChart.setOption(c.dept_profit_ranking, true)
    }

    if (c.drg_scatter && drgScatterRef.value) {
      if (!drgScatterChart) drgScatterChart = echarts.init(drgScatterRef.value)
      drgScatterChart.setOption(c.drg_scatter, true)
    }
    return
  }

  // 回退到静态演示图表（如果 backend 没有提供 charts）
  // 1. Quality/Daily Trend Chart
  if (qualityChart && stats.value.daily_trends) {
    const dates = stats.value.daily_trends.map((d: any) => d.date)
    const counts = stats.value.daily_trends.map((d: any) => d.count)
    const avgCmis = stats.value.daily_trends.map((d: any) => d.avg_cmi)

    qualityChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['入组例数', 'CMI'] },
      xAxis: { data: dates },
      yAxis: [
        { type: 'value', name: '例数' },
        { type: 'value', name: 'CMI', min: 0 },
      ],
      series: [
        {
          name: '入组例数',
          type: 'bar',
          data: counts,
          yAxisIndex: 0,
          itemStyle: { color: '#3b82f6' },
        },
        {
          name: 'CMI',
          type: 'line',
          data: avgCmis,
          yAxisIndex: 1,
          itemStyle: { color: '#22c55e' },
        },
      ],
    })
  }

  // 2. Department Comparison (Profit/Cost)
  if (deptChart && stats.value.department_stats) {
    const depts = stats.value.department_stats.map((d: any) => d.dept_name)
    const profits = stats.value.department_stats.map((d: any) => d.total_profit)
    const cmis = stats.value.department_stats.map((d: any) => d.avg_cmi)

    deptChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['总盈亏', '平均CMI'] },
      xAxis: { data: depts, axisLabel: { interval: 0, rotate: 30 } },
      yAxis: [
        { type: 'value', name: '盈亏' },
        { type: 'value', name: 'CMI' },
      ],
      series: [
        {
          name: '总盈亏',
          type: 'bar',
          data: profits,
          itemStyle: {
            color: (params: any) => {
              return params.value >= 0 ? '#22c55e' : '#ef4444'
            },
          },
        },
        {
          name: '平均CMI',
          type: 'line',
          data: cmis,
          yAxisIndex: 1,
          itemStyle: { color: '#f59e0b' },
        },
      ],
    })
  }

  // 3. DRG Distribution (Top 10) -> Changed to MDC Pie for simpler view as per PRD
  if (drgChart && stats.value.mdc_distribution) {
    const data = stats.value.mdc_distribution.map((d: any) => ({
      value: d.count,
      name: d.mdc,
    }))

    drgChart.setOption({
      tooltip: { trigger: 'item' },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          data: data,
        },
      ],
    })
  }

  // 4. Cost Structure
  if (costChart && stats.value.cost_structure) {
    const labels = ['药品', '耗材', '检查', '治疗']
    const s = stats.value.cost_structure
    const data = [s.drug, s.material, s.exam, s.treatment]

    costChart.setOption({
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: labels },
      series: [
        {
          type: 'bar',
          data: data,
          itemStyle: { color: '#8b5cf6' },
        },
      ],
    })
  }
}

// Event Handlers for Drill Down
const setupChartEvents = () => {
  if (deptChart) {
    deptChart.on('click', (params: any) => {
      openDrillDown('department', params.name)
    })
  }
  if (drgChart) {
    drgChart.on('click', (params: any) => {
      // params.name is MDC code like "MDCA"
      openDrillDown('mdc', params.name)
    })
  }
}

const openDrillDown = (dimension: string, value: string) => {
  drillDimension.value = dimension
  drillValue.value = value
  drillTitle.value = `${value} - 病例明细`
  drillVisible.value = true
}

onMounted(() => {
  // Initialize Charts
  if (qualityTrendRef.value) qualityChart = echarts.init(qualityTrendRef.value)
  if (deptComparisonRef.value) deptChart = echarts.init(deptComparisonRef.value)
  if (drgPieRef.value) drgChart = echarts.init(drgPieRef.value)
  if (costStructureRef.value) costChart = echarts.init(costStructureRef.value)

  setupChartEvents()

  drgMockEnabled.value = isDrgMockModeEnabled()
  unsubscribeDrgMockMode = onDrgMockModeChange((enabled) => {
    drgMockEnabled.value = enabled
    if (hasUploadedDataset.value) {
      initMockCharts()
      return
    }
    if (!useDemoData.value && props.sessionId) {
      fetchStatistics()
      return
    }
    initMockCharts()
  })

  // Initial load
  if (hasUploadedDataset.value) {
    initMockCharts()
    return
  }
  if (!useDemoData.value && props.sessionId) {
    fetchStatistics()
  } else {
    initMockCharts()
  }
})

watch(
  () => props.sessionId,
  (newVal) => {
    if (hasUploadedDataset.value) {
      initMockCharts()
      return
    }
    if (newVal && !useDemoData.value) {
      fetchStatistics()
    } else {
      initMockCharts()
    }
  },
)

const initMockCharts = () => {
  if (hasUploadedDataset.value) {
    updateDatasetDataForDimension()
    return
  }
  updateMockDataForDimension()
}

watch(
  () => drgDatasetStore.meta?.uploadedAt,
  () => {
    if (hasUploadedDataset.value) {
      initMockCharts()
      return
    }
    if (!useDemoData.value && props.sessionId) {
      fetchStatistics()
    } else {
      initMockCharts()
    }
  },
)

const buildMockExportPayload = () => {
  const selectedRows = (stats.value.department_stats || []).map((item: any) => [
    item.dept_name || item.name || '-',
    safeNumber(item.total_profit).toFixed(0),
    safeNumber(item.avg_cmi).toFixed(2),
    safeNumber(item.cost_index ?? item.cost_consumption_index).toFixed(2),
    safeNumber(item.avg_los ?? item.avg_length_of_stay).toFixed(1),
  ])
  return {
    title: `DRG ${dimensionLabel.value} 演示报告`,
    filenameBase: `drg_demo_report_${analysisDimension.value}_${Date.now()}`,
    meta: [
      ['当前维度', dimensionLabel.value],
      ['导出时间', new Date().toLocaleString('zh-CN')],
      [
        '数据模式',
        hasUploadedDataset.value
          ? `模板上传数据（${drgDatasetStore.meta?.validCount ?? drgDatasetStore.records.length}例）`
          : drgMockEnabled.value
            ? 'Mock 演示模式'
            : '无 session_id 的演示导出',
      ],
    ] as Array<[string, string]>,
    kpis: kpiCards.value.map(
      (card) => [card.label, `${card.value} (${card.hint})`] as [string, string],
    ),
    sections: selectedRows.length
      ? [
          {
            title: '分层绩效明细',
            columns: ['层级对象', '医保盈亏', '平均CMI', '费用消耗指数', '平均住院日'],
            rows: selectedRows,
          },
        ]
      : undefined,
  }
}

// Export handler - use fetch to properly go through proxy
const handleExport = async ({ key }: MenuInfo) => {
  const keyStr = String(key)
  const formatMap: Record<string, { ext: string; mime: string; name: string }> = {
    excel: {
      ext: 'xlsx',
      mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      name: 'Excel',
    },
    pdf: { ext: 'pdf', mime: 'application/pdf', name: 'PDF' },
    word: {
      ext: 'docx',
      mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      name: 'Word',
    },
  }

  const format = formatMap[keyStr]
  if (!format) return

  if (hasUploadedDataset.value || useDemoData.value || !props.sessionId) {
    exportDrgMockReport(keyStr as DrgExportFormat, buildMockExportPayload())
    if (hasUploadedDataset.value) {
      message.success(`已导出 ${format.name} 模板数据报告`)
    } else {
      message.warning(`当前缺少 session_id，已导出 ${format.name} 演示报告`)
    }
    return
  }

  const params = new URLSearchParams()
  params.set('session_id', props.sessionId)
  if (props.batchId) {
    params.set('batch_id', props.batchId)
  }
  const url = `/api/v1/drg/export/${key}?${params.toString()}`

  const hideLoading = message.loading(`正在生成 ${format.name} 报告...`, 0)

  try {
    const response = await axios.get(url, { responseType: 'blob' })
    const blob = new Blob([response.data], { type: format.mime })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `drg_report_${props.batchId || props.sessionId}.${format.ext}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
    message.success(`${format.name} 报告导出成功`)
  } catch (error: any) {
    console.error('Export failed:', error)
    message.error(error.response?.data?.detail || `${format.name} 导出失败`)
  } finally {
    hideLoading()
  }
}

onUnmounted(() => {
  unsubscribeDrgMockMode?.()
  qualityChart?.dispose()
  deptChart?.dispose()
  drgChart?.dispose()
  costChart?.dispose()
  waterfallChart?.dispose()
  deptRankingChart?.dispose()
  drgScatterChart?.dispose()
})
</script>
