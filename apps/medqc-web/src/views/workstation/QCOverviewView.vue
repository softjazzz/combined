<template>
  <div class="qc-home-shell workstation-shell min-h-screen">
    <div class="custom-scrollbar h-screen overflow-y-auto px-5 py-7 xl:px-8">
      <main class="qc-home-canvas mx-auto w-full max-w-[1440px]">
        <section class="qc-home-header workstation-surface-enter">
          <div>
            <h1>质控首页概览</h1>
            <p>查看全院病历的泸县0609质控结果，并优先处理需要复核的病历。</p>
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
            class="qc-home-scope workstation-surface-enter"
            data-testid="home-scope"
          >
            <span class="qc-home-scope__label">当前范围</span>
            <span>{{ scopeHospitalText }}</span>
            <i />
            <span>{{ scopeDepartmentText }}</span>
            <i />
            <span>{{ scopeSceneText }}</span>
            <i />
            <span>{{ clinicalQc.scope.rule_set_key }} · {{ clinicalQc.scope.rule_set_version }}</span>
            <span class="qc-home-scope__time">生成于 {{ formatDateTime(clinicalQc.scope.generated_at) }}</span>
          </section>

          <section
            class="qc-home-kpis workstation-surface-enter"
            data-testid="home-kpis"
          >
            <article
              v-for="card in kpiCards"
              :key="card.key"
              :class="['qc-home-kpi', `is-${card.tone}`]"
            >
              <component
                :is="card.icon"
                class="qc-home-kpi__icon"
              />
              <div>
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
                <small>{{ card.desc }}</small>
              </div>
            </article>
          </section>

          <section
            class="qc-home-grid qc-home-workspace workstation-surface-enter"
            data-testid="home-workspace"
          >
            <section
              class="qc-home-panel"
              data-testid="priority-queue"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2>优先复核</h2>
                  <p>按确定问题、资料待核实、待判断的结构化结果排序。</p>
                </div>
                <a-button
                  type="link"
                  @click="openRecordPool"
                >
                  查看病历池
                </a-button>
              </header>

              <div
                v-if="clinicalQc.priority_items.length"
                class="qc-home-priority-list"
              >
                <article
                  v-for="item in clinicalQc.priority_items"
                  :key="item.record_key"
                  class="qc-home-priority-row"
                >
                  <div class="qc-home-priority-row__identity">
                    <strong>{{ item.patient_name || '未返回患者姓名' }}</strong>
                    <span>{{ item.department || '未分科室' }} · 住院号 {{ item.visit_id }}</span>
                  </div>
                  <div class="qc-home-priority-row__counts">
                    <span
                      v-if="countOf(item, 'non_compliant')"
                      class="is-danger"
                    >
                      确定问题 {{ countOf(item, 'non_compliant') }} 项
                    </span>
                    <span
                      v-if="countOf(item, 'data_gap')"
                      class="is-warning"
                    >
                      资料待核实 {{ countOf(item, 'data_gap') }} 项
                    </span>
                    <span
                      v-if="countOf(item, 'uncertain')"
                      class="is-neutral"
                    >
                      待判断 {{ countOf(item, 'uncertain') }} 项
                    </span>
                  </div>
                  <button
                    type="button"
                    class="qc-home-text-action"
                    @click="openRecordPool"
                  >
                    进入病历池
                  </button>
                </article>
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
                    <h2>数据运行状态</h2>
                    <p>系统数据状态不等同于医疗质控结论。</p>
                  </div>
                </header>
                <dl class="qc-home-health-list">
                  <div>
                    <dt>资料同步状态</dt>
                    <dd>{{ sourceStateText }}</dd>
                  </div>
                  <div>
                    <dt>运行中任务</dt>
                    <dd>{{ runningTaskText }}</dd>
                  </div>
                  <div v-if="!isDemoPresentation">
                    <dt>技术异常</dt>
                    <dd :class="{ 'is-danger': clinicalQc.data_health.technical_error_total > 0 }">
                      技术异常 {{ clinicalQc.data_health.technical_error_total }} 份
                    </dd>
                  </div>
                  <div>
                    <dt>最近成功质控</dt>
                    <dd>{{ formatDateTime(clinicalQc.data_health.last_successful_qc_at) }}</dd>
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
              class="qc-home-panel qc-home-coverage"
              data-testid="qc-coverage-chart"
              aria-labelledby="qc-coverage-title"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2 id="qc-coverage-title">
                    质控覆盖构成
                  </h2>
                  <p>
                    {{
                      isDemoPresentation
                        ? '按病历汇总质控完成与待处理情况。'
                        : '按病历汇总执行覆盖；结果校验异常仅反映系统数据状态。'
                    }}
                  </p>
                </div>
              </header>
              <div
                class="qc-home-coverage__bar"
                role="img"
                :aria-label="coverageAriaLabel"
              >
                <span
                  v-for="segment in visibleCoverageSegments"
                  :key="segment.key"
                  :class="['qc-home-coverage__segment', `is-${segment.tone}`]"
                  :style="{ width: `${segment.percent}%` }"
                />
              </div>
              <ul
                class="qc-home-coverage__legend"
                aria-label="质控覆盖构成图例"
              >
                <li
                  v-for="segment in visibleCoverageSegments"
                  :key="segment.key"
                >
                  <i
                    :class="`is-${segment.tone}`"
                    aria-hidden="true"
                  />
                  <span>{{ segment.label }} {{ segment.value }}</span>
                  <small>{{ segment.percent }}%</small>
                </li>
              </ul>
              <p
                v-if="!coverageScopeIsClosed"
                class="qc-home-chart-note is-warning"
              >
                统计范围待核实：三个覆盖状态与纳入病历数暂不一致。
              </p>
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

            <section
              class="qc-home-panel qc-home-department-panel"
              data-testid="department-distribution"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2>科室风险排行</h2>
                  <p>按高风险待复核病历数排序，辅助显示资料待核实。</p>
                </div>
              </header>
              <div
                v-if="departmentChartItems.length"
                class="qc-home-department-chart"
                data-testid="department-chart"
              >
                <div
                  v-for="item in departmentChartItems"
                  :key="item.department"
                  class="qc-home-department-chart__row"
                  data-testid="department-chart-row"
                >
                  <div class="qc-home-department-chart__meta">
                    <strong>{{ item.department }}</strong>
                    <span>纳入 {{ item.records_total }} 份</span>
                  </div>
                  <div
                    class="qc-home-department-chart__track"
                    aria-hidden="true"
                  >
                    <i :style="{ width: `${departmentRiskBarPercent(item)}%` }" />
                  </div>
                  <div class="qc-home-department-chart__counts">
                    <em>待复核 {{ item.high_risk_review_total }}</em>
                    <span v-if="item.data_gap_record_total">待核实 {{ item.data_gap_record_total }}</span>
                  </div>
                </div>
                <p
                  v-if="hiddenDepartmentCount"
                  class="qc-home-department-chart__note"
                >
                  按待复核数量排序，仅展示前 8 个科室；其余
                  {{ hiddenDepartmentCount }} 个科室已收起。
                </p>
              </div>
              <a-empty
                v-else
                description="当前范围内暂无科室汇总"
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
import { computed, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs, { type Dayjs } from 'dayjs'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import type {
  ClinicalQcHomeDepartmentItem,
  ClinicalQcHomePriorityItem,
  WorkstationHomePayload,
} from '@/views/workstation-v2/types'
import {
  FileDoneOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import HomeHeroBar from './components/HomeHeroBar.vue'

interface KpiCard {
  key: string
  label: string
  value: number
  desc: string
  tone: 'brand' | 'warning' | 'success' | 'danger'
  icon: Component
}

type ChartTone = 'success' | 'warning' | 'neutral'

interface CoverageSegment {
  key: 'completed' | 'pending' | 'technical'
  label: string
  value: number
  tone: ChartTone
  percent: number
}

interface ConclusionSegment {
  status: string
  label: string
  value: number
  color: string
  percent: number
}

const CONCLUSION_STATUS_META = [
  { status: 'non_compliant', label: '确定问题', color: '#ef4444' },
  { status: 'data_gap', label: '资料待核实', color: '#f59e0b' },
  { status: 'uncertain', label: '待判断', color: '#64748b' },
  { status: 'compliant', label: '合规', color: '#10b981' },
  { status: 'not_applicable', label: '不适用', color: '#cbd5e1' },
  { status: 'not_executed', label: '未执行', color: '#94a3b8' },
] as const

function withClosedPercent(
  segments: Array<Omit<CoverageSegment, 'percent'>>,
  denominator: number,
): CoverageSegment[] {
  if (!denominator) return segments.map((segment) => ({ ...segment, percent: 0 }))
  const shouldClose = segments.reduce((sum, segment) => sum + segment.value, 0) === denominator
  let accumulated = 0
  return segments.map((segment, index) => {
    const percent =
      shouldClose && index === segments.length - 1
        ? Number((100 - accumulated).toFixed(1))
        : Number(((segment.value / denominator) * 100).toFixed(1))
    accumulated += percent
    return { ...segment, percent }
  })
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
// 首次进入即处于加载态，避免请求尚未发起时短暂展示无内容的页面框架。
const loading = ref(true)
const loadError = ref(false)
const selectedDate = ref<Dayjs>(dayjs())
const departmentFilter = ref('all')
const keyword = ref('')
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
      key: 'records',
      label: '纳入病历',
      value: Number(kpis?.records_total || 0),
      desc: '当前范围内三坐标完整的病历',
      tone: 'brand',
      icon: FileDoneOutlined,
    },
    {
      key: 'pending',
      label: '待质控',
      value: Number(kpis?.qc_pending_total || 0),
      desc: '尚未形成可用最终结论',
      tone: 'warning',
      icon: SyncOutlined,
    },
    {
      key: 'completed',
      label: '已完成',
      value: Number(kpis?.qc_completed_total || 0),
      desc: '已交付 Canonical 最终结论',
      tone: 'success',
      icon: SafetyCertificateOutlined,
    },
    {
      key: 'risk',
      label: '高风险待复核',
      value: Number(kpis?.high_risk_review_total || 0),
      desc: '至少含一项确定问题的病历',
      tone: 'danger',
      icon: WarningOutlined,
    },
  ]
})

const coverageSegments = computed<CoverageSegment[]>(() => {
  const kpis = clinicalQc.value?.kpis
  const total = Math.max(0, Number(kpis?.records_total || 0))
  const values = [
    {
      key: 'completed' as const,
      label: '已完成',
      value: Math.max(0, Number(kpis?.qc_completed_total || 0)),
      tone: 'success' as const,
    },
    {
      key: 'pending' as const,
      label: '待质控',
      value: Math.max(0, Number(kpis?.qc_pending_total || 0)),
      tone: 'warning' as const,
    },
    {
      key: 'technical' as const,
      label: '结果校验异常',
      value: Math.max(0, Number(clinicalQc.value?.data_health.technical_error_total || 0)),
      tone: 'neutral' as const,
    },
  ]
  return withClosedPercent(values, total)
})
const visibleCoverageSegments = computed(() => {
  if (!isDemoPresentation.value) return coverageSegments.value
  const visible = coverageSegments.value.filter((segment) => segment.key !== 'technical')
  const visibleTotal = visible.reduce((sum, segment) => sum + segment.value, 0)
  return withClosedPercent(visible, visibleTotal)
})
const coverageAriaLabel = computed(() =>
  visibleCoverageSegments.value.map((segment) => `${segment.label} ${segment.value}`).join('，'),
)
const coverageScopeIsClosed = computed(() => {
  const total = Math.max(0, Number(clinicalQc.value?.kpis.records_total || 0))
  return coverageSegments.value.reduce((sum, segment) => sum + segment.value, 0) === total
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
  clinicalQc.value?.data_health.source_sync_status === 'unknown'
    ? '资料同步状态待核实'
    : '资料同步状态待核实',
)
const runningTaskText = computed(() =>
  clinicalQc.value?.data_health.running_task_state === 'unknown'
    ? '运行状态待接入'
    : '运行状态待接入',
)
const departmentChartItems = computed<ClinicalQcHomeDepartmentItem[]>(() => {
  const items = clinicalQc.value?.department_distribution || []
  return [...items]
    .sort(
      (left, right) =>
        right.high_risk_review_total - left.high_risk_review_total ||
        right.data_gap_record_total - left.data_gap_record_total ||
        right.records_total - left.records_total ||
        left.department.localeCompare(right.department, 'zh-CN'),
    )
    .slice(0, 8)
})
const hiddenDepartmentCount = computed(() =>
  Math.max(
    0,
    (clinicalQc.value?.department_distribution.length || 0) - departmentChartItems.value.length,
  ),
)
const departmentRiskMaximum = computed(() =>
  Math.max(1, ...departmentChartItems.value.map((item) => item.high_risk_review_total)),
)

function countOf(item: ClinicalQcHomePriorityItem, status: string): number {
  return Math.max(0, Number(item.status_counts?.[status] || 0))
}

function departmentRiskBarPercent(item: ClinicalQcHomeDepartmentItem): number {
  return Math.round((item.high_risk_review_total / departmentRiskMaximum.value) * 100)
}

function formatDateTime(value?: string | null): string {
  if (!value) return '暂未返回'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : '暂未返回'
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
  display: grid;
  gap: 18px;
  min-height: calc(100vh - 64px);
}
.qc-home-header,
.qc-home-panel,
.qc-home-scope,
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
  gap: 24px;
  padding: 22px 24px;
}
.qc-home-header h1,
.qc-home-panel h2 {
  margin: 0;
  font-weight: 700;
}
.qc-home-header h1 {
  font-size: 28px;
  line-height: 31px;
}
.qc-home-header p,
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
.qc-home-scope__time {
  margin-left: auto;
  color: rgba(29, 29, 31, 0.48);
  font-weight: 500;
}
.qc-home-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: #fff;
}
.qc-home-kpi {
  display: flex;
  gap: 12px;
  min-height: 118px;
  padding: 21px;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
}
.qc-home-kpi:last-child {
  border: 0;
}
.qc-home-kpi__icon {
  width: 34px;
  height: 34px;
  padding: 8px;
  border-radius: 10px;
  background: rgba(0, 102, 204, 0.09);
  color: #0066cc;
}
.qc-home-kpi.is-warning .qc-home-kpi__icon {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}
.qc-home-kpi.is-success .qc-home-kpi__icon {
  background: rgba(16, 185, 129, 0.11);
  color: #047857;
}
.qc-home-kpi.is-danger .qc-home-kpi__icon {
  background: rgba(239, 68, 68, 0.11);
  color: #dc2626;
}
.qc-home-kpi span,
.qc-home-kpi small {
  display: block;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 18px;
}
.qc-home-kpi strong {
  display: block;
  margin: 3px 0;
  font-size: 25px;
  line-height: 30px;
}
.qc-home-kpi small {
  color: rgba(29, 29, 31, 0.48);
}
.qc-home-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(310px, 0.85fr);
  gap: 18px;
}
.qc-home-analysis {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(300px, 1fr);
  gap: 18px;
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
  align-content: start;
}
.qc-home-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.qc-home-panel h2 {
  font-size: 17px;
  line-height: 22px;
}
.qc-home-priority-list {
  display: grid;
}
.qc-home-priority-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 18px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}
.qc-home-priority-row:last-child {
  border-bottom: 0;
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
.qc-home-priority-row__identity strong {
  font-size: 14px;
}
.qc-home-priority-row__identity span {
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
}
.qc-home-priority-row__counts {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.qc-home-priority-row__counts span {
  padding: 3px 7px;
  border-radius: 7px;
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.68);
  font-size: 12px;
  white-space: nowrap;
}
.qc-home-priority-row__counts .is-danger {
  background: rgba(239, 68, 68, 0.09);
  color: #c2410c;
}
.qc-home-priority-row__counts .is-warning {
  background: rgba(245, 158, 11, 0.11);
  color: #a16207;
}
.qc-home-text-action {
  border: 0;
  background: none;
  color: #0066cc;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.qc-home-health-list {
  display: grid;
  gap: 0;
  margin: 0;
}
.qc-home-health-list > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}
.qc-home-health-list > div:last-child {
  border-bottom: 0;
}
.qc-home-health-list dt,
.qc-home-health-list dd {
  margin: 0;
  font-size: 13px;
}
.qc-home-health-list dt {
  color: rgba(29, 29, 31, 0.6);
}
.qc-home-health-list dd {
  text-align: right;
  font-weight: 600;
}
.qc-home-health-list .is-danger {
  color: #dc2626;
}
.qc-home-coverage {
  display: grid;
  gap: 16px;
}
.qc-home-coverage__bar {
  display: flex;
  min-height: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.055);
}
.qc-home-coverage__segment {
  display: block;
  min-width: 0;
  transition: width 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}
.qc-home-coverage__segment.is-success,
.qc-home-coverage__legend i.is-success {
  background: #10b981;
}
.qc-home-coverage__segment.is-warning,
.qc-home-coverage__legend i.is-warning {
  background: #f59e0b;
}
.qc-home-coverage__segment.is-neutral,
.qc-home-coverage__legend i.is-neutral {
  background: #94a3b8;
}
.qc-home-coverage__legend {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 0;
  margin: 0;
  list-style: none;
}
.qc-home-coverage__legend li {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
}
.qc-home-coverage__legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.qc-home-coverage__legend small {
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
}
.qc-home-chart-note {
  margin: 0;
  font-size: 12px;
  line-height: 18px;
}
.qc-home-chart-note.is-warning {
  color: #a16207;
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
.qc-home-department-chart {
  display: grid;
  gap: 12px;
}
.qc-home-department-chart__row {
  display: grid;
  grid-template-columns: minmax(90px, 0.8fr) minmax(88px, 1.35fr) auto;
  align-items: center;
  gap: 10px;
}
.qc-home-department-chart__meta {
  min-width: 0;
}
.qc-home-department-chart__meta strong,
.qc-home-department-chart__meta span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-home-department-chart__meta strong {
  font-size: 13px;
}
.qc-home-department-chart__meta span {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 11px;
}
.qc-home-department-chart__track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
}
.qc-home-department-chart__track i {
  display: block;
  min-width: 2px;
  height: 100%;
  border-radius: inherit;
  background: #0066cc;
  transition: width 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}
.qc-home-department-chart__counts {
  min-width: 80px;
  text-align: right;
}
.qc-home-department-chart__counts em,
.qc-home-department-chart__counts span {
  display: block;
  font-size: 11px;
  font-style: normal;
  white-space: nowrap;
}
.qc-home-department-chart__counts em {
  color: #b45309;
  font-weight: 650;
}
.qc-home-department-chart__counts span {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.48);
}
.qc-home-department-chart__note {
  margin: 1px 0 0;
  color: rgba(29, 29, 31, 0.48);
  font-size: 11px;
  line-height: 17px;
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
  .qc-home-grid {
    grid-template-columns: 1fr;
  }
  .qc-home-analysis {
    grid-template-columns: 1fr;
  }
  .qc-home-department-panel {
    grid-column: auto;
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
  .qc-home-priority-row {
    grid-template-columns: 1fr;
    gap: 9px;
  }
  .qc-home-coverage__legend,
  .qc-home-conclusion__legend {
    grid-template-columns: 1fr;
  }
  .qc-home-conclusion__content {
    grid-template-columns: 1fr;
    justify-items: center;
  }
  .qc-home-priority-row__counts {
    justify-content: flex-start;
  }
  .qc-home-text-action {
    justify-self: start;
  }
  .qc-home-scope__time {
    width: 100%;
    margin-left: 0;
  }
}
</style>
