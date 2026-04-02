<template>
  <div
    class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700"
  >
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
        <ExclamationCircleOutlined class="text-red-500" />
        超费原因分析
        <span
          class="text-[11px] px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-100 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800"
        >
          {{ dimensionLabel }} 视图
        </span>
      </h3>
      <a-button size="small" type="link" @click="handleExportReport">
        <DownloadOutlined /> 导出分析报告
      </a-button>
    </div>

    <div
      class="mb-4 rounded-lg border border-slate-100 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-700/40 p-3 text-xs text-slate-500 dark:text-slate-400"
    >
      会话模式：{{ sessionId ? `正式会话 ${sessionId}` : '演示模式' }}
    </div>

    <!-- Summary Stats -->
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div class="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-red-600">
          {{ lossCount }}
        </div>
        <div class="text-xs text-red-500">超费病例</div>
      </div>
      <div class="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-orange-600">
          ¥{{ totalLossAmount.toLocaleString() }}
        </div>
        <div class="text-xs text-orange-500">超费金额</div>
      </div>
      <div class="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-yellow-600">{{ avgLossRate.toFixed(1) }}%</div>
        <div class="text-xs text-yellow-500">平均超费率</div>
      </div>
    </div>

    <!-- Reason Distribution -->
    <div class="mb-4">
      <div class="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">超费原因分布</div>
      <div class="space-y-2">
        <div
          v-for="reason in reasonDistribution"
          :key="reason.type"
          class="flex items-center gap-2"
        >
          <div class="w-24 text-xs text-slate-600 dark:text-slate-400 truncate">
            {{ reason.label }}
          </div>
          <div class="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-4 overflow-hidden">
            <div
              :class="['h-full rounded-full', reason.color]"
              :style="{ width: `${reason.percentage}%` }"
            />
          </div>
          <div class="w-12 text-xs text-slate-500 text-right">{{ reason.count }}例</div>
        </div>
      </div>
    </div>

    <!-- Top Loss Cases -->
    <div>
      <div class="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">亏损TOP5病例</div>
      <div class="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
        <div
          v-for="item in topLossCases"
          :key="item.caseNo"
          class="flex items-center justify-between p-2 bg-slate-50 dark:bg-slate-700/50 rounded-lg text-xs"
        >
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-slate-600 dark:text-slate-300 font-medium whitespace-nowrap">{{
              item.caseNo
            }}</span>
            <span class="text-slate-400 truncate">{{ item.drg }}</span>
          </div>
          <div class="flex items-center gap-3 whitespace-nowrap">
            <span class="text-slate-500">{{ item.reason }}</span>
            <span class="text-red-600 font-medium">-¥{{ item.lossAmount.toLocaleString() }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Recommendations -->
    <div
      class="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800"
    >
      <div class="text-xs font-medium text-blue-700 dark:text-blue-300 mb-1">瓶颈报告</div>
      <ul class="text-xs text-blue-600/80 dark:text-blue-400/80 space-y-1">
        <li v-for="item in recommendations" :key="item">• {{ item }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ExclamationCircleOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

type DimensionKey = 'hospital' | 'department' | 'ward' | 'chief_group' | 'doctor'

const props = defineProps<{
  batchId?: string
  sessionId?: string
  dimension?: DimensionKey
  dimensionLabel?: string
}>()

type ReasonItem = {
  type: string
  label: string
  count: number
  percentage: number
  color: string
}

type LossCase = {
  caseNo: string
  drg: string
  reason: string
  lossAmount: number
}

type ReportScenario = {
  summary: {
    lossCount: number
    totalLossAmount: number
    avgLossRate: number
  }
  reasonDistribution: ReasonItem[]
  topLossCases: LossCase[]
  recommendations: string[]
}

const reportLibrary: Record<DimensionKey, ReportScenario> = {
  hospital: {
    summary: { lossCount: 23, totalLossAmount: 185000, avgLossRate: 12.3 },
    reasonDistribution: [
      { type: 'los', label: '住院日偏长', count: 8, percentage: 35, color: 'bg-red-500' },
      { type: 'material', label: '高值耗材', count: 7, percentage: 30, color: 'bg-orange-500' },
      { type: 'coding', label: '编码偏差', count: 5, percentage: 22, color: 'bg-yellow-500' },
      { type: 'path', label: '路径偏离', count: 3, percentage: 13, color: 'bg-slate-400' },
    ],
    topLossCases: [
      { caseNo: '#2026010105', drg: 'BR23', reason: '住院日超标', lossAmount: 15800 },
      { caseNo: '#2026010089', drg: 'IC19', reason: '耗材超标', lossAmount: 12500 },
      { caseNo: '#2026010067', drg: 'GD15', reason: '住院日超标', lossAmount: 9800 },
      { caseNo: '#2026010034', drg: 'EB13', reason: '编码问题', lossAmount: 8200 },
      { caseNo: '#2026010022', drg: 'FM19', reason: '耗材超标', lossAmount: 7500 },
    ],
    recommendations: [
      '住院日超标病例占比最高，应优先压缩低风险病组住院天数。',
      '高值耗材集中在骨科和心内科，建议做耗材限额与术式复盘。',
      '编码偏差仍影响部分病例入组，建议同步加强主诊记录与编码核验。',
    ],
  },
  department: {
    summary: { lossCount: 18, totalLossAmount: 146000, avgLossRate: 10.7 },
    reasonDistribution: [
      { type: 'case-mix', label: '病种结构偏重', count: 7, percentage: 39, color: 'bg-red-500' },
      { type: 'stay', label: '病区周转慢', count: 5, percentage: 28, color: 'bg-orange-500' },
      { type: 'material', label: '耗材超阈', count: 3, percentage: 17, color: 'bg-yellow-500' },
      { type: 'coding', label: '编码不一致', count: 3, percentage: 16, color: 'bg-slate-400' },
    ],
    topLossCases: [
      { caseNo: '#2026010212', drg: '冠心病介入', reason: '病种结构重', lossAmount: 16800 },
      { caseNo: '#2026010198', drg: '心衰治疗', reason: '住院日偏长', lossAmount: 14200 },
      { caseNo: '#2026010154', drg: '心律失常', reason: '编码偏差', lossAmount: 12100 },
      { caseNo: '#2026010128', drg: '搭桥手术', reason: '耗材偏高', lossAmount: 10300 },
      { caseNo: '#2026010096', drg: '慢病管理', reason: '周转慢', lossAmount: 9600 },
    ],
    recommendations: [
      '科级维度下，需先稳定病种结构，再控制高耗材和住院日波动。',
      '将病区周转指标和出院时效纳入月度复盘，避免盈亏下滑。',
      '针对高损失病组做模板化路径，减少不同班组之间的执行差异。',
    ],
  },
  ward: {
    summary: { lossCount: 14, totalLossAmount: 118000, avgLossRate: 9.4 },
    reasonDistribution: [
      { type: 'turnover', label: '床位周转慢', count: 6, percentage: 43, color: 'bg-red-500' },
      { type: 'stay', label: '护理日偏长', count: 4, percentage: 29, color: 'bg-orange-500' },
      { type: 'exam', label: '重复检查', count: 2, percentage: 14, color: 'bg-yellow-500' },
      { type: 'material', label: '耗材偏高', count: 2, percentage: 14, color: 'bg-slate-400' },
    ],
    topLossCases: [
      { caseNo: '#2026010321', drg: '心内科一病区', reason: '床位周转慢', lossAmount: 12800 },
      { caseNo: '#2026010308', drg: '骨科二病区', reason: '护理日偏长', lossAmount: 11800 },
      { caseNo: '#2026010277', drg: '呼吸病区', reason: '重复检查', lossAmount: 9200 },
      { caseNo: '#2026010264', drg: '消化病区', reason: '耗材偏高', lossAmount: 8600 },
      { caseNo: '#2026010231', drg: '骨科一病区', reason: '床位周转慢', lossAmount: 8200 },
    ],
    recommendations: [
      '病区层面应重点盯住床位周转和护理日，先把时间损耗压下来。',
      '对重复检查做病区级清单化管控，减少无效消耗。',
      '将耗材高发病区纳入周报，持续跟踪结构性超费。',
    ],
  },
  chief_group: {
    summary: { lossCount: 11, totalLossAmount: 96000, avgLossRate: 8.1 },
    reasonDistribution: [
      { type: 'path', label: '路径不统一', count: 4, percentage: 36, color: 'bg-red-500' },
      { type: 'coding', label: '编码偏差', count: 3, percentage: 27, color: 'bg-orange-500' },
      { type: 'prep', label: '术前准备长', count: 2, percentage: 18, color: 'bg-yellow-500' },
      { type: 'material', label: '耗材差异', count: 2, percentage: 19, color: 'bg-slate-400' },
    ],
    topLossCases: [
      { caseNo: '#2026010412', drg: '张明华主诊组', reason: '路径偏离', lossAmount: 12600 },
      { caseNo: '#2026010408', drg: '李建国主诊组', reason: '编码偏差', lossAmount: 10400 },
      { caseNo: '#2026010394', drg: '王志强主诊组', reason: '术前偏长', lossAmount: 9800 },
      { caseNo: '#2026010367', drg: '刘伟主诊组', reason: '耗材差异', lossAmount: 7600 },
      { caseNo: '#2026010355', drg: '陈晓东主诊组', reason: '路径偏离', lossAmount: 7200 },
    ],
    recommendations: [
      '主诊医师组要统一诊疗路径和术前准备节奏，避免组间差异放大。',
      '对编码偏差高发的主诊组做逐例点评，减少入组偏移。',
      '把耗材与耗时的差异同步纳入组内对标。',
    ],
  },
  doctor: {
    summary: { lossCount: 9, totalLossAmount: 82000, avgLossRate: 7.6 },
    reasonDistribution: [
      { type: 'coding', label: '个人编码问题', count: 4, percentage: 44, color: 'bg-red-500' },
      { type: 'stay', label: '住院日超标', count: 2, percentage: 22, color: 'bg-orange-500' },
      { type: 'material', label: '耗材超标', count: 2, percentage: 22, color: 'bg-yellow-500' },
      { type: 'exam', label: '检查偏多', count: 1, percentage: 12, color: 'bg-slate-400' },
    ],
    topLossCases: [
      { caseNo: '#2026010509', drg: '张明华', reason: '编码问题', lossAmount: 11200 },
      { caseNo: '#2026010496', drg: '李建国', reason: '住院日超标', lossAmount: 9800 },
      { caseNo: '#2026010477', drg: '王志强', reason: '耗材超标', lossAmount: 8600 },
      { caseNo: '#2026010458', drg: '刘伟', reason: '检查偏多', lossAmount: 7200 },
      { caseNo: '#2026010430', drg: '陈晓东', reason: '编码问题', lossAmount: 6800 },
    ],
    recommendations: [
      '个人维度下优先抓编码准确率和住院日控制，收益最直接。',
      '对高成本病例做逐例复盘，明确是否存在不必要的检查或耗材。',
      '将个人医保盈亏和低风险死亡率一起看，避免单指标优化。',
    ],
  },
}

const currentDimension = computed<DimensionKey>(() => props.dimension || 'hospital')
const reportData = computed(() => reportLibrary[currentDimension.value] || reportLibrary.hospital)
const dimensionLabel = computed(
  () =>
    props.dimensionLabel ||
    {
      hospital: '全院概览',
      department: '科室分析',
      ward: '病区分析',
      chief_group: '主诊医师组',
      doctor: '个人',
    }[currentDimension.value],
)

const lossCount = computed(() => reportData.value.summary.lossCount)
const totalLossAmount = computed(() => reportData.value.summary.totalLossAmount)
const avgLossRate = computed(() => reportData.value.summary.avgLossRate)
const reasonDistribution = computed(() => reportData.value.reasonDistribution)
const topLossCases = computed(() => reportData.value.topLossCases)
const recommendations = computed(() => reportData.value.recommendations)

const downloadTextReport = (filename: string, content: string) => {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(downloadUrl)
}

const handleExportReport = () => {
  const content = [
    `# ${dimensionLabel.value} 超费原因/瓶颈报告`,
    '',
    `- 会话: ${props.sessionId || '演示模式'}`,
    `- 批次: ${props.batchId || '未提供'}`,
    '',
    '## 核心指标',
    `- 超费病例: ${lossCount.value}`,
    `- 超费金额: ¥${totalLossAmount.value.toLocaleString()}`,
    `- 平均超费率: ${avgLossRate.value.toFixed(1)}%`,
    '',
    '## 瓶颈报告',
    ...recommendations.value.map((item) => `- ${item}`),
  ].join('\n')

  downloadTextReport(`overcost_report_${currentDimension.value}.md`, content)
  if (props.sessionId) {
    message.success('超费分析报告导出成功')
  } else {
    message.warning('当前缺少 session_id，已导出演示瓶颈报告')
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 2px;
}
</style>
