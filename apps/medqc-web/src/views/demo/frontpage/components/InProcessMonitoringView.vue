<template>
  <div class="h-full w-full overflow-y-auto bg-slate-50 px-6 py-5 text-slate-700">
    <div class="mx-auto flex max-w-[1600px] flex-col gap-5">
      <header class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/90 px-5 py-4 shadow-sm backdrop-blur">
        <div class="flex items-center gap-3">
          <button type="button" class="rounded-full p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800" @click="$router.back()">
            <ArrowLeftOutlined class="text-base" />
          </button>
          <div>
            <h2 class="text-xl font-semibold tracking-tight text-slate-900">事中监控</h2>
            <p class="mt-1 text-sm text-slate-500">费用控制提示 + 模拟分组监测，统一 mid/payment/post mock 口径</p>
          </div>
        </div>

        <div class="flex items-center gap-3 text-sm text-slate-500">
          <span class="rounded-full bg-slate-100 px-3 py-1">统一口径：{{ mockScopeNote }}</span>
          <span
            :class="drgMockEnabled ? 'rounded-full bg-emerald-50 px-3 py-1 text-emerald-700' : 'rounded-full bg-sky-50 px-3 py-1 text-sky-700'"
          >
            {{ drgMockEnabled ? 'Mock 演示模式' : '真实优先模式' }}
          </span>
          <span class="rounded-full bg-blue-50 px-3 py-1 text-blue-700">控制阈值 {{ stats.control_threshold.toFixed(2) }}</span>
          <span v-if="loading" class="flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-amber-700">
            <LoadingOutlined class="animate-spin" />
            加载中
          </span>
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
            <button class="rounded-lg bg-blue-500 px-3 py-1.5 text-white transition-colors hover:bg-blue-600">
              <DownloadOutlined /> 导出报告
            </button>
          </a-dropdown>
        </div>
      </header>

      <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">监测病例</div>
          <div class="mt-3 flex items-end gap-2">
            <WarningOutlined class="text-xl text-amber-500" />
            <span class="text-3xl font-semibold text-slate-900">{{ stats.total_alerts }}</span>
            <span class="pb-1 text-sm text-slate-400">例</span>
          </div>
          <p class="mt-2 text-xs text-slate-500">当前命中的模拟监测病例总数</p>
        </article>

        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">重点预警</div>
          <div class="mt-3 flex items-end gap-2">
            <CloseCircleOutlined class="text-xl text-red-500" />
            <span class="text-3xl font-semibold text-slate-900">{{ stats.severe_alerts }}</span>
            <span class="pb-1 text-sm text-slate-400">例</span>
          </div>
          <p class="mt-2 text-xs text-slate-500">费用比超过重点阈值的病例数</p>
        </article>

        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">待处理建议</div>
          <div class="mt-3 flex items-end gap-2">
            <InfoCircleOutlined class="text-xl text-blue-500" />
            <span class="text-3xl font-semibold text-slate-900">{{ stats.pending_suggestions }}</span>
            <span class="pb-1 text-sm text-slate-400">条</span>
          </div>
          <p class="mt-2 text-xs text-slate-500">可直接落地的费用控制建议</p>
        </article>

        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">模拟分组</div>
          <div class="mt-3 flex items-end gap-2">
            <RiseOutlined class="text-xl text-emerald-500" />
            <span class="text-3xl font-semibold text-slate-900">{{ stats.simulated_groups }}</span>
            <span class="pb-1 text-sm text-slate-400">组</span>
          </div>
          <p class="mt-2 text-xs text-slate-500">今日新增 {{ stats.today_new }} 条，支持离线演示</p>
        </article>
      </section>

      <section class="grid grid-cols-1 gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 class="text-base font-semibold text-slate-900">费用控制提示</h3>
              <p class="mt-1 text-sm text-slate-500">把“当前值、目标值、建议动作”拆开展示，便于 mid/payment/post 共用同一套话术</p>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-3">
            <article
              v-for="tip in controlTips"
              :key="tip.title"
              class="rounded-2xl border px-4 py-4 shadow-sm"
              :class="tipClass(tip.level)"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-xs font-medium uppercase tracking-[0.18em] opacity-70">{{ levelLabel(tip.level) }}</div>
                  <h4 class="mt-2 text-sm font-semibold text-slate-900">{{ tip.title }}</h4>
                </div>
                <span class="rounded-full bg-white/70 px-2.5 py-1 text-[11px] font-medium text-slate-600 shadow-sm">
                  {{ tip.indicator }}
                </span>
              </div>

              <dl class="mt-4 space-y-2 text-sm">
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-500">当前值</dt>
                  <dd class="font-medium text-slate-900">{{ tip.current_value }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-500">控制目标</dt>
                  <dd class="font-medium text-slate-900">{{ tip.target_value }}</dd>
                </div>
              </dl>

              <p class="mt-4 text-sm leading-6 text-slate-700">{{ tip.suggestion }}</p>
            </article>
          </div>
        </div>

        <div class="grid gap-5">
          <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="mb-4 flex items-center justify-between">
              <div>
                <h3 class="text-base font-semibold text-slate-900">CMI 近 7 日趋势</h3>
                <p class="mt-1 text-sm text-slate-500">用于展示事中波动和统一演示口径</p>
              </div>
            </div>
            <div ref="cmiChartRef" class="h-64"></div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="mb-4 flex items-center justify-between">
              <div>
                <h3 class="text-base font-semibold text-slate-900">科室费用消耗指数</h3>
                <p class="mt-1 text-sm text-slate-500">高于基准的科室会被标记为红色</p>
              </div>
            </div>
            <div ref="costChartRef" class="h-64"></div>
          </div>
        </div>
      </section>

      <section class="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <h3 class="text-base font-semibold text-slate-900">模拟分组监测</h3>
            <p class="mt-1 text-sm text-slate-500">字段明确展示：支付标准、实际费用、差额、费用比、控制提示、监测等级</p>
          </div>
          <a-select v-model:value="filterType" class="w-36" size="small">
            <a-select-option value="all">全部</a-select-option>
            <a-select-option value="warning">预警</a-select-option>
            <a-select-option value="normal">正常</a-select-option>
          </a-select>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-slate-500">
              <tr>
                <th class="px-4 py-3 text-left font-medium">病例号</th>
                <th class="px-4 py-3 text-left font-medium">科室</th>
                <th class="px-4 py-3 text-left font-medium">诊断</th>
                <th class="px-4 py-3 text-left font-medium">DRG</th>
                <th class="px-4 py-3 text-left font-medium">支付标准</th>
                <th class="px-4 py-3 text-left font-medium">实际费用</th>
                <th class="px-4 py-3 text-left font-medium">差额</th>
                <th class="px-4 py-3 text-left font-medium">费用比</th>
                <th class="px-4 py-3 text-left font-medium">控制提示</th>
                <th class="px-4 py-3 text-left font-medium">监测等级</th>
                <th class="px-4 py-3 text-left font-medium">状态</th>
                <th class="px-4 py-3 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredAlerts" :key="item.id" class="border-t border-slate-100 hover:bg-slate-50/80">
                <td class="px-4 py-3 font-medium text-slate-900">{{ item.case_no }}</td>
                <td class="px-4 py-3 text-slate-600">{{ item.dept }}</td>
                <td class="px-4 py-3 text-slate-600">{{ item.diagnosis }}</td>
                <td class="px-4 py-3">
                  <div class="font-medium text-slate-900">{{ item.drg }}</div>
                  <div class="text-xs text-slate-400">模拟分组</div>
                </td>
                <td class="px-4 py-3 text-slate-600">{{ formatMoney(item.baseline_payment) }}</td>
                <td class="px-4 py-3" :class="item.actual_cost >= item.baseline_payment ? 'text-red-600' : 'text-emerald-600'">
                  {{ formatMoney(item.actual_cost) }}
                </td>
                <td class="px-4 py-3" :class="item.payment_gap >= 0 ? 'text-red-600' : 'text-emerald-600'">
                  {{ formatMoney(item.payment_gap) }}
                </td>
                <td class="px-4 py-3">
                  <span :class="ratioClass(item.ratio)" class="rounded-full px-2.5 py-1 text-xs font-medium">
                    {{ formatRatio(item.ratio) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-slate-600">
                  <span class="line-clamp-2 max-w-[280px] leading-5">{{ item.control_tip }}</span>
                </td>
                <td class="px-4 py-3">
                  <span :class="levelClass(item.monitor_level)" class="rounded-full px-2.5 py-1 text-xs font-medium">
                    {{ levelLabel(item.monitor_level) }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span :class="statusClass(item.status)" class="rounded-full px-2.5 py-1 text-xs font-medium">
                    {{ statusLabel(item.status) }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <button type="button" class="text-xs font-medium text-blue-600 transition hover:text-blue-700" @click="openDetail(item)">
                    查看详情
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <a-modal v-model:open="detailOpen" title="模拟分组详情" :footer="null" width="760px">
      <template v-if="selectedAlert">
        <a-alert
          :type="selectedAlert.monitor_level === 'critical' ? 'error' : selectedAlert.monitor_level === 'warning' ? 'warning' : 'info'"
          show-icon
          :message="selectedAlert.control_tip"
          class="mb-4"
        />

        <a-descriptions bordered size="small" :column="2">
          <a-descriptions-item label="病例号">{{ selectedAlert.case_no }}</a-descriptions-item>
          <a-descriptions-item label="科室">{{ selectedAlert.dept }}</a-descriptions-item>
          <a-descriptions-item label="诊断">{{ selectedAlert.diagnosis }}</a-descriptions-item>
          <a-descriptions-item label="DRG">{{ selectedAlert.drg }}</a-descriptions-item>
          <a-descriptions-item label="支付标准">{{ formatMoney(selectedAlert.baseline_payment) }}</a-descriptions-item>
          <a-descriptions-item label="实际费用">{{ formatMoney(selectedAlert.actual_cost) }}</a-descriptions-item>
          <a-descriptions-item label="差额">{{ formatMoney(selectedAlert.payment_gap) }}</a-descriptions-item>
          <a-descriptions-item label="费用比">{{ formatRatio(selectedAlert.ratio) }}</a-descriptions-item>
          <a-descriptions-item label="住院天数">{{ selectedAlert.los }} 天</a-descriptions-item>
          <a-descriptions-item label="监测等级">{{ levelLabel(selectedAlert.monitor_level) }}</a-descriptions-item>
        </a-descriptions>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
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
  FileWordOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { panelApi } from '@/api/panel'
import type { CmiTrend, DeptCostIndex, DrgAlert, MonitoringControlTip, MonitoringStats } from '@/api/panel'
import { isDrgMockModeEnabled, onDrgMockModeChange } from '@/utils/drgMockMode'
import { exportDrgMockReport, type DrgExportFormat } from '@/utils/drgMockExport'

const FALLBACK_CMI: CmiTrend = {
  labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
  values: [1.0, 1.05, 1.03, 1.08, 1.12, 1.09, 1.15],
  benchmark: 1.0
}

const FALLBACK_COST: DeptCostIndex = {
  departments: ['心内科', '呼吸科', '骨科', '普外科', '神经内科', '神经外科', '消化内科', '泌尿外科'],
  values: [0.92, 0.89, 1.15, 0.85, 1.05, 1.28, 0.95, 0.88],
  benchmark: 1.0
}

const FALLBACK_TIPS: MonitoringControlTip[] = [
  {
    title: '高费用病例优先复核',
    indicator: '费用比 ≥ 1.20',
    current_value: '3 例',
    target_value: '0 例',
    suggestion: '优先核查高值耗材、术后用药和超标准检查，减少短期内的费用放大。',
    level: 'critical'
  },
  {
    title: '边界病例持续跟踪',
    indicator: '1.00 ~ 1.20',
    current_value: '2 例',
    target_value: '稳定在阈值内',
    suggestion: '对照路径和支付标准提前修正费用偏差，防止滑入预警区间。',
    level: 'warning'
  },
  {
    title: '统一 mock 口径',
    indicator: 'mid/payment/post',
    current_value: '同一契约',
    target_value: '字段不漂移',
    suggestion: '各页面共用同一套字段，兜底 mock 可直接演示，不依赖真实后端。',
    level: 'info'
  }
]

const FALLBACK_STATS: MonitoringStats = {
  total_alerts: 8,
  severe_alerts: 4,
  pending_suggestions: 8,
  today_new: 15,
  simulated_groups: 8,
  control_threshold: 1.0,
  mock_scope_note: 'mid/payment/post 共用同一 mock 口径',
  control_tips: FALLBACK_TIPS
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
    control_tip: '高值耗材和介入路径共同推高费用，建议优先复核。'
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
    control_tip: '术中耗材与术后监护费用偏高，建议提前归拢关键成本。'
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
    control_tip: '内固定耗材使用偏高，建议核对术式和耗材标准。'
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
    control_tip: '建议关注术后康复耗材和检查频次。'
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
    control_tip: '重点关注抗栓用药和病程记录的一致性。'
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
    control_tip: '建议核查内镜检查与止血耗材占比。'
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
    control_tip: '费用处于可控区间，可继续观察药占比变化。'
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
    control_tip: '当前费用低于标准，可作为稳定样本继续回放。'
  }
]

const REALISTIC_STATS: MonitoringStats = {
  ...FALLBACK_STATS,
  total_alerts: 112,
  severe_alerts: 28,
  pending_suggestions: 73,
  today_new: 36,
  simulated_groups: 2863,
  control_threshold: 1.2,
  mock_scope_note: '基于 2025 年病案与 DIP 关联数据重建（支付率约 58%）'
}

const REALISTIC_ALERTS: DrgAlert[] = [
  { id: 101, case_no: '#2025120001', dept: '心血管内科专业', diagnosis: '动脉粥样硬化性心脏病', drg: 'I25.1:88.5500', ratio: 1.34, status: 'warning', los: 8, est_cost: 10860, baseline_payment: 8100, actual_cost: 10860, payment_gap: 2760, monitor_level: 'critical', control_tip: '介入相关耗材和复查项目偏高，建议按术式路径复核。' },
  { id: 102, case_no: '#2025120002', dept: '普通外科专业', diagnosis: '化疗相关住院', drg: 'Z51.1:99.2503', ratio: 1.29, status: 'warning', los: 7, est_cost: 8260, baseline_payment: 6400, actual_cost: 8260, payment_gap: 1860, monitor_level: 'critical', control_tip: '药占比偏高且治疗项目偏密，建议分项核减。' },
  { id: 103, case_no: '#2025120003', dept: '骨科专业', diagnosis: '腰椎间盘突出', drg: 'M51:11', ratio: 1.22, status: 'warning', los: 9, est_cost: 7420, baseline_payment: 6080, actual_cost: 7420, payment_gap: 1340, monitor_level: 'critical', control_tip: '康复与检查组合超路径，建议核查治疗频次。' },
  { id: 104, case_no: '#2025120004', dept: '呼吸内科专业', diagnosis: '慢阻肺急性加重', drg: 'J44.0', ratio: 1.14, status: 'warning', los: 7, est_cost: 6690, baseline_payment: 5870, actual_cost: 6690, payment_gap: 820, monitor_level: 'warning', control_tip: '重点关注抗感染联合方案和重复检验。' },
  { id: 105, case_no: '#2025120005', dept: '神经内科专业', diagnosis: '短暂性脑缺血发作', drg: 'G45.0', ratio: 1.08, status: 'warning', los: 6, est_cost: 4360, baseline_payment: 4020, actual_cost: 4360, payment_gap: 340, monitor_level: 'warning', control_tip: '检查项目略超基准，建议控制影像复查。' },
  { id: 106, case_no: '#2025120006', dept: '儿科', diagnosis: '急性支气管炎', drg: 'J20.9', ratio: 0.78, status: 'normal', los: 4, est_cost: 1620, baseline_payment: 2080, actual_cost: 1620, payment_gap: -460, monitor_level: 'info', control_tip: '低费用组，建议回看计费完整性和治疗充分性。' },
  { id: 107, case_no: '#2025120007', dept: '呼吸内科专业', diagnosis: '未特指肺炎', drg: 'J18.0', ratio: 0.84, status: 'normal', los: 5, est_cost: 2120, baseline_payment: 2520, actual_cost: 2120, payment_gap: -400, monitor_level: 'info', control_tip: '当前处于低耗区间，建议核查路径完整度。' },
  { id: 108, case_no: '#2025120008', dept: '肿瘤科', diagnosis: '姑息治疗', drg: 'Z51.5', ratio: 0.96, status: 'normal', los: 6, est_cost: 4920, baseline_payment: 5120, actual_cost: 4920, payment_gap: -200, monitor_level: 'info', control_tip: '费用接近基准，维持常规监测。' }
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

let cmiChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null
let unsubscribeDrgMockMode: (() => void) | null = null

const moneyFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

const controlTips = computed(() => stats.value.control_tips?.length ? stats.value.control_tips : FALLBACK_TIPS)
const mockScopeNote = computed(() => stats.value.mock_scope_note || REALISTIC_STATS.mock_scope_note)

const filteredAlerts = computed(() => {
  if (filterType.value === 'all') return drgAlerts.value
  return drgAlerts.value.filter((item) => item.status === filterType.value)
})

function buildExportPayload() {
  const now = new Date().toLocaleString('zh-CN')
  return {
    title: 'DRG/DIP 事中监控演示报告',
    filenameBase: `drg_mid_${Date.now()}`,
    meta: [
      ['导出时间', now],
      ['数据模式', drgMockEnabled.value ? 'Mock 演示模式' : '真实优先模式（当前页导出为演示快照）'],
      ['筛选状态', filterType.value === 'all' ? '全部' : filterType.value === 'warning' ? '预警' : '正常'],
      ['统一口径', mockScopeNote.value]
    ] as Array<[string, string]>,
    kpis: [
      ['监测病例', String(stats.value.total_alerts)],
      ['重点预警', String(stats.value.severe_alerts)],
      ['待处理建议', String(stats.value.pending_suggestions)],
      ['模拟分组', String(stats.value.simulated_groups)],
      ['控制阈值', stats.value.control_threshold.toFixed(2)]
    ] as Array<[string, string]>,
    sections: [
      {
        title: '模拟分组监测明细',
        columns: ['病例号', '科室', '诊断', 'DRG', '支付标准(元)', '实际费用(元)', '差额(元)', '费用比', '控制提示', '监测等级', '状态'],
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
          statusLabel(item.status)
        ])
      }
    ]
  }
}

function handleExport({ key }: { key: string }) {
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
      return 'bg-gradient-to-br from-red-50 to-white border-red-100'
    case 'warning':
      return 'bg-gradient-to-br from-amber-50 to-white border-amber-100'
    default:
      return 'bg-gradient-to-br from-sky-50 to-white border-sky-100'
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
  return ratio > 1 ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
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
    level: item.level || 'info'
  }
}

function normalizeStats(data: Partial<MonitoringStats> | null | undefined): MonitoringStats {
  return {
    total_alerts: typeof data?.total_alerts === 'number' ? data.total_alerts : REALISTIC_STATS.total_alerts,
    severe_alerts: typeof data?.severe_alerts === 'number' ? data.severe_alerts : REALISTIC_STATS.severe_alerts,
    pending_suggestions: typeof data?.pending_suggestions === 'number' ? data.pending_suggestions : REALISTIC_STATS.pending_suggestions,
    today_new: typeof data?.today_new === 'number' ? data.today_new : REALISTIC_STATS.today_new,
    simulated_groups: typeof data?.simulated_groups === 'number' ? data.simulated_groups : REALISTIC_STATS.simulated_groups,
    control_threshold: typeof data?.control_threshold === 'number' ? data.control_threshold : REALISTIC_STATS.control_threshold,
    mock_scope_note: data?.mock_scope_note || REALISTIC_STATS.mock_scope_note,
    control_tips: Array.isArray(data?.control_tips) && data.control_tips.length > 0
      ? data.control_tips.map((item) => normalizeTip(item))
      : [...FALLBACK_TIPS]
  }
}

function normalizeAlert(item: Partial<DrgAlert>, index: number): DrgAlert {
  const ratio = typeof item.ratio === 'number' ? item.ratio : 1
  const actualCost = typeof item.actual_cost === 'number'
    ? item.actual_cost
    : typeof item.est_cost === 'number' && item.est_cost > 0
      ? item.est_cost
      : Math.round((42000 + index * 2500) * ratio)
  const baselinePayment = typeof item.baseline_payment === 'number'
    ? item.baseline_payment
    : Math.round(actualCost / Math.max(ratio, 0.01))
  const paymentGap = typeof item.payment_gap === 'number'
    ? item.payment_gap
    : Math.round(actualCost - baselinePayment)
  const monitorLevel = item.monitor_level || (ratio >= 1.2 ? 'critical' : ratio >= 1.05 ? 'warning' : 'info')

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
    control_tip: item.control_tip || (monitorLevel === 'critical'
      ? '优先复核高值耗材、术后用药和路径偏差。'
      : monitorLevel === 'warning'
        ? '建议跟踪费用构成，防止滑入预警区间。'
        : '费用处于可控区间，可继续观察。')
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
  cmiChart.setOption({
    grid: { left: 45, right: 20, top: 25, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data.labels,
      axisLine: { lineStyle: { color: '#dbe4f0' } },
      axisLabel: { color: '#64748b' }
    },
    yAxis: {
      type: 'value',
      min: 0.8,
      max: 1.2,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#eef2f7' } },
      axisLabel: { color: '#64748b' }
    },
    series: [
      {
        data: data.values,
        type: 'line',
        smooth: true,
        symbolSize: 8,
        lineStyle: { color: '#3b82f6', width: 3 },
        itemStyle: { color: '#3b82f6' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.28)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.04)' }
          ])
        },
        markLine: {
          silent: true,
          lineStyle: { color: '#f59e0b', type: 'dashed' },
          data: [{ yAxis: data.benchmark }],
          label: { formatter: '基准线' }
        }
      }
    ]
  })
}

function renderCostChart(data: DeptCostIndex) {
  if (!costChartRef.value) return
  costChart?.dispose()
  costChart = echarts.init(costChartRef.value)
  costChart.setOption({
    grid: { left: 55, right: 20, top: 25, bottom: 35 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data.departments,
      axisLine: { lineStyle: { color: '#dbe4f0' } },
      axisLabel: { color: '#64748b', rotate: 15 }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1.5,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#eef2f7' } },
      axisLabel: { color: '#64748b' }
    },
    series: [
      {
        type: 'bar',
        data: data.values.map((value) => ({
          value,
          itemStyle: { color: value > data.benchmark ? '#ef4444' : '#22c55e' }
        })),
        barWidth: '40%'
      },
      {
        type: 'line',
        data: data.departments.map(() => data.benchmark),
        lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
        symbol: 'none'
      }
    ]
  })
}

function renderFallbackCharts() {
  renderCmiChart(FALLBACK_CMI)
  renderCostChart(FALLBACK_COST)
}

async function loadData() {
  loading.value = true
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
      panelApi.getDeptCostIndex()
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

onUnmounted(() => {
  unsubscribeDrgMockMode?.()
  window.removeEventListener('resize', handleResize)
  cmiChart?.dispose()
  costChart?.dispose()
})
</script>
