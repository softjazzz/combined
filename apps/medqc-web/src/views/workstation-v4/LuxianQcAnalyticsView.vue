<template>
  <div class="analytics-shell custom-scrollbar">
    <main class="analytics-canvas">
      <section class="analytics-command-surface">
        <div class="analytics-heading">
          <div>
            <p class="analytics-eyebrow">
              全院临时范围 · 终末质控
            </p>
            <h1>质控统计分析</h1>
            <p>聚焦已完成任务中可交付的 Canonical 结果，不混入技术异常。</p>
          </div>

          <div
            class="analytics-toolbar"
            aria-label="统计筛选"
          >
            <a-range-picker
              v-model:value="dateRange"
              show-time
              value-format="YYYY-MM-DDTHH:mm:ss"
            />
            <a-select
              v-model:value="department"
              allow-clear
              placeholder="全部科室"
              :options="departmentOptions"
            />
            <a-input
              v-model:value="jobId"
              allow-clear
              placeholder="已完成任务 ID（可选）"
            />
            <a-button
              type="primary"
              :loading="loading"
              @click="void fetchAnalytics"
            >
              查询
            </a-button>
            <a-button @click="resetFilters">
              重置
            </a-button>
          </div>
        </div>

        <div
          v-if="payload"
          class="analytics-context"
          data-testid="analytics-scope"
        >
          <div class="analytics-scope-copy">
            <span>按质控完成时间</span><i />
            <span>{{ payload.scope.department || '全部科室' }}</span><i />
            <span>泸县0609终末质控</span>
            <small>版本 {{ payload.scope.rule_set_version }}</small>
          </div>
          <div
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
      >
        <div>
          <strong>统计范围暂时无法加载</strong>
          <span>{{ error }}</span>
        </div>
        <a-button
          size="small"
          @click="void fetchAnalytics"
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
          <span>正在核对已完成任务与 Canonical 结果。</span>
        </div>
      </section>

      <template v-else-if="payload">
        <section
          class="analytics-kpis"
          data-testid="analytics-kpis"
        >
          <article
            v-for="card in kpiCards"
            :key="card.label"
            :class="['analytics-kpi', `is-${card.tone}`]"
            data-testid="analytics-kpi"
          >
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.detail }}</small>
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
                  :style="{ background: statusRingBackground }"
                >
                  <span><strong>{{ primaryConcernTotal }}</strong><small>需重点关注</small></span>
                </div>
                <ul class="status-legend">
                  <li
                    v-for="item in statusItems"
                    :key="item.status"
                  >
                    <i :style="{ background: item.color }" />
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
              >
                <div
                  v-for="item in completionSeries"
                  :key="item.bucket"
                  class="rhythm-bar"
                >
                  <span>{{ item.completed_event_total }}</span>
                  <i :style="{ height: `${trendPercent(item.completed_event_total)}%` }" />
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
              class="analytics-surface analytics-panel analytics-department-panel"
              data-testid="analytics-department-chart"
            >
              <header class="panel-heading">
                <div>
                  <p>整改优先级</p>
                  <h2>科室风险排行</h2>
                </div>
                <span class="panel-note">红：确定问题 · 橙：资料待核实</span>
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
                  @click="drillDown({ department: item.department })"
                >
                  <span class="department-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                  <span class="department-name">{{ item.department }}</span>
                  <span class="department-track">
                    <i
                      class="bar-danger"
                      :style="{
                        width: `${barPercent(item.non_compliant_record_total, departmentMax)}%`,
                      }"
                    />
                    <i
                      class="bar-warning"
                      :style="{
                        width: `${barPercent(item.data_gap_record_total, departmentMax)}%`,
                      }"
                    />
                    <i
                      v-if="item.uncertain_record_total"
                      class="bar-uncertain"
                      :style="{
                        width: `${barPercent(item.uncertain_record_total, departmentMax)}%`,
                      }"
                    />
                  </span>
                  <strong>{{
                    item.non_compliant_record_total + item.data_gap_record_total
                  }}</strong>
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
              data-testid="analytics-physician-chart"
            >
              <header class="panel-heading">
                <div>
                  <p>责任归属</p>
                  <h2>主治医师风险排行</h2>
                </div>
                <span class="panel-note">按首页主治医师签名归属</span>
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
                  <span class="physician-name">{{ item.physician }}</span>
                  <span class="department-track">
                    <i
                      class="bar-danger"
                      :style="{
                        width: `${barPercent(item.non_compliant_record_total, physicianMax)}%`,
                      }"
                    />
                    <i
                      class="bar-warning"
                      :style="{ width: `${barPercent(item.data_gap_record_total, physicianMax)}%` }"
                    />
                    <i
                      v-if="item.uncertain_record_total"
                      class="bar-uncertain"
                      :style="{
                        width: `${barPercent(item.uncertain_record_total, physicianMax)}%`,
                      }"
                    />
                  </span>
                  <strong>{{
                    item.non_compliant_record_total + item.data_gap_record_total
                  }}</strong>
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
                <span class="panel-note">点击查看对应病历</span>
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
                    @click="drillDown({ rule_id: item.rule_id })"
                  >
                    <span class="rule-rank">{{ index + 1 }}</span>
                    <span class="rule-copy">
                      <small>{{ item.rule_id }}</small>
                      <strong>{{ item.rule_name }}</strong>
                      <span class="rule-breakdown">
                        <em v-if="item.non_compliant_count">确定 {{ item.non_compliant_count }}</em>
                        <em v-if="item.data_gap_count">待核实 {{ item.data_gap_count }}</em>
                        <em v-if="item.uncertain_count">待判断 {{ item.uncertain_count }}</em>
                      </span>
                    </span>
                    <span class="rule-count">
                      <strong>{{ ruleConcernTotal(item) }}</strong>
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ApiService } from '@/services/apiService'

type Status =
  | 'non_compliant'
  | 'data_gap'
  | 'uncertain'
  | 'compliant'
  | 'not_applicable'
  | 'not_executed'

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
  department_distribution: Array<{
    department: string
    distinct_record_total: number
    non_compliant_record_total: number
    data_gap_record_total: number
    uncertain_record_total: number
  }>
  physician_distribution: Array<{
    physician: string
    distinct_record_total: number
    non_compliant_record_total: number
    data_gap_record_total: number
    uncertain_record_total: number
  }>
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

const router = useRouter()
const loading = ref(true)
const error = ref('')
const payload = ref<AnalyticsPayload | null>(null)
const dateRange = ref<[string, string]>()
const department = ref<string>()
const jobId = ref('')

const STATUS_META: Array<{ status: Status; label: string; color: string }> = [
  { status: 'non_compliant', label: '确定问题', color: '#ef4444' },
  { status: 'data_gap', label: '资料待核实', color: '#f59e0b' },
  { status: 'uncertain', label: '待判断', color: '#64748b' },
  { status: 'compliant', label: '合规', color: '#10b981' },
  { status: 'not_applicable', label: '不适用', color: '#94a3b8' },
  { status: 'not_executed', label: '未执行', color: '#cbd5e1' },
]

const departmentOptions = computed(() =>
  (payload.value?.department_distribution || []).map((item) => ({
    label: item.department,
    value: item.department,
  })),
)
const statusItems = computed(() =>
  STATUS_META.map((meta) => ({
    ...meta,
    count: Number(
      payload.value?.status_distribution.find((item) => item.status === meta.status)?.count || 0,
    ),
  })).filter((item) => item.count > 0),
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
  [...(payload.value?.department_distribution || [])]
    .filter(
      (item) =>
        item.non_compliant_record_total ||
        item.data_gap_record_total ||
        item.uncertain_record_total,
    )
    .sort(
      (a, b) =>
        b.non_compliant_record_total - a.non_compliant_record_total ||
        b.data_gap_record_total - a.data_gap_record_total ||
        b.uncertain_record_total - a.uncertain_record_total,
    )
    .slice(0, 8),
)
const departmentMax = computed(() =>
  Math.max(
    1,
    ...departmentItems.value.map(
      (item) =>
        item.non_compliant_record_total + item.data_gap_record_total + item.uncertain_record_total,
    ),
  ),
)
const physicianItems = computed(() =>
  [...(payload.value?.physician_distribution || [])]
    .filter(
      (item) =>
        item.non_compliant_record_total ||
        item.data_gap_record_total ||
        item.uncertain_record_total,
    )
    .sort(
      (a, b) =>
        b.non_compliant_record_total - a.non_compliant_record_total ||
        b.data_gap_record_total - a.data_gap_record_total ||
        b.uncertain_record_total - a.uncertain_record_total ||
        a.physician.localeCompare(b.physician),
    )
    .slice(0, 8),
)
const physicianMax = computed(() =>
  Math.max(
    1,
    ...physicianItems.value.map(
      (item) =>
        item.non_compliant_record_total + item.data_gap_record_total + item.uncertain_record_total,
    ),
  ),
)
const ruleItems = computed(() =>
  [...(payload.value?.rule_distribution || [])]
    .sort(
      (a, b) =>
        b.non_compliant_count - a.non_compliant_count ||
        b.data_gap_count - a.data_gap_count ||
        b.uncertain_count - a.uncertain_count ||
        a.rule_id.localeCompare(b.rule_id),
    )
    .slice(0, 5),
)
const completionSeries = computed(() => payload.value?.completion_time_series || [])
const hasTrend = computed(() => completionSeries.value.length >= 2)
const kpiCards = computed(() => [
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
  {
    label: '资料待核实',
    value: payload.value?.kpis.records_with_data_gap || 0,
    detail: '至少一项资料待核实',
    tone: 'warning',
  },
])

function formatTime(value: string) {
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : '暂未返回'
}
function barPercent(value: number, maximum: number) {
  return Math.max(0, Math.round((value / maximum) * 100))
}
function trendPercent(value: number) {
  const maximum = Math.max(1, ...completionSeries.value.map((item) => item.completed_event_total))
  return Math.max(10, Math.round((value / maximum) * 100))
}
function ruleConcernTotal(item: AnalyticsPayload['rule_distribution'][number]) {
  return item.non_compliant_count + item.data_gap_count + item.uncertain_count
}
function resetFilters() {
  dateRange.value = undefined
  department.value = undefined
  jobId.value = ''
  void fetchAnalytics()
}
function drillDown(filters: { department?: string; rule_id?: string }) {
  void router.push({
    path: '/workstation-v4',
    query: {
      source: 'analytics',
      analytics_scope: 'final',
      department: filters.department || department.value,
      analytics_completed_from: dateRange.value?.[0],
      analytics_completed_to: dateRange.value?.[1],
      analytics_job_id: jobId.value || undefined,
      analytics_rule_id: filters.rule_id,
    },
  })
}
async function fetchAnalytics() {
  loading.value = true
  error.value = ''
  try {
    const response = await ApiService.get<AnalyticsPayload>(
      '/api/v1/workstation/analytics/luxian-0609',
      {
        completed_from: dateRange.value?.[0],
        completed_to: dateRange.value?.[1],
        department: department.value,
        job_id: jobId.value || undefined,
      },
    )
    if (!response.success || !response.data) {
      throw new Error(String(response.error || '统计接口未返回数据'))
    }
    payload.value = response.data
  } catch (caught) {
    payload.value = null
    error.value = caught instanceof Error ? caught.message : '请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void fetchAnalytics()
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

.analytics-eyebrow,
.panel-heading p {
  color: #0066cc;
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

.analytics-heading p:not(.analytics-eyebrow) {
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  margin: 5px 0 0;
}

.analytics-toolbar {
  align-items: center;
  display: flex;
  flex: 1;
  gap: 8px;
  justify-content: flex-end;
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
  color: rgba(29, 29, 31, 0.58);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 600;
  gap: 8px;
}

.analytics-scope-copy i {
  background: rgba(29, 29, 31, 0.24);
  border-radius: 50%;
  height: 3px;
  width: 3px;
}

.analytics-scope-copy small {
  color: rgba(29, 29, 31, 0.4);
  font-size: 11px;
  font-weight: 500;
}

.analytics-health-indicator {
  align-items: center;
  color: rgba(29, 29, 31, 0.5);
  display: flex;
  font-size: 11px;
  gap: 7px;
  white-space: nowrap;
}

.analytics-health-indicator span {
  color: rgba(29, 29, 31, 0.4);
}

.analytics-health-indicator strong {
  color: #059669;
  font-weight: 700;
}

.analytics-health-indicator.has-attention strong {
  color: #c17a08;
}

.analytics-health-indicator small {
  color: rgba(29, 29, 31, 0.38);
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
  color: rgba(29, 29, 31, 0.56);
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
  background: #0066cc;
}

.analytics-kpi.is-danger::before {
  background: #ef4444;
}

.analytics-kpi.is-warning::before {
  background: #f59e0b;
}

.analytics-kpi span,
.analytics-kpi small {
  color: rgba(29, 29, 31, 0.55);
  display: block;
  font-size: 12px;
}

.analytics-kpi strong {
  color: #1d1d1f;
  display: block;
  font-size: 28px;
  letter-spacing: -0.03em;
  line-height: 34px;
  margin: 5px 0 2px;
}

.analytics-kpi.is-brand strong {
  color: #0066cc;
}

.analytics-kpi.is-danger strong {
  color: #dc2626;
}

.analytics-kpi.is-warning strong {
  color: #c17a08;
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
  color: rgba(29, 29, 31, 0.44);
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
  color: rgba(29, 29, 31, 0.48);
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
  color: #1d1d1f;
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
  color: rgba(29, 29, 31, 0.63);
}

.status-legend strong {
  font-size: 13px;
}

.analytics-rhythm-panel {
  display: flex;
  flex-direction: column;
}

.rhythm-chart {
  align-items: end;
  display: flex;
  flex: 1;
  gap: 8px;
  height: 170px;
  margin: 20px 0 0;
  padding: 0 4px;
}

.rhythm-bar {
  align-items: center;
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  justify-content: end;
  min-width: 24px;
}

.rhythm-bar i {
  background: #0066cc;
  border-radius: 6px 6px 2px 2px;
  display: block;
  max-width: 28px;
  transition: height 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
  width: min(70%, 28px);
}

.rhythm-bar span,
.rhythm-bar small {
  color: rgba(29, 29, 31, 0.48);
  font-size: 10px;
}

.rhythm-bar span {
  color: #1d1d1f;
  font-weight: 700;
  margin-bottom: 5px;
}

.rhythm-bar small {
  margin-top: 7px;
}

.rhythm-empty {
  align-items: center;
  color: rgba(29, 29, 31, 0.48);
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.rhythm-empty strong {
  color: rgba(29, 29, 31, 0.7);
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
  grid-template-columns: 20px minmax(88px, 0.95fr) minmax(120px, 2fr) 32px;
  padding: 4px 6px;
  text-align: left;
  transition: background 200ms ease;
  width: 100%;
}

.department-row:hover {
  background: rgba(0, 102, 204, 0.045);
}

.department-rank {
  color: rgba(29, 29, 31, 0.34);
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
  color: rgba(29, 29, 31, 0.76);
  font-size: 12px;
  text-align: right;
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
  grid-template-columns: 20px minmax(88px, 0.95fr) minmax(120px, 2fr) 32px;
  padding: 4px 6px;
}

.physician-row.is-unassigned .physician-name {
  color: rgba(29, 29, 31, 0.48);
}

.physician-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.physician-row strong {
  color: rgba(29, 29, 31, 0.76);
  font-size: 12px;
  text-align: right;
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
  background: rgba(0, 102, 204, 0.045);
}

.rule-rank {
  color: #0066cc;
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
  color: rgba(29, 29, 31, 0.42);
  font-size: 10px;
}

.rule-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
}

.rule-breakdown em {
  background: rgba(148, 163, 184, 0.14);
  border-radius: 999px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 10px;
  font-style: normal;
  padding: 1px 6px;
}

.rule-breakdown em:first-child {
  background: rgba(239, 68, 68, 0.1);
  color: #c2410c;
}

.rule-breakdown em:nth-child(2) {
  background: rgba(245, 158, 11, 0.12);
  color: #a16207;
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
  color: #c2410c;
  font-size: 14px;
}

.rule-count small {
  margin-top: 1px;
}

@media (max-width: 1280px) {
  .analytics-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .analytics-toolbar {
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
  .analytics-command-surface,
  .analytics-panel {
    padding: 16px;
  }

  .analytics-heading h1 {
    font-size: 23px;
  }

  .analytics-toolbar > :deep(*) {
    flex: 1 1 auto;
  }

  .analytics-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analytics-kpi:nth-child(2n) {
    border-right: 0;
  }

  .analytics-kpi:nth-child(n + 3) {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
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

  .department-row {
    grid-template-columns: 20px minmax(72px, 0.9fr) minmax(80px, 1.5fr) 28px;
  }

  .physician-row {
    grid-template-columns: 20px minmax(72px, 0.9fr) minmax(80px, 1.5fr) 28px;
  }
}
</style>
