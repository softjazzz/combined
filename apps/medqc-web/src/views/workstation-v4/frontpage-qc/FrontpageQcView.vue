<template>
  <main
    class="mq-page fpqc-page"
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

    <FrontpageQcRunBar
      :run="run"
      :error="runError"
      :cancelling="cancelling"
      @cancel="cancel"
      @dismiss="dismiss"
    />

    <section class="fpqc-toolbar">
      <form
        class="fpqc-toolbar__filters"
        aria-label="病历筛选条件"
        @submit.prevent="applyFilters"
      >
        <input
          v-model="draft.keyword"
          class="fpqc-toolbar__control fpqc-toolbar__search"
          type="search"
          placeholder="搜索患者姓名、住院号"
          aria-label="关键词筛选"
        >
        <select
          v-model="draft.department"
          class="fpqc-toolbar__control"
          aria-label="科室筛选"
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
        >
          <span>出院</span>
          <input
            v-model="draft.start_date"
            type="date"
            aria-label="开始日期"
          >
          <span>至</span>
          <input
            v-model="draft.end_date"
            type="date"
            aria-label="结束日期"
          >
        </div>
        <select
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
          <option value="hint">
            有提示
          </option>
          <option value="data_gap">
            有资料不足
          </option>
          <option value="clean">
            无问题
          </option>
          <option value="unchecked">
            未质控
          </option>
        </select>
        <button
          type="submit"
          class="fpqc-toolbar__btn fpqc-toolbar__btn--primary"
          :disabled="loading"
        >
          查询
        </button>
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="loading"
          @click="resetFilters"
        >
          重置
        </button>
      </form>
      <div class="fpqc-toolbar__tools">
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="exporting || !selectedKeys.length"
          data-testid="fpqc-export-selected"
          @click="exportSelected"
        >
          导出所选
        </button>
        <button
          type="button"
          class="fpqc-toolbar__btn"
          :disabled="exporting"
          data-testid="fpqc-export-filtered"
          @click="exportFiltered"
        >
          {{ exporting ? '正在导出…' : '导出当前筛选' }}
        </button>
        <button
          type="button"
          class="fpqc-toolbar__btn"
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
      class="fpqc-split"
    >
      <div class="mq-card fpqc-list">
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
          class="fpqc-list__pager"
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
            对范围内已出院病历的首页重新质控，单次最多 <b>500</b> 份。等级、问题筛选不影响范围，不调用模型。
          </p>
        </div>
        <dl class="mq-soft fpqc-confirm__summary">
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
const confirmOpen = ref(false)
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
    { key: 'records', label: '已质控首页', value: String(records), unit: '份', icon: 'stack', tone: 'brand' },
    { key: 'score', label: '平均分', value: formatScore(data?.avg_score ?? null), unit: '分', icon: 'fp_qc', tone: 'brand' },
    {
      key: 'excellent',
      label: '优秀率（≥90 分）',
      value: records ? formatPercent((data?.grades.excellent ?? 0) / records) : '—',
      unit: '',
      icon: 'success',
      tone: 'success',
    },
    { key: 'issue', label: '有扣分问题', value: String(data?.issue_records ?? 0), unit: '份', icon: 'issue', tone: 'danger' },
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

function runFiltered() {
  confirmOpen.value = false
  notice.value = ''
  void start({
    department: applied.department,
    start_date: applied.start_date,
    end_date: applied.end_date,
    keyword: applied.keyword,
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

<style scoped src="../styles/frontpage-qc.css"></style>
