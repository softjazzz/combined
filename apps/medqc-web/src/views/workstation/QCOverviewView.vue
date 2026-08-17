<template>
  <div class="qc-home-shell workstation-shell min-h-screen">
    <div class="custom-scrollbar h-screen overflow-y-auto px-5 py-7 xl:px-8">
      <main class="qc-home-canvas mx-auto w-full max-w-[1440px]">
        <section class="qc-home-header workstation-surface-enter">
          <div class="qc-home-header__copy">
            <h1>质控首页概览</h1>
          </div>
          <HomeHeroBar
            v-model:keyword="keyword"
            v-model:department-filter="departmentFilter"
            :selected-date="selectedDate"
            workflow-filter="all"
            :department-options="departmentOptions"
            :loading="loading"
            :disabled-future-date="disabledFutureDate"
            :show-date="false"
            :show-workflow="false"
            @refresh="void fetchHome()"
          />
        </section>

        <section
          v-if="loadError"
          class="qc-home-notice qc-home-notice--error"
          data-testid="home-load-error"
        >
          <strong>暂时无法加载质控首页</strong>
          <span>请稍后刷新；不会以旧任务或缓存数据替代当前结果。</span>
          <a-button
            size="small"
            @click="void fetchHome()"
          >
            重新加载
          </a-button>
        </section>

        <section
          v-else-if="loading"
          class="qc-home-loading workstation-surface-enter"
          data-testid="home-loading"
          aria-live="polite"
          aria-busy="true"
        >
          <a-spin size="large" />
          <div>
            <strong>正在加载全院质控概览</strong>
            <span>正在汇总当前范围内的病历与最新质控结果。</span>
          </div>
        </section>

        <template v-else-if="clinicalQc">
          <section
            class="qc-home-kpis workstation-surface-enter"
            data-testid="home-kpis"
          >
            <article
              v-for="card in kpiCards"
              :key="card.key"
              :class="['qc-home-kpi', `is-${card.tone}`]"
            >
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </article>
          </section>

          <section
            class="qc-home-grid qc-home-workspace workstation-surface-enter"
            data-testid="home-workspace"
          >
            <section
              class="qc-home-panel qc-home-panel--queue"
              data-testid="priority-queue"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2>病历质控队列</h2>
                  <p>优先展示需要复核的病历，直接进入对应的质控结果。</p>
                </div>
                <button
                  type="button"
                  class="qc-home-panel-link"
                  @click="openRecordPool"
                >
                  全部病历
                  <ArrowRight :size="15" />
                </button>
              </header>

              <div
                class="qc-home-scope qc-home-priority-scope"
                data-testid="home-scope"
              >
                <span class="qc-home-scope__label">当前范围</span>
                <span>{{ scopeHospitalText }}</span>
                <i />
                <span>{{ scopeDepartmentText }}</span>
                <i />
                <span>{{ scopeSceneText }}</span>
                <i />
                <span class="qc-home-scope__rule-set">泸县0609质控点</span>
                <span class="qc-home-scope__time">生成于 {{ formatDateTime(clinicalQc.scope.generated_at) }}</span>
              </div>

              <div
                v-if="clinicalQc.priority_items.length"
                class="qc-home-priority-list"
              >
                <div
                  class="qc-home-priority-columns"
                  aria-hidden="true"
                >
                  <span>患者 / 病历</span>
                  <span>科室</span>
                  <span>确定问题</span>
                  <span>资料待核实</span>
                  <span>最近质控</span>
                  <span>操作</span>
                </div>
                <button
                  v-for="(item, index) in clinicalQc.priority_items"
                  :key="item.record_key"
                  type="button"
                  class="qc-home-priority-row"
                  :aria-label="`查看${item.patient_name || '该病历'}的质控结果`"
                  @click="openQcResult(item)"
                >
                  <span class="qc-home-priority-row__rank">{{
                    String(index + 1).padStart(2, '0')
                  }}</span>
                  <div class="qc-home-priority-row__identity">
                    <strong>{{ item.patient_name || '未返回患者姓名' }}</strong>
                    <span>住院号 {{ item.visit_id }}</span>
                  </div>
                  <span
                    class="qc-home-priority-row__department"
                    data-testid="priority-department"
                  >{{ item.department || '未分科室' }}</span>
                  <div
                    class="qc-home-priority-row__metric is-defect"
                    data-testid="priority-defect-count"
                  >
                    <span>确定问题</span>
                    <strong>{{ countOf(item, 'non_compliant') }}</strong>
                    <small>项</small>
                  </div>
                  <div
                    class="qc-home-priority-row__metric is-gap"
                    data-testid="priority-data-gap-count"
                  >
                    <span>资料待核实</span>
                    <strong>{{ countOf(item, 'data_gap') }}</strong>
                    <small>项</small>
                  </div>
                  <div
                    class="qc-home-priority-row__time"
                    data-testid="priority-completed-at"
                  >
                    <span>最近质控</span>
                    <strong>{{ formatPriorityTime(item.completed_at) }}</strong>
                  </div>
                  <span
                    class="qc-home-priority-row__action"
                    data-testid="priority-open-result"
                  >
                    查看质控结果
                    <ChevronRight
                      :size="16"
                      aria-hidden="true"
                    />
                  </span>
                </button>
              </div>
              <a-empty
                v-else
                description="当前范围内没有需要优先复核的病历"
                :image-style="{ height: '72px' }"
              />
            </section>

            <aside class="qc-home-side-stack">
              <section
                class="qc-home-panel qc-home-panel--health"
                data-testid="data-health"
              >
                <header class="qc-home-panel__head">
                  <div>
                    <h2>运行与数据</h2>
                    <p>用于判断数据与任务是否可正常使用，不代表医疗结论。</p>
                  </div>
                </header>
                <dl class="qc-home-health-list">
                  <div data-testid="health-status-item">
                    <span class="qc-home-health-list__icon is-brand">
                      <Database :size="18" />
                    </span>
                    <div>
                      <dt>资料同步</dt>
                      <dd>{{ sourceStateText }}</dd>
                    </div>
                    <small>当前尚无权威同步状态</small>
                  </div>
                  <div data-testid="health-status-item">
                    <span class="qc-home-health-list__icon is-brand">
                      <Activity :size="18" />
                    </span>
                    <div>
                      <dt>质控任务</dt>
                      <dd>{{ runningTaskText }}</dd>
                    </div>
                    <small>运行状态尚未接入首页</small>
                  </div>
                  <div
                    v-if="!isDemoPresentation"
                    data-testid="health-status-item"
                  >
                    <span class="qc-home-health-list__icon is-danger">
                      <TriangleAlert :size="18" />
                    </span>
                    <div>
                      <dt>技术异常</dt>
                      <dd
                        :class="{ 'is-danger': clinicalQc.data_health.technical_error_total > 0 }"
                      >
                        {{ clinicalQc.data_health.technical_error_total }} 份
                      </dd>
                    </div>
                    <small>仅反映结果交付状态</small>
                  </div>
                  <div data-testid="health-status-item">
                    <span class="qc-home-health-list__icon is-success">
                      <CircleCheckBig :size="18" />
                    </span>
                    <div>
                      <dt>最近成功质控</dt>
                      <dd>{{ formatDateTime(clinicalQc.data_health.last_successful_qc_at) }}</dd>
                    </div>
                    <small>最近一次可用结果生成时间</small>
                  </div>
                </dl>
              </section>
            </aside>
          </section>

          <section
            class="qc-home-analysis workstation-surface-enter"
            data-testid="home-analysis"
          >
            <section
              class="qc-home-panel qc-home-defect-analysis"
              data-testid="defect-analysis-chart"
              aria-labelledby="defect-analysis-title"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2 id="defect-analysis-title">
                    质控缺陷分析
                  </h2>
                  <p>缺陷仅统计确定问题，资料待核实与待判断不计入缺陷数。</p>
                </div>
              </header>
              <div class="qc-home-defect-analysis__toolbar">
                <div class="qc-home-defect-analysis__control">
                  <span>统计对象</span>
                  <div
                    role="group"
                    aria-label="统计对象"
                  >
                    <button
                      type="button"
                      :class="{ 'is-active': analysisObject === 'department' }"
                      data-testid="analysis-object-department"
                      @click="analysisObject = 'department'"
                    >
                      按科室
                    </button>
                    <button
                      type="button"
                      :class="{ 'is-active': analysisObject === 'physician' }"
                      data-testid="analysis-object-physician"
                      @click="analysisObject = 'physician'"
                    >
                      按主治医师
                    </button>
                  </div>
                </div>
                <div class="qc-home-defect-analysis__control">
                  <span>分析指标</span>
                  <div
                    role="group"
                    aria-label="分析指标"
                  >
                    <button
                      type="button"
                      :class="{ 'is-active': analysisMetric === 'total' }"
                      data-testid="analysis-metric-total"
                      @click="analysisMetric = 'total'"
                    >
                      缺陷总数
                    </button>
                    <button
                      type="button"
                      :class="{ 'is-active': analysisMetric === 'average' }"
                      data-testid="analysis-metric-average"
                      @click="analysisMetric = 'average'"
                    >
                      平均缺陷数
                    </button>
                  </div>
                </div>
                <div class="qc-home-defect-analysis__control">
                  <span>排序</span>
                  <div
                    role="group"
                    aria-label="排序方式"
                  >
                    <button
                      type="button"
                      :class="{ 'is-active': analysisSort === 'metric' }"
                      data-testid="analysis-sort-metric"
                      @click="analysisSort = 'metric'"
                    >
                      当前指标
                    </button>
                    <button
                      type="button"
                      :class="{ 'is-active': analysisSort === 'risk' }"
                      data-testid="analysis-sort-risk"
                      @click="analysisSort = 'risk'"
                    >
                      高风险病历
                    </button>
                    <button
                      type="button"
                      :class="{ 'is-active': analysisSort === 'gap' }"
                      data-testid="analysis-sort-gap"
                      @click="analysisSort = 'gap'"
                    >
                      资料待核实
                    </button>
                  </div>
                </div>
              </div>
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
                      'is-active':
                        analysisObject === 'department' && departmentFilter === item.name,
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
                    <strong>高风险 {{ item.highRiskReviewTotal }}</strong>
                    <span>待核实 {{ item.dataGapRecordTotal }}</span>
                  </div>
                  <ChevronRight
                    v-if="analysisObject === 'department'"
                    :size="17"
                    aria-hidden="true"
                  />
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

            <section
              class="qc-home-panel qc-home-conclusion"
              data-testid="qc-conclusion-chart"
              aria-labelledby="qc-conclusion-title"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2 id="qc-conclusion-title">
                    结论结构
                  </h2>
                  <p>已完成病历中的规则结论。</p>
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
                  aria-label="已完成病历中的规则结论图例"
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
                :image-style="{ height: '58px' }"
              />
            </section>
          </section>

          <section
            v-if="clinicalQc.trend"
            class="qc-home-panel workstation-surface-enter"
            data-testid="home-trend"
          >
            <header class="qc-home-panel__head">
              <div>
                <h2>质控趋势</h2>
                <p>仅在后端返回真实时间序列时展示。</p>
              </div>
            </header>
          </section>
        </template>

        <section
          v-else-if="!loading"
          class="qc-home-empty workstation-surface-enter"
          data-testid="home-empty"
        >
          <a-empty description="当前暂无可展示的全病历质控汇总">
            <template #description>
              <p>请先在病历池完成质控；系统不会用旧工作流数据代替正式质控结果。</p>
            </template>
            <a-button
              type="primary"
              @click="openRecordPool"
            >
              进入病历池
            </a-button>
          </a-empty>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs, { type Dayjs } from 'dayjs'
import {
  Activity,
  ArrowRight,
  ChevronRight,
  CircleCheckBig,
  Database,
  TriangleAlert,
} from 'lucide-vue-next'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import type {
  ClinicalQcHomeDepartmentItem,
  ClinicalQcHomePhysicianItem,
  ClinicalQcHomePriorityItem,
  WorkstationHomePayload,
} from '@/views/workstation-v2/types'
import HomeHeroBar from './components/HomeHeroBar.vue'

interface KpiCard {
  key: string
  label: string
  value: number
  tone: 'brand' | 'warning' | 'success' | 'danger'
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
  { status: 'non_compliant', label: '确定问题', color: '#ef4444' },
  { status: 'data_gap', label: '资料待核实', color: '#f59e0b' },
  { status: 'uncertain', label: '待判断', color: '#64748b' },
  { status: 'compliant', label: '合规', color: '#10b981' },
  { status: 'not_applicable', label: '不适用', color: '#cbd5e1' },
  { status: 'not_executed', label: '未执行', color: '#94a3b8' },
] as const

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
// 首次进入即处于加载态，避免请求尚未发起时短暂展示无内容的页面框架。
const loading = ref(true)
const loadError = ref(false)
const selectedDate = ref<Dayjs>(dayjs())
const departmentFilter = ref('all')
const keyword = ref('')
const analysisObject = ref<AnalysisObject>('department')
const analysisMetric = ref<AnalysisMetric>('total')
const analysisSort = ref<AnalysisSort>('metric')
const syncingFromRoute = ref(false)
const homeData = ref<WorkstationHomePayload | null>(null)

const clinicalQc = computed(() => homeData.value?.clinical_qc ?? null)
const isDemoPresentation = computed(() => authStore.user?.is_demo_account === true)
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
      label: '高风险待复核',
      value: Number(kpis?.high_risk_review_total || 0),
      tone: 'danger',
    },
    {
      key: 'pending',
      label: '待质控',
      value: Number(kpis?.qc_pending_total || 0),
      tone: 'warning',
    },
    {
      key: 'completed',
      label: '已完成',
      value: Number(kpis?.qc_completed_total || 0),
      tone: 'success',
    },
    {
      key: 'records',
      label: '纳入病历',
      value: Number(kpis?.records_total || 0),
      tone: 'brand',
    },
  ]
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

function countOf(item: ClinicalQcHomePriorityItem, status: string): number {
  return Math.max(0, Number(item.status_counts?.[status] || 0))
}

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

function formatPriorityTime(value?: string | null): string {
  if (!value) return '暂未返回'
  const parsed = dayjs(value)
  if (!parsed.isValid()) return '暂未返回'
  return parsed.isSame(dayjs(), 'day') ? parsed.format('HH:mm') : parsed.format('MM-DD HH:mm')
}

function disabledFutureDate(current: Dayjs) {
  return current.isAfter(dayjs(), 'day')
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
    path: '/workstation-v4',
    query: {
      source: 'dashboard',
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
    },
  })
}

function openQcResult(item: ClinicalQcHomePriorityItem) {
  void router.push({
    path: '/workstation-v4/records/final',
    query: {
      record_key: item.record_key,
      visit_id: item.visit_id,
    },
  })
}

async function fetchHome() {
  loading.value = true
  loadError.value = false
  try {
    const res = await ApiService.get<WorkstationHomePayload>('/api/v1/workstation/home', {
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

watch([departmentFilter, keyword], () => {
  if (syncingFromRoute.value) return
  void fetchHome()
})
</script>

<style scoped>
@import '../workstation-v4/styles/workstation-v4-view.css';

.qc-home-shell {
  background: #f5f5f7;
  color: #1d1d1f;
}
.qc-home-canvas {
  --qc-home-dashboard-columns: minmax(0, 1.88fr) minmax(320px, 0.72fr);
  display: grid;
  gap: 18px;
  min-height: calc(100vh - 64px);
}
.qc-home-header,
.qc-home-panel,
.qc-home-notice,
.qc-home-empty,
.qc-home-loading {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.035);
  backdrop-filter: blur(18px);
}
.qc-home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 17px 22px;
}
.qc-home-header__copy {
  min-width: 230px;
}
.qc-home-header h1,
.qc-home-panel h2 {
  margin: 0;
  font-weight: 700;
}
.qc-home-header h1 {
  font-size: 24px;
  line-height: 29px;
}
.qc-home-panel p {
  margin: 7px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}
.qc-home-scope {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  padding: 12px 16px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  font-weight: 600;
}
.qc-home-scope i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(29, 29, 31, 0.28);
}
.qc-home-scope__label {
  color: #0066cc;
}
.qc-home-scope__rule-set {
  color: #1d1d1f;
}
.qc-home-scope__time {
  margin-left: auto;
  color: rgba(29, 29, 31, 0.48);
  font-weight: 500;
}
.qc-home-kpis {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
}
.qc-home-kpi {
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  padding: 13px 20px 15px;
  position: relative;
}
.qc-home-kpi:last-child {
  border-right: 0;
}
.qc-home-kpi::before {
  background: #94a3b8;
  border-radius: 0 0 4px 4px;
  content: '';
  height: 3px;
  left: 20px;
  position: absolute;
  top: 0;
  width: 34px;
}
.qc-home-kpi.is-brand::before {
  background: #0066cc;
}
.qc-home-kpi.is-warning::before {
  background: #f59e0b;
}
.qc-home-kpi.is-success::before {
  background: #10b981;
}
.qc-home-kpi.is-danger::before {
  background: #ef4444;
}
.qc-home-kpi span {
  display: block;
  color: rgba(29, 29, 31, 0.55);
  font-size: 13px;
  font-weight: 600;
  line-height: 22px;
}
.qc-home-kpi strong {
  color: #1d1d1f;
  display: block;
  font-size: 26px;
  letter-spacing: -0.03em;
  line-height: 34px;
  margin: 8px 0 0;
}
.qc-home-kpi.is-brand strong {
  color: #0066cc;
}
.qc-home-kpi.is-warning strong {
  color: #c17a08;
}
.qc-home-kpi.is-success strong {
  color: #047857;
}
.qc-home-kpi.is-danger strong {
  color: #dc2626;
}
.qc-home-grid {
  display: grid;
  grid-template-columns: var(--qc-home-dashboard-columns);
  gap: 18px;
  align-items: stretch;
}
.qc-home-workspace {
  min-height: 480px;
}
.qc-home-analysis {
  display: grid;
  grid-template-columns: var(--qc-home-dashboard-columns);
  gap: 18px;
  align-items: stretch;
}
.qc-home-department-panel {
  grid-column: 1;
}
.qc-home-panel {
  padding: 20px 22px;
}
.qc-home-side-stack {
  display: grid;
  gap: 18px;
  height: 100%;
  align-content: stretch;
}
.qc-home-panel--health {
  display: grid;
  height: 100%;
  grid-template-rows: auto 1fr;
}
.qc-home-panel--queue .qc-home-panel__head {
  border-bottom: 0;
  padding-bottom: 8px;
}
.qc-home-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.qc-home-panel-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  min-height: 32px;
  padding: 0 2px;
  border: 0;
  background: transparent;
  color: #0066cc;
  cursor: pointer;
  font-size: 13px;
  font-weight: 650;
}
.qc-home-panel-link:hover {
  color: #004f9e;
}
.qc-home-panel-link:focus-visible,
.qc-home-priority-row:focus-visible {
  outline: 2px solid rgba(0, 102, 204, 0.42);
  outline-offset: 2px;
}
.qc-home-panel h2 {
  font-size: 17px;
  line-height: 22px;
}
.qc-home-priority-list {
  display: grid;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.075);
  border-radius: 12px;
}
.qc-home-priority-columns {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 105px 96px 106px 84px 82px;
  gap: 10px;
  padding: 11px 12px 9px 42px;
  background: rgba(0, 0, 0, 0.018);
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  font-weight: 650;
  line-height: 16px;
}
.qc-home-priority-columns span:not(:first-child, :nth-child(2)) {
  text-align: right;
}
.qc-home-priority-row {
  display: grid;
  grid-template-columns: 30px minmax(180px, 1fr) 105px 96px 106px 84px 82px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 74px;
  padding: 11px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  border-top: 0;
  border-right: 0;
  border-left: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition:
    background 160ms ease,
    color 160ms ease;
}
.qc-home-priority-row:last-child {
  border-bottom: 0;
}
.qc-home-priority-row:hover {
  background: rgba(0, 102, 204, 0.035);
}
.qc-home-priority-row__rank {
  color: rgba(29, 29, 31, 0.32);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-align: center;
}
.qc-home-priority-row__identity {
  min-width: 0;
}
.qc-home-priority-row__identity strong,
.qc-home-priority-row__identity span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-home-priority-row__department {
  color: rgba(29, 29, 31, 0.64);
  font-size: 12px;
  font-weight: 550;
  line-height: 18px;
  overflow-wrap: anywhere;
  text-align: left;
}
.qc-home-priority-row__identity strong {
  color: #1d1d1f;
  font-size: 15px;
  line-height: 22px;
}
.qc-home-priority-row__identity span {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
  line-height: 18px;
}
.qc-home-priority-row__metric {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  justify-content: flex-end;
  min-width: 0;
  white-space: nowrap;
}
.qc-home-priority-row__metric.is-defect {
  padding: 5px 7px;
  border: 1px solid rgba(239, 68, 68, 0.12);
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.055);
  color: #b42318;
}
.qc-home-priority-row__metric.is-gap {
  padding: 5px 7px;
  border: 1px solid rgba(0, 102, 204, 0.1);
  border-radius: 8px;
  background: rgba(0, 102, 204, 0.045);
  color: #a16207;
}
.qc-home-priority-row__metric span,
.qc-home-priority-row__metric small {
  color: rgba(29, 29, 31, 0.48);
  font-size: 11px;
}
.qc-home-priority-row__metric strong {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  line-height: 20px;
}
.qc-home-priority-row__time {
  min-width: 0;
  text-align: right;
}
.qc-home-priority-row__time span,
.qc-home-priority-row__time strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-home-priority-row__time span {
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  line-height: 16px;
}
.qc-home-priority-row__time strong {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}
.qc-home-priority-row__action {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
  color: #0066cc;
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}
.qc-home-priority-row__action svg {
  transition: transform 160ms ease;
}
.qc-home-priority-row:hover .qc-home-priority-row__action svg {
  transform: translateX(2px);
}
.qc-home-priority-scope {
  gap: 7px;
  padding: 8px 0 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(29, 29, 31, 0.62);
  font-size: 11px;
}
.qc-home-priority-scope .qc-home-scope__time {
  font-size: 11px;
}
.qc-home-health-list {
  display: grid;
  gap: 0;
  margin: 0;
}
.qc-home-health-list > div {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 2px 11px;
  align-items: center;
  padding: 13px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}
.qc-home-health-list > div:last-child {
  border-bottom: 0;
}
.qc-home-health-list dt,
.qc-home-health-list dd,
.qc-home-health-list small {
  margin: 0;
}
.qc-home-health-list dt {
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  line-height: 18px;
}
.qc-home-health-list dd {
  margin-top: 1px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 650;
  line-height: 20px;
}
.qc-home-health-list small {
  grid-column: 2;
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  line-height: 16px;
}
.qc-home-health-list__icon {
  display: grid;
  grid-row: 1 / span 2;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  background: rgba(0, 102, 204, 0.075);
  color: #0066cc;
}
.qc-home-health-list__icon.is-danger {
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
}
.qc-home-health-list__icon.is-success {
  background: rgba(16, 185, 129, 0.085);
  color: #047857;
}
.qc-home-health-list .is-danger {
  color: #dc2626;
}
.qc-home-defect-analysis {
  display: grid;
  gap: 14px;
}
.qc-home-defect-analysis__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px 18px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.025);
}
.qc-home-defect-analysis__control {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.qc-home-defect-analysis__control > span {
  color: rgba(29, 29, 31, 0.46);
  font-size: 11px;
  white-space: nowrap;
}
.qc-home-defect-analysis__control > div {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.045);
}
.qc-home-defect-analysis__control button {
  min-height: 28px;
  padding: 4px 9px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgba(29, 29, 31, 0.62);
  font: inherit;
  font-size: 11px;
  font-weight: 550;
  cursor: pointer;
  transition: 160ms ease;
}
.qc-home-defect-analysis__control button:hover {
  color: #0066cc;
}
.qc-home-defect-analysis__control button.is-active {
  background: #fff;
  color: #0066cc;
  font-weight: 650;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
.qc-home-defect-analysis__control button:focus-visible {
  outline: 2px solid rgba(0, 102, 204, 0.32);
  outline-offset: 1px;
}
.qc-home-defect-analysis__list {
  display: grid;
}
.qc-home-defect-analysis__row {
  display: grid;
  grid-template-columns: minmax(145px, 0.9fr) minmax(170px, 1.45fr) auto 18px;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 56px;
  padding: 8px 6px;
  border: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.065);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
}
button.qc-home-defect-analysis__row {
  cursor: pointer;
  transition:
    background 160ms ease,
    transform 160ms ease;
}
.qc-home-defect-analysis__row:last-of-type {
  border-bottom: 0;
}
button.qc-home-defect-analysis__row:hover,
.qc-home-defect-analysis__row.is-active {
  background: rgba(0, 102, 204, 0.045);
}
button.qc-home-defect-analysis__row:hover {
  transform: translateX(2px);
}
button.qc-home-defect-analysis__row:focus-visible {
  border-radius: 8px;
  outline: 2px solid rgba(0, 102, 204, 0.35);
  outline-offset: -2px;
}
.qc-home-defect-analysis__meta {
  min-width: 0;
}
.qc-home-defect-analysis__meta strong,
.qc-home-defect-analysis__meta span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-home-defect-analysis__meta strong {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
}
.qc-home-defect-analysis__meta span {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.46);
  font-size: 11px;
}
.qc-home-defect-analysis__metric {
  display: grid;
  grid-template-columns: minmax(90px, 1fr) 42px;
  align-items: center;
  gap: 10px;
}
.qc-home-defect-analysis__track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.075);
}
.qc-home-defect-analysis__track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #0066cc;
  transition: width 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}
.qc-home-defect-analysis__metric strong {
  color: #0066cc;
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}
.qc-home-defect-analysis__counts {
  display: flex;
  justify-content: flex-end;
  gap: 11px;
  min-width: 132px;
  font-size: 11px;
  white-space: nowrap;
}
.qc-home-defect-analysis__counts strong {
  color: #c2413a;
  font-weight: 650;
}
.qc-home-defect-analysis__counts span {
  color: #a16207;
}
.qc-home-defect-analysis__row > svg {
  color: rgba(0, 102, 204, 0.54);
}
.qc-home-defect-analysis__note {
  margin: 8px 6px 0;
  color: rgba(29, 29, 31, 0.46);
  font-size: 11px;
  line-height: 17px;
}
.qc-home-conclusion {
  display: grid;
  gap: 16px;
}
.qc-home-conclusion__content {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  align-items: center;
  gap: 22px;
}
.qc-home-conclusion__ring {
  display: grid;
  width: 132px;
  height: 132px;
  place-items: center;
  border-radius: 50%;
}
.qc-home-conclusion__ring > div {
  display: grid;
  width: 96px;
  height: 96px;
  place-content: center;
  border-radius: 50%;
  background: #fff;
  text-align: center;
}
.qc-home-conclusion__ring strong,
.qc-home-conclusion__ring span {
  display: block;
}
.qc-home-conclusion__ring strong {
  color: #1d1d1f;
  font-size: 26px;
  line-height: 30px;
}
.qc-home-conclusion__ring span {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 11px;
}
.qc-home-conclusion__legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
  padding: 0;
  margin: 0;
  list-style: none;
}
.qc-home-conclusion__legend li {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
}
.qc-home-conclusion__legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.qc-home-conclusion__legend small {
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
}
.qc-home-notice {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
}
.qc-home-notice span {
  flex: 1;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
.qc-home-notice--error {
  border-color: rgba(239, 68, 68, 0.2);
}
.qc-home-notice--error strong {
  color: #b91c1c;
}
.qc-home-empty {
  display: grid;
  min-height: 280px;
  place-items: center;
  padding: 28px;
}
.qc-home-loading {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 28px;
  color: rgba(29, 29, 31, 0.72);
}
.qc-home-loading :deep(.ant-spin-dot-item) {
  background-color: #0066cc;
}
.qc-home-loading strong,
.qc-home-loading span {
  display: block;
}
.qc-home-loading strong {
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 650;
  line-height: 22px;
}
.qc-home-loading span {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 13px;
  line-height: 20px;
}
@media (max-width: 1360px) {
  .qc-home-grid {
    grid-template-columns: 1fr;
  }
  .qc-home-workspace {
    min-height: auto;
  }
}
@media (max-width: 1100px) {
  .qc-home-priority-row {
    grid-template-columns: 28px minmax(0, 1fr) auto;
    gap: 10px;
  }
  .qc-home-priority-columns {
    display: none;
  }
  .qc-home-priority-row__identity {
    grid-column: 2;
  }
  .qc-home-priority-row__department {
    grid-column: 2;
    grid-row: 2;
    text-align: left;
  }
  .qc-home-priority-row__metric.is-defect {
    grid-column: 3;
    grid-row: 1;
  }
  .qc-home-priority-row__metric.is-gap,
  .qc-home-priority-row__time {
    grid-column: 2;
  }
  .qc-home-priority-row__metric.is-gap {
    grid-row: 3;
    justify-content: flex-start;
  }
  .qc-home-priority-row__time {
    grid-row: 4;
    text-align: left;
  }
  .qc-home-priority-row__action {
    grid-column: 3;
    grid-row: 2 / span 3;
    align-self: center;
  }
}
@media (max-width: 980px) {
  .qc-home-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .qc-home-header :deep(.flex.min-w-\[280px\]) {
    width: 100%;
  }
  .qc-home-kpis {
    grid-template-columns: repeat(2, 1fr);
  }
  .qc-home-kpi:nth-child(2) {
    border-right: 0;
  }
  .qc-home-kpi:nth-child(-n + 2) {
    border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  }
  .qc-home-analysis {
    grid-template-columns: 1fr;
  }
  .qc-home-defect-analysis__row {
    grid-template-columns: minmax(145px, 0.9fr) minmax(150px, 1.2fr) auto 18px;
  }
}
@media (max-width: 620px) {
  .qc-home-canvas {
    gap: 12px;
  }
  .qc-home-header,
  .qc-home-panel {
    padding: 17px;
  }
  .qc-home-header h1 {
    font-size: 23px;
  }
  .qc-home-kpis {
    grid-template-columns: 1fr;
  }
  .qc-home-kpi,
  .qc-home-kpi:nth-child(2) {
    border-right: 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  }
  .qc-home-kpi:last-child {
    border-bottom: 0;
  }
  .qc-home-conclusion__legend {
    grid-template-columns: 1fr;
  }
  .qc-home-defect-analysis__toolbar,
  .qc-home-defect-analysis__control {
    align-items: flex-start;
    flex-direction: column;
    width: 100%;
  }
  .qc-home-defect-analysis__control > div {
    flex-wrap: wrap;
    width: 100%;
  }
  .qc-home-defect-analysis__row {
    grid-template-columns: minmax(0, 1fr) 18px;
    gap: 7px 10px;
    padding: 11px 4px;
  }
  .qc-home-defect-analysis__metric,
  .qc-home-defect-analysis__counts {
    grid-column: 1;
  }
  .qc-home-defect-analysis__counts {
    justify-content: flex-start;
  }
  .qc-home-defect-analysis__row > svg {
    grid-column: 2;
    grid-row: 1 / span 3;
  }
  .qc-home-conclusion__content {
    grid-template-columns: 1fr;
    justify-items: center;
  }
  .qc-home-scope__time {
    width: 100%;
    margin-left: 0;
  }
}
</style>
