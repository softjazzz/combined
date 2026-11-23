<template>
  <div class="qc-home-shell">
    <main class="mq-page">
      <!-- 页头：眉标一行写清范围（纯文字，不做胶囊）；右侧工具栏只留科室筛选与刷新 -->
      <header
        class="mq-page-head"
        data-testid="home-scope"
      >
        <div class="mq-page-head__copy">
          <span class="mq-page-eyebrow">{{ scopeLine }}</span>
          <h1 class="mq-page-title">
            质控首页概览
          </h1>
        </div>
        <div
          v-if="clinicalQc"
          class="qc-home-toolbar"
        >
          <template v-if="keyword.trim()">
            <span class="qc-home-toolbar__keyword">关键词：{{ keyword.trim() }}</span>
            <button
              type="button"
              class="qc-home-toolbar__clear"
              aria-label="清除关键词"
              @click="clearKeyword"
            >
              清除
            </button>
          </template>
          <label class="qc-home-pulldown qc-home-pulldown--bordered">
            <select
              v-model="departmentFilter"
              class="qc-home-department"
              aria-label="统计科室"
              :title="scopeDepartmentText"
            >
              <option value="all">全部科室</option>
              <option
                v-for="department in departmentOptions"
                :key="department"
                :value="department"
              >
                {{ department }}
              </option>
            </select>
            <svg
              class="qc-home-pulldown__caret"
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.6"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            ><path d="m6 9 6 6 6-6" /></svg>
          </label>
          <span class="qc-home-toolbar__time">生成于 {{ formatDateTime(clinicalQc.scope.generated_at) }}</span>
          <button
            type="button"
            class="qc-home-icon-button"
            aria-label="刷新首页数据"
            @click="void fetchHome()"
          >
            <MqIcon
              name="sync"
              :size="16"
              color="#515154"
            />
          </button>
        </div>
      </header>

      <section
        v-if="loadError"
        class="mq-card qc-home-notice"
        data-testid="home-load-error"
      >
        <MqIconTile
          name="tech_error"
          tone="danger"
          :size="36"
        />
        <div class="qc-home-notice__copy">
          <strong>暂时无法加载质控首页</strong>
          <span>请稍后刷新；不会以旧任务或缓存数据替代当前结果。</span>
        </div>
        <button
          type="button"
          class="qc-home-button"
          @click="void fetchHome()"
        >
          重新加载
        </button>
      </section>

      <section
        v-else-if="loading"
        class="mq-card qc-home-loading"
        data-testid="home-loading"
        aria-live="polite"
        aria-busy="true"
      >
        <a-spin />
        <div>
          <strong>正在加载全院质控概览</strong>
          <span>正在汇总当前范围内的病历与最新质控结果。</span>
        </div>
      </section>

      <template v-else-if="clinicalQc">
        <section
          class="qc-home-overview"
          aria-label="质控总览"
          data-testid="home-overview"
        >
          <!-- 主卡：待质控 + 工作入口 -->
          <div class="qc-home-hero">
            <span
              class="qc-home-hero__glow"
              aria-hidden="true"
            />
            <span class="qc-home-hero__label">
              <MqIcon
                name="task"
                :size="18"
                color="#FFFFFF"
              />待质控
            </span>
            <div class="qc-home-hero__value">
              <strong>{{ pendingKpi.value }}</strong>
              <span>/ {{ recordsTotal }} 份</span>
            </div>
            <div class="qc-home-hero__progress">
              <span
                class="qc-home-hero__track"
                aria-hidden="true"
              >
                <i :style="{ width: `${rates.pending}%` }" />
              </span>
              <span>占纳入病历 {{ formatRate(rates.pending) }}%，尚未生成最终结果。</span>
            </div>
            <nav
              class="qc-home-shortcuts"
              data-testid="home-workspace"
              aria-label="质控工作入口"
            >
              <button
                type="button"
                class="qc-home-shortcuts__primary"
                @click="openRecordPool"
              >
                选择病历质控
              </button>
              <button
                type="button"
                @click="router.push('/workstation-v5/records/running')"
              >
                运行病历质控
              </button>
              <button
                type="button"
                @click="router.push('/workstation-v5/records/final')"
              >
                终末病历质控
              </button>
            </nav>
          </div>

          <!-- 质控进度圆环卡（浅色玻璃，比例均由现有 KPI 计算） -->
          <div
            class="qc-home-rings"
            aria-label="质控进度"
          >
            <span class="qc-home-rings__title">质控进度</span>
            <div class="qc-home-rings__body">
              <svg
                width="96"
                height="96"
                viewBox="0 0 200 200"
                aria-hidden="true"
              >
                <defs>
                  <linearGradient
                    v-for="ring in ringDefs"
                    :id="ring.gradient"
                    :key="ring.gradient"
                    x1="0"
                    y1="0"
                    x2="1"
                    y2="1"
                  >
                    <stop
                      offset="0"
                      :stop-color="ring.from"
                    />
                    <stop
                      offset="1"
                      :stop-color="ring.to"
                    />
                  </linearGradient>
                </defs>
                <g
                  v-for="ring in ringDefs"
                  :key="ring.key"
                >
                  <circle
                    cx="100"
                    cy="100"
                    :r="ring.r"
                    fill="none"
                    :stroke="`url(#${ring.gradient})`"
                    stroke-opacity="0.14"
                    stroke-width="20"
                  />
                  <!-- 零值不画进度弧，避免圆角端点残留成一个点 -->
                  <circle
                    v-if="ring.rate > 0"
                    cx="100"
                    cy="100"
                    :r="ring.r"
                    fill="none"
                    :stroke="`url(#${ring.gradient})`"
                    stroke-width="20"
                    stroke-linecap="round"
                    :stroke-dasharray="ringDash(ring.r, ring.rate)"
                    transform="rotate(-90 100 100)"
                  />
                </g>
              </svg>
              <dl class="qc-home-rings__legend">
                <div
                  v-for="ring in ringDefs"
                  :key="ring.key"
                >
                  <dt :style="{ color: ring.textColor }">
                    {{ ring.label }}
                  </dt>
                  <dd>{{ formatRate(ring.rate) }}<small> %</small></dd>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <!-- 三栏指标卡 -->
        <section
          class="mq-card qc-home-metrics"
          data-testid="home-kpis"
          aria-label="质控指标汇总"
        >
          <div
            v-for="card in metricCards"
            :key="card.key"
            :class="['qc-home-metric', `qc-home-metric--${card.key}`, { 'is-zero': card.value === 0 }]"
          >
            <span
              class="qc-home-metric__watermark"
              aria-hidden="true"
            >
              <MqIcon
                :name="card.icon"
                :size="104"
                :color="toneColor(card.tone)"
              />
            </span>
            <div class="qc-home-metric__head">
              <MqIconTile
                :name="card.icon"
                :tone="card.tone"
                :size="40"
              />
              <div>
                <span class="qc-home-metric__label">{{ card.label }}</span>
                <p class="qc-home-metric__helper">
                  {{ card.helper }}
                </p>
              </div>
            </div>
            <div class="qc-home-metric__foot">
              <strong class="qc-home-metric__value">{{ card.value }}<small>份</small></strong>
              <span class="qc-home-metric__rate">
                <em :style="{ color: toneColor(card.tone) }">{{ card.rateLabel }}</em>
                <span
                  class="qc-home-metric__track"
                  aria-hidden="true"
                >
                  <i :style="{ width: `${card.rate}%`, background: toneGradient(card.tone) }" />
                </span>
              </span>
            </div>
          </div>
        </section>

        <section
          class="qc-home-analysis"
          data-testid="home-analysis"
        >
          <section
            class="mq-card qc-home-panel qc-home-defect-analysis"
            data-testid="defect-analysis-chart"
            aria-labelledby="defect-analysis-title"
          >
            <header class="qc-home-panel__head qc-home-defect-analysis__head">
              <div>
                <h2
                  id="defect-analysis-title"
                  class="mq-card__title"
                >
                  质控缺陷分析
                </h2>
                <p>缺陷仅统计确定问题，资料待核实与待判断不计入缺陷数。</p>
              </div>
              <!-- 一个分段控件切统计对象；指标与排序收进下拉 -->
              <div class="qc-home-defect-analysis__toolbar">
                <div
                  class="mq-segmented mq-segmented--sm"
                  role="group"
                  aria-label="统计对象"
                >
                  <button
                    type="button"
                    class="mq-segmented__item"
                    :class="{ 'is-active': analysisObject === 'department' }"
                    data-testid="analysis-object-department"
                    @click="analysisObject = 'department'"
                  >
                    按科室
                  </button>
                  <button
                    type="button"
                    class="mq-segmented__item"
                    :class="{ 'is-active': analysisObject === 'physician' }"
                    data-testid="analysis-object-physician"
                    @click="analysisObject = 'physician'"
                  >
                    按主治医师
                  </button>
                </div>
                <label class="qc-home-pulldown">
                  <span class="qc-home-pulldown__label">指标</span>
                  <select
                    v-model="analysisMetric"
                    data-testid="analysis-metric"
                    aria-label="分析指标"
                  >
                    <option value="total">缺陷总数</option>
                    <option value="average">平均缺陷数</option>
                  </select>
                  <svg
                    class="qc-home-pulldown__caret"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  ><path d="m6 9 6 6 6-6" /></svg>
                </label>
                <label class="qc-home-pulldown">
                  <span class="qc-home-pulldown__label">排序</span>
                  <select
                    v-model="analysisSort"
                    data-testid="analysis-sort"
                    aria-label="排序方式"
                  >
                    <option value="metric">当前指标</option>
                    <option value="risk">高风险病历</option>
                    <option value="gap">资料待核实</option>
                  </select>
                  <svg
                    class="qc-home-pulldown__caret"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  ><path d="m6 9 6 6 6-6" /></svg>
                </label>
              </div>
            </header>
            <div
              v-if="defectAnalysisItems.length"
              class="qc-home-defect-analysis__list"
            >
              <component
                :is="analysisObject === 'department' ? 'button' : 'div'"
                v-for="item in defectAnalysisItems"
                :key="item.name"
                :type="analysisObject === 'department' ? 'button' : undefined"
                :class="[
                  'qc-home-defect-analysis__row',
                  {
                    'is-active': analysisObject === 'department' && departmentFilter === item.name,
                  },
                ]"
                data-testid="defect-analysis-row"
                :aria-label="
                  analysisObject === 'department' ? `切换到${item.name}科室质控范围` : undefined
                "
                @click="analysisObject === 'department' && selectDepartment(item.name)"
              >
                <div class="qc-home-defect-analysis__meta">
                  <strong>{{ item.name }}</strong>
                  <span>纳入 {{ item.recordsTotal }} 份 · 完成
                    {{ item.completedRecordTotal }} 份</span>
                </div>
                <div
                  class="qc-home-defect-analysis__metric"
                  aria-hidden="true"
                >
                  <div class="qc-home-defect-analysis__track">
                    <i :style="{ width: `${defectAnalysisPercent(item)}%` }" />
                  </div>
                  <strong>{{ formatAnalysisMetric(item) }}</strong>
                </div>
                <div class="qc-home-defect-analysis__counts">
                  <strong :class="{ 'is-zero': !item.highRiskReviewTotal }">高风险 {{ item.highRiskReviewTotal }}</strong>
                  <span :class="{ 'is-zero': !item.dataGapRecordTotal }">待核实 {{ item.dataGapRecordTotal }}</span>
                </div>
                <svg
                  v-if="analysisObject === 'department'"
                  class="qc-home-defect-analysis__chevron"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                ><path d="m9 6 6 6-6 6" /></svg>
              </component>
              <p
                v-if="hiddenDefectAnalysisCount"
                class="qc-home-defect-analysis__note"
              >
                仅展示前 8 项；其余 {{ hiddenDefectAnalysisCount }} 个{{
                  analysisObjectLabel
                }}已收起。
              </p>
            </div>
            <a-empty
              v-else
              :description="`当前范围内暂无${analysisObjectLabel}统计`"
              :image-style="{ height: '58px' }"
            />
          </section>

          <div class="qc-home-side">
            <section
              class="mq-card qc-home-panel qc-home-conclusion"
              data-testid="qc-conclusion-chart"
              aria-labelledby="qc-conclusion-title"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2
                    id="qc-conclusion-title"
                    class="mq-card__title"
                  >
                    结论结构
                  </h2>
                  <p>{{ clinicalQc.kpis.qc_partial_failed_total ? '已回写的有效规则结论，含未全部完成病历。' : '已完成病历中的规则结论。' }}</p>
                </div>
              </header>
              <div
                v-if="conclusionSegments.length"
                class="qc-home-conclusion__content"
              >
                <div
                  class="qc-home-conclusion__ring"
                  role="img"
                  :aria-label="`已完成规则结论共 ${conclusionTotal} 条`"
                  :style="{ background: conclusionRingBackground }"
                >
                  <div>
                    <strong>{{ conclusionTotal }}</strong>
                    <span>规则结论</span>
                  </div>
                </div>
                <ul
                  class="qc-home-conclusion__legend"
                  :aria-label="clinicalQc.kpis.qc_partial_failed_total ? '已回写有效规则结论图例' : '已完成病历中的规则结论图例'"
                >
                  <li
                    v-for="segment in conclusionSegments"
                    :key="segment.status"
                  >
                    <i
                      :style="{ background: segment.color }"
                      aria-hidden="true"
                    />
                    <span>{{ segment.label }} {{ segment.value }}</span>
                    <small>{{ segment.percent }}%</small>
                  </li>
                </ul>
              </div>
              <a-empty
                v-else
                description="暂无已完成质控结论"
                :image-style="{ height: '52px' }"
              />
            </section>

            <section
              class="mq-card qc-home-panel qc-home-panel--health"
              data-testid="data-health"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2 class="mq-card__title">
                    数据与服务状态
                  </h2>
                  <p>用于判断数据与任务是否可正常使用，不代表医疗结论。</p>
                </div>
              </header>
              <dl class="qc-home-health-list">
                <div data-testid="health-status-item">
                  <MqIconTile
                    name="sync"
                    tone="brand"
                    :size="34"
                  />
                  <dt>资料同步</dt>
                  <dd>{{ sourceStateText }}</dd>
                </div>
                <div data-testid="health-status-item">
                  <MqIconTile
                    name="task"
                    tone="brand"
                    :size="34"
                  />
                  <dt>质控任务</dt>
                  <dd>{{ runningTaskText }}</dd>
                </div>
                <div
                  v-if="!isDemoPresentation"
                  data-testid="health-status-item"
                >
                  <MqIconTile
                    name="tech_error"
                    tone="warning"
                    :size="34"
                  />
                  <dt>技术异常</dt>
                  <dd :class="{ 'is-danger': clinicalQc.data_health.technical_error_total > 0 }">
                    {{ clinicalQc.data_health.technical_error_total }} 份
                  </dd>
                </div>
                <div data-testid="health-status-item">
                  <MqIconTile
                    name="success"
                    tone="success"
                    :size="34"
                  />
                  <dt>最近成功质控</dt>
                  <dd>{{ formatDateTime(clinicalQc.data_health.last_successful_qc_at) }}</dd>
                </div>
                <div
                  v-if="clinicalQc.kpis.qc_partial_failed_total || clinicalQc.kpis.qc_failed_total"
                  data-testid="qc-execution-failures"
                >
                  <MqIconTile
                    name="failed"
                    tone="warning"
                    :size="34"
                  />
                  <dt>未全部完成</dt>
                  <dd>部分失败 {{ clinicalQc.kpis.qc_partial_failed_total || 0 }} 份、执行失败 {{ clinicalQc.kpis.qc_failed_total || 0 }} 份</dd>
                </div>
              </dl>
            </section>
          </div>
        </section>
      </template>

      <section
        v-else-if="!loading"
        class="mq-card qc-home-empty"
        data-testid="home-empty"
      >
        <a-empty description="当前暂无可展示的全病历质控汇总">
          <template #description>
            <p>请先在病历池完成质控；系统不会用旧工作流数据代替正式质控结果。</p>
          </template>
          <button
            type="button"
            class="qc-home-button qc-home-button--primary"
            @click="openRecordPool"
          >
            进入病历池
          </button>
        </a-empty>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { MQ_ICON_TONES, type MqIconName, type MqIconTone } from '@/components/icons/mqIcons'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { QC_RESULT_STATUS_LABELS } from '../workstation-v4/utils/qcResultStatusLabels'
import type {
  ClinicalQcHomeDepartmentItem,
  ClinicalQcHomePhysicianItem,
  ClinicalQcHomePayload,
} from './types'

interface KpiCard {
  key: string
  label: string
  value: number
  helper: string
  icon: MqIconName
  tone: MqIconTone
}

interface MetricCard extends KpiCard {
  /** 进度条比例（0-100） */
  rate: number
  rateLabel: string
}

interface ConclusionSegment {
  status: string
  label: string
  value: number
  color: string
  percent: number
}

type AnalysisObject = 'department' | 'physician'
type AnalysisMetric = 'total' | 'average'
type AnalysisSort = 'metric' | 'risk' | 'gap'

interface DefectAnalysisItem {
  name: string
  recordsTotal: number
  completedRecordTotal: number
  highRiskReviewTotal: number
  dataGapRecordTotal: number
  defectTotal: number
  averageDefectCount: number
}

const CONCLUSION_STATUS_META = [
  { status: 'non_compliant', label: QC_RESULT_STATUS_LABELS.non_compliant, color: '#ef4444' },
  { status: 'data_gap', label: QC_RESULT_STATUS_LABELS.data_gap, color: '#f59e0b' },
  { status: 'uncertain', label: QC_RESULT_STATUS_LABELS.uncertain, color: '#64748b' },
  { status: 'compliant', label: '合规', color: '#10b981' },
  // 与质控分析页保持同一套语义色，避免同一状态在不同首页模块变色。
  { status: 'not_applicable', label: '不适用', color: '#94a3b8' },
  { status: 'not_executed', label: '未执行', color: '#cbd5e1' },
] as const

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
// 首次进入即处于加载态，避免请求尚未发起时短暂展示无内容的页面框架。
const loading = ref(true)
const loadError = ref(false)
const departmentFilter = ref('all')
const keyword = ref('')
const analysisObject = ref<AnalysisObject>('department')
const analysisMetric = ref<AnalysisMetric>('total')
const analysisSort = ref<AnalysisSort>('metric')
const syncingFromRoute = ref(false)
const homeData = ref<ClinicalQcHomePayload | null>(null)

const clinicalQc = computed(() => homeData.value?.clinical_qc ?? null)
const isDemoPresentation = computed(() => authStore.user?.is_demo_account === true && !authStore.userRoles?.includes('sync_admin'))
const departmentOptions = computed(() => homeData.value?.department_options ?? [])
const scopeHospitalText = computed(() =>
  clinicalQc.value?.scope.hospital_scope === 'all' ? '全院' : '当前范围',
)
const scopeDepartmentText = computed(() => clinicalQc.value?.scope.department || '全部科室')
const scopeSceneText = computed(() =>
  clinicalQc.value?.scope.scene === 'final'
    ? '最终结果'
    : clinicalQc.value?.scope.scene || '场景待确认',
)

const kpiCards = computed<KpiCard[]>(() => {
  const kpis = clinicalQc.value?.kpis
  return [
    {
      key: 'risk',
      label: '有确定问题的病历',
      value: Number(kpis?.high_risk_review_total || 0),
      helper: '含确定问题的病历',
      icon: 'issue',
      tone: 'danger',
    },
    {
      key: 'pending',
      label: '待质控',
      value: Number(kpis?.qc_pending_total || 0),
      helper: '尚未生成最终结果',
      icon: 'task',
      tone: 'warning',
    },
    {
      key: 'completed',
      label: '已完成',
      value: Number(kpis?.qc_completed_total || 0),
      helper: '已生成正式质控结果',
      icon: 'fp_qc',
      tone: 'success',
    },
    {
      key: 'records',
      label: '纳入病历',
      value: Number(kpis?.records_total || 0),
      helper: '当前筛选范围',
      icon: 'stack',
      tone: 'brand',
    },
  ]
})

const kpiByKey = computed(() =>
  Object.fromEntries(kpiCards.value.map((card) => [card.key, card])),
)
const pendingKpi = computed(() => kpiByKey.value.pending)
const recordsTotal = computed(() => kpiByKey.value.records.value)

function ratio(part: number, whole: number): number {
  return whole > 0 ? Math.min(100, (part / whole) * 100) : 0
}

function formatRate(value: number): string {
  return String(Math.round(value * 10) / 10)
}

// 进度比例全部由现有 KPI 计算，不引入新口径
const rates = computed(() => ({
  pending: ratio(kpiByKey.value.pending.value, recordsTotal.value),
  completion: ratio(kpiByKey.value.completed.value, recordsTotal.value),
  issue: ratio(kpiByKey.value.risk.value, kpiByKey.value.completed.value + (clinicalQc.value?.kpis.qc_partial_failed_total || 0)),
}))

const metricCards = computed<MetricCard[]>(() => [
  {
    ...kpiByKey.value.risk,
    rate: rates.value.issue,
    rateLabel: `占${clinicalQc.value?.kpis.qc_partial_failed_total ? '有结果病历' : '已完成'} ${formatRate(rates.value.issue)}%`,
  },
  {
    ...kpiByKey.value.completed,
    rate: rates.value.completion,
    rateLabel: `完成率 ${formatRate(rates.value.completion)}%`,
  },
  { ...kpiByKey.value.records, rate: recordsTotal.value > 0 ? 100 : 0, rateLabel: scopeHospitalText.value },
])

const ringDefs = computed(() => [
  {
    key: 'issue',
    label: '问题率',
    r: 84,
    rate: rates.value.issue,
    gradient: 'qcRingRed',
    from: '#FF6B61',
    to: '#FF3B30',
    textColor: 'var(--mq-danger-text)',
  },
  {
    key: 'completion',
    label: '完成率',
    r: 60,
    rate: rates.value.completion,
    gradient: 'qcRingGreen',
    from: '#5FD97E',
    to: '#34C759',
    textColor: 'var(--mq-success-text)',
  },
  {
    key: 'pending',
    label: '待质控',
    r: 36,
    rate: rates.value.pending,
    gradient: 'qcRingAmber',
    from: '#FFB340',
    to: '#FF9500',
    textColor: 'var(--mq-warning-text)',
  },
])

function ringDash(radius: number, rate: number): string {
  const circumference = 2 * Math.PI * radius
  return `${((circumference * rate) / 100).toFixed(1)} ${circumference.toFixed(1)}`
}

const TONE_GRADIENTS: Record<MqIconTone, string> = {
  neutral: 'linear-gradient(90deg, #A1A7B3, #6E7585)',
  brand: 'linear-gradient(90deg, #6FB0FF, #0A6CFF)',
  success: 'linear-gradient(90deg, #6EE08E, #34C759)',
  warning: 'linear-gradient(90deg, #FFC36B, #FF9500)',
  danger: 'linear-gradient(90deg, #FF7A70, #FF3B30)',
}

function toneColor(tone: MqIconTone): string {
  return MQ_ICON_TONES[tone].color
}

function toneGradient(tone: MqIconTone): string {
  return TONE_GRADIENTS[tone]
}

const todayLabel = computed(() => dayjs().format('M月D日 dddd'))

// 眉标：日期与范围合成一行纯文字（原先拆成多个胶囊）
const scopeLine = computed(() => {
  const parts = [todayLabel.value]
  if (clinicalQc.value) parts.push(scopeHospitalText.value, scopeSceneText.value)
  parts.push('泸县0609质控点')
  return parts.join(' · ')
})

const conclusionSegments = computed<ConclusionSegment[]>(() => {
  const counts = clinicalQc.value?.canonical_status_counts || {}
  const values = CONCLUSION_STATUS_META.map((meta) => ({
    ...meta,
    value: Math.max(0, Number(counts[meta.status] || 0)),
  })).filter((segment) => segment.value > 0)
  const total = values.reduce((sum, segment) => sum + segment.value, 0)
  return values.map((segment) => ({
    ...segment,
    percent: total ? Number(((segment.value / total) * 100).toFixed(1)) : 0,
  }))
})
const conclusionTotal = computed(() =>
  conclusionSegments.value.reduce((sum, segment) => sum + segment.value, 0),
)
const conclusionRingBackground = computed(() => {
  if (!conclusionSegments.value.length) return 'transparent'
  let offset = 0
  const stops = conclusionSegments.value.map((segment) => {
    const start = offset
    offset += segment.percent
    return `${segment.color} ${start}% ${offset}%`
  })
  return `conic-gradient(${stops.join(', ')})`
})

const sourceStateText = computed(() =>
  clinicalQc.value?.data_health.source_sync_status === 'unknown' ? '待核实' : '待核实',
)
const runningTaskText = computed(() =>
  clinicalQc.value?.data_health.running_task_state === 'unknown' ? '待接入' : '待接入',
)
const analysisObjectLabel = computed(() =>
  analysisObject.value === 'department' ? '科室' : '主治医师',
)
const allDefectAnalysisItems = computed<DefectAnalysisItem[]>(() => {
  if (analysisObject.value === 'physician') {
    return (clinicalQc.value?.physician_distribution || []).map(
      (item: ClinicalQcHomePhysicianItem) => ({
        name: item.physician,
        recordsTotal: Math.max(0, Number(item.records_total || 0)),
        completedRecordTotal: Math.max(0, Number(item.completed_record_total || 0)),
        highRiskReviewTotal: Math.max(0, Number(item.high_risk_review_total || 0)),
        dataGapRecordTotal: Math.max(0, Number(item.data_gap_record_total || 0)),
        defectTotal: Math.max(0, Number(item.defect_total || 0)),
        averageDefectCount: Math.max(0, Number(item.average_defect_count || 0)),
      }),
    )
  }
  return (clinicalQc.value?.department_distribution || []).map(
    (item: ClinicalQcHomeDepartmentItem) => ({
      name: item.department,
      recordsTotal: Math.max(0, Number(item.records_total || 0)),
      completedRecordTotal: Math.max(0, Number(item.completed_record_total || 0)),
      highRiskReviewTotal: Math.max(0, Number(item.high_risk_review_total || 0)),
      dataGapRecordTotal: Math.max(0, Number(item.data_gap_record_total || 0)),
      defectTotal: Math.max(0, Number(item.defect_total || 0)),
      averageDefectCount: Math.max(0, Number(item.average_defect_count || 0)),
    }),
  )
})
const defectAnalysisItems = computed(() =>
  [...allDefectAnalysisItems.value]
    .sort((left, right) => {
      const primary =
        analysisSort.value === 'risk'
          ? right.highRiskReviewTotal - left.highRiskReviewTotal
          : analysisSort.value === 'gap'
            ? right.dataGapRecordTotal - left.dataGapRecordTotal
            : analysisMetric.value === 'average'
              ? right.averageDefectCount - left.averageDefectCount
              : right.defectTotal - left.defectTotal
      return (
        primary ||
        right.defectTotal - left.defectTotal ||
        right.recordsTotal - left.recordsTotal ||
        left.name.localeCompare(right.name, 'zh-CN')
      )
    })
    .slice(0, 8),
)
const hiddenDefectAnalysisCount = computed(() =>
  Math.max(0, allDefectAnalysisItems.value.length - defectAnalysisItems.value.length),
)
const defectAnalysisMaximum = computed(() =>
  Math.max(
    1,
    ...defectAnalysisItems.value.map((item) =>
      analysisMetric.value === 'average' ? item.averageDefectCount : item.defectTotal,
    ),
  ),
)

function defectAnalysisPercent(item: DefectAnalysisItem): number {
  const value = analysisMetric.value === 'average' ? item.averageDefectCount : item.defectTotal
  return Number(((value / defectAnalysisMaximum.value) * 100).toFixed(1))
}

function formatAnalysisMetric(item: DefectAnalysisItem): string {
  return analysisMetric.value === 'average'
    ? item.averageDefectCount.toFixed(2)
    : String(item.defectTotal)
}

function selectDepartment(department: string) {
  departmentFilter.value = department
}

function formatDateTime(value?: string | null): string {
  if (!value) return '暂未返回'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : '暂未返回'
}

function applyRouteFilters() {
  const department = typeof route.query.department === 'string' ? route.query.department : 'all'
  const queryKeyword = typeof route.query.keyword === 'string' ? route.query.keyword : ''
  syncingFromRoute.value = true
  departmentFilter.value = department || 'all'
  keyword.value = queryKeyword
  syncingFromRoute.value = false
}

function openRecordPool() {
  void router.push({
    path: '/workstation-v5/worklist',
    query: {
      source: 'dashboard',
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
    },
  })
}

function clearKeyword() {
  const query = { ...route.query }
  delete query.keyword
  if (departmentFilter.value === 'all') delete query.department
  else query.department = departmentFilter.value
  void router.replace({ query })
}

async function fetchHome() {
  loading.value = true
  loadError.value = false
  try {
    const res = await ApiService.get<ClinicalQcHomePayload>('/api/v1/workstation/qc-home', {
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
      hotspot_limit: 20,
      todo_limit: 1,
    })
    if (!res.success || !res.data?.clinical_qc)
      throw new Error(String(res.error || '首页聚合未返回'))
    homeData.value = res.data
  } catch {
    homeData.value = null
    loadError.value = true
  } finally {
    loading.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    applyRouteFilters()
    void fetchHome()
  },
  { immediate: true },
)

watch(
  [departmentFilter, keyword],
  () => {
    if (syncingFromRoute.value) return
    void fetchHome()
  },
  // 路由同步期间立即识别保护标记，由路由监听统一请求，避免清除关键词时重复加载。
  { flush: 'sync' },
)
</script>

<style scoped src="./styles/qc-overview.css"></style>
