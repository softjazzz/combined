<template>
  <div class="analytics-shell custom-scrollbar">
    <main class="analytics-canvas">
      <header class="analytics-header analytics-surface">
        <div>
          <p class="analytics-eyebrow">
            全院临时范围
          </p>
          <h1>质控统计分析</h1>
          <p>按质控完成时间汇总已交付的泸县0609 Canonical 最终结果。</p>
        </div>
        <a-button @click="resetFilters">
          重置筛选
        </a-button>
      </header>

      <section
        class="analytics-filters analytics-surface"
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
          查询统计
        </a-button>
      </section>

      <section
        v-if="error"
        class="analytics-notice analytics-surface"
        data-testid="analytics-error"
      >
        <strong>统计范围暂时无法加载</strong>
        <span>{{ error }}</span>
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
          <strong>正在汇总统计范围</strong><span>正在核对已完成任务与 Canonical 结果。</span>
        </div>
      </section>

      <template v-else-if="payload">
        <section
          class="analytics-scope analytics-surface"
          data-testid="analytics-scope"
        >
          <span>按质控完成时间</span><i /> <span>{{ payload.scope.department || '全部科室' }}</span><i />
          <span>{{ payload.scope.rule_set_key }} · {{ payload.scope.rule_set_version }}</span>
          <small>数据截至 {{ formatTime(payload.scope.generated_at) }}</small>
        </section>

        <section
          class="analytics-kpis"
          data-testid="analytics-kpis"
        >
          <article
            v-for="card in kpiCards"
            :key="card.label"
            :class="['analytics-kpi', `is-${card.tone}`]"
          >
            <span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.detail }}</small>
          </article>
        </section>

        <section
          v-if="payload.kpis.completed_event_total === 0"
          class="analytics-empty analytics-surface"
        >
          <a-empty description="当前范围内暂无完成质控事件" />
        </section>

        <template v-else>
          <section class="analytics-grid analytics-grid--summary">
            <article
              class="analytics-surface analytics-panel"
              data-testid="analytics-status-chart"
            >
              <header>
                <div>
                  <h2>结果结构</h2>
                  <p>只统计有效 Canonical 规则条目；技术异常不计入医疗结论。</p>
                </div>
              </header>
              <div class="status-chart">
                <div
                  class="status-ring"
                  :style="{ background: statusRingBackground }"
                >
                  <span><strong>{{ statusTotal }}</strong>条<br>有效结论</span>
                </div>
                <ul class="status-legend">
                  <li
                    v-for="item in statusItems"
                    :key="item.status"
                  >
                    <i :style="{ background: item.color }" /><span>{{ item.label }}</span><strong>{{ item.count }}</strong>
                  </li>
                </ul>
              </div>
            </article>
            <article
              class="analytics-surface analytics-panel analytics-health"
              data-testid="analytics-health"
            >
              <header>
                <div>
                  <h2>数据健康</h2>
                  <p>结果可用性，不等同于医疗风险。</p>
                </div>
              </header>
              <strong>{{ payload.data_health.canonical_invalid_or_missing_total }}</strong>
              <span>无效或缺失 Canonical 结果候选</span>
              <p>该数量未计入不合规、资料待核实或待判断。</p>
            </article>
          </section>

          <section class="analytics-grid analytics-grid--detail">
            <article
              class="analytics-surface analytics-panel"
              data-testid="analytics-department-chart"
            >
              <header>
                <div>
                  <h2>科室质量对比</h2>
                  <p>前 10 个存在确定问题或资料待核实的科室。</p>
                </div>
              </header>
              <div
                v-if="departmentItems.length"
                class="bar-chart"
              >
                <button
                  v-for="item in departmentItems"
                  :key="item.department"
                  type="button"
                  class="bar-row"
                  @click="drillDown({ department: item.department })"
                >
                  <span>{{ item.department }}</span>
                  <div>
                    <i
                      class="bar-danger"
                      :style="{
                        width: `${barPercent(item.non_compliant_record_total, departmentMax)}%`,
                      }"
                    /><i
                      class="bar-warning"
                      :style="{
                        width: `${barPercent(item.data_gap_record_total, departmentMax)}%`,
                      }"
                    />
                  </div>
                  <strong>{{ item.non_compliant_record_total }} /
                    {{ item.data_gap_record_total }}</strong>
                </button>
              </div>
              <a-empty
                v-else
                description="暂无可展示的科室统计"
                :image-style="{ height: '56px' }"
              />
            </article>
            <article
              class="analytics-surface analytics-panel"
              data-testid="analytics-rule-chart"
            >
              <header>
                <div>
                  <h2>高频问题规则</h2>
                  <p>按确定问题、资料待核实和待判断排序。</p>
                </div>
              </header>
              <ol
                v-if="payload.rule_distribution.length"
                class="rule-list"
              >
                <li
                  v-for="item in payload.rule_distribution"
                  :key="item.rule_id"
                >
                  <button
                    type="button"
                    @click="drillDown({ rule_id: item.rule_id })"
                  >
                    <span>{{ item.rule_id }}</span><strong>{{ item.rule_name }}</strong><small>确定问题 {{ item.non_compliant_count }} · 待核实 {{ item.data_gap_count }} ·
                      待判断 {{ item.uncertain_count }}</small>
                  </button>
                </li>
              </ol>
              <a-empty
                v-else
                description="暂无高频问题规则"
                :image-style="{ height: '56px' }"
              />
            </article>
          </section>

          <section
            v-if="payload.completion_time_series"
            class="analytics-surface analytics-panel"
            data-testid="analytics-trend"
          >
            <header>
              <div>
                <h2>质控完成量</h2>
                <p>按自然日统计已完成根任务的 Canonical 事件，不代表患者数。</p>
              </div>
            </header>
            <div class="trend-chart">
              <div
                v-for="item in payload.completion_time_series"
                :key="item.bucket"
              >
                <i :style="{ height: `${trendPercent(item.completed_event_total)}%` }" /><span>{{
                  item.bucket.slice(5)
                }}</span><strong>{{ item.completed_event_total }}</strong>
              </div>
            </div>
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
const dateRange = ref<string[]>()
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
        b.data_gap_record_total - a.data_gap_record_total,
    )
    .slice(0, 10),
)
const departmentMax = computed(() =>
  Math.max(
    1,
    ...departmentItems.value.map(
      (item) => item.non_compliant_record_total + item.data_gap_record_total,
    ),
  ),
)
const kpiCards = computed(() => [
  {
    label: '纳入病历',
    value: payload.value?.kpis.distinct_record_total || 0,
    detail: '按三坐标去重',
    tone: 'brand',
  },
  {
    label: '完成事件',
    value: payload.value?.kpis.completed_event_total || 0,
    detail: '根任务 + 三坐标',
    tone: 'success',
  },
  {
    label: '确定问题病历',
    value: payload.value?.kpis.records_with_non_compliant || 0,
    detail: '至少一项确定问题',
    tone: 'danger',
  },
  {
    label: '资料待核实病历',
    value: payload.value?.kpis.records_with_data_gap || 0,
    detail: '至少一项资料待核实',
    tone: 'warning',
  },
  {
    label: '结果校验异常',
    value: payload.value?.kpis.canonical_invalid_or_missing_total || 0,
    detail: '不计入医疗结论',
    tone: 'neutral',
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
  const maximum = Math.max(
    1,
    ...(payload.value?.completion_time_series || []).map((item) => item.completed_event_total),
  )
  return Math.max(8, Math.round((value / maximum) * 100))
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
    if (!response.success || !response.data)
      throw new Error(String(response.error || '统计接口未返回数据'))
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
  height: 100%;
  overflow: auto;
  background: #f5f5f7;
  color: #1d1d1f;
  padding: 28px;
}
.analytics-canvas {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}
.analytics-surface {
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.035);
}
.analytics-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
}
.analytics-eyebrow {
  margin: 0;
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
}
.analytics-header h1 {
  margin: 4px 0 0;
  font-size: 28px;
  line-height: 31px;
}
.analytics-header p:not(.analytics-eyebrow),
.analytics-panel p {
  margin: 7px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
.analytics-filters {
  display: flex;
  gap: 10px;
  padding: 12px;
}
.analytics-filters :deep(.ant-picker),
.analytics-filters :deep(.ant-select),
.analytics-filters :deep(.ant-input-affix-wrapper) {
  min-width: 220px;
}
.analytics-notice,
.analytics-loading,
.analytics-empty {
  padding: 30px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.analytics-loading {
  justify-content: center;
  min-height: 210px;
}
.analytics-loading span,
.analytics-health span {
  display: block;
  color: rgba(29, 29, 31, 0.6);
  margin-top: 4px;
}
.analytics-scope {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 16px;
  color: rgba(29, 29, 31, 0.7);
  font-size: 12px;
  font-weight: 600;
}
.analytics-scope i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(29, 29, 31, 0.28);
}
.analytics-scope small {
  margin-left: auto;
  color: rgba(29, 29, 31, 0.46);
  font-weight: 500;
}
.analytics-kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  overflow: hidden;
}
.analytics-kpi {
  padding: 18px;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
}
.analytics-kpi:last-child {
  border: 0;
}
.analytics-kpi span,
.analytics-kpi small {
  display: block;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}
.analytics-kpi strong {
  display: block;
  margin: 7px 0 3px;
  font-size: 25px;
  line-height: 30px;
}
.analytics-kpi.is-danger strong {
  color: #dc2626;
}
.analytics-kpi.is-warning strong {
  color: #d97706;
}
.analytics-kpi.is-success strong {
  color: #059669;
}
.analytics-kpi.is-brand strong {
  color: #0066cc;
}
.analytics-grid {
  display: grid;
  gap: 18px;
}
.analytics-grid--summary {
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
}
.analytics-grid--detail {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
}
.analytics-panel {
  padding: 22px;
}
.analytics-panel header h2 {
  margin: 0;
  font-size: 17px;
}
.status-chart {
  display: flex;
  align-items: center;
  gap: 30px;
  margin-top: 24px;
}
.status-ring {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex: none;
}
.status-ring:before {
  content: '';
  width: 108px;
  height: 108px;
  border-radius: 50%;
  background: #fff;
  grid-area: 1/1;
}
.status-ring span {
  position: relative;
  z-index: 1;
  text-align: center;
  font-size: 11px;
  color: rgba(29, 29, 31, 0.56);
}
.status-ring strong {
  font-size: 21px;
  color: #1d1d1f;
}
.status-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 9px;
  flex: 1;
}
.status-legend li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.status-legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-legend span {
  color: rgba(29, 29, 31, 0.66);
}
.status-legend strong {
  margin-left: auto;
}
.analytics-health {
  display: flex;
  flex-direction: column;
}
.analytics-health > strong {
  font-size: 42px;
  line-height: 48px;
  color: #d97706;
  margin-top: 27px;
}
.analytics-health > p {
  margin-top: auto !important;
}
.bar-chart {
  display: grid;
  gap: 13px;
  margin-top: 24px;
}
.bar-row {
  display: grid;
  grid-template-columns: 100px minmax(100px, 1fr) 74px;
  gap: 10px;
  align-items: center;
  border: 0;
  background: transparent;
  padding: 0;
  text-align: left;
  cursor: pointer;
}
.bar-row > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.bar-row > div {
  height: 12px;
  background: #eef2f7;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
}
.bar-row i {
  display: block;
  height: 100%;
}
.bar-danger {
  background: #ef4444;
}
.bar-warning {
  background: #f59e0b;
}
.bar-row strong {
  font-size: 12px;
  text-align: right;
  color: rgba(29, 29, 31, 0.62);
}
.rule-list {
  list-style: none;
  margin: 20px 0 0;
  padding: 0;
  display: grid;
  gap: 4px;
}
.rule-list button {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 10px 0;
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  cursor: pointer;
}
.rule-list span,
.rule-list small {
  display: block;
  color: rgba(29, 29, 31, 0.55);
  font-size: 11px;
}
.rule-list strong {
  display: block;
  margin: 2px 0;
  font-size: 13px;
}
.trend-chart {
  height: 180px;
  margin-top: 20px;
  display: flex;
  align-items: end;
  gap: 8px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.trend-chart > div {
  height: 100%;
  flex: 1;
  min-width: 24px;
  display: flex;
  flex-direction: column;
  justify-content: end;
  align-items: center;
  gap: 4px;
  position: relative;
}
.trend-chart i {
  width: min(28px, 70%);
  background: #0066cc;
  border-radius: 6px 6px 0 0;
}
.trend-chart span,
.trend-chart strong {
  font-size: 10px;
  color: rgba(29, 29, 31, 0.54);
}
.trend-chart strong {
  color: #1d1d1f;
}
@media (max-width: 900px) {
  .analytics-shell {
    padding: 16px;
  }
  .analytics-header,
  .analytics-filters {
    align-items: stretch;
    flex-direction: column;
  }
  .analytics-filters :deep(.ant-picker),
  .analytics-filters :deep(.ant-select),
  .analytics-filters :deep(.ant-input-affix-wrapper) {
    min-width: 0;
    width: 100%;
  }
  .analytics-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .analytics-grid--summary,
  .analytics-grid--detail {
    grid-template-columns: 1fr;
  }
  .analytics-scope small {
    width: 100%;
    margin-left: 0;
  }
  .analytics-kpi:nth-child(2n) {
    border-right: 0;
  }
  .analytics-kpi:last-child {
    border-right: 1px solid rgba(0, 0, 0, 0.07);
  }
  .status-chart {
    gap: 15px;
  }
  .status-ring {
    width: 128px;
    height: 128px;
  }
  .status-ring:before {
    width: 92px;
    height: 92px;
  }
}
</style>
