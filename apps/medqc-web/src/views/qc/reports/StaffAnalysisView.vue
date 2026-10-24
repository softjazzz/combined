<template>
  <main class="mq-page staff-analysis">
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">统计分析 · 质量报表</span>
        <h1 class="mq-page-title">
          {{ reportTab === 'manual' ? '人工质控报表' : '质控员工作分析' }}
        </h1>
        <p class="page-desc">
          {{
            reportTab === 'manual'
              ? '按上海自然日的缺陷创建日期统计人工缺陷录入、审核与整改状态'
              : '按质控场景、病例科室、任务和时间核对人员工作量'
          }}
        </p>
      </div>
      <div class="mq-page-head__actions">
        <div class="mq-segmented" role="group" aria-label="报表切换">
          <button
            v-for="option in reportTabs"
            :key="option.value"
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': reportTab === option.value }"
            :aria-pressed="reportTab === option.value"
            :data-testid="`staff-report-tab-${option.value}`"
            @click="reportTab = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <div v-if="reportTab === 'staff'" class="head-actions">
          <button class="secondary mq-btn" type="button" :disabled="loading" @click="loadReport">
            <MqIcon name="sync" :size="16" />刷新
          </button>
          <button
            class="secondary mq-btn"
            type="button"
            :disabled="!report || exporting"
            @click="download"
          >
            <MqIcon name="download" :size="16" />导出 CSV
          </button>
        </div>
      </div>
    </header>
    <ManualQualityReportPanel v-if="reportTab === 'manual'" />
    <div v-show="reportTab === 'staff'" class="staff-body">
      <section class="filters mq-card mq-card--padded" aria-label="工作分析筛选">
        <div class="filter-switches">
          <div class="filter-field mq-field">
            <span class="mq-field__label">统计周期</span>
            <div class="segmented mq-segmented" role="group" aria-label="统计周期">
              <button
                v-for="option in periodOptions"
                :key="option.value"
                type="button"
                class="mq-segmented__item"
                :class="{ 'is-active': draft.period === option.value }"
                :aria-pressed="draft.period === option.value"
                @click="draft.period = option.value"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
          <div class="filter-field mq-field">
            <span class="mq-field__label">质控场景</span>
            <div class="segmented mq-segmented" role="group" aria-label="质控场景">
              <button
                v-for="option in sceneOptions"
                :key="option.value"
                type="button"
                class="mq-segmented__item"
                :class="{ 'is-active': scene === option.value }"
                :aria-pressed="scene === option.value"
                @click="setScene(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
        </div>
        <div class="filter-grid">
          <label class="filter-field mq-field">
            <span class="mq-field__label">病例科室</span>
            <select
              v-model="draft.departmentKey"
              class="mq-input"
              data-testid="staff-department-filter"
            >
              <option value="">全部科室</option>
              <option
                v-for="option in report?.filter_options.departments || []"
                :key="departmentKey(option.institute_id, option.department_name)"
                :value="departmentKey(option.institute_id, option.department_name)"
              >
                {{ option.department_name }}（{{ option.institute_id }}）
              </option>
            </select>
          </label>
          <label class="filter-field mq-field">
            <span class="mq-field__label">质控任务</span>
            <select v-model="draft.task_id" class="mq-input" data-testid="staff-task-filter">
              <option value="">全部任务</option>
              <option
                v-for="option in report?.filter_options.tasks || []"
                :key="option.task_id"
                :value="option.task_id"
              >
                {{ option.task_name || option.task_id }}
              </option>
            </select>
          </label>
          <label class="filter-field mq-field">
            <span class="mq-field__label">开始日期</span>
            <input
              v-model="draft.start_date"
              class="mq-input"
              type="date"
              data-testid="staff-start-date"
            />
          </label>
          <label class="filter-field mq-field">
            <span class="mq-field__label">结束日期</span>
            <input
              v-model="draft.end_date"
              class="mq-input"
              type="date"
              data-testid="staff-end-date"
            />
          </label>
          <div class="filter-actions">
            <button class="primary mq-btn mq-btn--primary" type="button" @click="applyFilters">
              <MqIcon name="search" :size="16" />查询
            </button>
            <button class="secondary mq-btn" type="button" @click="resetFilters">重置</button>
          </div>
        </div>
        <p v-if="filterError" class="filter-error" role="alert">
          {{ filterError }}
        </p>
        <p v-if="report?.filter_options_unavailable_reason" class="filter-hint">
          {{ filterOptionsUnavailableText(report.filter_options_unavailable_reason) }}
        </p>
      </section>

      <div v-if="!authKey" class="state-message">请先登录后查看质控员工作分析</div>
      <div v-else-if="loading" class="state-message" role="status">正在读取质控员工作数据…</div>
      <div
        v-else-if="errorMessage"
        class="state-message error"
        role="alert"
        data-testid="staff-error"
      >
        <MqIcon name="issue" :size="18" />{{ errorMessage }}
      </div>
      <template v-else-if="report">
        <div
          v-if="report.unavailable_reason"
          class="state-message unavailable"
          data-testid="staff-unavailable"
        >
          <MqIcon name="issue" :size="18" />{{ unavailableText(report.unavailable_reason) }}
        </div>
        <template v-else-if="report.summary && report.staff">
          <section class="overview" aria-label="工作量总览">
            <div class="section-title">
              <h2>工作量总览</h2>
              <span class="mq-status">{{ report.period_label }} · {{ sceneWorkLabel }}</span>
            </div>
            <p class="range-label">
              {{ rangeLabel(report.range) }}
            </p>
            <p
              v-if="report.defect_snapshot_coverage"
              class="context-notice"
              data-testid="staff-defect-snapshot-coverage"
            >
              可核实初审记录 {{ report.defect_snapshot_coverage.covered_initial_review_count }} /
              {{ report.defect_snapshot_coverage.initial_review_count }}，已知
              {{ report.defect_snapshot_coverage.known_defect_count }} 项缺陷。
              <template v-if="report.defect_snapshot_coverage.missing_initial_review_count > 0">
                {{ report.defect_snapshot_coverage.missing_initial_review_count }}
                次初审缺少完整缺陷明细，总数及该项排名未知。
              </template>
            </p>
            <div class="metric-grid">
              <div v-for="metric in summaryMetrics" :key="metric.label" class="metric mq-card">
                <span>{{ metric.label }}</span>
                <strong :class="{ 'is-text': typeof metric.value === 'string' }">{{
                  metric.value
                }}</strong>
                <small>{{ metric.note }}</small>
              </div>
            </div>
            <div
              v-if="report.context_unavailable_count > 0"
              class="context-notice"
              data-testid="staff-context-unavailable"
            >
              {{ report.context_unavailable_count }}
              条工作事件缺少可核实的任务或病例科室上下文，未纳入相应筛选结果。
            </div>
            <details class="metric-note mq-soft">
              <summary>统计口径</summary>
              <p>
                病历份数按机构、患者、就诊三坐标去重；审核次数按初审和复审动作计数。
                全局病历份数独立去重，不等于各质控员份数之和。人均以有工作记录的人员数为分母。
              </p>
            </details>
          </section>

          <section class="details mq-card" aria-label="人员明细">
            <div class="section-title">
              <h2>人员明细</h2>
              <div class="details-tools">
                <label class="rank-field"
                  >排名指标
                  <select
                    v-model="rankMetric"
                    class="mq-input"
                    data-testid="staff-rank-metric"
                    @change="loadReport"
                  >
                    <option v-for="metric in rowMetrics" :key="metric.key" :value="metric.key">
                      {{ metric.label }}
                    </option>
                  </select>
                </label>
                <span>共 {{ report.staff.length }} 人有工作记录</span>
              </div>
            </div>
            <div v-if="report.staff.length" class="table-scroll">
              <table class="mq-table staff-table">
                <thead>
                  <tr>
                    <th scope="col">排名</th>
                    <th scope="col">操作人</th>
                    <th v-for="metric in rowMetrics" :key="metric.key" scope="col">
                      {{ metric.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="staff in report.staff" :key="staff.user_id">
                    <td class="rank mq-mono">
                      {{ staff.rank ?? '未知' }}
                    </td>
                    <td class="name">
                      {{ staff.name || staff.user_id }}
                    </td>
                    <td v-for="metric in rowMetrics" :key="metric.key">
                      <button
                        v-if="
                          metricValue(staff, metric.key) !== null ||
                          (metric.key === 'confirmed_defect_count' &&
                            staff.defect_snapshot_coverage)
                        "
                        class="metric-link"
                        type="button"
                        :aria-label="`查看${staff.name || staff.user_id}的${metric.label}明细`"
                        @click="openDetails(staff, metric.key, metric.label)"
                      >
                        {{ metricValue(staff, metric.key) ?? '未知'
                        }}<small
                          v-if="
                            metric.key === 'confirmed_defect_count' &&
                            metricValue(staff, metric.key) === null
                          "
                          >（已知
                          {{
                            staff.defect_snapshot_coverage?.known_defect_count ?? '未知'
                          }}）</small
                        >
                      </button>
                      <span v-else class="unknown">未知</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="empty-state">该筛选范围暂无可核实的工作记录</div>
          </section>
        </template>
        <div v-else class="state-message unavailable">工作数据暂不可用</div>
      </template>

      <a-drawer
        v-model:open="drawerOpen"
        :title="drawerTitle"
        width="min(880px, 100vw)"
        :root-style="{ zIndex: 1100 }"
        destroy-on-close
      >
        <p
          v-if="detailsError"
          class="state-message error"
          role="alert"
          data-testid="staff-details-error"
        >
          {{ detailsError }}
        </p>
        <p v-else-if="detailsLoading" class="state-message" role="status">正在读取人员工作明细…</p>
        <template v-else-if="detailsPage">
          <p
            v-if="
              detailsPage.unavailable_reason &&
              detailsPage.unavailable_reason !== 'snapshot_incomplete'
            "
            class="state-message unavailable"
          >
            该指标在当前筛选条件下无法可靠下钻。
          </p>
          <template v-else>
            <div
              v-if="detailsPage.total_complete === false"
              class="drawer-summary mq-soft"
              data-testid="staff-details-known-only"
            >
              总数未知，可核实 {{ detailsPage.known_total ?? '未知' }} 条已知缺陷；{{
                detailsPage.defect_snapshot_coverage?.missing_initial_review_count ?? '未知'
              }}
              次初审缺少完整缺陷明细。
            </div>
            <div v-else class="drawer-summary mq-soft">
              共 {{ detailsPage.total ?? '未知' }} 条可核实记录
            </div>
            <div class="table-scroll drawer-table">
              <table class="mq-table">
                <thead>
                  <tr>
                    <th>发生时间</th>
                    <th>工作动作</th>
                    <th v-if="detailsPage.metric === 'confirmed_defect_count'">缺陷来源 / 标识</th>
                    <th>病例</th>
                    <th>科室 / 任务</th>
                    <th>阶段 / 决策</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in detailsPage.items || []" :key="item.event_id">
                    <td class="mq-mono">
                      {{ formatTime(item.occurred_at) }}
                    </td>
                    <td>{{ eventTypeText(item.event_type) }}</td>
                    <td v-if="detailsPage.metric === 'confirmed_defect_count'">
                      {{
                        item.source === 'auto' ? '自动' : item.source === 'manual' ? '人工' : '未知'
                      }}
                      · {{ item.defect_id || '未知' }}
                    </td>
                    <td class="mq-mono">
                      {{ identityText(item) }}
                    </td>
                    <td>
                      {{ item.department || '未知' }}<small>{{ item.task_id || '任务未知' }}</small>
                    </td>
                    <td>
                      {{ stageText(item.stage) }}<small>{{ decisionText(item.decision) }}</small>
                    </td>
                  </tr>
                  <tr v-if="!detailsPage.items?.length">
                    <td
                      :colspan="detailsPage.metric === 'confirmed_defect_count' ? 6 : 5"
                      class="empty-state"
                    >
                      暂无明细
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="detailPaginationTotal > detailsPage.page_size" class="pager">
              <button
                class="secondary mq-btn"
                type="button"
                :disabled="detailsPage.page <= 1 || detailsLoading"
                @click="loadDetails(detailsPage.page - 1)"
              >
                上一页
              </button>
              <span
                >{{ detailsPage.page }} /
                {{ Math.ceil(detailPaginationTotal / detailsPage.page_size) }}</span
              >
              <button
                class="secondary mq-btn"
                type="button"
                :disabled="
                  detailsPage.page * detailsPage.page_size >= detailPaginationTotal ||
                  detailsLoading
                "
                @click="loadDetails(detailsPage.page + 1)"
              >
                下一页
              </button>
            </div>
          </template>
        </template>
      </a-drawer>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
import ManualQualityReportPanel from './ManualQualityReportPanel.vue'
type ReportTab = 'staff' | 'manual'
const reportTabs: Array<{ value: ReportTab; label: string }> = [
  { value: 'staff', label: '质控员工作分析' },
  { value: 'manual', label: '人工质控报表' },
]
const reportTab = ref<ReportTab>('staff')
import { exportStaffAnalysis, getStaffAnalysis, getStaffAnalysisDetails } from '@/api/staffAnalysis'
import type {
  StaffAnalysisAppliedFilters,
  StaffAnalysisDetailItem,
  StaffAnalysisDetailsPage,
  StaffAnalysisFilters,
  StaffAnalysisMetric,
  StaffAnalysisPeriod,
  StaffAnalysisReport,
  StaffAnalysisScene,
  StaffWorkRow,
} from '@/api/staffAnalysis'

const periodOptions: Array<{ value: StaffAnalysisPeriod; label: string }> = [
  { value: 'this_week', label: '本周' },
  { value: 'last_week', label: '上周' },
  { value: 'this_month', label: '本月' },
]
const sceneOptions: Array<{ value: StaffAnalysisScene; label: string }> = [
  { value: 'all', label: '全部场景' },
  { value: 'running', label: '运行质控' },
  { value: 'final', label: '终末质控' },
]
const rowMetrics: Array<{ key: StaffAnalysisMetric; label: string }> = [
  { key: 'confirmed_defect_count', label: '质控缺陷' },
  { key: 'reviewed_case_count', label: '病历份数' },
  { key: 'rechecked_case_count', label: '复审病历份数' },
  { key: 'record_review_count', label: '审核次数' },
  { key: 'initial_count', label: '初审' },
  { key: 'recheck_count', label: '复审' },
  { key: 'manual_defect_created_count', label: '补录缺陷' },
  { key: 'manual_review_approved_count', label: '缺陷审核通过' },
  { key: 'manual_review_rejected_count', label: '缺陷驳回' },
  { key: 'appeal_approved_count', label: '申诉通过' },
  { key: 'appeal_rejected_count', label: '申诉驳回' },
  { key: 'urged_defect_count', label: '催办缺陷' },
]
const rankMetric = ref<StaffAnalysisMetric>('record_review_count')

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const scene = computed<StaffAnalysisScene>(() => {
  if (route.query.scene === 'running' || route.query.scene === 'final') return route.query.scene
  return 'all'
})
const authKey = computed(() => {
  const id = authStore.user?.id?.trim()
  if (!id) return ''
  return `${id}|${[...authStore.userRoles].sort().join(',')}`
})
const draft = reactive({
  period: 'this_month' as StaffAnalysisPeriod,
  departmentKey: '',
  task_id: '',
  start_date: '',
  end_date: '',
})
const appliedFilters = ref<StaffAnalysisFilters>({ period: draft.period, scene: scene.value })
const report = ref<StaffAnalysisReport | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const filterError = ref('')
const exporting = ref(false)
const drawerOpen = ref(false)
const drawerTitle = ref('人员工作明细')
const detailsPage = ref<StaffAnalysisDetailsPage | null>(null)
const detailPaginationTotal = computed(() =>
  detailsPage.value?.total_complete === false
    ? (detailsPage.value.known_total ?? 0)
    : (detailsPage.value?.total ?? 0),
)
const detailsLoading = ref(false)
const detailsError = ref('')
const detailSelection = ref<{ userId: string; metric: StaffAnalysisMetric } | null>(null)
let reportRequest = 0
let detailsRequest = 0
let exportRequest = 0

const sceneWorkLabel = computed(() => {
  if (report.value?.scene === 'running') return '运行质控工作记录'
  if (report.value?.scene === 'final') return '终末质控工作记录'
  return '全部工作记录'
})
const summaryMetrics = computed(() => {
  const summary = report.value?.summary
  if (!summary) return []
  const appealTotal =
    summary.appeal_approved_count === null || summary.appeal_rejected_count === null
      ? null
      : summary.appeal_approved_count + summary.appeal_rejected_count
  return [
    {
      label: '人均质控病历',
      value: summary.avg_reviewed_cases_per_active_staff ?? '不可用',
      note: '个人三坐标去重病历合计 / 活跃人员数',
    },
    {
      label: '人均复审病历',
      value: summary.avg_rechecked_cases_per_active_staff ?? '不可用',
      note: '个人三坐标去重复审病历合计 / 活跃人员数',
    },
    {
      label: '人均人工缺陷',
      value: summary.avg_manual_defects_per_active_staff ?? '不可用',
      note: '人工创建缺陷数 / 活跃人员数',
    },
    {
      label: '人均驳回缺陷',
      value: summary.avg_rejected_defects_per_active_staff ?? '不可用',
      note: '人工缺陷审核驳回数 / 活跃人员数',
    },
    { label: '审核病历', value: summary.reviewed_case_count, note: '全局三坐标去重' },
    {
      label: '审核次数',
      value: summary.record_review_count,
      note: `初审 ${summary.initial_count} · 复审 ${summary.recheck_count}`,
    },
    {
      label: '人均审核病历',
      value: summary.avg_reviewed_cases_per_reviewer ?? '不可用',
      note: `各人病历数合计 / ${summary.record_reviewer_count} 名审核人员`,
    },
    {
      label: '活跃工作人数',
      value: summary.active_staff_count,
      note: '筛选范围内有可核实工作动作',
    },
    { label: '补录人工缺陷', value: summary.manual_defect_created_count, note: '按创建动作计数' },
    {
      label: '初审确认质控缺陷',
      value: summary.confirmed_defect_count ?? '未知',
      note: '按初审记录统计，复审不重复',
    },
    {
      label: '人工缺陷审核',
      value: summary.manual_review_approved_count + summary.manual_review_rejected_count,
      note: `通过 ${summary.manual_review_approved_count} · 驳回 ${summary.manual_review_rejected_count}`,
    },
    {
      label: '申诉处理',
      value: appealTotal ?? '未知',
      note:
        appealTotal === null
          ? appealUnavailableText()
          : `通过 ${summary.appeal_approved_count} · 驳回 ${summary.appeal_rejected_count}`,
    },
  ]
})

function departmentKey(instituteId: string, department: string): string {
  return JSON.stringify([instituteId, department])
}
function selectedDepartment(): { institute_id: string; department: string } | null {
  if (!draft.departmentKey) return null
  try {
    const value: unknown = JSON.parse(draft.departmentKey)
    if (
      Array.isArray(value) &&
      value.length === 2 &&
      value.every((item) => typeof item === 'string' && item.trim())
    ) {
      return { institute_id: value[0].trim(), department: value[1].trim() }
    }
  } catch {
    return null
  }
  return null
}
function makeFilters(): StaffAnalysisFilters | null {
  filterError.value = ''
  if (Boolean(draft.start_date) !== Boolean(draft.end_date)) {
    filterError.value = '开始日期和结束日期必须同时填写'
    return null
  }
  if (draft.start_date && draft.start_date > draft.end_date) {
    filterError.value = '开始日期不能晚于结束日期'
    return null
  }
  const department = selectedDepartment()
  return {
    period: draft.period,
    scene: scene.value,
    ...(department || {}),
    ...(draft.task_id ? { task_id: draft.task_id } : {}),
    ...(draft.start_date ? { start_date: draft.start_date, end_date: draft.end_date } : {}),
  }
}
function frozenFilters(filters: StaffAnalysisAppliedFilters): StaffAnalysisFilters {
  return {
    period: filters.period,
    scene: filters.scene,
    ...(filters.institute_id && filters.department
      ? { institute_id: filters.institute_id, department: filters.department }
      : {}),
    ...(filters.task_id ? { task_id: filters.task_id } : {}),
    ...(filters.start_date && filters.end_date
      ? { start_date: filters.start_date, end_date: filters.end_date }
      : {}),
    as_of: filters.as_of,
  }
}
function invalidateSecondary(): void {
  ++detailsRequest
  ++exportRequest
  detailsLoading.value = false
  detailsPage.value = null
  detailsError.value = ''
  drawerOpen.value = false
  exporting.value = false
}
function clearAll(): void {
  ++reportRequest
  invalidateSecondary()
  loading.value = false
  report.value = null
  errorMessage.value = ''
}
async function loadReport(): Promise<void> {
  const identity = authKey.value
  if (!identity) {
    clearAll()
    return
  }
  const request = ++reportRequest
  invalidateSecondary()
  loading.value = true
  errorMessage.value = ''
  report.value = null
  const result =
    rankMetric.value === 'record_review_count'
      ? await getStaffAnalysis({ ...appliedFilters.value })
      : await getStaffAnalysis({ ...appliedFilters.value }, rankMetric.value)
  if (request !== reportRequest || identity !== authKey.value) return
  loading.value = false
  if (!result.success || !result.data) {
    errorMessage.value = result.message || '质控员工作分析暂不可用'
    return
  }
  report.value = result.data
}
function applyFilters(): void {
  const filters = makeFilters()
  if (!filters) return
  appliedFilters.value = filters
  void loadReport()
}
function resetFilters(): void {
  draft.period = 'this_month'
  draft.departmentKey = ''
  draft.task_id = ''
  draft.start_date = ''
  draft.end_date = ''
  applyFilters()
}
function setScene(value: StaffAnalysisScene): void {
  if (scene.value !== value)
    void router.replace({ path: route.path, query: { ...route.query, scene: value } })
}
function metricValue(row: StaffWorkRow, metric: StaffAnalysisMetric): number | null {
  return row[metric] ?? null
}
function openDetails(row: StaffWorkRow, metric: StaffAnalysisMetric, label: string): void {
  if (
    !report.value ||
    (metricValue(row, metric) === null &&
      !(metric === 'confirmed_defect_count' && row.defect_snapshot_coverage))
  )
    return
  detailSelection.value = { userId: row.user_id, metric }
  drawerTitle.value = `${row.name || row.user_id} · ${label}`
  drawerOpen.value = true
  void loadDetails(1)
}
async function loadDetails(page = 1): Promise<void> {
  const selection = detailSelection.value
  const currentReport = report.value
  const identity = authKey.value
  if (!selection || !currentReport || !identity) return
  const request = ++detailsRequest
  detailsLoading.value = true
  detailsError.value = ''
  detailsPage.value = null
  const result = await getStaffAnalysisDetails(
    selection.userId,
    frozenFilters(currentReport.filters),
    selection.metric,
    page,
    20,
  )
  if (request !== detailsRequest || identity !== authKey.value || !drawerOpen.value) return
  detailsLoading.value = false
  if (!result.success || !result.data) {
    detailsError.value = result.message || '人员工作明细暂不可用'
    return
  }
  detailsPage.value = result.data
}
async function download(): Promise<void> {
  const currentReport = report.value
  const identity = authKey.value
  if (!currentReport || !identity) return
  const request = ++exportRequest
  const filters = frozenFilters(currentReport.filters)
  const fingerprint = JSON.stringify(filters)
  exporting.value = true
  const result =
    currentReport.rank_metric && currentReport.rank_metric !== 'record_review_count'
      ? await exportStaffAnalysis(filters, currentReport.rank_metric)
      : await exportStaffAnalysis(filters)
  if (
    request !== exportRequest ||
    identity !== authKey.value ||
    fingerprint !== JSON.stringify(frozenFilters(currentReport.filters))
  )
    return
  exporting.value = false
  if (!result.success || !result.data) {
    errorMessage.value = result.message || '导出质控员工作分析失败'
    return
  }
  const url = URL.createObjectURL(result.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '质控员工作分析.csv'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function filterOptionsUnavailableText(reason: string): string {
  if (reason === 'task_source_unavailable') return '任务选项暂不可用'
  if (reason === 'department_source_unavailable') return '科室选项暂不可用'
  return '筛选选项暂不可用'
}

function appealUnavailableText(): string {
  const reasons = report.value?.unavailable_metrics
  if (
    reasons?.appeal_approved_count === 'filter_not_attributable' ||
    reasons?.appeal_rejected_count === 'filter_not_attributable'
  )
    return '当前筛选无法可靠归属'
  return reasons?.appeal_approved_count === 'scene_not_attributable' ||
    reasons?.appeal_rejected_count === 'scene_not_attributable'
    ? '当前场景无法可靠归属'
    : '数据暂不可用'
}
function unavailableText(reason: string): string {
  return reason === 'scene_not_attributable'
    ? '现有工作记录不能可靠区分当前场景，暂无该场景的质控员统计。'
    : '该场景的质控员工作分析暂不可用。'
}
function rangeLabel(range: StaffAnalysisReport['range']): string {
  return `统计时间：${formatTime(range.start)} 至 ${formatTime(range.end)}（北京时间，结束时间不含）`
}
function formatTime(value: string): string {
  const parsed = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  if (Number.isNaN(parsed.getTime())) return '未知'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
}
function eventTypeText(value: StaffAnalysisDetailItem['event_type']): string {
  return (
    {
      record_review: '病历审核',
      manual_defect_created: '补录人工缺陷',
      manual_review_approved: '人工缺陷审核通过',
      manual_review_rejected: '人工缺陷驳回',
      appeal_approved: '申诉通过',
      appeal_rejected: '申诉驳回',
      defect_urged: '缺陷催办',
      initial_defect_confirmed: '初审确认缺陷',
    } as const
  )[value]
}
function identityText(item: StaffAnalysisDetailItem): string {
  return item.institute_id && item.patient_id && item.visit_id
    ? `${item.institute_id} / ${item.patient_id} / ${item.visit_id}`
    : '无病例坐标'
}
function stageText(value: string | null): string {
  return ({ initial: '初审', recheck: '复审' } as Record<string, string>)[value || ''] || '未知'
}
function decisionText(value: string | null): string {
  return (
    (
      {
        approved: '通过',
        rejected: '驳回',
        doubtful: '存疑',
      } as Record<string, string>
    )[value || ''] || '结果未知'
  )
}

watch(
  [scene, authKey],
  ([nextScene, nextAuth], previous) => {
    const previousScene = previous?.[0]
    appliedFilters.value = { ...appliedFilters.value, scene: nextScene }
    if (previousScene !== undefined && previousScene !== nextScene) filterError.value = ''
    if (!nextAuth) clearAll()
    else void loadReport()
  },
  { immediate: true },
)
watch(drawerOpen, (open) => {
  if (!open) {
    ++detailsRequest
    detailsLoading.value = false
  }
})
onBeforeUnmount(() => {
  ++reportRequest
  ++detailsRequest
  ++exportRequest
})
</script>

<style scoped src="./styles/staff-analysis.css"></style>
