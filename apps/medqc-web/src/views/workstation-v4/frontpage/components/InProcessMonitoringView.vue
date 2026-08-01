<template>
  <div class="in-process-page h-full w-full overflow-y-auto px-5 py-5 lg:px-6">
    <div class="mx-auto flex max-w-[1600px] flex-col gap-4">
      <header class="page-header">
        <div class="header-title">
          <button
            type="button"
            class="back-button"
            @click="$router.back()"
          >
            <ArrowLeftOutlined />
          </button>
          <div>
            <div class="breadcrumb">
              工作台 / 事中监控
            </div>
            <h2>事中监控</h2>
            <p>跟踪在院病例费用消耗、分组变化和干预优先级。</p>
          </div>
        </div>

        <div class="header-actions">
          <span class="filter-chip">近 7 日</span>
          <span class="filter-chip">全部科室</span>
          <span class="filter-chip threshold-chip">阈值 {{ stats.control_threshold.toFixed(2) }}</span>
          <span :class="dataModeClass">
            {{ dataModeLabel }}
          </span>
          <button
            type="button"
            class="secondary-button"
            :disabled="loading"
            @click="loadData"
          >
            <LoadingOutlined
              v-if="loading"
              class="animate-spin"
            />
            <span v-else>刷新</span>
          </button>
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
            <button class="primary-button">
              <DownloadOutlined /> 导出
            </button>
          </a-dropdown>
        </div>
      </header>

      <DatasetUploadPanel
        class="dataset-upload-surface"
        @data-changed="handleDatasetChanged"
      />

      <section class="kpi-strip">
        <article class="kpi-card">
          <span class="kpi-icon kpi-icon--blue"><InfoCircleOutlined /></span>
          <div>
            <div class="kpi-label">
              监测病例
            </div>
            <div class="kpi-value">
              {{ stats.total_alerts }}
            </div>
            <p>当前纳入事中跟踪的病例</p>
          </div>
        </article>

        <article class="kpi-card">
          <span class="kpi-icon kpi-icon--red"><CloseCircleOutlined /></span>
          <div>
            <div class="kpi-label">
              重点预警
            </div>
            <div class="kpi-value">
              {{ stats.severe_alerts }}
            </div>
            <p>费用比超过重点阈值</p>
          </div>
        </article>

        <article class="kpi-card">
          <span class="kpi-icon kpi-icon--amber"><WarningOutlined /></span>
          <div>
            <div class="kpi-label">
              待处理建议
            </div>
            <div class="kpi-value">
              {{ stats.pending_suggestions }}
            </div>
            <p>需科室复核的控费建议</p>
          </div>
        </article>

        <article class="kpi-card">
          <span class="kpi-icon kpi-icon--green"><RiseOutlined /></span>
          <div>
            <div class="kpi-label">
              今日干预
            </div>
            <div class="kpi-value">
              {{ stats.today_new }}
            </div>
            <p>新进入监控队列的变化</p>
          </div>
        </article>
      </section>

      <section class="main-grid">
        <div class="panel monitor-panel">
          <div class="panel-head">
            <div>
              <h3>费用消耗监控</h3>
              <p>{{ mockScopeNote }}</p>
            </div>
            <div class="panel-tools">
              <a-select
                v-model:value="filterType"
                class="status-select"
                size="small"
              >
                <a-select-option value="all">
                  全部病例
                </a-select-option>
                <a-select-option value="warning">
                  仅看预警
                </a-select-option>
                <a-select-option value="normal">
                  仅看正常
                </a-select-option>
              </a-select>
            </div>
          </div>

          <div class="chart-toolbar">
            <span>费用比中位数</span>
            <span>消耗比均值</span>
            <span>阈值 {{ stats.control_threshold.toFixed(2) }}</span>
          </div>
          <div
            ref="cmiChartRef"
            class="trend-chart"
          />

          <div class="case-list">
            <table>
              <thead>
                <tr>
                  <th>患者信息 / 分组</th>
                  <th>科室</th>
                  <th>费用消耗比</th>
                  <th>风险原因</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in filteredAlerts"
                  :key="item.id"
                >
                  <td>
                    <div class="patient-cell">
                      <strong>{{ item.diagnosis }}</strong>
                      <span>{{ item.case_no }} · {{ item.drg }}</span>
                    </div>
                  </td>
                  <td>{{ item.dept }}</td>
                  <td>
                    <div class="ratio-cell">
                      <strong :class="item.ratio > 1 ? 'text-red-600' : 'text-emerald-600'">
                        {{ formatRatio(item.ratio) }}
                      </strong>
                      <span :class="item.payment_gap >= 0 ? 'text-red-600' : 'text-emerald-600'">
                        {{ formatMoney(item.payment_gap) }}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span class="reason-text">{{ item.control_tip }}</span>
                  </td>
                  <td>
                    <span
                      :class="levelClass(item.monitor_level)"
                      class="status-pill"
                    >
                      {{ levelLabel(item.monitor_level) }}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      class="link-button"
                      @click="openDetail(item)"
                    >
                      查看建议
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <aside class="panel priority-panel">
          <div class="panel-head">
            <div>
              <h3>干预优先级</h3>
              <p>按费用比和监测等级排序处理</p>
            </div>
            <button
              type="button"
              class="text-link"
              @click="filterType = 'warning'"
            >
              查看全部
            </button>
          </div>

          <div class="priority-list">
            <button
              v-for="(item, index) in drgAlerts.slice(0, 5)"
              :key="item.id"
              type="button"
              class="priority-row"
              @click="openDetail(item)"
            >
              <span
                class="rank"
                :class="index < 3 ? 'rank--hot' : ''"
              >
                {{ index + 1 }}
              </span>
              <span class="priority-main">
                <strong>{{ item.diagnosis }}</strong>
                <span>{{ item.dept }} · {{ item.case_no }}</span>
              </span>
              <span class="priority-value">
                {{ formatRatio(item.ratio) }}
              </span>
              <span class="priority-action">评估费用</span>
            </button>
          </div>

          <div class="suggestion-block">
            <div
              v-for="tip in controlTips"
              :key="tip.title"
              class="suggestion-row"
            >
              <span
                class="suggestion-dot"
                :class="`suggestion-dot--${tip.level}`"
              />
              <div>
                <strong>{{ tip.title }}</strong>
                <p>{{ tip.suggestion }}</p>
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section class="bottom-grid">
        <div class="panel">
          <div class="panel-head compact">
            <div>
              <h3>科室消耗指数</h3>
              <p>高于基准的科室优先纳入复核</p>
            </div>
            <span class="panel-meta">模拟分组 {{ stats.simulated_groups }} 组</span>
          </div>
          <div
            ref="costChartRef"
            class="cost-chart"
          />
        </div>

        <div class="panel">
          <div class="panel-head compact">
            <div>
              <h3>分组变动提醒</h3>
              <p>跟踪费用比、分组和路径变化</p>
            </div>
            <span class="panel-meta">共 {{ stats.pending_suggestions }} 条建议</span>
          </div>

          <div class="change-list">
            <button
              v-for="(item, index) in drgAlerts.slice(0, 5)"
              :key="`change-${item.id}`"
              type="button"
              class="change-row"
              @click="openDetail(item)"
            >
              <span
                class="change-dot"
                :class="
                  item.monitor_level === 'critical'
                    ? 'bg-red-500'
                    : item.monitor_level === 'warning'
                      ? 'bg-amber-500'
                      : 'bg-blue-500'
                "
              />
              <span class="change-main">
                <strong>{{ item.diagnosis }}</strong>
                <span>{{ item.drg }} · {{ item.dept }}</span>
              </span>
              <span
                class="change-tag"
                :class="item.ratio > 1 ? 'change-tag--up' : 'change-tag--down'"
              >
                {{ item.ratio > 1 ? '费用上浮' : '低耗复核' }}
              </span>
              <span class="change-time">{{
                index === 0 ? '10:25' : `0${9 - index}:5${index}`
              }}</span>
            </button>
          </div>
        </div>
      </section>
    </div>

    <a-modal
      v-model:open="detailOpen"
      title="模拟分组详情"
      :footer="null"
      width="760px"
    >
      <template v-if="selectedAlert">
        <a-alert
          :type="
            selectedAlert.monitor_level === 'critical'
              ? 'error'
              : selectedAlert.monitor_level === 'warning'
                ? 'warning'
                : 'info'
          "
          show-icon
          :message="selectedAlert.control_tip"
          class="mb-4"
        />

        <a-descriptions
          bordered
          size="small"
          :column="2"
        >
          <a-descriptions-item label="病例号">
            {{ selectedAlert.case_no }}
          </a-descriptions-item>
          <a-descriptions-item label="科室">
            {{ selectedAlert.dept }}
          </a-descriptions-item>
          <a-descriptions-item label="诊断">
            {{ selectedAlert.diagnosis }}
          </a-descriptions-item>
          <a-descriptions-item label="DRG">
            {{ selectedAlert.drg }}
          </a-descriptions-item>
          <a-descriptions-item label="支付标准">
            {{ formatMoney(selectedAlert.baseline_payment) }}
          </a-descriptions-item>
          <a-descriptions-item label="实际费用">
            {{ formatMoney(selectedAlert.actual_cost) }}
          </a-descriptions-item>
          <a-descriptions-item label="差额">
            {{ formatMoney(selectedAlert.payment_gap) }}
          </a-descriptions-item>
          <a-descriptions-item label="费用比">
            {{ formatRatio(selectedAlert.ratio) }}
          </a-descriptions-item>
          <a-descriptions-item label="住院天数">
            {{ selectedAlert.los }} 天
          </a-descriptions-item>
          <a-descriptions-item label="监测等级">
            {{ levelLabel(selectedAlert.monitor_level) }}
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import {
  ArrowLeftOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  RiseOutlined,
  WarningOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  FileWordOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import { panelApi } from '@/api/panel'
import type {
  CmiTrend,
  DeptCostIndex,
  DrgAlert,
  MonitoringControlTip,
  MonitoringStats,
} from '@/api/panel'
import { useDrgDatasetStore } from '@/stores/drgDataset'
import { buildInProcessMonitoringDataset } from '@/utils/drg-aggregation'
import { isDrgMockModeEnabled, onDrgMockModeChange } from '@/utils/drgMockMode'
import { exportDrgMockReport, type DrgExportFormat } from '@/utils/drgMockExport'
import DatasetUploadPanel from '@/components/drg/DatasetUploadPanel.vue'

const FALLBACK_CMI: CmiTrend = {
  labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
  values: [1.0, 1.05, 1.03, 1.08, 1.12, 1.09, 1.15],
  benchmark: 1.0,
}

const FALLBACK_COST: DeptCostIndex = {
  departments: [
    '心内科',
    '呼吸科',
    '骨科',
    '普外科',
    '神经内科',
    '神经外科',
    '消化内科',
    '泌尿外科',
  ],
  values: [0.92, 0.89, 1.15, 0.85, 1.05, 1.28, 0.95, 0.88],
  benchmark: 1.0,
}

const FALLBACK_TIPS: MonitoringControlTip[] = [
  {
    title: '高费用病例优先复核',
    indicator: '费用比 ≥ 1.20',
    current_value: '3 例',
    target_value: '0 例',
    suggestion: '优先核查高值耗材、术后用药和超标准检查，减少短期内的费用放大。',
    level: 'critical',
  },
  {
    title: '边界病例持续跟踪',
    indicator: '1.00 ~ 1.20',
    current_value: '2 例',
    target_value: '稳定在阈值内',
    suggestion: '对照路径和支付标准提前修正费用偏差，防止滑入预警区间。',
    level: 'warning',
  },
  {
    title: '数据口径统一',
    indicator: 'mid/payment/post',
    current_value: '同一契约',
    target_value: '字段不漂移',
    suggestion: '各页面共用同一套字段，后端未接入时仅展示降级数据，不写入正式结果。',
    level: 'info',
  },
]

const FALLBACK_STATS: MonitoringStats = {
  total_alerts: 8,
  severe_alerts: 4,
  pending_suggestions: 8,
  today_new: 15,
  simulated_groups: 8,
  control_threshold: 1.0,
  mock_scope_note: '事中/付费/事后共用同一数据口径',
  control_tips: FALLBACK_TIPS,
}

const FALLBACK_ALERTS: DrgAlert[] = [
  {
    id: 1,
    case_no: '#2026010101',
    dept: '心内科',
    diagnosis: '急性心肌梗死',
    drg: 'FM19',
    ratio: 1.35,
    status: 'warning',
    los: 12,
    est_cost: 85000,
    baseline_payment: 63000,
    actual_cost: 85000,
    payment_gap: 22000,
    monitor_level: 'critical',
    control_tip: '高值耗材和介入路径共同推高费用，建议优先复核。',
  },
  {
    id: 2,
    case_no: '#2026010108',
    dept: '神经外科',
    diagnosis: '颅内动脉瘤',
    drg: 'IC15',
    ratio: 1.28,
    status: 'warning',
    los: 18,
    est_cost: 125000,
    baseline_payment: 98000,
    actual_cost: 125000,
    payment_gap: 27000,
    monitor_level: 'critical',
    control_tip: '术中耗材与术后监护费用偏高，建议提前归拢关键成本。',
  },
  {
    id: 3,
    case_no: '#2026010115',
    dept: '骨科',
    diagnosis: '胫腓骨骨折',
    drg: 'IB19',
    ratio: 1.22,
    status: 'warning',
    los: 15,
    est_cost: 65000,
    baseline_payment: 53300,
    actual_cost: 65000,
    payment_gap: 11700,
    monitor_level: 'critical',
    control_tip: '内固定耗材使用偏高，建议核对术式和耗材标准。',
  },
  {
    id: 4,
    case_no: '#2026010103',
    dept: '骨科',
    diagnosis: '腰椎间盘突出',
    drg: 'EB13',
    ratio: 1.08,
    status: 'warning',
    los: 8,
    est_cost: 38000,
    baseline_payment: 35200,
    actual_cost: 38000,
    payment_gap: 2800,
    monitor_level: 'warning',
    control_tip: '建议关注术后康复耗材和检查频次。',
  },
  {
    id: 5,
    case_no: '#2026010105',
    dept: '神经内科',
    diagnosis: '急性脑梗死',
    drg: 'BR23',
    ratio: 1.05,
    status: 'warning',
    los: 10,
    est_cost: 42000,
    baseline_payment: 40000,
    actual_cost: 42000,
    payment_gap: 2000,
    monitor_level: 'warning',
    control_tip: '重点关注抗栓用药和病程记录的一致性。',
  },
  {
    id: 6,
    case_no: '#2026010112',
    dept: '消化内科',
    diagnosis: '上消化道出血',
    drg: 'GD21',
    ratio: 1.03,
    status: 'warning',
    los: 7,
    est_cost: 28000,
    baseline_payment: 27200,
    actual_cost: 28000,
    payment_gap: 800,
    monitor_level: 'warning',
    control_tip: '建议核查内镜检查与止血耗材占比。',
  },
  {
    id: 7,
    case_no: '#2026010102',
    dept: '呼吸科',
    diagnosis: '社区获得性肺炎',
    drg: 'BW15',
    ratio: 0.92,
    status: 'normal',
    los: 6,
    est_cost: 18000,
    baseline_payment: 19500,
    actual_cost: 18000,
    payment_gap: -1500,
    monitor_level: 'info',
    control_tip: '费用处于可控区间，可继续观察药占比变化。',
  },
  {
    id: 8,
    case_no: '#2026010104',
    dept: '普外科',
    diagnosis: '急性阑尾炎',
    drg: 'GD15',
    ratio: 0.85,
    status: 'normal',
    los: 4,
    est_cost: 12000,
    baseline_payment: 14100,
    actual_cost: 12000,
    payment_gap: -2100,
    monitor_level: 'info',
    control_tip: '当前费用低于标准，可作为稳定样本继续回放。',
  },
]

const REALISTIC_STATS: MonitoringStats = {
  ...FALLBACK_STATS,
  total_alerts: 112,
  severe_alerts: 28,
  pending_suggestions: 73,
  today_new: 36,
  simulated_groups: 2863,
  control_threshold: 1.2,
  mock_scope_note: '基于 2025 年病案与 DIP 关联数据重建（支付率约 58%）',
}

const REALISTIC_ALERTS: DrgAlert[] = [
  {
    id: 101,
    case_no: '#2025120001',
    dept: '心血管内科专业',
    diagnosis: '动脉粥样硬化性心脏病',
    drg: 'I25.1:88.5500',
    ratio: 1.34,
    status: 'warning',
    los: 8,
    est_cost: 10860,
    baseline_payment: 8100,
    actual_cost: 10860,
    payment_gap: 2760,
    monitor_level: 'critical',
    control_tip: '介入相关耗材和复查项目偏高，建议按术式路径复核。',
  },
  {
    id: 102,
    case_no: '#2025120002',
    dept: '普通外科专业',
    diagnosis: '化疗相关住院',
    drg: 'Z51.1:99.2503',
    ratio: 1.29,
    status: 'warning',
    los: 7,
    est_cost: 8260,
    baseline_payment: 6400,
    actual_cost: 8260,
    payment_gap: 1860,
    monitor_level: 'critical',
    control_tip: '药占比偏高且治疗项目偏密，建议分项核减。',
  },
  {
    id: 103,
    case_no: '#2025120003',
    dept: '骨科专业',
    diagnosis: '腰椎间盘突出',
    drg: 'M51:11',
    ratio: 1.22,
    status: 'warning',
    los: 9,
    est_cost: 7420,
    baseline_payment: 6080,
    actual_cost: 7420,
    payment_gap: 1340,
    monitor_level: 'critical',
    control_tip: '康复与检查组合超路径，建议核查治疗频次。',
  },
  {
    id: 104,
    case_no: '#2025120004',
    dept: '呼吸内科专业',
    diagnosis: '慢阻肺急性加重',
    drg: 'J44.0',
    ratio: 1.14,
    status: 'warning',
    los: 7,
    est_cost: 6690,
    baseline_payment: 5870,
    actual_cost: 6690,
    payment_gap: 820,
    monitor_level: 'warning',
    control_tip: '重点关注抗感染联合方案和重复检验。',
  },
  {
    id: 105,
    case_no: '#2025120005',
    dept: '神经内科专业',
    diagnosis: '短暂性脑缺血发作',
    drg: 'G45.0',
    ratio: 1.08,
    status: 'warning',
    los: 6,
    est_cost: 4360,
    baseline_payment: 4020,
    actual_cost: 4360,
    payment_gap: 340,
    monitor_level: 'warning',
    control_tip: '检查项目略超基准，建议控制影像复查。',
  },
  {
    id: 106,
    case_no: '#2025120006',
    dept: '儿科',
    diagnosis: '急性支气管炎',
    drg: 'J20.9',
    ratio: 0.78,
    status: 'normal',
    los: 4,
    est_cost: 1620,
    baseline_payment: 2080,
    actual_cost: 1620,
    payment_gap: -460,
    monitor_level: 'info',
    control_tip: '低费用组，建议回看计费完整性和治疗充分性。',
  },
  {
    id: 107,
    case_no: '#2025120007',
    dept: '呼吸内科专业',
    diagnosis: '未特指肺炎',
    drg: 'J18.0',
    ratio: 0.84,
    status: 'normal',
    los: 5,
    est_cost: 2120,
    baseline_payment: 2520,
    actual_cost: 2120,
    payment_gap: -400,
    monitor_level: 'info',
    control_tip: '当前处于低耗区间，建议核查路径完整度。',
  },
  {
    id: 108,
    case_no: '#2025120008',
    dept: '肿瘤科',
    diagnosis: '姑息治疗',
    drg: 'Z51.5',
    ratio: 0.96,
    status: 'normal',
    los: 6,
    est_cost: 4920,
    baseline_payment: 5120,
    actual_cost: 4920,
    payment_gap: -200,
    monitor_level: 'info',
    control_tip: '费用接近基准，维持常规监测。',
  },
]

const cmiChartRef = ref<HTMLElement | null>(null)
const costChartRef = ref<HTMLElement | null>(null)
const filterType = ref<'all' | 'warning' | 'normal'>('all')
const loading = ref(false)
const stats = ref<MonitoringStats>({ ...REALISTIC_STATS, control_tips: [...FALLBACK_TIPS] })
const drgAlerts = ref<DrgAlert[]>([...REALISTIC_ALERTS])
const detailOpen = ref(false)
const selectedAlert = ref<DrgAlert | null>(null)
const drgMockEnabled = ref(isDrgMockModeEnabled())
const drgDatasetStore = useDrgDatasetStore()
const hasUploadedData = computed(() => drgDatasetStore.hasUploadedData)

let cmiChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null
let unsubscribeDrgMockMode: (() => void) | null = null

const moneyFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const controlTips = computed(() =>
  stats.value.control_tips?.length ? stats.value.control_tips : FALLBACK_TIPS,
)
const mockScopeNote = computed(() => stats.value.mock_scope_note || REALISTIC_STATS.mock_scope_note)
const dataModeLabel = computed(() => {
  if (hasUploadedData.value) return '模板上传数据'
  return drgMockEnabled.value ? '降级数据' : '真实优先'
})
const dataModeClass = computed(() => [
  'mode-chip',
  hasUploadedData.value || !drgMockEnabled.value ? 'mode-chip--real' : 'mode-chip--mock',
])

const filteredAlerts = computed(() => {
  if (filterType.value === 'all') return drgAlerts.value
  return drgAlerts.value.filter((item) => item.status === filterType.value)
})

function buildExportPayload() {
  const now = new Date().toLocaleString('zh-CN')
  return {
    title: 'DRG/DIP 事中监控报告',
    filenameBase: `drg_mid_${Date.now()}`,
    meta: [
      ['导出时间', now],
      ['数据模式', dataModeLabel.value],
      [
        '筛选状态',
        filterType.value === 'all' ? '全部' : filterType.value === 'warning' ? '预警' : '正常',
      ],
      ['统一口径', mockScopeNote.value],
    ] as Array<[string, string]>,
    kpis: [
      ['监测病例', String(stats.value.total_alerts)],
      ['重点预警', String(stats.value.severe_alerts)],
      ['待处理建议', String(stats.value.pending_suggestions)],
      ['模拟分组', String(stats.value.simulated_groups)],
      ['控制阈值', stats.value.control_threshold.toFixed(2)],
    ] as Array<[string, string]>,
    sections: [
      {
        title: '模拟分组监测明细',
        columns: [
          '病例号',
          '科室',
          '诊断',
          'DRG',
          '支付标准(元)',
          '实际费用(元)',
          '差额(元)',
          '费用比',
          '控制提示',
          '监测等级',
          '状态',
        ],
        rows: filteredAlerts.value.map((item) => [
          item.case_no,
          item.dept,
          item.diagnosis,
          item.drg,
          item.baseline_payment ?? 0,
          item.actual_cost ?? 0,
          item.payment_gap ?? 0,
          formatRatio(item.ratio),
          item.control_tip,
          levelLabel(item.monitor_level),
          statusLabel(item.status),
        ]),
      },
    ],
  }
}

function handleExport(info: MenuInfo) {
  const key = String(info.key)
  if (key !== 'excel' && key !== 'pdf' && key !== 'word') return
  exportDrgMockReport(key as DrgExportFormat, buildExportPayload())
  message.success(`${key.toUpperCase()} 报告导出成功`)
}

function levelLabel(level: MonitoringControlTip['level'] | DrgAlert['monitor_level']) {
  switch (level) {
    case 'critical':
      return '重点关注'
    case 'warning':
      return '需跟踪'
    default:
      return '常规'
  }
}

function levelClass(level: MonitoringControlTip['level'] | DrgAlert['monitor_level']) {
  switch (level) {
    case 'critical':
      return 'bg-red-50 text-red-700 border border-red-200'
    case 'warning':
      return 'bg-amber-50 text-amber-700 border border-amber-200'
    default:
      return 'bg-sky-50 text-sky-700 border border-sky-200'
  }
}

function tipClass(level: MonitoringControlTip['level']) {
  switch (level) {
    case 'critical':
      return 'bg-red-50 border-red-100'
    case 'warning':
      return 'bg-amber-50 border-amber-100'
    default:
      return 'bg-sky-50 border-sky-100'
  }
}

function statusLabel(status: DrgAlert['status']) {
  return status === 'warning' ? '预警' : '正常'
}

function statusClass(status: DrgAlert['status']) {
  return status === 'warning'
    ? 'bg-red-50 text-red-700 border border-red-200'
    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
}

function ratioClass(ratio: number) {
  return ratio > 1
    ? 'bg-red-50 text-red-700 border border-red-200'
    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
}

function formatMoney(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `¥${moneyFormatter.format(value)}`
}

function formatRatio(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return value.toFixed(2)
}

function normalizeTip(item: Partial<MonitoringControlTip>): MonitoringControlTip {
  return {
    title: item.title || '费用控制提示',
    indicator: item.indicator || 'mid/payment/post',
    current_value: item.current_value || '-',
    target_value: item.target_value || '-',
    suggestion: item.suggestion || '暂无建议',
    level: item.level || 'info',
  }
}

function normalizeStats(data: Partial<MonitoringStats> | null | undefined): MonitoringStats {
  return {
    total_alerts:
      typeof data?.total_alerts === 'number' ? data.total_alerts : REALISTIC_STATS.total_alerts,
    severe_alerts:
      typeof data?.severe_alerts === 'number' ? data.severe_alerts : REALISTIC_STATS.severe_alerts,
    pending_suggestions:
      typeof data?.pending_suggestions === 'number'
        ? data.pending_suggestions
        : REALISTIC_STATS.pending_suggestions,
    today_new: typeof data?.today_new === 'number' ? data.today_new : REALISTIC_STATS.today_new,
    simulated_groups:
      typeof data?.simulated_groups === 'number'
        ? data.simulated_groups
        : REALISTIC_STATS.simulated_groups,
    control_threshold:
      typeof data?.control_threshold === 'number'
        ? data.control_threshold
        : REALISTIC_STATS.control_threshold,
    mock_scope_note: data?.mock_scope_note || REALISTIC_STATS.mock_scope_note,
    control_tips:
      Array.isArray(data?.control_tips) && data.control_tips.length > 0
        ? data.control_tips.map((item) => normalizeTip(item))
        : [...FALLBACK_TIPS],
  }
}

function normalizeAlert(item: Partial<DrgAlert>, index: number): DrgAlert {
  const ratio = typeof item.ratio === 'number' ? item.ratio : 1
  const actualCost =
    typeof item.actual_cost === 'number'
      ? item.actual_cost
      : typeof item.est_cost === 'number' && item.est_cost > 0
        ? item.est_cost
        : Math.round((42000 + index * 2500) * ratio)
  const baselinePayment =
    typeof item.baseline_payment === 'number'
      ? item.baseline_payment
      : Math.round(actualCost / Math.max(ratio, 0.01))
  const paymentGap =
    typeof item.payment_gap === 'number'
      ? item.payment_gap
      : Math.round(actualCost - baselinePayment)
  const monitorLevel =
    item.monitor_level || (ratio >= 1.2 ? 'critical' : ratio >= 1.05 ? 'warning' : 'info')

  return {
    id: typeof item.id === 'number' ? item.id : index + 1,
    case_no: item.case_no || `#MOCK-${index + 1}`,
    dept: item.dept || '未知科室',
    diagnosis: item.diagnosis || '未知诊断',
    drg: item.drg || 'SIM',
    ratio,
    status: item.status || (ratio > 1 ? 'warning' : 'normal'),
    los: typeof item.los === 'number' ? item.los : 0,
    est_cost: typeof item.est_cost === 'number' ? item.est_cost : actualCost,
    baseline_payment: baselinePayment,
    actual_cost: actualCost,
    payment_gap: paymentGap,
    monitor_level: monitorLevel,
    control_tip:
      item.control_tip ||
      (monitorLevel === 'critical'
        ? '优先复核高值耗材、术后用药和路径偏差。'
        : monitorLevel === 'warning'
          ? '建议跟踪费用构成，防止滑入预警区间。'
          : '费用处于可控区间，可继续观察。'),
  }
}

function normalizeAlerts(data: DrgAlert[] | null | undefined): DrgAlert[] {
  const source = Array.isArray(data) && data.length > 0 ? data : REALISTIC_ALERTS
  return source.map((item, index) => normalizeAlert(item, index))
}

function renderCmiChart(data: CmiTrend) {
  if (!cmiChartRef.value) return
  cmiChart?.dispose()
  cmiChart = echarts.init(cmiChartRef.value)
  const yMax = Math.max(1.2, data.benchmark, ...data.values) + 0.1
  const yMin = Math.max(0, Math.min(0.8, ...data.values) - 0.1)
  cmiChart.setOption({
    grid: { left: 45, right: 20, top: 25, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data.labels,
      axisLine: { lineStyle: { color: '#dbe4f0' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      min: yMin,
      max: yMax,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#eef2f7' } },
      axisLabel: { color: '#64748b' },
    },
    series: [
      {
        data: data.values,
        type: 'line',
        smooth: true,
        symbolSize: 8,
        lineStyle: { color: '#0066cc', width: 3 },
        itemStyle: { color: '#0066cc' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.28)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.04)' },
          ]),
        },
        markLine: {
          silent: true,
          lineStyle: { color: '#f59e0b', type: 'dashed' },
          data: [{ yAxis: data.benchmark }],
          label: { formatter: '基准线' },
        },
      },
    ],
  })
}

function renderCostChart(data: DeptCostIndex) {
  if (!costChartRef.value) return
  costChart?.dispose()
  costChart = echarts.init(costChartRef.value)
  const yMax = Math.max(1.5, data.benchmark, ...data.values) + 0.1
  costChart.setOption({
    grid: { left: 55, right: 20, top: 25, bottom: 35 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data.departments,
      axisLine: { lineStyle: { color: '#dbe4f0' } },
      axisLabel: { color: '#64748b', rotate: 15 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: yMax,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#eef2f7' } },
      axisLabel: { color: '#64748b' },
    },
    series: [
      {
        type: 'bar',
        data: data.values.map((value) => ({
          value,
          itemStyle: { color: value > data.benchmark ? '#ef4444' : '#22c55e' },
        })),
        barWidth: '40%',
      },
      {
        type: 'line',
        data: data.departments.map(() => data.benchmark),
        lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
        symbol: 'none',
      },
    ],
  })
}

function renderFallbackCharts() {
  renderCmiChart(FALLBACK_CMI)
  renderCostChart(FALLBACK_COST)
}

function applyUploadedDataset() {
  const dataset = buildInProcessMonitoringDataset(drgDatasetStore.records)
  stats.value = dataset.stats
  drgAlerts.value = dataset.alerts
  renderCmiChart(dataset.cmiTrend)
  renderCostChart(dataset.costIndex)
}

async function loadData() {
  loading.value = true
  if (hasUploadedData.value) {
    applyUploadedDataset()
    loading.value = false
    return
  }

  const mockMode = isDrgMockModeEnabled()
  drgMockEnabled.value = mockMode
  if (mockMode) {
    stats.value = { ...REALISTIC_STATS, control_tips: [...FALLBACK_TIPS] }
    drgAlerts.value = [...REALISTIC_ALERTS]
    renderFallbackCharts()
    loading.value = false
    return
  }

  try {
    const [statsData, alertsData, cmiData, costData] = await Promise.all([
      panelApi.getMonitoringStats(),
      panelApi.getDrgAlerts(),
      panelApi.getCmiTrend(7),
      panelApi.getDeptCostIndex(),
    ])

    stats.value = normalizeStats(statsData)
    drgAlerts.value = normalizeAlerts(alertsData)
    renderCmiChart(cmiData?.labels?.length ? cmiData : FALLBACK_CMI)
    renderCostChart(costData?.departments?.length ? costData : FALLBACK_COST)
  } catch (error) {
    console.error('加载事中监控数据失败:', error)
    stats.value = { ...REALISTIC_STATS, control_tips: [...FALLBACK_TIPS] }
    drgAlerts.value = [...REALISTIC_ALERTS]
    renderFallbackCharts()
  } finally {
    loading.value = false
  }
}

function handleDatasetChanged() {
  filterType.value = 'all'
  loadData()
}

function openDetail(item: DrgAlert) {
  selectedAlert.value = item
  detailOpen.value = true
}

function handleResize() {
  cmiChart?.resize()
  costChart?.resize()
}

onMounted(() => {
  drgMockEnabled.value = isDrgMockModeEnabled()
  unsubscribeDrgMockMode = onDrgMockModeChange((enabled) => {
    drgMockEnabled.value = enabled
    loadData()
  })
  loadData()
  window.addEventListener('resize', handleResize)
})

watch(
  () => drgDatasetStore.meta?.uploadedAt,
  () => {
    loadData()
  },
)

onUnmounted(() => {
  unsubscribeDrgMockMode?.()
  window.removeEventListener('resize', handleResize)
  cmiChart?.dispose()
  costChart?.dispose()
})
</script>

<style scoped>
@import './drg-dip-workbench.css';

.in-process-page {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.page-header,
.panel,
.kpi-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 72px;
  border-radius: 14px;
  padding: 14px 18px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 260px;
}

.back-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  color: rgba(29, 29, 31, 0.6);
  background: rgba(255, 255, 255, 0.72);
  transition: all 0.16s ease;
}

.back-button:hover {
  border-color: #bfdbfe;
  color: #0066cc;
  background: rgba(0, 102, 204, 0.06);
}

.breadcrumb {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.page-header h2 {
  margin: 4px 0 0;
  color: #1d1d1f;
  font-size: 24px;
  font-weight: 700;
  line-height: 32px;
}

.page-header p,
.panel-head p,
.kpi-card p {
  margin: 0;
  color: rgba(29, 29, 31, 0.6);
}

.page-header p {
  margin-top: 2px;
  font-size: 13px;
  line-height: 20px;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.filter-chip,
.mode-chip {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0 12px;
  color: #334155;
  background: #f8fafc;
  font-size: 13px;
  font-weight: 600;
}

.threshold-chip {
  color: #0057b8;
  background: #eff6ff;
  border-color: #bfdbfe;
}

.mode-chip--mock {
  color: #047857;
  background: #ecfdf5;
  border-color: #a7f3d0;
}

.mode-chip--real {
  color: #0369a1;
  background: #f0f9ff;
  border-color: #bae6fd;
}

.primary-button,
.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  border-radius: 8px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.16s ease;
}

.primary-button {
  border: 1px solid #0066cc;
  color: #ffffff;
  background: #0066cc;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

.primary-button:hover {
  background: #0057b8;
}

.secondary-button {
  border: 1px solid #dbe4f0;
  color: #334155;
  background: #ffffff;
}

.secondary-button:hover {
  color: #0066cc;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.dataset-upload-surface {
  margin: 0;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 96px;
  border-radius: 12px;
  padding: 16px 18px;
}

.kpi-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  font-size: 20px;
}

.kpi-icon--blue {
  color: #0066cc;
  background: #eaf2ff;
}

.kpi-icon--red {
  color: #ef4444;
  background: #fee2e2;
}

.kpi-icon--amber {
  color: #f59e0b;
  background: #fef3c7;
}

.kpi-icon--green {
  color: #10b981;
  background: #d1fae5;
}

.kpi-label {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
  line-height: 18px;
}

.kpi-value {
  margin-top: 4px;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 34px;
}

.kpi-card p {
  margin-top: 2px;
  font-size: 12px;
  line-height: 18px;
}

.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.65fr);
  gap: 14px;
}

.bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(380px, 1.05fr);
  gap: 14px;
}

.panel {
  min-width: 0;
  border-radius: 12px;
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #edf2f7;
  padding: 14px 16px;
}

.panel-head.compact {
  align-items: center;
}

.panel-head h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 700;
  line-height: 24px;
}

.panel-head p {
  margin-top: 2px;
  font-size: 13px;
  line-height: 20px;
}

.panel-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-select {
  width: 116px;
}

.panel-meta {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.chart-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  padding: 12px 16px 0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.chart-toolbar span {
  position: relative;
  padding-left: 12px;
}

.chart-toolbar span::before {
  position: absolute;
  top: 50%;
  left: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0066cc;
  content: '';
  transform: translateY(-50%);
}

.chart-toolbar span:nth-child(2)::before {
  background: #10b981;
}

.chart-toolbar span:nth-child(3)::before {
  background: #ef4444;
}

.trend-chart {
  height: 208px;
  margin: 0 12px;
}

.cost-chart {
  height: 218px;
  padding: 4px 8px 10px;
}

.case-list {
  overflow-x: auto;
  border-top: 1px solid #edf2f7;
}

.case-list table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
  font-size: 13px;
}

.case-list th {
  padding: 10px 14px;
  color: #64748b;
  background: #f8fafc;
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
}

.case-list td {
  padding: 11px 14px;
  border-top: 1px solid #edf2f7;
  color: #334155;
  vertical-align: middle;
}

.case-list tbody tr:hover {
  background: #f8fbff;
}

.patient-cell,
.ratio-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.patient-cell strong {
  color: #1d1d1f;
  font-weight: 700;
}

.patient-cell span,
.ratio-cell span {
  color: #64748b;
  font-size: 12px;
}

.ratio-cell strong {
  font-size: 15px;
  font-weight: 700;
}

.reason-text {
  display: -webkit-box;
  max-width: 280px;
  overflow: hidden;
  color: #475569;
  line-height: 20px;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
}

.link-button,
.text-link {
  border: 0;
  color: #0066cc;
  background: transparent;
  font-size: 13px;
  font-weight: 700;
}

.link-button:hover,
.text-link:hover {
  color: #0057b8;
}

.priority-panel {
  display: flex;
  flex-direction: column;
}

.priority-list {
  padding: 10px 16px 8px;
}

.priority-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 52px 64px;
  align-items: center;
  width: 100%;
  gap: 10px;
  border: 0;
  border-bottom: 1px solid #edf2f7;
  padding: 11px 0;
  background: transparent;
  text-align: left;
}

.priority-row:hover {
  background: #f8fbff;
}

.rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  color: #64748b;
  background: #f1f5f9;
  font-size: 13px;
  font-weight: 700;
}

.rank--hot {
  color: #ef4444;
  background: #fee2e2;
}

.priority-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.priority-main strong {
  overflow: hidden;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.priority-main span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.priority-value {
  color: #ef4444;
  font-size: 15px;
  font-weight: 700;
  text-align: right;
}

.priority-action {
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
  text-align: right;
}

.suggestion-block {
  margin: 0 16px 16px;
  border-radius: 10px;
  background: #f8fbff;
}

.suggestion-row {
  display: flex;
  gap: 10px;
  padding: 11px 12px;
  border-top: 1px solid #edf2f7;
}

.suggestion-row:first-child {
  border-top: 0;
}

.suggestion-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  margin-top: 7px;
  border-radius: 50%;
  background: #0066cc;
}

.suggestion-dot--critical {
  background: #ef4444;
}

.suggestion-dot--warning {
  background: #f59e0b;
}

.suggestion-row strong {
  display: block;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
}

.suggestion-row p {
  margin: 1px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
}

.change-list {
  padding: 6px 16px 14px;
}

.change-row {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) 70px 42px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 45px;
  border: 0;
  border-bottom: 1px solid #edf2f7;
  padding: 8px 0;
  background: transparent;
  text-align: left;
}

.change-row:hover {
  background: #f8fbff;
}

.change-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.change-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.change-main strong,
.change-main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.change-main strong {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
}

.change-main span {
  color: #64748b;
  font-size: 12px;
}

.change-tag {
  display: inline-flex;
  justify-content: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
}

.change-tag--up {
  color: #ef4444;
  background: #fee2e2;
}

.change-tag--down {
  color: #0066cc;
  background: #dbeafe;
}

.change-time {
  color: #64748b;
  font-size: 12px;
  text-align: right;
}

.in-process-page {
  --workstation-canvas: #f5f5f7;
  --workstation-surface: rgba(255, 255, 255, 0.86);
  --workstation-surface-strong: rgba(255, 255, 255, 0.94);
  --workstation-border: rgba(0, 0, 0, 0.08);
  --workstation-text: #1d1d1f;
  --workstation-muted: rgba(29, 29, 31, 0.6);
  --workstation-subtle: rgba(29, 29, 31, 0.38);
  --workstation-primary: #0066cc;
  --workstation-primary-soft: rgba(0, 102, 204, 0.1);

  background: var(--workstation-canvas) !important;
  color: var(--workstation-text) !important;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.page-header,
.panel,
.kpi-card {
  border-color: var(--workstation-border);
  background: var(--workstation-surface);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
}

.page-header {
  border-radius: 20px;
}

.panel,
.kpi-card {
  border-radius: 16px;
}

.page-header:hover,
.panel:hover,
.kpi-card:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
}

.breadcrumb,
.page-header p,
.panel-head p,
.kpi-card p,
.panel-meta,
.patient-cell span,
.ratio-cell span,
.suggestion-row p,
.change-main span,
.change-time {
  color: var(--workstation-muted);
}

.page-header h2,
.panel-head h3,
.kpi-value,
.patient-cell strong,
.priority-main strong,
.suggestion-row strong,
.change-main strong {
  color: var(--workstation-text);
}

.back-button,
.secondary-button,
.filter-chip,
.mode-chip {
  border-color: var(--workstation-border);
  background: var(--workstation-surface-strong);
  color: var(--workstation-muted);
}

.back-button:hover,
.secondary-button:hover {
  border-color: rgba(0, 102, 204, 0.22);
  background: var(--workstation-primary-soft);
  color: var(--workstation-primary);
}

.threshold-chip,
.kpi-icon--blue,
.change-tag--down {
  border-color: rgba(0, 102, 204, 0.16);
  background: var(--workstation-primary-soft);
  color: var(--workstation-primary);
}

.primary-button {
  border-color: var(--workstation-primary);
  background: var(--workstation-primary);
  box-shadow: 0 4px 10px rgba(0, 102, 204, 0.16);
}

.primary-button:hover {
  background: #0057b8;
}

.chart-toolbar span::before,
.suggestion-dot {
  background: var(--workstation-primary);
}

.case-list,
.case-list th,
.case-list td,
.priority-row,
.change-row,
.panel-head {
  border-color: rgba(0, 0, 0, 0.08);
}

.case-list th {
  background: rgba(255, 255, 255, 0.72);
  color: var(--workstation-subtle);
}

.case-list tbody tr:hover,
.priority-row:hover,
.change-row:hover {
  background: rgba(0, 0, 0, 0.025);
}

.link-button,
.text-link,
.priority-action {
  color: var(--workstation-primary);
}

@media (max-width: 1280px) {
  .main-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .kpi-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .page-header,
  .panel-head {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .kpi-strip {
    grid-template-columns: 1fr;
  }

  .trend-chart,
  .cost-chart {
    height: 240px;
  }
}
</style>
