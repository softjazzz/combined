<template>
  <main
    class="mq-page fpqc-page"
    data-testid="frontpage-qc-view"
  >
    <section class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">首页与结算清单 · 按 2016 版首页填写规范</span>
        <h1 class="mq-page-title">
          首页质控<span class="fpqc-page__badge">新</span>
        </h1>
      </div>
      <div class="mq-page-head__actions">
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
          @click="confirmRunFiltered"
        >
          质控当前筛选
        </button>
      </div>
    </section>

    <section
      class="fpqc-page__metrics"
      aria-label="首页质控汇总"
    >
      <article
        v-for="metric in metrics"
        :key="metric.key"
        class="mq-card fpqc-page__metric"
      >
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.hint }}</small>
        <MqIconTile
          class="fpqc-page__metric-icon"
          :name="metric.icon"
          :tone="metric.tone"
          :size="36"
          :icon-size="20"
        />
      </article>
    </section>

    <FrontpageQcRunBar
      :run="run"
      :error="runError"
      :cancelling="cancelling"
      @cancel="cancel"
      @dismiss="dismiss"
    />

    <section class="mq-card fpqc-page__toolbar">
      <form
        class="fpqc-page__filters"
        aria-label="病历筛选条件"
        @submit.prevent="applyFilters"
      >
        <label class="mq-field fpqc-page__field fpqc-page__field--wide">
          <span class="mq-field__label">关键词</span>
          <input
            v-model="draft.keyword"
            class="mq-input"
            type="search"
            placeholder="患者、住院号"
            aria-label="关键词筛选"
          >
        </label>
        <label class="mq-field fpqc-page__field">
          <span class="mq-field__label">科室</span>
          <select
            v-model="draft.department"
            class="mq-input"
            aria-label="科室筛选"
          >
            <option value="">全部科室</option>
            <option
              v-for="name in departments"
              :key="name"
              :value="name"
            >
              {{ name }}
            </option>
          </select>
        </label>
        <div
          class="mq-field fpqc-page__field fpqc-page__field--dates"
          role="group"
          aria-label="出院日期范围"
        >
          <span class="mq-field__label">出院日期</span>
          <div class="fpqc-page__dates">
            <input
              v-model="draft.start_date"
              class="mq-input"
              type="date"
              aria-label="开始日期"
            >
            <span>至</span>
            <input
              v-model="draft.end_date"
              class="mq-input"
              type="date"
              aria-label="结束日期"
            >
          </div>
        </div>
        <label class="mq-field fpqc-page__field">
          <span class="mq-field__label">等级</span>
          <select
            v-model="draft.grade"
            class="mq-input"
            aria-label="等级筛选"
          >
            <option value="">全部等级</option>
            <option value="excellent">优秀</option>
            <option value="qualified">合格</option>
            <option value="unqualified">不合格</option>
          </select>
        </label>
        <label class="mq-field fpqc-page__field">
          <span class="mq-field__label">问题</span>
          <select
            v-model="draft.issue"
            class="mq-input"
            aria-label="问题筛选"
          >
            <option value="">全部病历</option>
            <option value="fail">有扣分问题</option>
            <option value="hint">有提示</option>
            <option value="data_gap">有资料不足</option>
            <option value="clean">无问题</option>
            <option value="unchecked">未质控</option>
          </select>
        </label>
        <div class="fpqc-page__filter-actions">
          <button
            type="submit"
            class="mq-btn mq-btn--primary"
            :disabled="loading"
          >
            查询
          </button>
          <button
            type="button"
            class="mq-btn"
            :disabled="loading"
            @click="resetFilters"
          >
            重置
          </button>
        </div>
      </form>
      <div class="fpqc-page__tools">
        <button
          type="button"
          class="mq-btn"
          :disabled="exporting || !selectedKeys.length"
          data-testid="fpqc-export-selected"
          @click="exportSelected"
        >
          导出所选
        </button>
        <button
          type="button"
          class="mq-btn"
          :disabled="exporting"
          data-testid="fpqc-export-filtered"
          @click="exportFiltered"
        >
          {{ exporting ? '正在导出…' : '导出当前筛选' }}
        </button>
        <button
          type="button"
          class="mq-btn"
          :disabled="loading"
          @click="refreshAll"
        >
          刷新
        </button>
      </div>
    </section>

    <p
      v-if="notice"
      class="fpqc-page__notice"
      role="status"
    >
      {{ notice }}
    </p>

    <section
      v-if="activeView === 'records'"
      class="fpqc-page__split"
    >
      <div class="mq-card fpqc-page__list">
        <header class="fpqc-page__list-head">
          <h2>病历结果</h2>
          <span>共 {{ total }} 份 · 本页 {{ rows.length }} 份</span>
          <span
            v-if="selectedKeys.length"
            class="fpqc-page__selected"
          >已选 {{ selectedKeys.length }} 份
            <button
              type="button"
              class="fpqc-page__link"
              @click="clearSelection"
            >清空</button></span>
        </header>
        <FrontpageQcRecordTable
          :rows="rows"
          :selected="selectedKeys"
          :active-key="activeKey"
          :empty-message="emptyMessage"
          @select="activeKey = $event"
          @update:selected="updateSelection"
        />
        <footer
          v-if="total > pageSize"
          class="fpqc-page__pager"
        >
          <Pagination
            :current="page"
            :page-size="pageSize"
            :total="total"
            :disabled="loading"
            :page-size-options="['15', '30', '50', '100']"
            :locale="{ items_per_page: '条/页', jump_to: '跳至', page: '页' }"
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
    />
  </main>
</template>

<script setup lang="ts">
import { Modal, Pagination } from 'ant-design-vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import MqIconTile from '@/components/icons/MqIconTile.vue'
import type { MqIconName, MqIconTone } from '@/components/icons/mqIcons'
import {
  exportFrontpageQcRecords,
  getFrontpageQcAnalytics,
  getFrontpageQcFilters,
  isFrontpageQcRunActive,
  listFrontpageQcRecords,
  type FrontpageQcAnalytics,
  type FrontpageQcGrade,
  type FrontpageQcIssueFilter,
  type FrontpageQcRecordItem,
  type FrontpageQcRef,
  type FrontpageQcRun,
  type FrontpageQcScopeFilters,
} from '@/services/frontpage-qc-v2-service'

import { downloadBlob } from '../customer-sample-validation/batchExport'
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

const emptyFilters = (): FilterState => ({
  keyword: '',
  department: '',
  start_date: '',
  end_date: '',
  grade: '',
  issue: '',
})

const activeView = ref<'records' | 'analysis'>('records')
const draft = reactive<FilterState>(emptyFilters())
const applied = reactive<FilterState>(emptyFilters())
const departments = ref<string[]>([])
const rows = ref<FrontpageQcRecordItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(15)
const loading = ref(false)
const loadError = ref('')
const notice = ref('')
const exporting = ref(false)
const activeKey = ref('')
const previewRefreshKey = ref(0)
const analyticsRefreshKey = ref(0)
const summary = ref<FrontpageQcAnalytics['summary'] | null>(null)
const selectedKeys = ref<string[]>([])
const selectedRefs = ref<Record<string, FrontpageQcRef>>({})
let listSeq = 0

const { run, starting, cancelling, error: runError, start, cancel, resume, dismiss } =
  useFrontpageQcRun(handleRunFinished)

const runBusy = computed(() => starting.value || isFrontpageQcRunActive(run.value))
const activeRow = computed(() => rows.value.find((row) => row.record_key === activeKey.value) ?? null)
const scopeFilters = computed<FrontpageQcScopeFilters>(() => ({
  department: applied.department,
  start_date: applied.start_date,
  end_date: applied.end_date,
}))
const emptyMessage = computed(() => {
  if (loading.value) return '正在加载…'
  if (loadError.value) return loadError.value
  return '当前筛选条件下没有病历'
})

const metrics = computed<
  Array<{ key: string; label: string; value: string; hint: string; icon: MqIconName; tone: MqIconTone }>
>(() => {
  const data = summary.value
  const records = data?.records ?? 0
  return [
    { key: 'records', label: '已质控首页', value: String(records), hint: '份（当前科室与日期范围）', icon: 'stack', tone: 'brand' },
    { key: 'score', label: '平均分', value: formatScore(data?.avg_score ?? null), hint: '满分 100', icon: 'fp_qc', tone: 'success' },
    {
      key: 'excellent',
      label: '优秀率',
      value: records ? formatPercent((data?.grades.excellent ?? 0) / records) : '—',
      hint: '≥ 90 分',
      icon: 'success',
      tone: 'success',
    },
    { key: 'issue', label: '有扣分问题', value: String(data?.issue_records ?? 0), hint: '份', icon: 'issue', tone: 'danger' },
  ]
})

async function loadList(targetPage = page.value) {
  const seq = ++listSeq
  loading.value = true
  loadError.value = ''
  try {
    const data = await listFrontpageQcRecords({ ...applied, page: targetPage, page_size: pageSize.value })
    if (seq !== listSeq) return
    rows.value = data.items
    total.value = data.total
    page.value = data.page
    if (!rows.value.some((row) => row.record_key === activeKey.value)) {
      activeKey.value = rows.value[0]?.record_key ?? ''
    }
    rememberRefs(data.items)
  } catch (error) {
    if (seq !== listSeq) return
    rows.value = []
    total.value = 0
    loadError.value = error instanceof Error ? error.message : '读取首页质控结果失败'
  } finally {
    if (seq === listSeq) loading.value = false
  }
}

async function loadSummary() {
  try {
    summary.value = (await getFrontpageQcAnalytics(scopeFilters.value)).summary
  } catch {
    summary.value = null
  }
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

function applyFilters() {
  Object.assign(applied, draft)
  clearSelection()
  void loadList(1)
  void loadSummary()
  analyticsRefreshKey.value += 1
}

function resetFilters() {
  Object.assign(draft, emptyFilters())
  applyFilters()
}

function refreshAll() {
  void loadList()
  void loadSummary()
  previewRefreshKey.value += 1
  analyticsRefreshKey.value += 1
}

function handlePageChange(nextPage: number, nextSize: number) {
  if (nextSize !== pageSize.value) {
    pageSize.value = nextSize
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
  void start({ record_refs: refs })
}

function runOne(ref: FrontpageQcRef) {
  notice.value = ''
  void start({ record_refs: [ref] })
}

function confirmRunFiltered() {
  const parts = [applied.department || '全部科室']
  if (applied.start_date || applied.end_date) parts.push(`出院 ${applied.start_date || '不限'} 至 ${applied.end_date || '不限'}`)
  if (applied.keyword) parts.push(`关键词“${applied.keyword}”`)
  Modal.confirm({
    title: '质控当前筛选范围内的首页？',
    content: `范围：${parts.join('，')}。将对范围内全部已出院病历重新质控（等级、问题筛选不影响范围），单次最多 500 份。不调用模型。`,
    okText: '开始质控',
    cancelText: '取消',
    wrapClassName: 'mq-modal',
    onOk: () => {
      notice.value = ''
      void start({
        department: applied.department,
        start_date: applied.start_date,
        end_date: applied.end_date,
        keyword: applied.keyword,
      })
    },
  })
}

function handleRunFinished(finished: FrontpageQcRun) {
  if (finished.status === 'completed' || finished.status === 'completed_with_errors') {
    notice.value = `首页质控完成：${finished.success_count} 份已出结果${finished.issue_records ? `，其中 ${finished.issue_records} 份有扣分问题` : ''}`
  }
  clearSelection()
  refreshAll()
}

async function exportWith(body: Parameters<typeof exportFrontpageQcRecords>[0], filename: string) {
  if (exporting.value) return
  exporting.value = true
  notice.value = ''
  try {
    downloadBlob(await exportFrontpageQcRecords(body), filename)
    notice.value = '已开始下载'
  } catch (error) {
    notice.value = error instanceof Error ? error.message : '导出失败'
  } finally {
    exporting.value = false
  }
}

function exportSelected() {
  const refs = selectedRefList()
  if (!refs.length) return
  void exportWith({ record_refs: refs }, `首页质控-所选${refs.length}份.xlsx`)
}

function exportFiltered() {
  const { issue, ...rest } = applied
  void exportWith({ ...rest, issue: issue === 'unchecked' ? '' : issue }, '首页质控-当前筛选.xlsx')
}

watch(activeView, (view) => {
  if (view === 'analysis') analyticsRefreshKey.value += 1
})

onMounted(async () => {
  void resume()
  void loadSummary()
  await loadList(1)
  try {
    departments.value = (await getFrontpageQcFilters()).departments
  } catch {
    departments.value = []
  }
})
</script>

<style scoped>
.fpqc-page__badge {
  display: inline-flex;
  align-items: center;
  margin-left: 10px;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--mq-info-bg);
  color: var(--mq-info-text);
  font-family: var(--mq-font-family);
  font-size: var(--mq-font-12);
  font-weight: 600;
  letter-spacing: 0;
  vertical-align: middle;
}

.fpqc-page__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.fpqc-page__metric {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 16px 20px;
}

.fpqc-page__metric span {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.fpqc-page__metric strong {
  font-family: var(--mq-font-display);
  font-size: 28px;
  line-height: 1.15;
}

.fpqc-page__metric small {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.fpqc-page__metric-icon {
  position: absolute;
  top: 16px;
  right: 18px;
}

.fpqc-page__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px 16px;
  padding: 16px 20px;
}

.fpqc-page__filters {
  display: flex;
  flex: 1 1 640px;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}

.fpqc-page__field {
  flex: 0 1 150px;
}

.fpqc-page__field--wide {
  flex: 1 1 180px;
}

.fpqc-page__field--dates {
  flex: 0 1 300px;
}

.fpqc-page__dates {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--mq-text-tertiary);
}

.fpqc-page__filter-actions,
.fpqc-page__tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fpqc-page__notice {
  margin: 0;
  padding: 10px 16px;
  border-radius: 12px;
  background: var(--mq-info-bg);
  color: var(--mq-info-text);
  font-size: var(--mq-font-13);
}

.fpqc-page__split {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(340px, 1fr);
  align-items: start;
  gap: 16px;
}

.fpqc-page__list {
  min-width: 0;
  overflow: hidden;
}

.fpqc-page__list-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 14px;
  padding: 16px 20px 12px;
}

.fpqc-page__list-head h2 {
  margin: 0;
  font-size: var(--mq-font-16, 16px);
}

.fpqc-page__list-head span {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}

.fpqc-page__selected {
  color: var(--mq-brand-600) !important;
  font-weight: 600;
}

.fpqc-page__link {
  margin-left: 4px;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.fpqc-page__pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 20px 16px;
}

@media (max-width: 1100px) {
  .fpqc-page__split {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
