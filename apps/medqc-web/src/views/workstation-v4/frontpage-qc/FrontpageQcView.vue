<template>
  <section
    class="mq-page fpqc-page"
    aria-label="首页质控"
    data-testid="frontpage-qc-view"
  >
    <section class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">首页与结算清单 · 首页质控</span>
        <h1 class="mq-page-title fpqc-page__title">
          首页质控
          <span class="fpqc-page__scope">新版 · 2016 填写规范</span>
        </h1>
      </div>
      <div class="mq-page-head__actions">
        <nav
          v-if="canSwitchDataScope"
          class="mq-segmented mq-segmented--sm"
          aria-label="数据范围"
        >
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': applied.data_scope === 'home' }"
            :aria-pressed="applied.data_scope === 'home'"
            :disabled="scopeChanging"
            data-testid="fpqc-scope-home"
            @click="changeDataScope('home')"
          >
            本院病历
          </button>
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': applied.data_scope === 'all' }"
            :aria-pressed="applied.data_scope === 'all'"
            :disabled="scopeChanging"
            data-testid="fpqc-scope-all"
            @click="changeDataScope('all')"
          >
            含测试数据
          </button>
        </nav>
        <nav
          class="mq-segmented"
          aria-label="首页质控视图"
        >
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': activeView === 'records' }"
            :aria-pressed="activeView === 'records'"
            data-testid="fpqc-view-records"
            @click="activeView = 'records'"
          >
            病历结果
          </button>
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': activeView === 'analysis' }"
            :aria-pressed="activeView === 'analysis'"
            data-testid="fpqc-view-analysis"
            @click="activeView = 'analysis'"
          >
            结果分析
          </button>
        </nav>
        <button
          type="button"
          class="mq-btn"
          :disabled="runBusy || !selectedKeys.length"
          data-testid="fpqc-run-selected"
          @click="runSelected"
        >
          质控所选{{ selectedKeys.length ? `（${selectedKeys.length}）` : '' }}
        </button>
        <button
          type="button"
          class="mq-btn mq-btn--primary"
          :disabled="runBusy"
          data-testid="fpqc-run-filtered"
          @click="confirmOpen = true"
        >
          质控当前筛选
        </button>
      </div>
    </section>

    <section
      class="mq-card fpqc-metrics"
      aria-label="首页质控汇总"
    >
      <div
        v-for="metric in metrics"
        :key="metric.key"
        class="fpqc-metrics__item"
      >
        <MqIconTile
          :name="metric.icon"
          :tone="metric.tone"
          :size="36"
          :icon-size="20"
        />
        <span class="fpqc-metrics__label">{{ metric.label }}</span>
        <strong class="fpqc-metrics__value">{{ metric.value }}</strong>
        <span class="fpqc-metrics__unit">{{ metric.unit }}</span>
      </div>
    </section>

    <Alert
      v-if="activeView === 'records' && summaryUnavailable"
      type="warning"
      message="质控摘要暂不可用"
      show-icon
    >
      <template #action>
        <Button size="small" data-testid="fpqc-retry-summary" @click="loadSummary">重试摘要</Button>
      </template>
    </Alert>

    <FrontpageQcRunBar
      :run="run"
      :error="runError"
      :cancelling="cancelling"
      :poll-stopped="pollStopped"
      @cancel="cancel"
      @dismiss="dismiss"
      @retry-poll="retryPoll"
    />

    <section class="fpqc-toolbar">
      <form
        class="fpqc-toolbar__filters"
        aria-label="病历筛选条件"
        @submit.prevent="applyFilters"
      >
        <input
          v-if="activeView === 'records'"
          v-model="draft.keyword"
          class="fpqc-toolbar__control fpqc-toolbar__search"
          type="search"
          placeholder="搜索患者姓名、住院号"
          aria-label="关键词筛选"
        >
        <select
          v-model="draft.department"
          class="fpqc-toolbar__control fpqc-toolbar__dept"
          aria-label="科室筛选"
          :title="draft.department || '全部科室'"
        >
          <option value="">
            全部科室
          </option>
          <option
            v-for="name in departments"
            :key="name"
            :value="name"
          >
            {{ name }}
          </option>
        </select>
        <div
          class="fpqc-toolbar__control fpqc-toolbar__dates"
          role="group"
          aria-label="出院日期范围"
          :aria-invalid="dateRangeInvalid || undefined"
        >
          <span>出院</span>
          <label class="sr-only" for="fpqc-start-date">开始日期</label>
          <a-date-picker
            id="fpqc-start-date"
            :value="draft.start_date"
            @update:value="draft.start_date = typeof $event === 'string' ? $event : ''"
            value-format="YYYY-MM-DD"
            class="fpqc-toolbar__date-picker"
            :bordered="false"
          />
          <span>至</span>
          <label class="sr-only" for="fpqc-end-date">结束日期</label>
          <a-date-picker
            id="fpqc-end-date"
            :value="draft.end_date"
            @update:value="draft.end_date = typeof $event === 'string' ? $event : ''"
            value-format="YYYY-MM-DD"
            class="fpqc-toolbar__date-picker"
            :bordered="false"
          />
        </div>
        <select
          v-if="activeView === 'records'"
          v-model="draft.grade"
          class="fpqc-toolbar__control"
          aria-label="等级筛选"
        >
          <option value="">
            全部等级
          </option>
          <option value="excellent">
            优秀
          </option>
          <option value="qualified">
            合格
          </option>
          <option value="unqualified">
            不合格
          </option>
        </select>
        <select
          v-if="activeView === 'records'"
          v-model="draft.issue"
          class="fpqc-toolbar__control"
          aria-label="问题筛选"
        >
          <option value="">
            全部病历
          </option>
          <option value="fail">
            有扣分问题
          </option>
          <option value="required_missing">
            有必填缺项
          </option>
          <option
            v-if="!confirmedResultsOnly"
            value="hint"
          >
            有提示
          </option>
          <option
            v-if="!confirmedResultsOnly"
            value="data_gap"
          >
            有资料不足
          </option>
          <option value="clean">
            无问题
          </option>
          <option value="unchecked">
            未质控
          </option>
        </select>
        <span
          v-if="activeView === 'records' && ruleFilter && (!confirmedResultsOnly || ruleFilter.rule_verdict !== 'data_gap')"
          class="fpqc-toolbar__rule"
          data-testid="fpqc-rule-filter"
        >
          {{ ruleFilter.rule_verdict === 'data_gap' ? '资料不足' : '命中规则' }}：<span class="mq-mono">{{ ruleFilter.rule_id }}</span>
          {{ ruleFilter.rule_name }}
          <button
            type="button"
            class="fpqc-toolbar__rule-clear"
            aria-label="清除规则筛选"
            @click="clearRuleFilter"
          >×</button>
        </span>
        <button
          type="submit"
          class="fpqc-toolbar__btn fpqc-toolbar__btn--primary"
          :disabled="loading || scopeChanging"
        >
          查询
        </button>
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="loading || scopeChanging"
          @click="resetFilters"
        >
          重置
        </button>
      </form>
      <div class="fpqc-toolbar__tools">
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="exporting || !selectedKeys.length || applied.issue === 'unchecked'"
          data-testid="fpqc-export-selected"
          @click="exportSelected"
        >
          导出所选
        </button>
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="exporting || applied.issue === 'unchecked'"
          data-testid="fpqc-export-filtered"
          @click="exportFiltered"
        >
          {{ exporting ? '正在导出…' : '导出当前筛选' }}
        </button>
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="loading || scopeChanging"
          @click="refreshAll"
        >
          刷新
        </button>
      </div>
    </section>

    <p
      v-if="dateRangeError"
      class="fpqc-page__notice fpqc-page__notice--error"
      role="alert"
      data-testid="fpqc-date-error"
    >
      {{ dateRangeError }}
    </p>

    <p
      v-if="noticeError"
      class="fpqc-page__notice fpqc-page__notice--error"
      role="alert"
      data-testid="fpqc-page-error"
    >
      {{ noticeError }}
    </p>

    <p
      v-if="notice"
      class="fpqc-page__notice fpqc-page__notice--status"
      role="status"
      data-testid="fpqc-page-notice"
    >
      {{ notice }}
    </p>

    <section
      v-if="activeView === 'records'"
      class="fpqc-split"
    >
      <div
        class="mq-card fpqc-list"
        :aria-busy="listBusy"
      >
        <header class="fpqc-list__head">
          <h2>病历结果</h2>
          <span>共 {{ total }} 份</span>
          <span
            v-if="selectedKeys.length"
            class="fpqc-list__selected"
          >已选 {{ selectedKeys.length }} 份</span>
          <button
            v-if="selectedKeys.length"
            type="button"
            class="fpqc-list__clear"
            @click="clearSelection"
          >
            清空
          </button>
        </header>
        <Alert
          v-if="!listBusy && loadError"
          type="error"
          message="病历列表加载失败"
          :description="loadError"
          show-icon
        >
          <template #action>
            <Button
              size="small"
              data-testid="fpqc-retry-list"
              @click="loadList(lastRequestedPage)"
            >
              重试
            </Button>
          </template>
        </Alert>
        <Spin
          v-if="rows.length || listBusy || !loadError"
          :spinning="listBusy"
          tip="正在加载病历列表…"
        >
          <FrontpageQcRecordTable
            v-if="rows.length || listBusy"
            :rows="rows"
            :selected="selectedKeys"
            :active-key="activeKey"
            empty-message=""
            @select="selectRecord"
            @update:selected="updateSelection"
          />
          <Empty
            v-else
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            description="当前筛选条件下没有病历"
          />
        </Spin>
        <footer
          v-if="total > 0"
          class="fpqc-list__pager"
        >
          <Pagination
            :current="page"
            :page-size="pageSize"
            :total="total"
            :disabled="listBusy"
            :page-size-options="WORKSTATION_LIST_PAGE_SIZE_OPTIONS"
            :locale="WORKSTATION_LIST_PAGINATION_LOCALE"
            show-size-changer
            show-quick-jumper
            size="small"
            @change="handlePageChange"
          />
        </footer>
      </div>
      <FrontpageQcPreview
        :record="activeRow"
        :refresh-key="previewRefreshKey"
        :run-busy="runBusy"
        @rerun="runOne"
      />
    </section>

    <FrontpageQcAnalysisPanel
      v-else
      :filters="scopeFilters"
      :refresh-key="analyticsRefreshKey"
      @drill-rule="drillRule"
      @drill-department="drillDepartment"
      @summary-loaded="syncSummaryFromAnalysis"
    />

    <!-- 质控当前筛选：页面内弹窗，跟随工作台主题（静态 Modal.confirm 拿不到嵌套主题） -->
    <Modal
      :open="confirmOpen"
      :footer="null"
      :width="460"
      centered
      wrap-class-name="mq-modal"
      :mask-style="{ backdropFilter: 'blur(6px)' }"
      @cancel="confirmOpen = false"
    >
      <div
        v-if="confirmOpen"
        class="fpqc-confirm"
        data-testid="fpqc-confirm"
      >
        <MqIconTile
          name="fp_qc"
          tone="brand"
          :size="52"
          :icon-size="28"
        />
        <div class="fpqc-confirm__copy">
          <h2>质控当前筛选范围</h2>
          <p>
            对范围内已出院病历的首页重新质控，单次最多 <b>500</b> 份。等级、问题和规则筛选不影响范围，不调用模型。
          </p>
        </div>
        <dl class="mq-soft fpqc-confirm__summary">
          <div v-if="canSwitchDataScope">
            <dt>数据范围</dt>
            <dd>{{ applied.data_scope === 'all' ? '含测试数据' : '本院病历' }}</dd>
          </div>
          <div>
            <dt>科室</dt>
            <dd>{{ applied.department || '全部科室' }}</dd>
          </div>
          <div>
            <dt>出院日期</dt>
            <dd>{{ appliedDateLabel }}</dd>
          </div>
          <div v-if="applied.keyword">
            <dt>关键词</dt>
            <dd>{{ applied.keyword }}</dd>
          </div>
        </dl>
        <div class="fpqc-confirm__actions">
          <button
            type="button"
            class="mq-btn"
            @click="confirmOpen = false"
          >
            取消
          </button>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            data-testid="fpqc-confirm-ok"
            @click="runFiltered"
          >
            开始质控
          </button>
        </div>
      </div>
    </Modal>
  </section>
</template>

<script setup lang="ts">
import { Alert, Button, DatePicker as ADatePicker, Empty, Modal, Pagination, Spin } from 'ant-design-vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter, type LocationQuery, type LocationQueryValue } from 'vue-router'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { useAuthStore } from '@/stores/auth'

import MqIconTile from '@/components/icons/MqIconTile.vue'
import type { MqIconName, MqIconTone } from '@/components/icons/mqIcons'
import {
  exportFrontpageQcRecords,
  getFrontpageQcAnalytics,
  getFrontpageQcFilters,
  isFrontpageQcAbortError,
  isFrontpageQcRunActive,
  listFrontpageQcRecords,
  type FrontpageQcAnalytics,
  type FrontpageQcDataScope,
  type FrontpageQcGrade,
  type FrontpageQcIssueFilter,
  type FrontpageQcRecordItem,
  type FrontpageQcRef,
  type FrontpageQcRun,
  type FrontpageQcScopeFilters,
} from '@/services/frontpage-qc-v2-service'

import { downloadBlob } from '../customer-sample-validation/batchExport'
import {
  WORKSTATION_LIST_PAGE_SIZE,
  WORKSTATION_LIST_PAGE_SIZE_OPTIONS,
  WORKSTATION_LIST_PAGINATION_LOCALE,
} from '../utils/workstationListPagination'
import FrontpageQcAnalysisPanel from './FrontpageQcAnalysisPanel.vue'
import FrontpageQcPreview from './FrontpageQcPreview.vue'
import FrontpageQcRecordTable from './FrontpageQcRecordTable.vue'
import FrontpageQcRunBar from './FrontpageQcRunBar.vue'
import { formatPercent, formatScore } from './presentation'
import { useFrontpageQcRun } from './useFrontpageQcRun'

interface FilterState extends Required<FrontpageQcScopeFilters> {
  grade: FrontpageQcGrade | ''
  issue: FrontpageQcIssueFilter
}

interface RuleFilterState {
  rule_id: string
  rule_name: string
  rule_verdict: 'fail' | 'data_gap'
}

const UNFILLED_DEPARTMENT = '未填科室'
const DATE_RANGE_ERROR_TEXT = '开始日期不能晚于结束日期'
const VALID_GRADES = new Set<FrontpageQcGrade>(['excellent', 'qualified', 'unqualified'])
const VALID_ISSUES = new Set<FrontpageQcIssueFilter>([
  'fail',
  'hint',
  'required_missing',
  'data_gap',
  'clean',
  'unchecked',
])
const VALID_PAGE_SIZES = new Set<number>(WORKSTATION_LIST_PAGE_SIZE_OPTIONS.map((value) => Number(value)))
const SYNCED_QUERY_KEYS = [
  'view',
  'data_scope',
  'department',
  'start_date',
  'end_date',
  'keyword',
  'grade',
  'issue',
  'rule_id',
  'rule_verdict',
  'page',
  'page_size',
  'record_key',
] as const

const emptyFilters = (): FilterState => ({
  data_scope: 'home',
  keyword: '',
  department: '',
  start_date: '',
  end_date: '',
  grade: '',
  issue: '',
})

function safeUseRoute() {
  try {
    const current = useRoute()
    return current && typeof current === 'object' && 'query' in current ? current : null
  } catch {
    return null
  }
}

function safeUseRouter() {
  try {
    const current = useRouter()
    return current && typeof current === 'object' && typeof current.replace === 'function' ? current : null
  } catch {
    return null
  }
}

function readQueryString(value: LocationQueryValue | LocationQueryValue[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw.trim() : ''
}

function sameScopeFilters(a: FrontpageQcScopeFilters, b: FrontpageQcScopeFilters): boolean {
  return (
    (a.data_scope || 'home') === (b.data_scope || 'home') &&
    (a.department || '') === (b.department || '') &&
    (a.start_date || '') === (b.start_date || '') &&
    (a.end_date || '') === (b.end_date || '')
  )
}

const route = safeUseRoute()
const router = safeUseRouter()

const activeView = ref<'records' | 'analysis'>('records')
const draft = reactive<FilterState>(emptyFilters())
const applied = reactive<FilterState>(emptyFilters())
const departments = ref<string[]>([])
const homeInstitute = ref('')
const scopeChanging = ref(false)
const rows = ref<FrontpageQcRecordItem[]>([])
const total = ref(0)
const page = ref(1)
const lastRequestedPage = ref(1)
const pageSize = ref(WORKSTATION_LIST_PAGE_SIZE)
const loading = ref(false)
const listBusy = computed(() => loading.value || scopeChanging.value)
const loadError = ref('')
const notice = ref('')
const noticeError = ref('')
const exporting = ref(false)
const auth = useAuthStore()
const { confirmedResultsOnly } = useQcResultVisibility()
const normalizedRoles = computed(() => {
  const raw = Array.isArray(auth.user?.roles)
    ? auth.user.roles
    : auth.user?.role
      ? [auth.user.role]
      : Array.isArray(auth.userRoles)
        ? auth.userRoles
        : []
  return new Set(raw.map((role) => String(role || '').trim().toLowerCase()).filter(Boolean))
})
const boundInstitute = computed(() =>
  String(auth.user?.institute_id || auth.user?.hospital_id || '').trim(),
)
const isGlobalAdmin = computed(() => {
  const roles = normalizedRoles.value
  if (roles.has('sync_admin')) return true
  return (roles.has('admin') || roles.has('super_admin')) && !boundInstitute.value
})
const canSwitchDataScope = computed(
  () => Boolean(homeInstitute.value) && !confirmedResultsOnly.value && isGlobalAdmin.value,
)
const dateRangeInvalid = computed(() =>
  Boolean(draft.start_date && draft.end_date && draft.start_date > draft.end_date),
)
const dateRangeError = computed(() => (dateRangeInvalid.value ? DATE_RANGE_ERROR_TEXT : ''))

let alive = true
let exportGeneration = 0
let exportAlive = true
let listSeq = 0
let summarySeq = 0
let filterSeq = 0
let summaryLoading = false
let recordsDirty = false
let syncingFromRoute = false
let listController: AbortController | null = null
let summaryController: AbortController | null = null
let filterController: AbortController | null = null
let exportController: AbortController | null = null

const activeKey = ref('')
const previewRefreshKey = ref(0)
const analyticsRefreshKey = ref(0)
const summary = ref<FrontpageQcAnalytics['summary'] | null>(null)
const summaryUnavailable = ref(false)
const selectedKeys = ref<string[]>([])
const selectedRefs = ref<Record<string, FrontpageQcRef>>({})
const confirmOpen = ref(false)
/** 从结果分析下钻的规则筛选；与等级、问题筛选叠加，不影响“质控当前筛选”的范围 */
const ruleFilter = ref<RuleFilterState | null>(null)
const exportIdentity = computed(() => JSON.stringify([
  auth.user?.id, auth.user?.institute_id, auth.user?.hospital_id, auth.user?.roles,
  auth.userRoles, auth.user?.is_active, draft, applied, ruleFilter.value,
]))
watch(exportIdentity, () => {
  exportGeneration++
  exportController?.abort()
  exportController = null
  exporting.value = false
})

const { run, starting, cancelling, pollStopped, error: runError, start, cancel, resume, retryPoll, dismiss } =
  useFrontpageQcRun(handleRunFinished)

const runBusy = computed(() => starting.value || (isFrontpageQcRunActive(run.value) && !pollStopped.value))
const activeRow = computed(() => rows.value.find((row) => row.record_key === activeKey.value) ?? null)
const scopeFilters = computed<FrontpageQcScopeFilters>(() => ({
  data_scope: applied.data_scope,
  department: applied.department,
  start_date: applied.start_date,
  end_date: applied.end_date,
}))
const appliedDateLabel = computed(() =>
  applied.start_date || applied.end_date
    ? `${applied.start_date || '不限'} 至 ${applied.end_date || '不限'}`
    : '不限',
)

const metrics = computed<
  Array<{ key: string; label: string; value: string; unit: string; icon: MqIconName; tone: MqIconTone }>
>(() => {
  const data = summary.value
  const records = data?.records ?? 0
  return [
    { key: 'records', label: '已质控首页', value: data ? String(records) : '—', unit: '份', icon: 'stack', tone: 'brand' },
    { key: 'score', label: '平均分', value: formatScore(data?.avg_score ?? null), unit: '分', icon: 'fp_qc', tone: 'brand' },
    {
      key: 'excellent',
      label: '优秀率（≥90 分）',
      value: records ? formatPercent((data?.grades.excellent ?? 0) / records) : '—',
      unit: '',
      icon: 'success',
      tone: 'success',
    },
    { key: 'issue', label: '有扣分问题', value: data ? String(data.issue_records) : '—', unit: '份', icon: 'issue', tone: 'danger' },
  ]
})

function parseQueryState(query: LocationQuery) {
  const view: 'records' | 'analysis' = readQueryString(query.view) === 'analysis' ? 'analysis' : 'records'
  const rawScope = readQueryString(query.data_scope)
  const data_scope: FrontpageQcDataScope =
    rawScope === 'all' && !confirmedResultsOnly.value && isGlobalAdmin.value ? 'all' : 'home'
  const department = readQueryString(query.department)
  const start_date = readQueryString(query.start_date)
  const end_date = readQueryString(query.end_date)
  const keyword = readQueryString(query.keyword)
  const rawGrade = readQueryString(query.grade)
  const grade: FrontpageQcGrade | '' = VALID_GRADES.has(rawGrade as FrontpageQcGrade)
    ? (rawGrade as FrontpageQcGrade)
    : ''
  const rawIssue = readQueryString(query.issue)
  let issue: FrontpageQcIssueFilter = VALID_ISSUES.has(rawIssue as FrontpageQcIssueFilter)
    ? (rawIssue as FrontpageQcIssueFilter)
    : ''
  if (confirmedResultsOnly.value && (issue === 'hint' || issue === 'data_gap')) {
    issue = ''
  }
  const rawRuleId = readQueryString(query.rule_id)
  const rawVerdict = readQueryString(query.rule_verdict)
  const ruleVerdict: 'fail' | 'data_gap' = rawVerdict === 'data_gap' ? 'data_gap' : 'fail'
  let parsedRule: RuleFilterState | null = null
  if (rawRuleId && !(confirmedResultsOnly.value && ruleVerdict === 'data_gap')) {
    const preservedName =
      ruleFilter.value?.rule_id === rawRuleId && ruleFilter.value.rule_verdict === ruleVerdict
        ? ruleFilter.value.rule_name
        : ''
    parsedRule = { rule_id: rawRuleId, rule_name: preservedName, rule_verdict: ruleVerdict }
    if (issue === 'unchecked') issue = ''
  }
  const parsedPage = Number.parseInt(readQueryString(query.page), 10)
  const nextPage = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1
  const parsedPageSize = Number.parseInt(readQueryString(query.page_size), 10)
  const nextPageSize = VALID_PAGE_SIZES.has(parsedPageSize) ? parsedPageSize : WORKSTATION_LIST_PAGE_SIZE
  const recordKey = readQueryString(query.record_key)

  const invalidDates = Boolean(start_date && end_date && start_date > end_date)
  const draftState: FilterState = {
    data_scope,
    keyword,
    department,
    start_date,
    end_date,
    grade,
    issue,
  }
  const appliedState: FilterState = invalidDates
    ? { ...draftState, start_date: '', end_date: '' }
    : { ...draftState }

  return {
    view,
    draftState,
    appliedState,
    rule: parsedRule,
    page: nextPage,
    pageSize: nextPageSize,
    recordKey,
  }
}

function hydrateFromQuery(query: LocationQuery) {
  const parsed = parseQueryState(query)
  activeView.value = parsed.view
  Object.assign(draft, parsed.draftState)
  Object.assign(applied, parsed.appliedState)
  ruleFilter.value = parsed.rule
  page.value = parsed.page
  lastRequestedPage.value = parsed.page
  pageSize.value = parsed.pageSize
  activeKey.value = parsed.recordKey
}

function buildStateQueryValues(): Record<(typeof SYNCED_QUERY_KEYS)[number], string> {
  return {
    view: activeView.value === 'analysis' ? 'analysis' : '',
    data_scope: applied.data_scope === 'all' ? 'all' : '',
    department: applied.department || '',
    start_date: applied.start_date || '',
    end_date: applied.end_date || '',
    keyword: applied.keyword || '',
    grade: applied.grade || '',
    issue: applied.issue || '',
    rule_id: ruleFilter.value?.rule_id || '',
    rule_verdict: ruleFilter.value ? ruleFilter.value.rule_verdict : '',
    page: page.value > 1 ? String(page.value) : '',
    page_size: pageSize.value !== WORKSTATION_LIST_PAGE_SIZE ? String(pageSize.value) : '',
    record_key: activeKey.value || '',
  }
}

function normalizedQuerySignature(query: LocationQuery): string {
  const parsed = parseQueryState(query)
  return JSON.stringify({
    view: parsed.view === 'analysis' ? 'analysis' : '',
    data_scope: parsed.appliedState.data_scope === 'all' ? 'all' : '',
    department: parsed.appliedState.department || '',
    start_date: parsed.appliedState.start_date || '',
    end_date: parsed.appliedState.end_date || '',
    keyword: parsed.appliedState.keyword || '',
    grade: parsed.appliedState.grade || '',
    issue: parsed.appliedState.issue || '',
    rule_id: parsed.rule?.rule_id || '',
    rule_verdict: parsed.rule ? parsed.rule.rule_verdict : '',
    page: parsed.page > 1 ? String(parsed.page) : '',
    page_size: parsed.pageSize !== WORKSTATION_LIST_PAGE_SIZE ? String(parsed.pageSize) : '',
    record_key: parsed.recordKey || '',
  })
}

function stateQuerySignature(): string {
  return JSON.stringify(buildStateQueryValues())
}

function listQuerySignature(): string {
  return JSON.stringify({
    ...applied,
    ...ruleQuery(),
    page: page.value,
    page_size: pageSize.value,
  })
}

function syncUrlFromState() {
  if (!router || !route || syncingFromRoute || !alive) return
  const nextValues = buildStateQueryValues()
  if (normalizedQuerySignature(route.query) === JSON.stringify(nextValues)) return
  const nextQuery: Record<string, LocationQueryValue | LocationQueryValue[]> = { ...route.query }
  for (const key of SYNCED_QUERY_KEYS) {
    const val = nextValues[key]
    if (val) nextQuery[key] = val
    else delete nextQuery[key]
  }
  void Promise.resolve(router.replace({ query: nextQuery })).catch(() => undefined)
}

if (route?.query) {
  hydrateFromQuery(route.query)
}

async function loadList(targetPage = page.value) {
  listController?.abort()
  const controller = new AbortController()
  listController = controller
  const seq = ++listSeq
  lastRequestedPage.value = targetPage
  loading.value = true
  loadError.value = ''
  try {
    const data = await listFrontpageQcRecords(
      {
        ...applied,
        ...ruleQuery(),
        page: targetPage,
        page_size: pageSize.value,
      },
      { signal: controller.signal },
    )
    if (!alive || seq !== listSeq || controller.signal.aborted) return
    rows.value = data.items
    total.value = data.total
    page.value = data.page
    lastRequestedPage.value = data.page
    if (!rows.value.some((row) => row.record_key === activeKey.value)) {
      activeKey.value = rows.value[0]?.record_key ?? ''
    }
    rememberRefs(data.items)
    syncUrlFromState()
  } catch (error) {
    if (!alive || seq !== listSeq || controller.signal.aborted || isFrontpageQcAbortError(error)) return
    loadError.value = error instanceof Error ? error.message : '读取首页质控结果失败'
  } finally {
    if (alive && seq === listSeq) loading.value = false
    if (listController === controller) listController = null
  }
}

async function loadSummary() {
  summaryController?.abort()
  const controller = new AbortController()
  summaryController = controller
  const seq = ++summarySeq
  summaryLoading = true
  try {
    const data = await getFrontpageQcAnalytics(scopeFilters.value, { signal: controller.signal })
    if (!alive || seq !== summarySeq || controller.signal.aborted) return
    summary.value = data.summary
    summaryUnavailable.value = false
  } catch (error) {
    if (!alive || seq !== summarySeq || controller.signal.aborted || isFrontpageQcAbortError(error)) return
    summary.value = null
    summaryUnavailable.value = true
  } finally {
    if (seq === summarySeq) summaryLoading = false
    if (summaryController === controller) summaryController = null
  }
}

function syncSummaryFromAnalysis(
  filters: FrontpageQcScopeFilters,
  next: FrontpageQcAnalytics['summary'],
) {
  if (!sameScopeFilters(filters, scopeFilters.value)) return
  summary.value = next
  summaryUnavailable.value = false
}

async function loadFilterOptions(
  targetScope: FrontpageQcDataScope = applied.data_scope,
  options: { pruneApplied?: boolean; reloadOnPrune?: boolean } = {},
): Promise<string[] | null> {
  const { pruneApplied = true, reloadOnPrune = false } = options
  filterController?.abort()
  const controller = new AbortController()
  filterController = controller
  const seq = ++filterSeq
  try {
    const data = await getFrontpageQcFilters({ data_scope: targetScope }, { signal: controller.signal })
    if (!alive || seq !== filterSeq || controller.signal.aborted) return null
    departments.value = data.departments
    homeInstitute.value = data.home_institute
    if (noticeError.value === '读取筛选项失败，请重试') {
      noticeError.value = ''
    }
    if (pruneApplied) {
      let appliedChanged = false
      if (draft.department && !departments.value.includes(draft.department)) draft.department = ''
      if (applied.department && !departments.value.includes(applied.department)) {
        applied.department = ''
        appliedChanged = true
      }
      if (!canSwitchDataScope.value && (draft.data_scope !== 'home' || applied.data_scope !== 'home')) {
        draft.data_scope = 'home'
        applied.data_scope = 'home'
        appliedChanged = true
      }
      if (appliedChanged) {
        syncUrlFromState()
        if (reloadOnPrune) {
          if (activeView.value === 'records') {
            void loadList(1)
            void loadSummary()
          } else {
            recordsDirty = true
          }
        }
      }
    }
    return data.departments
  } catch (error) {
    if (!alive || seq !== filterSeq || controller.signal.aborted || isFrontpageQcAbortError(error)) return null
    departments.value = []
    notice.value = ''
    noticeError.value = '读取筛选项失败，请重试'
    return null
  } finally {
    if (filterController === controller) filterController = null
  }
}

async function changeDataScope(scope: FrontpageQcDataScope) {
  if (!canSwitchDataScope.value || scopeChanging.value || scope === applied.data_scope) return
  scopeChanging.value = true
  clearSelection()
  // 使旧范围的在途请求失效，避免切换期间回填旧结果。
  listSeq += 1
  summarySeq += 1
  listController?.abort()
  summaryController?.abort()
  try {
    const nextDepartments = await loadFilterOptions(scope, { pruneApplied: false })
    if (!alive) return
    draft.data_scope = scope
    applied.data_scope = scope
    if (nextDepartments && draft.department && !nextDepartments.includes(draft.department)) {
      draft.department = ''
    }
    if (nextDepartments && applied.department && !nextDepartments.includes(applied.department)) {
      applied.department = ''
    }
    page.value = 1
    lastRequestedPage.value = 1
    syncUrlFromState()
    if (activeView.value === 'records') {
      recordsDirty = false
      await Promise.all([loadList(1), loadSummary()])
    } else {
      recordsDirty = true
    }
  } finally {
    if (alive) scopeChanging.value = false
  }
}

function selectRecord(key: string) {
  activeKey.value = key
  syncUrlFromState()
}

function rememberRefs(items: FrontpageQcRecordItem[]) {
  const next = { ...selectedRefs.value }
  for (const item of items) {
    if (selectedKeys.value.includes(item.record_key)) {
      next[item.record_key] = { institute_id: item.institute_id, patient_id: item.patient_id, visit_id: item.visit_id }
    }
  }
  selectedRefs.value = next
}

function updateSelection(keys: string[]) {
  selectedKeys.value = keys
  const next: Record<string, FrontpageQcRef> = {}
  for (const key of keys) {
    const row = rows.value.find((item) => item.record_key === key)
    const known = selectedRefs.value[key]
    if (row) next[key] = { institute_id: row.institute_id, patient_id: row.patient_id, visit_id: row.visit_id }
    else if (known) next[key] = known
  }
  selectedRefs.value = next
}

function clearSelection() {
  selectedKeys.value = []
  selectedRefs.value = {}
}

function ruleQuery() {
  const rule = ruleFilter.value
  return rule ? { rule_id: rule.rule_id, rule_verdict: rule.rule_verdict } : {}
}

function clearRuleFilter() {
  ruleFilter.value = null
  clearSelection()
  page.value = 1
  lastRequestedPage.value = 1
  syncUrlFromState()
  void loadList(1)
}

function drillRule(rule: RuleFilterState) {
  if (confirmedResultsOnly.value && rule.rule_verdict === 'data_gap') return
  ruleFilter.value = rule
  // 按规则只能看已质控病历；“未质控”与之冲突时清掉
  if (draft.issue === 'unchecked') draft.issue = ''
  if (applied.issue === 'unchecked') applied.issue = ''
  activeView.value = 'records'
  clearSelection()
  page.value = 1
  lastRequestedPage.value = 1
  recordsDirty = false
  syncUrlFromState()
  void loadList(1)
}

function drillDepartment(department: string) {
  const normalized = String(department || '').trim()
  if (!normalized || normalized === UNFILLED_DEPARTMENT) return
  draft.department = normalized
  activeView.value = 'records'
  applyFilters()
}

function applyFilters() {
  if (dateRangeInvalid.value) return
  if (ruleFilter.value && draft.issue === 'unchecked') ruleFilter.value = null
  const scopeChanged = !sameScopeFilters(applied, draft)
  Object.assign(applied, draft)
  clearSelection()
  page.value = 1
  lastRequestedPage.value = 1
  syncUrlFromState()
  if (activeView.value === 'records') {
    recordsDirty = false
    void loadList(1)
    void loadSummary()
  } else {
    recordsDirty = true
    if (!scopeChanged) analyticsRefreshKey.value += 1
  }
}

async function resetFilters() {
  if (scopeChanging.value) return
  const scopeChanged = applied.data_scope !== 'home'
  const hadScopeDiff = !sameScopeFilters(applied, emptyFilters())
  if (scopeChanged) {
    scopeChanging.value = true
    listSeq += 1
    summarySeq += 1
    listController?.abort()
    summaryController?.abort()
    try {
      await loadFilterOptions('home', { pruneApplied: false })
    } finally {
      if (alive) scopeChanging.value = false
    }
    if (!alive) return
  }
  Object.assign(draft, emptyFilters())
  Object.assign(applied, emptyFilters())
  ruleFilter.value = null
  clearSelection()
  page.value = 1
  lastRequestedPage.value = 1
  syncUrlFromState()
  if (activeView.value === 'records') {
    recordsDirty = false
    void loadList(1)
    void loadSummary()
  } else {
    recordsDirty = true
    if (!hadScopeDiff) analyticsRefreshKey.value += 1
  }
}

function refreshAll() {
  void resume()
  if (activeView.value === 'records') {
    recordsDirty = false
    void loadList()
    void loadSummary()
    previewRefreshKey.value += 1
  } else {
    recordsDirty = true
    analyticsRefreshKey.value += 1
  }
}

function handlePageChange(nextPage: number, nextSize: number) {
  if (nextSize !== pageSize.value) {
    pageSize.value = nextSize
    page.value = 1
    syncUrlFromState()
    void loadList(1)
    return
  }
  void loadList(nextPage)
}

function selectedRefList(): FrontpageQcRef[] {
  return selectedKeys.value.map((key) => selectedRefs.value[key]).filter((item): item is FrontpageQcRef => Boolean(item))
}

function runSelected() {
  const refs = selectedRefList()
  if (!refs.length) return
  notice.value = ''
  noticeError.value = ''
  void start({ record_refs: refs })
}

function runOne(ref: FrontpageQcRef) {
  notice.value = ''
  noticeError.value = ''
  void start({ record_refs: [ref] })
}

function runFiltered() {
  confirmOpen.value = false
  notice.value = ''
  noticeError.value = ''
  void start({
    data_scope: applied.data_scope,
    department: applied.department,
    start_date: applied.start_date,
    end_date: applied.end_date,
    keyword: applied.keyword,
  })
}

function handleRunFinished(finished: FrontpageQcRun) {
  if (finished.status === 'completed' || finished.status === 'completed_with_errors') {
    noticeError.value = ''
    notice.value = `首页质控完成：${finished.success_count} 份已出结果${finished.issue_records ? `，其中 ${finished.issue_records} 份有扣分问题` : ''}`
  }
  clearSelection()
  refreshAll()
}

async function exportWith(body: Parameters<typeof exportFrontpageQcRecords>[0], filename: string) {
  if (exporting.value || applied.issue === 'unchecked') return
  const generation = ++exportGeneration
  const identity = exportIdentity.value
  const current = () => exportAlive && generation === exportGeneration && identity === exportIdentity.value
  const frozenBody = JSON.parse(JSON.stringify(body)) as typeof body
  exportController?.abort()
  const controller = new AbortController()
  exportController = controller
  exporting.value = true
  notice.value = ''
  noticeError.value = ''
  try {
    const blob = await exportFrontpageQcRecords(frozenBody, { signal: controller.signal })
    if (!current() || controller.signal.aborted) return
    downloadBlob(blob, filename)
    notice.value = '已开始下载'
  } catch (error) {
    if (current() && !controller.signal.aborted && !isFrontpageQcAbortError(error)) {
      noticeError.value = error instanceof Error ? error.message : '导出失败'
    }
  } finally {
    if (exportController === controller) exportController = null
    if (current()) exporting.value = false
  }
}

function exportSelected() {
  const refs = selectedRefList()
  if (!refs.length) return
  void exportWith({ record_refs: refs }, `首页质控-所选${refs.length}份.xlsx`)
}

function exportFiltered() {
  if (applied.issue === 'unchecked') return
  void exportWith(
    { ...applied, ...ruleQuery() },
    '首页质控-当前筛选.xlsx',
  )
}

watch(canSwitchDataScope, (allowed) => {
  if (!allowed && (draft.data_scope !== 'home' || applied.data_scope !== 'home')) {
    draft.data_scope = 'home'
    applied.data_scope = 'home'
    syncUrlFromState()
  }
})

watch(confirmedResultsOnly, (onlyConfirmed) => {
  if (!onlyConfirmed) return
  if (draft.issue === 'hint' || draft.issue === 'data_gap') draft.issue = ''
  if (applied.issue === 'hint' || applied.issue === 'data_gap') applied.issue = ''
  if (ruleFilter.value?.rule_verdict === 'data_gap') ruleFilter.value = null
  syncUrlFromState()
})

watch(activeView, (view) => {
  syncUrlFromState()
  if (view === 'records') {
    if (recordsDirty) {
      recordsDirty = false
      void loadList(page.value)
    }
    if (!summaryLoading && (!summary.value || summaryUnavailable.value)) {
      void loadSummary()
    }
  }
})

if (route) {
  watch(
    () => route.query,
    (nextQuery) => {
      if (!alive || !nextQuery) return
      if (normalizedQuerySignature(nextQuery) === stateQuerySignature()) return
      const prevScope = applied.data_scope
      const prevScopeFilters: FrontpageQcScopeFilters = { ...scopeFilters.value }
      const prevListSig = listQuerySignature()
      syncingFromRoute = true
      try {
        hydrateFromQuery(nextQuery)
      } finally {
        syncingFromRoute = false
      }
      const scopeChanged = applied.data_scope !== prevScope
      const scopeFiltersChanged = !sameScopeFilters(prevScopeFilters, scopeFilters.value)
      const listChanged = listQuerySignature() !== prevListSig
      if (scopeChanged) {
        void loadFilterOptions(applied.data_scope, { reloadOnPrune: false })
      }
      if (activeView.value === 'records') {
        if (listChanged || recordsDirty) {
          recordsDirty = false
          void loadList(page.value)
        }
        if (scopeFiltersChanged || (!summaryLoading && !summary.value)) {
          void loadSummary()
        }
      } else if (listChanged) {
        recordsDirty = true
      }
    },
  )
}

onMounted(() => {
  void resume()
  if (activeView.value === 'records') {
    void loadSummary()
    void Promise.all([
      loadFilterOptions(applied.data_scope, { reloadOnPrune: true }),
      loadList(page.value),
    ])
  } else {
    recordsDirty = true
    void loadFilterOptions(applied.data_scope, { reloadOnPrune: true })
  }
})

onBeforeUnmount(() => {
  alive = false
  exportAlive = false
  exportGeneration++
  listSeq += 1
  summarySeq += 1
  filterSeq += 1
  listController?.abort()
  listController = null
  summaryController?.abort()
  summaryController = null
  filterController?.abort()
  filterController = null
  exportController?.abort()
  exportController = null
})
</script>

<style scoped src="../styles/frontpage-qc.css"></style>
