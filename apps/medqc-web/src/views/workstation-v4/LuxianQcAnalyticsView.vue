<template>
  <div class="analytics-shell custom-scrollbar">
    <main class="analytics-canvas">
      <section class="analytics-command-surface">
        <div class="analytics-heading">
          <div
            v-if="isDepartmentReport"
            class="analytics-department-title"
          >
            <div class="analytics-title-row">
              <h1>{{ `${activeDepartmentName}质控分析` }}</h1>
              <span class="analytics-mode-chip">终末质控</span>
            </div>
          </div>
          <div v-else>
            <p class="analytics-eyebrow">
              全院临时范围 · 终末质控
            </p>
            <h1>质控统计分析</h1>
            <p>
              {{
                confirmedResultsOnly
                  ? '基于已完成终末质控任务的确定问题统计分析。'
                  : '聚焦已完成任务中可交付的 Canonical 结果，不混入技术异常。'
              }}
            </p>
          </div>

          <div
            class="analytics-toolbar"
            aria-label="统计筛选"
          >
            <a-range-picker
              v-model:value="dateRange"
              show-time
              value-format="YYYY-MM-DDTHH:mm:ss"
              aria-label="质控完成时间范围"
            />
            <a-select
              v-if="!isDepartmentReport"
              v-model:value="department"
              allow-clear
              placeholder="全部科室"
              aria-label="筛选科室"
              :options="departmentOptions"
            />
            <a-input
              v-model:value="jobId"
              allow-clear
              placeholder="已完成任务 ID（可选）"
              aria-label="已完成任务 ID"
            />
            <a-button
              type="primary"
              :loading="loading"
              @click="handleQuery()"
            >
              查询
            </a-button>
            <a-button
              v-if="isDepartmentReport"
              data-testid="analytics-return-hospital"
              @click="returnToHospitalAnalytics"
            >
              返回全院
            </a-button>
            <a-button @click="resetFilters">
              重置
            </a-button>
          </div>
        </div>

        <div
          v-if="payload && !isDepartmentReport"
          class="analytics-context"
          data-testid="analytics-scope"
        >
          <div class="analytics-scope-copy">
            <span>按质控完成时间</span><i aria-hidden="true" />
            <span>{{ payload.scope.department || '全部科室' }}</span><i aria-hidden="true" />
            <span>泸县0609终末质控</span>
            <small>版本 {{ payload.scope.rule_set_version }}</small>
          </div>
          <div
            v-if="!confirmedResultsOnly"
            class="analytics-health-indicator"
            :class="{ 'has-attention': payload.data_health.canonical_invalid_or_missing_total > 0 }"
            data-testid="analytics-data-health"
          >
            <span>数据状态</span>
            <strong v-if="payload.data_health.canonical_invalid_or_missing_total">
              {{ payload.data_health.canonical_invalid_or_missing_total.toLocaleString() }}
              份历史候选待核验
            </strong>
            <strong v-else>已交付结果可用</strong>
            <small>截至 {{ formatTime(payload.scope.generated_at) }}</small>
          </div>
        </div>
      </section>

      <section
        v-if="error"
        class="analytics-notice analytics-surface"
        data-testid="analytics-error"
        role="alert"
      >
        <div>
          <strong>统计范围暂时无法加载</strong>
          <span>{{ error }}</span>
        </div>
        <a-button
          size="small"
          @click="fetchAnalytics()"
        >
          重新加载
        </a-button>
      </section>

      <section
        v-else-if="loading"
        class="analytics-loading analytics-surface"
        data-testid="analytics-loading"
        aria-live="polite"
      >
        <a-spin size="large" />
        <div>
          <strong>正在汇总统计范围</strong>
          <span>{{
            confirmedResultsOnly
              ? '正在汇总已完成任务的质控统计结果。'
              : '正在核对已完成任务与 Canonical 结果。'
          }}</span>
        </div>
      </section>

      <template v-else-if="payload">
        <section
          class="analytics-kpis"
          :class="{ 'is-confirmed-only': confirmedResultsOnly }"
          data-testid="analytics-kpis"
        >
          <article
            v-for="card in kpiCards"
            :key="card.label"
            :class="['analytics-kpi', `is-${card.tone}`]"
            data-testid="analytics-kpi"
          >
            <span>{{ card.label }}</span>
            <strong>{{ card.value.toLocaleString() }}</strong>
          </article>
        </section>

        <section
          v-if="payload.kpis.completed_event_total === 0"
          class="analytics-empty analytics-surface"
        >
          <a-empty description="当前范围内暂无完成质控事件" />
        </section>

        <template v-else>
          <section class="analytics-overview-grid">
            <article
              class="analytics-surface analytics-panel analytics-conclusion-panel"
              data-testid="analytics-conclusion-structure"
            >
              <header class="panel-heading">
                <div>
                  <p>全院结论结构</p>
                  <h2>质控结论分布</h2>
                </div>
                <span class="panel-note">共 {{ statusTotal.toLocaleString() }} 条有效结论</span>
              </header>
              <div class="conclusion-layout">
                <div
                  class="status-ring"
                  role="img"
                  :aria-label="statusRingAriaLabel"
                  :style="{ background: statusRingBackground }"
                >
                  <span aria-hidden="true"><strong>{{ primaryConcernTotal.toLocaleString() }}</strong><small>需重点关注</small></span>
                </div>
                <ul class="status-legend">
                  <li
                    v-for="item in statusItems"
                    :key="item.status"
                  >
                    <i
                      aria-hidden="true"
                      :style="{ background: item.color }"
                    />
                    <span>{{ item.label }}</span>
                    <strong>{{ item.count.toLocaleString() }}</strong>
                  </li>
                </ul>
              </div>
            </article>

            <article
              class="analytics-surface analytics-panel analytics-rhythm-panel"
              data-testid="analytics-trend-panel"
            >
              <header class="panel-heading">
                <div>
                  <p>完成节奏</p>
                  <h2>近期质控完成量</h2>
                </div>
                <span
                  v-if="hasTrend"
                  class="panel-note"
                >按自然日</span>
              </header>
              <div
                v-if="hasTrend"
                class="rhythm-chart"
                data-testid="analytics-trend"
                role="img"
                :aria-label="trendChartAriaLabel"
              >
                <div
                  v-for="item in completionSeries"
                  :key="item.bucket"
                  class="rhythm-bar"
                >
                  <span>{{ item.completed_event_total.toLocaleString() }}</span>
                  <div class="rhythm-bar-track">
                    <i :style="{ height: `${trendPercent(item.completed_event_total)}%` }" />
                  </div>
                  <small>{{ item.bucket.slice(5) }}</small>
                </div>
              </div>
              <div
                v-else
                class="rhythm-empty"
              >
                <strong>尚未形成连续时间序列</strong>
                <span>有足够的真实完成日期后，这里会自动显示完成节奏。</span>
              </div>
            </article>
          </section>

          <section class="analytics-detail-grid">
            <article
              v-if="!isDepartmentReport"
              class="analytics-surface analytics-panel analytics-department-panel"
              data-testid="analytics-department-chart"
            >
              <header class="panel-heading">
                <div>
                  <p>整改优先级</p>
                  <h2>科室风险排行</h2>
                </div>
                <span class="panel-note">{{
                  confirmedResultsOnly
                    ? '仅统计确定问题病历'
                    : '红：确定问题 · 橙：资料待核实 · 灰：待判断'
                }}</span>
              </header>
              <div
                v-if="departmentItems.length"
                class="department-chart"
              >
                <button
                  v-for="(item, index) in departmentItems"
                  :key="item.department"
                  type="button"
                  class="department-row"
                  @click="openDepartmentReport(item.department)"
                >
                  <span class="department-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                  <span
                    class="department-name"
                    :title="item.department"
                  >{{ item.department }}</span>
                  <span
                    class="department-track"
                    role="img"
                    :aria-label="riskBarAriaLabel(item.department, item)"
                  >
                    <i
                      v-if="item.primaryNonCompliant"
                      class="bar-danger"
                      :style="{
                        width: `${barPercent(item.primaryNonCompliant, departmentMax)}%`,
                      }"
                    />
                    <i
                      v-if="!confirmedResultsOnly && item.primaryDataGap"
                      class="bar-warning"
                      :style="{
                        width: `${barPercent(item.primaryDataGap, departmentMax)}%`,
                      }"
                    />
                    <i
                      v-if="!confirmedResultsOnly && item.primaryUncertain"
                      class="bar-uncertain"
                      :style="{
                        width: `${barPercent(item.primaryUncertain, departmentMax)}%`,
                      }"
                    />
                  </span>
                  <strong>{{ item.problemTotal.toLocaleString() }}</strong>
                </button>
              </div>
              <a-empty
                v-else
                description="暂无可展示的科室统计"
                :image-style="{ height: '56px' }"
              />
            </article>

            <article
              class="analytics-surface analytics-panel analytics-physician-panel"
              :class="{ 'is-full-span': isDepartmentReport }"
              data-testid="analytics-physician-chart"
            >
              <header class="panel-heading">
                <div>
                  <p>责任归属</p>
                  <h2>主治医师风险排行</h2>
                </div>
                <span class="panel-note">按病历主治医师归属</span>
              </header>
              <div
                v-if="physicianItems.length"
                class="physician-chart"
              >
                <div
                  v-for="(item, index) in physicianItems"
                  :key="item.physician"
                  :class="[
                    'physician-row',
                    { 'is-unassigned': item.physician === '未登记主治医师' },
                  ]"
                >
                  <span class="department-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                  <span
                    class="physician-name"
                    :title="item.physician"
                  >{{ item.physician }}</span>
                  <span
                    class="department-track"
                    role="img"
                    :aria-label="riskBarAriaLabel(item.physician, item)"
                  >
                    <i
                      v-if="item.primaryNonCompliant"
                      class="bar-danger"
                      :style="{
                        width: `${barPercent(item.primaryNonCompliant, physicianMax)}%`,
                      }"
                    />
                    <i
                      v-if="!confirmedResultsOnly && item.primaryDataGap"
                      class="bar-warning"
                      :style="{ width: `${barPercent(item.primaryDataGap, physicianMax)}%` }"
                    />
                    <i
                      v-if="!confirmedResultsOnly && item.primaryUncertain"
                      class="bar-uncertain"
                      :style="{
                        width: `${barPercent(item.primaryUncertain, physicianMax)}%`,
                      }"
                    />
                  </span>
                  <strong>{{ item.problemTotal.toLocaleString() }}</strong>
                </div>
              </div>
              <a-empty
                v-else
                description="暂无可归属的医师风险统计"
                :image-style="{ height: '56px' }"
              />
            </article>

            <article
              class="analytics-surface analytics-panel analytics-rule-panel"
              data-testid="analytics-rule-chart"
            >
              <header class="panel-heading">
                <div>
                  <p>问题聚焦</p>
                  <h2>质控点问题 Top 5</h2>
                </div>
                <span class="panel-note">点击质控点，进入病历池查看命中病历</span>
              </header>
              <ol
                v-if="ruleItems.length"
                class="rule-list"
              >
                <li
                  v-for="(item, index) in ruleItems"
                  :key="item.rule_id"
                >
                  <button
                    type="button"
                    :title="`查看命中 ${item.rule_id} 的病历`"
                    @click="drillDown({ rule_id: item.rule_id, rule_name: item.rule_name })"
                  >
                    <span class="rule-rank">{{ index + 1 }}</span>
                    <span class="rule-copy">
                      <small>{{ item.rule_id }}</small>
                      <strong>{{ item.rule_name }}</strong>
                      <span class="rule-breakdown">
                        <em
                          v-if="item.non_compliant_count"
                          class="is-danger"
                        >确定 {{ item.non_compliant_count.toLocaleString() }}</em>
                        <em
                          v-if="!confirmedResultsOnly && item.data_gap_count"
                          class="is-warning"
                        >待核实 {{ item.data_gap_count.toLocaleString() }}</em>
                        <em
                          v-if="!confirmedResultsOnly && item.uncertain_count"
                          class="is-neutral"
                        >待判断 {{ item.uncertain_count.toLocaleString() }}</em>
                      </span>
                    </span>
                    <span class="rule-count">
                      <strong>{{ ruleConcernTotal(item).toLocaleString() }}</strong>
                      <small>问题结果</small>
                    </span>
                  </button>
                </li>
              </ol>
              <a-empty
                v-else
                description="暂无可展示的质控点问题"
                :image-style="{ height: '56px' }"
              />
            </article>
          </section>
        </template>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { ApiService } from '@/services/apiService'
import {
  ANALYTICS_PROBLEM_RESULT_STATUS_PARAM,
  ANALYTICS_WORKLIST_PATH,
} from './utils/analyticsDrilldown'
import { QC_RESULT_STATUS_LABELS } from './utils/qcResultStatusLabels'

type Status =
  | 'non_compliant'
  | 'data_gap'
  | 'uncertain'
  | 'compliant'
  | 'not_applicable'
  | 'not_executed'

interface RiskDistributionMetrics {
  distinct_record_total: number
  non_compliant_record_total: number
  data_gap_record_total: number
  uncertain_record_total: number
  problem_record_total?: number
  primary_non_compliant_record_total?: number
  primary_data_gap_record_total?: number
  primary_uncertain_record_total?: number
}

interface ResolvedRiskMetrics {
  primaryNonCompliant: number
  primaryDataGap: number
  primaryUncertain: number
  problemTotal: number
}

interface AnalyticsPayload {
  scope: {
    time_basis: 'qc_completed_at'
    completed_from: string | null
    completed_to: string | null
    department: string | null
    job_id: string | null
    rule_set_key: string
    rule_set_version: string
    generated_at: string
  }
  kpis: {
    distinct_record_total: number
    completed_event_total: number
    records_with_non_compliant: number
    records_with_data_gap: number
    canonical_invalid_or_missing_total: number
  }
  status_distribution: Array<{ status: Status; count: number }>
  department_options?: string[]
  department_distribution: Array<RiskDistributionMetrics & { department: string }>
  physician_distribution: Array<RiskDistributionMetrics & { physician: string }>
  rule_distribution: Array<{
    rule_id: string
    rule_name: string
    non_compliant_count: number
    data_gap_count: number
    uncertain_count: number
    evaluated_count: number
  }>
  completion_time_series: Array<{ bucket: string; completed_event_total: number }> | null
  data_health: { canonical_invalid_or_missing_total: number }
}

const DEMO_HIDDEN_STATUSES = new Set<Status>(['data_gap', 'uncertain'])
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const router = useRouter()
const route = useRoute()
const { confirmedResultsOnly } = useQcResultVisibility()
const loading = ref(true)
const error = ref('')
const payload = ref<AnalyticsPayload | null>(null)
const dateRange = ref<[string, string]>()
const department = ref<string>()
const jobId = ref('')
const cachedDepartmentOptions = ref<string[]>([])
const routeScopeInitialized = ref(false)
let lastSyncedRouteSignature = ''

function cleanDateValue(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

function normalizeDepartmentList(values: unknown): string[] {
  if (!Array.isArray(values)) return []
  return [
    ...new Set(
      values
        .map((item) => (typeof item === 'string' ? item.trim() : ''))
        .filter(Boolean),
    ),
  ]
}

function routeQueryText(name: string) {
  const value = route.query[name]
  return typeof value === 'string' ? value.trim() : ''
}

const isDepartmentReport = computed(
  () => routeQueryText('view') === 'department' && Boolean(routeQueryText('department')),
)
const activeDepartmentName = computed(
  () => routeQueryText('department') || department.value || '当前科室',
)

const STATUS_META: Array<{ status: Status; label: string; color: string }> = [
  { status: 'non_compliant', label: QC_RESULT_STATUS_LABELS.non_compliant, color: '#ef4444' },
  { status: 'data_gap', label: QC_RESULT_STATUS_LABELS.data_gap, color: '#f59e0b' },
  { status: 'uncertain', label: QC_RESULT_STATUS_LABELS.uncertain, color: '#64748b' },
  { status: 'compliant', label: '合规', color: '#10b981' },
  { status: 'not_applicable', label: '不适用', color: '#94a3b8' },
  { status: 'not_executed', label: '未执行', color: '#cbd5e1' },
]

function nonNegativeCount(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

function resolveRiskMetrics(item: RiskDistributionMetrics): ResolvedRiskMetrics {
  const nc = nonNegativeCount(item.non_compliant_record_total)
  if (confirmedResultsOnly.value) {
    return {
      primaryNonCompliant: nc,
      primaryDataGap: 0,
      primaryUncertain: 0,
      problemTotal: nc,
    }
  }
  const hasPrimaryBuckets =
    item.primary_non_compliant_record_total != null ||
    item.primary_data_gap_record_total != null ||
    item.primary_uncertain_record_total != null
  if (hasPrimaryBuckets) {
    const primaryNonCompliant = nonNegativeCount(
      item.primary_non_compliant_record_total ?? item.non_compliant_record_total,
    )
    const primaryDataGap = nonNegativeCount(item.primary_data_gap_record_total)
    const primaryUncertain = nonNegativeCount(item.primary_uncertain_record_total)
    const bucketSum = primaryNonCompliant + primaryDataGap + primaryUncertain
    const problemTotal =
      item.problem_record_total != null
        ? nonNegativeCount(item.problem_record_total)
        : bucketSum
    return {
      primaryNonCompliant,
      primaryDataGap,
      primaryUncertain,
      problemTotal,
    }
  }
  // 向后兼容无新字段的旧返回：按 non_compliant > data_gap > uncertain 互斥分桶，
  // 并在 distinct_record_total > 0 时限制不超过去重总病历数，同时计入 uncertain。
  const dg = nonNegativeCount(item.data_gap_record_total)
  const unc = nonNegativeCount(item.uncertain_record_total)
  const distinctTotal = nonNegativeCount(item.distinct_record_total)
  const explicitProblem =
    item.problem_record_total != null ? nonNegativeCount(item.problem_record_total) : null
  const cap =
    distinctTotal > 0
      ? explicitProblem != null
        ? Math.min(explicitProblem, distinctTotal)
        : distinctTotal
      : explicitProblem
  if (cap != null) {
    const primaryNonCompliant = Math.min(nc, cap)
    const primaryDataGap = Math.min(dg, Math.max(0, cap - primaryNonCompliant))
    const primaryUncertain = Math.min(unc, Math.max(0, cap - primaryNonCompliant - primaryDataGap))
    const problemTotal =
      explicitProblem != null
        ? explicitProblem
        : primaryNonCompliant + primaryDataGap + primaryUncertain
    return {
      primaryNonCompliant,
      primaryDataGap,
      primaryUncertain,
      problemTotal,
    }
  }
  return {
    primaryNonCompliant: nc,
    primaryDataGap: dg,
    primaryUncertain: unc,
    problemTotal: nc + dg + unc,
  }
}

const departmentOptions = computed(() => {
  const fromPayloadOptions = normalizeDepartmentList(payload.value?.department_options)
  const fromDistribution = normalizeDepartmentList(
    (payload.value?.department_distribution || []).map((item) => item.department),
  )
  const selected = department.value?.trim() ? [department.value.trim()] : []
  const merged = [
    ...new Set([
      ...cachedDepartmentOptions.value,
      ...fromPayloadOptions,
      ...fromDistribution,
      ...selected,
    ]),
  ]
  return merged.map((dept) => ({ label: dept, value: dept }))
})
const statusItems = computed(() =>
  STATUS_META.filter((meta) => !confirmedResultsOnly.value || !DEMO_HIDDEN_STATUSES.has(meta.status))
    .map((meta) => ({
      ...meta,
      count: Number(
        payload.value?.status_distribution.find((item) => item.status === meta.status)?.count || 0,
      ),
    }))
    .filter((item) => item.count > 0),
)
const statusTotal = computed(() => statusItems.value.reduce((total, item) => total + item.count, 0))
const primaryConcernTotal = computed(() =>
  statusItems.value
    .filter((item) => ['non_compliant', 'data_gap', 'uncertain'].includes(item.status))
    .reduce((total, item) => total + item.count, 0),
)
const statusRingBackground = computed(() => {
  if (!statusTotal.value) return 'transparent'
  let offset = 0
  return `conic-gradient(${statusItems.value
    .map((item) => {
      const start = offset
      offset += (item.count / statusTotal.value) * 100
      return `${item.color} ${start}% ${offset}%`
    })
    .join(', ')})`
})
const departmentItems = computed(() =>
  (payload.value?.department_distribution || [])
    .map((item) => ({ ...item, ...resolveRiskMetrics(item) }))
    .filter((item) => item.problemTotal > 0)
    .sort((a, b) =>
      confirmedResultsOnly.value
        ? b.primaryNonCompliant - a.primaryNonCompliant ||
          a.department.localeCompare(b.department)
        : b.primaryNonCompliant - a.primaryNonCompliant ||
          b.problemTotal - a.problemTotal ||
          b.primaryDataGap - a.primaryDataGap ||
          b.primaryUncertain - a.primaryUncertain ||
          a.department.localeCompare(b.department),
    )
    .slice(0, 8),
)
const departmentMax = computed(() =>
  Math.max(
    1,
    ...departmentItems.value.map((item) =>
      Math.max(
        item.problemTotal,
        item.primaryNonCompliant + item.primaryDataGap + item.primaryUncertain,
      ),
    ),
  ),
)
const physicianItems = computed(() =>
  (payload.value?.physician_distribution || [])
    .map((item) => ({ ...item, ...resolveRiskMetrics(item) }))
    .filter((item) => item.problemTotal > 0)
    .sort((a, b) =>
      confirmedResultsOnly.value
        ? b.primaryNonCompliant - a.primaryNonCompliant ||
          a.physician.localeCompare(b.physician)
        : b.primaryNonCompliant - a.primaryNonCompliant ||
          b.problemTotal - a.problemTotal ||
          b.primaryDataGap - a.primaryDataGap ||
          b.primaryUncertain - a.primaryUncertain ||
          a.physician.localeCompare(b.physician),
    )
    .slice(0, 8),
)
const physicianMax = computed(() =>
  Math.max(
    1,
    ...physicianItems.value.map((item) =>
      Math.max(
        item.problemTotal,
        item.primaryNonCompliant + item.primaryDataGap + item.primaryUncertain,
      ),
    ),
  ),
)
const ruleItems = computed(() =>
  [...(payload.value?.rule_distribution || [])]
    .filter((item) => ruleConcernTotal(item) > 0)
    .sort((a, b) =>
      confirmedResultsOnly.value
        ? b.non_compliant_count - a.non_compliant_count || a.rule_id.localeCompare(b.rule_id)
        : b.non_compliant_count - a.non_compliant_count ||
          b.data_gap_count - a.data_gap_count ||
          b.uncertain_count - a.uncertain_count ||
          a.rule_id.localeCompare(b.rule_id),
    )
    .slice(0, 5),
)
const completionSeries = computed(() => payload.value?.completion_time_series || [])
const hasTrend = computed(() => completionSeries.value.length >= 2)
const statusRingAriaLabel = computed(() => {
  if (!statusTotal.value) return '质控结论分布：暂无有效结论'
  const breakdown = statusItems.value
    .map((item) => `${item.label} ${item.count.toLocaleString()} 条`)
    .join('，')
  return `质控结论分布：共 ${statusTotal.value.toLocaleString()} 条有效结论，需重点关注 ${primaryConcernTotal.value.toLocaleString()} 条；${breakdown}`
})
const trendChartAriaLabel = computed(() => {
  if (!completionSeries.value.length) return '近期质控完成量趋势：暂无连续时间序列'
  const summary = completionSeries.value
    .map((item) => `${item.bucket} 完成 ${item.completed_event_total.toLocaleString()} 次`)
    .join('，')
  return `近期质控完成量趋势（共 ${completionSeries.value.length} 天）：${summary}`
})
const kpiCards = computed(() => {
  const cards = [
    {
      label: '纳入病历',
      value: payload.value?.kpis.distinct_record_total || 0,
      detail: '按三坐标去重',
      tone: 'brand',
    },
    {
      label: '质控事件',
      value: payload.value?.kpis.completed_event_total || 0,
      detail: '已完成根任务',
      tone: 'neutral',
    },
    {
      label: '需优先处理',
      value: payload.value?.kpis.records_with_non_compliant || 0,
      detail: '至少一项确定问题',
      tone: 'danger',
    },
  ]
  if (!confirmedResultsOnly.value) {
    cards.push({
      label: '资料待核实',
      value: payload.value?.kpis.records_with_data_gap || 0,
      detail: '至少一项资料待核实',
      tone: 'warning',
    })
  }
  return cards
})

function formatTime(value: string) {
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : '暂未返回'
}
function barPercent(value: number, maximum: number) {
  if (value <= 0 || maximum <= 0) return 0
  return Math.min(100, Math.floor((value * 10000) / maximum) / 100)
}
function trendPercent(value: number) {
  const maximum = Math.max(1, ...completionSeries.value.map((item) => item.completed_event_total))
  return Math.min(100, Math.max(10, Math.round((value / maximum) * 100)))
}
function riskBarAriaLabel(name: string, item: ResolvedRiskMetrics) {
  if (confirmedResultsOnly.value) {
    return `${name}风险分布：共 ${item.problemTotal.toLocaleString()} 份确定问题病历`
  }
  return `${name}风险分布：共 ${item.problemTotal.toLocaleString()} 份问题病历（确定问题 ${item.primaryNonCompliant.toLocaleString()}，资料待核实 ${item.primaryDataGap.toLocaleString()}，待判断 ${item.primaryUncertain.toLocaleString()}）`
}
function ruleConcernTotal(item: AnalyticsPayload['rule_distribution'][number]) {
  if (confirmedResultsOnly.value) return item.non_compliant_count
  return item.non_compliant_count + item.data_gap_count + item.uncertain_count
}
function querySignature(query: Record<string, unknown>): string {
  const pick = (key: string) => {
    const raw = query[key]
    const value = Array.isArray(raw) ? raw[0] : raw
    return typeof value === 'string' ? value.trim() : ''
  }
  return [
    pick('view'),
    pick('department'),
    pick('completed_from'),
    pick('completed_to'),
    pick('job_id'),
  ].join('|')
}

function buildSyncedQuery(): Record<string, string | undefined> {
  const completedFrom = cleanDateValue(dateRange.value?.[0])
  const completedTo = cleanDateValue(dateRange.value?.[1])
  const dept = department.value?.trim() || undefined
  const trimmedJobId = jobId.value.trim() || undefined
  const nextQuery: Record<string, string | undefined> = {}
  if (isDepartmentReport.value && dept) nextQuery.view = 'department'
  if (dept) nextQuery.department = dept
  if (completedFrom) nextQuery.completed_from = completedFrom
  if (completedTo) nextQuery.completed_to = completedTo
  if (trimmedJobId) nextQuery.job_id = trimmedJobId
  return nextQuery
}

async function syncFiltersToRoute() {
  if (typeof router.replace !== 'function') return
  const nextQuery = buildSyncedQuery()
  const nextSig = querySignature(nextQuery)
  const currentSig = querySignature((route.query || {}) as Record<string, unknown>)
  if (nextSig === currentSig) return
  lastSyncedRouteSignature = nextSig
  await router.replace({
    path: route.path || '/workstation-v5/stats',
    query: nextQuery,
  })
}

async function handleQuery() {
  const trimmedJobId = jobId.value.trim()
  if (trimmedJobId && !UUID_PATTERN.test(trimmedJobId)) {
    analyticsAbortController?.abort()
    analyticsAbortController = null
    loading.value = false
    error.value = '任务 ID 格式不正确，请输入有效的 UUID'
    return
  }
  await syncFiltersToRoute()
  await fetchAnalytics()
}

async function resetFilters() {
  dateRange.value = undefined
  department.value = isDepartmentReport.value ? activeDepartmentName.value : undefined
  jobId.value = ''
  await syncFiltersToRoute()
  await fetchAnalytics()
}

function openDepartmentReport(departmentName: string) {
  void router.push({
    path: '/workstation-v5/stats',
    query: {
      view: 'department',
      department: departmentName,
      completed_from: cleanDateValue(dateRange.value?.[0]),
      completed_to: cleanDateValue(dateRange.value?.[1]),
      job_id: jobId.value.trim() || undefined,
    },
  })
}

function returnToHospitalAnalytics() {
  void router.push({
    path: '/workstation-v5/stats',
    query: {
      completed_from: cleanDateValue(dateRange.value?.[0]),
      completed_to: cleanDateValue(dateRange.value?.[1]),
      job_id: jobId.value.trim() || undefined,
    },
  })
}

function drillDown(filters: {
  department?: string
  rule_id?: string
  rule_name?: string
  result_status?: string
}) {
  const defaultRuleResultStatus = confirmedResultsOnly.value
    ? 'non_compliant'
    : ANALYTICS_PROBLEM_RESULT_STATUS_PARAM
  const resultStatus =
    filters.result_status ?? (filters.rule_id ? defaultRuleResultStatus : undefined)
  void router.push({
    // 下钻目标是病历池列表；工作台根路径是首页总览，不承载统计筛选
    path: ANALYTICS_WORKLIST_PATH,
    query: {
      source: 'analytics',
      analytics_scope: 'final',
      department: filters.department || department.value,
      analytics_completed_from: cleanDateValue(dateRange.value?.[0]),
      analytics_completed_to: cleanDateValue(dateRange.value?.[1]),
      analytics_job_id: jobId.value.trim() || undefined,
      analytics_rule_id: filters.rule_id,
      analytics_result_status: resultStatus,
      // 仅供病历池展示下钻上下文，不参与后端筛选
      analytics_rule_name: filters.rule_name || undefined,
    },
  })
}

let analyticsRequestSeq = 0
let analyticsAbortController: AbortController | null = null

async function fetchAnalytics() {
  const trimmedJobId = jobId.value.trim()
  if (trimmedJobId && !UUID_PATTERN.test(trimmedJobId)) {
    analyticsAbortController?.abort()
    analyticsAbortController = null
    loading.value = false
    error.value = '任务 ID 格式不正确，请输入有效的 UUID'
    return
  }

  const requestSeq = ++analyticsRequestSeq
  analyticsAbortController?.abort()
  const controller = new AbortController()
  analyticsAbortController = controller
  loading.value = true
  error.value = ''
  try {
    const completedFrom = cleanDateValue(dateRange.value?.[0])
    const completedTo = cleanDateValue(dateRange.value?.[1])
    const selectedDept = department.value?.trim() || undefined
    const response = await ApiService.get<AnalyticsPayload>(
      '/api/v1/workstation/analytics/luxian-0609',
      {
        completed_from: completedFrom,
        completed_to: completedTo,
        department: selectedDept,
        job_id: trimmedJobId || undefined,
      },
      { signal: controller.signal },
    )
    if (controller.signal.aborted || requestSeq !== analyticsRequestSeq) return
    if (!response.success || !response.data) {
      throw new Error(String(response.error || '统计接口未返回数据'))
    }
    payload.value = response.data
    const incomingOptions = normalizeDepartmentList(response.data.department_options)
    if (incomingOptions.length > 0) {
      cachedDepartmentOptions.value = incomingOptions
    } else {
      const fromDist = normalizeDepartmentList(
        (response.data.department_distribution || []).map((item) => item.department),
      )
      if (fromDist.length > 0) {
        cachedDepartmentOptions.value = selectedDept
          ? [...new Set([...cachedDepartmentOptions.value, ...fromDist])]
          : fromDist
      }
    }
  } catch (caught) {
    if (controller.signal.aborted || requestSeq !== analyticsRequestSeq) return
    payload.value = null
    error.value = caught instanceof Error ? caught.message : '请稍后重试'
  } finally {
    if (analyticsAbortController === controller) {
      analyticsAbortController = null
    }
    if (requestSeq === analyticsRequestSeq) {
      loading.value = false
    }
  }
}

watch(
  () => route.fullPath,
  () => {
    const currentSig = querySignature((route.query || {}) as Record<string, unknown>)
    if (routeScopeInitialized.value && lastSyncedRouteSignature && currentSig === lastSyncedRouteSignature) {
      lastSyncedRouteSignature = ''
      return
    }
    lastSyncedRouteSignature = ''
    const selectedDepartment = routeQueryText('department')
    const completedFrom = routeQueryText('completed_from')
    const completedTo = routeQueryText('completed_to')
    department.value = selectedDepartment || undefined
    dateRange.value = completedFrom || completedTo ? [completedFrom, completedTo] : undefined
    jobId.value = routeQueryText('job_id')
    if (routeScopeInitialized.value) {
      void fetchAnalytics()
    }
    routeScopeInitialized.value = true
  },
  { immediate: true },
)

onMounted(() => {
  void fetchAnalytics()
})

onBeforeUnmount(() => {
  ++analyticsRequestSeq
  analyticsAbortController?.abort()
  analyticsAbortController = null
})
</script>

<style scoped>
.analytics-shell {
  min-height: 100%;
  background: #f5f5f7;
  color: #1d1d1f;
  padding: 24px;
}

.analytics-canvas {
  display: grid;
  gap: 16px;
  margin: 0 auto;
  max-width: 1380px;
}

.analytics-surface,
.analytics-command-surface {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.035);
}

.analytics-command-surface {
  padding: 20px 22px 13px;
}

.analytics-heading {
  align-items: center;
  display: flex;
  gap: 28px;
  justify-content: space-between;
}

.analytics-heading > div:first-child {
  flex: 0 1 auto;
  min-width: 0;
}

.analytics-eyebrow,
.panel-heading p {
  color: #0a6cff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0;
}

.analytics-heading h1 {
  font-size: 26px;
  letter-spacing: -0.02em;
  line-height: 32px;
  margin: 4px 0 0;
}

.analytics-title-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.analytics-title-row h1 {
  margin: 0;
}

.analytics-mode-chip {
  background: #eaf4ff;
  border: 1px solid #cce5ff;
  border-radius: 999px;
  color: #0a6cff;
  font-size: 12px;
  font-weight: 700;
  line-height: 22px;
  padding: 0 10px;
}

.analytics-heading p:not(.analytics-eyebrow) {
  color: var(--mq-text-secondary);
  font-size: 13px;
  margin: 5px 0 0;
}

.analytics-toolbar {
  align-items: center;
  display: flex;
  flex: 1;
  gap: 8px;
  justify-content: flex-end;
  min-width: 0;
}

.analytics-toolbar :deep(.ant-picker) {
  min-width: 218px;
}

.analytics-toolbar :deep(.ant-select) {
  min-width: 148px;
}

.analytics-toolbar :deep(.ant-input-affix-wrapper) {
  min-width: 184px;
}

.analytics-toolbar :deep(.ant-btn) {
  border-radius: 8px;
  font-weight: 600;
}

.analytics-context {
  align-items: center;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 12px;
}

.analytics-scope-copy {
  align-items: center;
  color: var(--mq-text-secondary);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 600;
  gap: 8px;
}

.analytics-scope-copy i {
  background: var(--mq-border-strong, rgba(29, 29, 31, 0.24));
  border-radius: 50%;
  height: 3px;
  width: 3px;
}

.analytics-scope-copy small {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 500;
}

.analytics-health-indicator {
  align-items: center;
  color: var(--mq-text-secondary);
  display: flex;
  font-size: 11px;
  gap: 7px;
  white-space: nowrap;
}

.analytics-health-indicator span {
  color: var(--mq-text-secondary);
}

.analytics-health-indicator strong {
  color: #047857;
  font-weight: 700;
}

.analytics-health-indicator.has-attention strong {
  color: #9a4a00;
}

.analytics-health-indicator small {
  color: var(--mq-text-tertiary);
}

.analytics-notice,
.analytics-loading,
.analytics-empty {
  align-items: center;
  display: flex;
  gap: 14px;
  justify-content: center;
  min-height: 180px;
  padding: 26px;
}

.analytics-notice {
  justify-content: space-between;
  min-height: 100px;
}

.analytics-notice span,
.analytics-loading span {
  color: var(--mq-text-secondary);
  display: block;
  font-size: 13px;
  margin-top: 3px;
}

.analytics-kpis {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
}

.analytics-kpis.is-confirmed-only {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.analytics-kpi {
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  padding: 16px 20px;
  position: relative;
}

.analytics-kpi:last-child {
  border-right: 0;
}

.analytics-kpi::before {
  background: #94a3b8;
  border-radius: 0 0 4px 4px;
  content: '';
  height: 3px;
  left: 20px;
  position: absolute;
  top: 0;
  width: 34px;
}

.analytics-kpi.is-brand::before {
  background: #0a6cff;
}

.analytics-kpi.is-danger::before {
  background: #ef4444;
}

.analytics-kpi.is-warning::before {
  background: #f59e0b;
}

.analytics-kpi span {
  color: var(--mq-text-secondary);
  display: block;
  font-size: 15px;
  font-weight: 600;
  line-height: 22px;
}

.analytics-kpi strong {
  color: var(--mq-text-primary);
  display: block;
  font-size: 28px;
  letter-spacing: -0.03em;
  line-height: 34px;
  margin: 8px 0 0;
}

.analytics-kpi.is-brand strong {
  color: #0a6cff;
}

.analytics-kpi.is-danger strong {
  color: #dc2626;
}

.analytics-kpi.is-warning strong {
  color: #9a4a00;
}

.analytics-overview-grid,
.analytics-detail-grid {
  display: grid;
  gap: 16px;
}

.analytics-overview-grid {
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
}

.analytics-detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.analytics-panel {
  min-width: 0;
  padding: 20px;
}

.panel-heading {
  align-items: flex-start;
  display: flex;
  gap: 14px;
  justify-content: space-between;
}

.panel-heading h2 {
  font-size: 17px;
  letter-spacing: -0.01em;
  line-height: 23px;
  margin: 3px 0 0;
}

.panel-note {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  line-height: 18px;
  text-align: right;
}

.conclusion-layout {
  align-items: center;
  display: flex;
  gap: 28px;
  margin-top: 20px;
  min-height: 170px;
}

.status-ring {
  border-radius: 50%;
  display: grid;
  flex: none;
  height: 152px;
  place-items: center;
  width: 152px;
}

.status-ring::before {
  background: #fff;
  border-radius: 50%;
  content: '';
  grid-area: 1 / 1;
  height: 108px;
  width: 108px;
}

.status-ring span {
  color: var(--mq-text-tertiary);
  grid-area: 1 / 1;
  position: relative;
  text-align: center;
  z-index: 1;
}

.status-ring strong,
.status-ring small {
  display: block;
}

.status-ring strong {
  color: var(--mq-text-primary);
  font-size: 26px;
  letter-spacing: -0.04em;
  line-height: 30px;
}

.status-ring small {
  font-size: 11px;
  margin-top: 2px;
}

.status-legend {
  display: grid;
  flex: 1;
  gap: 8px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.status-legend li {
  align-items: center;
  display: grid;
  font-size: 13px;
  gap: 8px;
  grid-template-columns: 8px 1fr auto;
}

.status-legend i {
  border-radius: 50%;
  height: 8px;
  width: 8px;
}

.status-legend span {
  color: var(--mq-text-secondary);
}

.status-legend strong {
  font-size: 13px;
}

.analytics-rhythm-panel {
  display: flex;
  flex-direction: column;
}

.rhythm-chart {
  align-items: stretch;
  display: flex;
  flex: 1;
  gap: 8px;
  height: 170px;
  margin: 20px 0 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 4px 4px;
}

.rhythm-bar {
  align-items: center;
  display: flex;
  flex: 1 0 32px;
  flex-direction: column;
  height: 100%;
  min-width: 32px;
}

.rhythm-bar-track {
  align-items: flex-end;
  display: flex;
  flex: 1;
  justify-content: center;
  min-height: 0;
  width: 100%;
}

.rhythm-bar-track i {
  background: #0a6cff;
  border-radius: 6px 6px 2px 2px;
  display: block;
  max-width: 28px;
  transition: height 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
  width: min(70%, 28px);
}

.rhythm-bar span,
.rhythm-bar small {
  color: var(--mq-text-tertiary);
  flex: none;
  font-size: 10px;
  line-height: 14px;
  white-space: nowrap;
}

.rhythm-bar span {
  color: var(--mq-text-primary);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  margin-bottom: 5px;
}

.rhythm-bar small {
  margin-top: 7px;
}

.rhythm-empty {
  align-items: center;
  color: var(--mq-text-tertiary);
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.rhythm-empty strong {
  color: var(--mq-text-secondary);
  font-size: 13px;
}

.rhythm-empty span {
  font-size: 12px;
  margin-top: 6px;
  max-width: 240px;
}

.department-chart {
  display: grid;
  gap: 13px;
  margin-top: 22px;
}

.department-row {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  display: grid;
  gap: 10px;
  grid-template-columns: 20px minmax(88px, 0.95fr) minmax(120px, 2fr) minmax(40px, auto);
  padding: 4px 6px;
  text-align: left;
  transition: background 200ms ease;
  width: 100%;
}

.department-row:hover {
  background: rgba(10, 108, 255, 0.045);
}

.department-rank {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.department-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.department-track {
  background: #edf1f6;
  border-radius: 999px;
  display: flex;
  height: 9px;
  overflow: hidden;
}

.department-track i {
  display: block;
  height: 100%;
}

.bar-danger {
  background: #ef4444;
}

.bar-warning {
  background: #f59e0b;
}

.bar-uncertain {
  background: #94a3b8;
}

.department-row strong {
  color: var(--mq-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
}

.analytics-physician-panel.is-full-span {
  grid-column: 1 / -1;
}

.physician-chart {
  display: grid;
  gap: 13px;
  margin-top: 22px;
}

.physician-row {
  align-items: center;
  display: grid;
  gap: 10px;
  grid-template-columns: 20px minmax(88px, 0.95fr) minmax(120px, 2fr) minmax(40px, auto);
  padding: 4px 6px;
}

.physician-row.is-unassigned .physician-name {
  color: var(--mq-text-tertiary);
}

.physician-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.physician-row strong {
  color: var(--mq-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
}

.analytics-rule-panel {
  grid-column: 1 / -1;
}

.rule-list {
  display: grid;
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
}

.rule-list li + li {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.rule-list button {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  display: grid;
  gap: 10px;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  padding: 11px 5px;
  text-align: left;
  transition: background 200ms ease;
  width: 100%;
}

.rule-list button:hover {
  background: rgba(10, 108, 255, 0.045);
}

.department-row:focus-visible,
.rule-list button:focus-visible,
.analytics-toolbar :deep(.ant-btn:focus-visible),
.analytics-notice :deep(.ant-btn:focus-visible) {
  outline: 2px solid var(--mq-brand-600, #0a6cff);
  outline-offset: 2px;
}

.department-row:focus-visible,
.rule-list button:focus-visible {
  background: rgba(10, 108, 255, 0.045);
}

.rule-rank {
  color: #0a6cff;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
}

.rule-copy {
  min-width: 0;
}

.rule-copy small,
.rule-copy strong,
.rule-count small,
.rule-count strong {
  display: block;
}

.rule-copy small,
.rule-count small {
  color: var(--mq-text-tertiary);
  font-size: 10px;
}

.rule-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
}

.rule-breakdown em {
  background: var(--mq-neutral-bg, rgba(148, 163, 184, 0.14));
  border-radius: 999px;
  color: var(--mq-neutral-text, #4a5468);
  font-size: 11px;
  font-style: normal;
  padding: 1px 7px;
}

.rule-breakdown em.is-danger {
  background: var(--mq-danger-bg, rgba(239, 68, 68, 0.1));
  color: #b91c1c;
}

.rule-breakdown em.is-warning {
  background: var(--mq-warning-bg, rgba(245, 158, 11, 0.12));
  color: #9a4a00;
}

.rule-breakdown em.is-neutral {
  background: var(--mq-neutral-bg, rgba(148, 163, 184, 0.14));
  color: var(--mq-neutral-text, #4a5468);
}

.rule-copy strong {
  font-size: 13px;
  line-height: 19px;
  margin-top: 2px;
}

.rule-count {
  text-align: right;
}

.rule-count strong {
  color: #b91c1c;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.rule-count small {
  margin-top: 1px;
}

/* ===== v7.1 液态玻璃基础覆写（置于所有 @media 之前以保证响应式断点完整生效） ===== */
.analytics-shell {
  padding: 8px 28px 32px 22px;
  background: transparent;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}

.analytics-canvas {
  gap: 20px;
  max-width: 1440px;
}

.analytics-surface,
.analytics-kpis {
  border: 1px solid var(--mq-glass-border);
  border-radius: var(--mq-radius-card);
  background: var(--mq-glass-bg);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow);
}

/* 页头：标题与筛选不再套卡片 */
.analytics-command-surface {
  padding: 0 4px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.analytics-heading {
  align-items: flex-end;
}

.analytics-eyebrow {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  font-weight: 600;
  letter-spacing: 0;
}

.analytics-heading h1 {
  margin: 4px 0 0;
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-title);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.analytics-heading p:not(.analytics-eyebrow) {
  color: var(--mq-text-tertiary);
}

.analytics-toolbar :deep(.ant-picker),
.analytics-toolbar :deep(.ant-select-selector),
.analytics-toolbar :deep(.ant-input-affix-wrapper) {
  border: 1px solid rgba(255, 255, 255, 0.9) !important;
  border-radius: var(--mq-radius-control) !important;
  background: rgba(255, 255, 255, 0.75) !important;
  box-shadow: 0 1px 3px rgba(10, 55, 115, 0.06);
}

.analytics-toolbar :deep(.ant-btn) {
  border-radius: 999px;
}

.analytics-context {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 0.5px solid var(--mq-border);
}

/* 指标：去掉彩色顶条，数值统一中性色 */
.analytics-kpi {
  padding: 18px 22px;
  border-right: 0.5px solid var(--mq-border);
}

.analytics-kpi:last-child {
  border-right: 0;
}

.analytics-kpi::before {
  display: none;
}

.analytics-kpi span {
  color: var(--mq-text-primary);
  font-size: var(--mq-font-14);
}

.analytics-kpi strong,
.analytics-kpi.is-brand strong,
.analytics-kpi.is-danger strong,
.analytics-kpi.is-warning strong {
  margin-top: 10px;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: 40px;
  font-weight: 600;
  letter-spacing: -0.035em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.panel-heading p {
  color: var(--mq-text-tertiary);
  letter-spacing: 0;
}

@media (max-width: 1440px) {
  .analytics-toolbar {
    flex-wrap: wrap;
  }
}

@media (max-width: 1280px) {
  .analytics-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .analytics-toolbar {
    flex-wrap: wrap;
    justify-content: flex-start;
    width: 100%;
  }
}

@media (max-width: 980px) {
  .analytics-shell {
    padding: 16px;
  }

  .analytics-toolbar,
  .analytics-context {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .analytics-toolbar :deep(.ant-picker),
  .analytics-toolbar :deep(.ant-select),
  .analytics-toolbar :deep(.ant-input-affix-wrapper) {
    flex: 1 1 180px;
    min-width: 0;
  }

  .analytics-health-indicator {
    justify-content: flex-start;
    white-space: normal;
    width: 100%;
  }

  .analytics-overview-grid,
  .analytics-detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .analytics-command-surface {
    padding: 0;
  }

  .analytics-panel {
    padding: 16px;
  }

  .analytics-heading h1 {
    font-size: 23px;
  }

  .analytics-toolbar > :deep(*) {
    flex: 1 1 auto;
  }

  .analytics-kpis,
  .analytics-kpis.is-confirmed-only {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analytics-kpi {
    padding: 14px 16px;
  }

  .analytics-kpi:nth-child(2n) {
    border-right: 0;
  }

  .analytics-kpi:nth-child(n + 3) {
    border-top: 1px solid var(--mq-border);
  }

  .analytics-kpi strong,
  .analytics-kpi.is-brand strong,
  .analytics-kpi.is-danger strong,
  .analytics-kpi.is-warning strong {
    font-size: 28px;
  }

  .conclusion-layout {
    gap: 18px;
  }

  .status-ring {
    height: 122px;
    width: 122px;
  }

  .status-ring::before {
    height: 88px;
    width: 88px;
  }

  .status-ring strong {
    font-size: 21px;
  }

  .department-row,
  .physician-row {
    grid-template-columns: 20px minmax(72px, 0.9fr) minmax(80px, 1.5fr) minmax(40px, auto);
  }
}
</style>
