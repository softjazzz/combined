<template>
  <div class="payment-monitoring-page drg-workbench-page">
    <div class="payment-monitoring-shell">
      <header class="payment-header mq-page-head">
        <div class="payment-title-block">
          <button type="button" class="back-button" aria-label="返回" @click="$router.back()">
            <MqIcon name="back" />
          </button>
          <div>
            <div class="payment-eyebrow mq-page-eyebrow">分析 · DRG/DIP</div>
            <h2 class="payment-title mq-page-title">付费监测</h2>
            <p class="payment-subtitle">
              按分组支付、实际费用、盈亏风险和控费边界复核病例付费表现。
            </p>
          </div>
        </div>

        <div class="payment-filter-strip">
          <div class="filter-chip scope-chip">
            <span>数据口径</span>
            <strong>{{ dataScopeLabel }}</strong>
          </div>
          <button type="button" class="standard-config-button" @click="configDrawerOpen = true">
            <MqIcon name="settings" />
            付费标准配置
          </button>
          <button
            type="button"
            class="backend-sync-button"
            :disabled="backendLoading"
            @click="runBackendPaymentSimulation"
          >
            {{ backendLoading ? '测算中' : '后端测算' }}
          </button>
          <a-select v-model:value="deptFilter" class="filter-control" size="middle">
            <a-select-option
              v-for="option in activeDeptOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </a-select-option>
          </a-select>
          <div class="filter-chip date-chip">
            <span>时间</span>
            <strong>{{ trendDateRangeLabel }}</strong>
          </div>
          <a-dropdown>
            <template #overlay>
              <a-menu @click="handleExport">
                <a-menu-item key="excel"> <MqIcon name="data" /> 导出 Excel </a-menu-item>
                <a-menu-item key="pdf"> <MqIcon name="doc" /> 导出 PDF </a-menu-item>
                <a-menu-item key="word"> <MqIcon name="doc" /> 导出 Word </a-menu-item>
              </a-menu>
            </template>
            <button type="button" class="export-button">
              <MqIcon name="download" />
              导出报告
            </button>
          </a-dropdown>
        </div>
      </header>

      <DatasetUploadPanel class="dataset-upload-surface" @data-changed="handleDatasetChanged" />

      <section class="standard-summary-panel mq-card">
        <div class="standard-summary-main">
          <span class="standard-status">地方付费标准库</span>
          <strong
            >{{ paymentStandardForm.regionName }} · {{ paymentStandardForm.schemeName }}</strong
          >
          <p>
            DIP 点值 {{ paymentStandardForm.dipPointValue }} 元/分，DRG 基准费率
            {{ paymentStandardForm.baseRate }} 元，医院系数
            {{ paymentStandardForm.hospitalCoefficient }}，地区系数
            {{ paymentStandardForm.regionCoefficient }}。
          </p>
        </div>
        <div class="standard-summary-meta">
          <span>极高组 &gt;= {{ formatRatioPercent(paymentStandardForm.highRateThreshold) }}</span>
          <span>极低组 &lt;= {{ formatRatioPercent(paymentStandardForm.lowRateThreshold) }}</span>
        </div>
      </section>

      <a-drawer
        v-model:open="configDrawerOpen"
        title="地方付费标准配置"
        placement="right"
        :width="560"
        destroy-on-close
      >
        <div class="standard-config-drawer">
          <div class="drawer-intro">
            <strong>模拟地方付费标准库</strong>
            <p>当前配置仅用于本页后端模拟测算，不写入正式医保结算清单或正式 DRG/DIP 结果。</p>
          </div>

          <div class="config-form-grid">
            <label class="config-field config-field-wide">
              <span>地区名称</span>
              <a-input v-model:value="paymentStandardForm.regionName" placeholder="例如：泸州" />
            </label>

            <label class="config-field config-field-wide">
              <span>方案名称</span>
              <a-input
                v-model:value="paymentStandardForm.schemeName"
                placeholder="例如：2025 DIP 付费方案"
              />
            </label>

            <label class="config-field">
              <span>DIP 点值（元/分）</span>
              <a-input-number
                v-model:value="paymentStandardForm.dipPointValue"
                :min="1"
                :precision="2"
                class="config-number"
              />
            </label>

            <label class="config-field">
              <span>DRG 基准费率（元）</span>
              <a-input-number
                v-model:value="paymentStandardForm.baseRate"
                :min="1"
                :precision="2"
                class="config-number"
              />
            </label>

            <label class="config-field">
              <span>医院系数</span>
              <a-input-number
                v-model:value="paymentStandardForm.hospitalCoefficient"
                :min="0.1"
                :step="0.01"
                :precision="2"
                class="config-number"
              />
            </label>

            <label class="config-field">
              <span>地区系数</span>
              <a-input-number
                v-model:value="paymentStandardForm.regionCoefficient"
                :min="0.1"
                :step="0.01"
                :precision="2"
                class="config-number"
              />
            </label>

            <label class="config-field">
              <span>费用极高组阈值</span>
              <a-input-number
                v-model:value="paymentStandardForm.highRateThreshold"
                :min="0.1"
                :step="0.05"
                :precision="2"
                class="config-number"
              />
            </label>

            <label class="config-field">
              <span>费用极低组阈值</span>
              <a-input-number
                v-model:value="paymentStandardForm.lowRateThreshold"
                :min="0.1"
                :step="0.05"
                :precision="2"
                class="config-number"
              />
            </label>
          </div>

          <div class="config-preview">
            <span>测算公式</span>
            <strong>DIP 支付 = DIP 分值 x 点值 x 医院系数 x 地区系数</strong>
            <strong>DRG 支付 = DRG 权重 x 基准费率 x 医院系数 x 地区系数</strong>
          </div>

          <div class="drawer-actions">
            <button type="button" class="secondary-action" @click="resetPaymentStandardConfig">
              恢复默认
            </button>
            <button
              type="button"
              class="primary-action"
              :disabled="backendLoading"
              @click="savePaymentStandardConfig"
            >
              应用并重新测算
            </button>
          </div>
        </div>
      </a-drawer>

      <div v-if="!drgMockEnabled && !hasUploadedData" class="data-warning">
        {{ backendStatusText }}
      </div>

      <section class="kpi-strip">
        <article class="kpi-card mq-card kpi-card-blue">
          <div class="kpi-content">
            <span class="kpi-label">总费用</span>
            <div class="kpi-value-row">
              <strong>{{ formatWan(overview.actualCost) }}</strong>
              <span>万元</span>
            </div>
            <p>纳入 {{ overview.caseCount }} 例，支付率 {{ overview.paymentRate.toFixed(1) }}%</p>
          </div>
          <span class="kpi-icon">
            <MqIcon name="settlement" />
          </span>
        </article>

        <article class="kpi-card mq-card kpi-card-green">
          <div class="kpi-content">
            <span class="kpi-label">预计医保支付</span>
            <div class="kpi-value-row">
              <strong>{{ formatWan(overview.payment) }}</strong>
              <span>万元</span>
            </div>
            <p>按当前病例费用与分组支付自动汇总</p>
          </div>
          <span class="kpi-icon">
            <MqIcon name="settlement" />
          </span>
        </article>

        <article class="kpi-card mq-card kpi-card-red">
          <div class="kpi-content">
            <span class="kpi-label">预计盈亏</span>
            <div class="kpi-value-row" :class="overview.profit >= 0 ? 'is-profit' : 'is-loss'">
              <strong>{{ formatWanSigned(overview.profit) }}</strong>
              <span>万元</span>
            </div>
            <p>差额占总费用 {{ profitGapRate.toFixed(1) }}%</p>
          </div>
          <span class="kpi-icon">
            <MqIcon v-if="overview.profit >= 0" name="stats" />
            <MqIcon v-else name="stats" />
          </span>
        </article>

        <article class="kpi-card mq-card kpi-card-amber">
          <div class="kpi-content">
            <span class="kpi-label">亏损病例</span>
            <div class="kpi-value-row is-loss">
              <strong>{{ overview.lossCases }}</strong>
              <span>例</span>
            </div>
            <p>占比 {{ lossCaseRate.toFixed(1) }}%，优先复核亏损金额 Top 病例</p>
          </div>
          <span class="kpi-icon">
            <MqIcon name="stats" />
          </span>
        </article>
      </section>

      <section class="analysis-grid">
        <div class="analysis-panel mq-card trend-panel">
          <div class="panel-heading">
            <div>
              <h3>费用与支付趋势</h3>
              <p>实际费用、预计医保支付与支付率同屏观察</p>
            </div>
            <a-segmented v-model:value="trendScope" :options="trendScopeOptions" size="small" />
          </div>
          <div ref="paymentTrendRef" class="trend-chart" />
        </div>

        <div class="analysis-panel mq-card risk-panel">
          <div class="panel-heading">
            <div>
              <h3>亏损风险洞察</h3>
              <p>按当前科室筛选汇总亏损金额 Top4</p>
            </div>
            <button type="button" class="text-action" @click="statusFilter = 'loss'">详情</button>
          </div>

          <div class="risk-table">
            <div class="risk-head">
              <span>排名</span>
              <span>风险原因</span>
              <span>风险强度</span>
              <span>亏损金额</span>
              <span>占比</span>
            </div>
            <div v-for="item in lossRiskInsights" :key="item.caseNo" class="risk-row">
              <span class="risk-rank">{{ item.rank }}</span>
              <div class="risk-reason">
                <strong>{{ item.reason }}</strong>
                <small>{{ item.deptName }} · {{ item.caseNo }}</small>
              </div>
              <div class="risk-bar-cell">
                <i :style="{ width: `${item.barPercent}%` }" />
              </div>
              <span class="risk-amount">{{ formatWan(item.lossAmount) }}</span>
              <span class="risk-percent">{{ item.percent.toFixed(1) }}%</span>
            </div>
            <div v-if="!lossRiskInsights.length" class="risk-empty">当前筛选下暂无亏损病例。</div>
          </div>
        </div>
      </section>

      <section class="detail-layout">
        <div class="detail-panel mq-card">
          <div class="detail-toolbar">
            <div>
              <h3>病例付费明细</h3>
              <p>{{ tableSummaryLabel }}</p>
            </div>
            <div class="detail-filters">
              <a-segmented v-model:value="groupFilter" :options="paymentMonitoringGroupOptions" />
              <a-select v-model:value="statusFilter" class="status-filter" size="small">
                <a-select-option value="all"> 全部状态 </a-select-option>
                <a-select-option value="profit"> 盈余 </a-select-option>
                <a-select-option value="loss"> 亏损 </a-select-option>
              </a-select>
            </div>
          </div>

          <div class="payment-table-wrap">
            <table class="payment-table">
              <thead>
                <tr>
                  <th>患者信息</th>
                  <th>科室</th>
                  <th>DRG/DIP 组</th>
                  <th>权重/分值</th>
                  <th>实际费用</th>
                  <th>预计支付</th>
                  <th>盈亏</th>
                  <th>风险</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredRows" :key="item.id">
                  <td>
                    <div class="case-cell">
                      <span>{{ item.caseNo }}</span>
                      <small>{{ item.ruleHint }}</small>
                    </div>
                  </td>
                  <td>{{ item.deptName }}</td>
                  <td>
                    <strong>{{ item.drg }}</strong>
                  </td>
                  <td>
                    <div class="rate-cell">
                      <span>{{ calcCostRate(item).toFixed(1) }}%</span>
                      <small>成本消耗率</small>
                    </div>
                  </td>
                  <td>¥{{ formatYuan(item.actualCost) }}</td>
                  <td>¥{{ formatYuan(item.payment) }}</td>
                  <td>
                    <span
                      :class="item.payment - item.actualCost >= 0 ? 'money-profit' : 'money-loss'"
                    >
                      {{ item.payment - item.actualCost >= 0 ? '+' : '-' }}¥{{
                        formatYuan(Math.abs(item.payment - item.actualCost))
                      }}
                    </span>
                  </td>
                  <td>
                    <a-tag :color="getGroupTagColor(resolveGroupType(item))">
                      {{ getPaymentGroupLabel(resolveGroupType(item)) }}
                    </a-tag>
                  </td>
                </tr>
                <tr v-if="!filteredRows.length">
                  <td colspan="8" class="empty-cell">当前筛选下暂无数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <aside class="advice-panel mq-card">
          <div class="panel-heading">
            <div>
              <h3>控费建议</h3>
              <p>按成本消耗率分组给出复核重点</p>
            </div>
          </div>
          <div class="advice-list">
            <button
              v-for="item in controlAdviceItems"
              :key="item.groupType"
              type="button"
              class="advice-item"
              :class="{ active: groupFilter === item.groupType }"
              @click="groupFilter = item.groupType"
            >
              <span class="advice-icon">{{ item.count }}</span>
              <span class="advice-copy">
                <strong>{{ item.title }}</strong>
                <small>{{ item.suggestion }}</small>
              </span>
            </button>
          </div>
          <div class="advice-footnote">数据截至：{{ trendDateRangeLabel }}</div>
        </aside>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import MqIcon from '@/components/icons/MqIcon.vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'

import { message } from 'ant-design-vue'
import {
  simulatePaymentMonitoring,
  type PaymentMonitoringRecordInput,
  type PaymentMonitoringResult,
} from '@/api/drg'
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
const backendRows = ref<PaymentMonitoringRow[]>([])
const backendResult = ref<PaymentMonitoringResult | null>(null)
const backendLoading = ref(false)
const backendError = ref('')
const configDrawerOpen = ref(false)

type LocalPaymentStandardConfig = {
  regionName: string
  schemeName: string
  dipPointValue: number
  baseRate: number
  hospitalCoefficient: number
  regionCoefficient: number
  highRateThreshold: number
  lowRateThreshold: number
}

const PAYMENT_STANDARD_STORAGE_KEY = 'medqc.localPaymentStandard.v1'
const DEFAULT_PAYMENT_STANDARD: LocalPaymentStandardConfig = {
  regionName: '泸州',
  schemeName: '2025 DIP 付费方案',
  dipPointValue: 75,
  baseRate: 7000,
  hospitalCoefficient: 1,
  regionCoefficient: 1,
  highRateThreshold: 1.2,
  lowRateThreshold: 0.8,
}

const paymentStandardForm = ref<LocalPaymentStandardConfig>({ ...DEFAULT_PAYMENT_STANDARD })

// 数据源：优先从上传数据 Store 映射，无上传数据时回退到本地降级数据
const sourceRows = computed<PaymentMonitoringRow[]>(() => {
  if (hasUploadedData.value) {
    return mapCaseRecordsToPaymentMonitoringRows(drgDatasetStore.records)
  }
  return paymentMonitoringRows
})

const activeRows = computed<PaymentMonitoringRow[]>(() => {
  if (backendRows.value.length) return backendRows.value
  return sourceRows.value
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
const deptFilter = ref('all')
const statusFilter = ref<'all' | 'profit' | 'loss'>('all')
const groupFilter = ref<PaymentGroupType>('all')
const drgMockEnabled = ref(isDrgMockModeEnabled())
const trendScope = ref('hospital')

const trendScopeOptions = [
  { label: '全院', value: 'hospital' },
  { label: '科室', value: 'department' },
  { label: '病种', value: 'disease' },
]

let paymentChart: echarts.ECharts | null = null
let unsubscribeDrgMockMode: (() => void) | null = null

const overview = computed(() => getPaymentMonitoringOverview(activeRows.value))
const selectedDeptRows = computed(() =>
  filterPaymentMonitoringRows(activeRows.value, { deptKey: deptFilter.value }),
)
const filteredRows = computed(() =>
  filterPaymentMonitoringRows(activeRows.value, {
    deptKey: deptFilter.value,
    groupType: groupFilter.value,
    status: statusFilter.value,
  }),
)

const selectedDeptLabel = computed(() => {
  return (
    activeDeptOptions.value.find((option) => option.value === deptFilter.value)?.label || '全部科室'
  )
})

const selectedGroupLabel = computed(() => {
  return (
    paymentMonitoringGroupOptions.find((option) => option.value === groupFilter.value)?.label ||
    '全部组别'
  )
})

const dataScopeLabel = computed(() => {
  if (backendRows.value.length) return '地方标准库测算'
  if (hasUploadedData.value) return '上传数据'
  return drgMockEnabled.value ? '降级数据' : '真实优先'
})

const backendStatusText = computed(() => {
  if (backendRows.value.length && backendResult.value) {
    return `${backendResult.value.safety_warning} 当前按 ${paymentStandardForm.value.regionName} ${paymentStandardForm.value.schemeName} 测算，不写入正式结算结果。`
  }
  if (backendError.value) {
    return `后端付费监测暂不可用：${backendError.value}。当前展示降级数据，不写入正式结算结果。`
  }
  return '当前处于真实优先模式。若未接入正式数据，将展示“待接入/降级数据”状态，不写入正式结算结果。'
})

const trendDateRangeLabel = computed(() => {
  if (!paymentMonitoringTrend.length) return '近30日'
  const firstDay = String(paymentMonitoringTrend[0].day).padStart(2, '0')
  const lastDay = String(paymentMonitoringTrend[paymentMonitoringTrend.length - 1].day).padStart(
    2,
    '0',
  )
  return `2025-05-${firstDay} 至 2025-05-${lastDay}`
})

const lossCaseRate = computed(() => {
  if (!overview.value.caseCount) return 0
  return (overview.value.lossCases / overview.value.caseCount) * 100
})

const profitGapRate = computed(() => {
  if (!overview.value.actualCost) return 0
  return (Math.abs(overview.value.profit) / overview.value.actualCost) * 100
})

const tableSummaryLabel = computed(() => {
  const statusLabel =
    statusFilter.value === 'all' ? '全部状态' : statusFilter.value === 'profit' ? '盈余' : '亏损'
  return `${selectedDeptLabel.value} · ${selectedGroupLabel.value} · ${statusLabel}，共 ${filteredRows.value.length} 条`
})

const lossRiskInsights = computed(() => {
  const losses = selectedDeptRows.value
    .filter((row) => row.payment - row.actualCost < 0)
    .map((row) => ({
      row,
      lossAmount: Math.abs(row.payment - row.actualCost),
    }))
    .sort((left, right) => right.lossAmount - left.lossAmount)

  const totalLoss = losses.reduce((sum, item) => sum + item.lossAmount, 0)
  const maxLoss = losses[0]?.lossAmount || 1

  return losses.slice(0, 4).map((item, index) => ({
    rank: index + 1,
    caseNo: item.row.caseNo,
    deptName: item.row.deptName,
    reason:
      item.row.controlTip || item.row.ruleHint || getPaymentGroupLabel(resolveGroupType(item.row)),
    lossAmount: item.lossAmount,
    percent: totalLoss ? (item.lossAmount / totalLoss) * 100 : 0,
    barPercent: Math.max(6, (item.lossAmount / maxLoss) * 100),
  }))
})

const controlAdviceItems = computed(() => {
  return paymentMonitoringRules.map((rule) => ({
    ...rule,
    count: getGroupCaseCount(rule.groupType),
  }))
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

function formatYuan(value: number): string {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatRatioPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`
}

function getGroupCaseCount(groupType: Exclude<PaymentGroupType, 'all'>): number {
  return selectedDeptRows.value.filter((row) => resolveGroupType(row) === groupType).length
}

function buildPaymentSimulationInput(rows: PaymentMonitoringRow[]): PaymentMonitoringRecordInput[] {
  const standard = paymentStandardForm.value
  return rows.map((row) => ({
    case_id: String(row.id),
    visit_id: row.caseNo,
    patient_name: row.caseNo,
    department: row.deptName,
    group_type: row.drg.includes(':') ? 'DIP' : 'DRG',
    group_code: row.drg,
    group_name: row.ruleHint,
    drg_code: row.drg.includes(':') ? undefined : row.drg,
    dip_code: row.drg.includes(':') ? row.drg : undefined,
    weight: row.drg.includes(':')
      ? undefined
      : (row.weight ?? roundNumber(row.baselinePayment / standard.baseRate, 4)),
    rw: row.drg.includes(':')
      ? undefined
      : (row.weight ?? roundNumber(row.baselinePayment / standard.baseRate, 4)),
    score: row.drg.includes(':')
      ? (row.dipScore ?? roundNumber(row.baselinePayment / standard.dipPointValue, 2))
      : undefined,
    dip_score: row.drg.includes(':')
      ? (row.dipScore ?? roundNumber(row.baselinePayment / standard.dipPointValue, 2))
      : undefined,
    actual_cost: row.actualCost,
  }))
}

function roundNumber(value: number, precision: number): number {
  const factor = 10 ** precision
  return Math.round(value * factor) / factor
}

function getRecordText(record: Record<string, unknown>, key: string, fallback = ''): string {
  const value = record[key]
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  return fallback
}

function getRecordNumber(record: Record<string, unknown>, key: string, fallback = 0): number {
  const value = record[key]
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

function mapBackendRecordToRow(
  record: Record<string, unknown>,
  index: number,
): PaymentMonitoringRow {
  const actualCost = getRecordNumber(record, 'actual_cost')
  const expectedPayment = getRecordNumber(record, 'expected_payment')
  const costRatio = getRecordNumber(record, 'cost_ratio', 1)
  const groupCode = getRecordText(record, 'group_code', '-')
  const groupName = getRecordText(record, 'group_name', '后端模拟测算')

  return {
    id: index + 1,
    caseNo: getRecordText(record, 'case_id', `CASE-${index + 1}`),
    deptKey: getRecordText(record, 'department', 'unknown'),
    deptName: getRecordText(record, 'department', '未知科室'),
    drg: groupCode,
    actualCost,
    payment: expectedPayment,
    baselinePayment:
      expectedPayment > 0
        ? Math.max(expectedPayment, actualCost / Math.max(costRatio, 0.01))
        : actualCost,
    weight: getRecordNumber(record, 'weight'),
    dipScore: getRecordNumber(record, 'score'),
    ruleHint: groupName,
    controlTip:
      getRecordText(record, 'risk_level') === 'high'
        ? '费用高于支付标准，优先复核耗材、药品、检查和住院日结构'
        : '按当前本地化付费标准完成模拟测算',
  }
}

function buildPaymentStandardPayload(): Record<string, unknown> {
  const standard = paymentStandardForm.value
  return {
    config_version_id: `local-payment-${Date.now()}`,
    region: standard.regionName,
    standard_name: standard.schemeName,
    base_rate: standard.baseRate,
    dip_point_value: standard.dipPointValue,
    hospital_coefficient: standard.hospitalCoefficient,
    region_coefficient: standard.regionCoefficient,
    high_rate_threshold: standard.highRateThreshold,
    low_rate_threshold: standard.lowRateThreshold,
  }
}

function loadPaymentStandardConfig() {
  if (typeof window === 'undefined') return
  const raw = window.localStorage.getItem(PAYMENT_STANDARD_STORAGE_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw) as Partial<LocalPaymentStandardConfig>
    paymentStandardForm.value = {
      ...DEFAULT_PAYMENT_STANDARD,
      ...parsed,
    }
  } catch {
    window.localStorage.removeItem(PAYMENT_STANDARD_STORAGE_KEY)
  }
}

function persistPaymentStandardConfig() {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(
    PAYMENT_STANDARD_STORAGE_KEY,
    JSON.stringify(paymentStandardForm.value),
  )
}

function resetPaymentStandardConfig() {
  paymentStandardForm.value = { ...DEFAULT_PAYMENT_STANDARD }
}

async function savePaymentStandardConfig() {
  persistPaymentStandardConfig()
  configDrawerOpen.value = false
  await runBackendPaymentSimulation()
}

async function runBackendPaymentSimulation() {
  backendLoading.value = true
  backendError.value = ''
  try {
    const result = await simulatePaymentMonitoring({
      records: buildPaymentSimulationInput(sourceRows.value),
      payment_standard: buildPaymentStandardPayload(),
    })
    backendResult.value = result
    backendRows.value = result.records.map(mapBackendRecordToRow)
    message.success('后端付费模拟测算完成')
    renderPaymentTrendChart()
  } catch (error) {
    backendRows.value = []
    backendResult.value = null
    backendError.value = error instanceof Error ? error.message : '接口调用失败'
    message.warning('后端付费监测暂不可用，已保留降级数据')
  } finally {
    backendLoading.value = false
  }
}

function buildExportPayload() {
  const now = new Date().toLocaleString('zh-CN')
  return {
    title: 'DRG/DIP 付费监测报告',
    filenameBase: `drg_payment_${Date.now()}`,
    meta: [
      ['导出时间', now],
      ['数据模式', drgMockEnabled.value ? '降级数据模式' : '真实优先模式'],
      [
        '地方付费标准',
        `${paymentStandardForm.value.regionName} ${paymentStandardForm.value.schemeName}`,
      ],
      ['DIP点值', `${paymentStandardForm.value.dipPointValue} 元/分`],
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
        lineStyle: { color: '#0a6cff', width: 2 },
        itemStyle: { color: '#0a6cff' },
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

onMounted(() => {
  loadPaymentStandardConfig()
  drgMockEnabled.value = isDrgMockModeEnabled()
  unsubscribeDrgMockMode = onDrgMockModeChange((enabled) => {
    drgMockEnabled.value = enabled
  })
  void runBackendPaymentSimulation()
  renderPaymentTrendChart()
})

/** 数据集变更（上传/清除）后刷新图表 */
function handleDatasetChanged() {
  deptFilter.value = 'all'
  groupFilter.value = 'all'
  statusFilter.value = 'all'
  backendRows.value = []
  backendResult.value = null
  void runBackendPaymentSimulation()
}

onUnmounted(() => {
  unsubscribeDrgMockMode?.()
  paymentChart?.dispose()
})
</script>

<style scoped src="../../styles/drg-payment.css"></style>
<style scoped src="./drg-dip-workbench.css"></style>
