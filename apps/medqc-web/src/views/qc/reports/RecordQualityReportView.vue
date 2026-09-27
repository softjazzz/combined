<template>
  <main class="report-page">
    <header class="page-head">
      <div>
        <h1>病历质量分析</h1>
        <p>{{ scene === 'running' ? '当前在院病历的已完成质控结果' : '终末归档病历质量分析' }}</p>
      </div>
      <div class="head-actions">
        <button class="secondary" type="button" :disabled="loading" @click="loadReport">
          <RefreshCw :size="16" />刷新
        </button>
        <button
          class="secondary"
          type="button"
          :disabled="!report || exporting !== null"
          @click="download('departments')"
        >
          <Download :size="16" />科室 CSV
        </button>
        <button
          class="secondary"
          type="button"
          :disabled="!report || exporting !== null"
          @click="download('doctors')"
        >
          <Download :size="16" />医生 CSV
        </button>
      </div>
    </header>

    <section class="filters" aria-label="报表筛选">
      <div class="field scene-field">
        <label>场景</label>
        <div class="segmented">
          <button
            type="button"
            :class="{ active: scene === 'running' }"
            @click="setScene('running')"
          >
            运行病历</button
          ><button type="button" :class="{ active: scene === 'final' }" @click="setScene('final')">
            终末病历
          </button>
        </div>
      </div>
      <div class="field">
        <label for="report-department">科室</label
        ><input id="report-department" v-model.trim="draft.department" placeholder="全部科室" />
      </div>
      <div class="field">
        <label for="report-doctor">主治医师</label
        ><input id="report-doctor" v-model.trim="draft.doctor" placeholder="全部医生" />
      </div>
      <div class="field">
        <label for="report-from">完成时间起</label
        ><input id="report-from" v-model="draft.completed_from" type="datetime-local" />
      </div>
      <div class="field">
        <label for="report-to">完成时间止</label
        ><input id="report-to" v-model="draft.completed_to" type="datetime-local" />
      </div>
      <div class="field">
        <label for="report-source">质控类型</label
        ><select id="report-source" v-model="draft.defect_source">
          <option value="all">全部</option>
          <option value="auto">自动缺陷</option>
          <option value="manual">人工缺陷</option>
        </select>
      </div>
      <button class="primary" type="button" @click="applyFilters"><Search :size="16" />查询</button>
      <button class="secondary" type="button" @click="resetFilters">重置</button>
    </section>

    <div v-if="loading" class="status" role="status">正在读取病历质量报表…</div>
    <div v-else-if="loadError" class="status error" role="alert" data-testid="report-error">
      <CircleAlert :size="18" />{{ loadError }}
    </div>
    <template v-else-if="report">
      <section class="overview" aria-label="总览">
        <h2>总览</h2>
        <div class="metrics">
          <div v-for="item in kpiCards" :key="item.label" class="metric">
            <span>{{ item.label }}</span
            ><strong>{{ item.value }}</strong
            ><small>{{ item.note }}</small>
          </div>
        </div>
        <div v-if="report.kpis.qc_unavailable_total" class="notice">
          {{ report.kpis.qc_unavailable_total }} 份病历的质控结果无法读取，未纳入已完成结果统计。
        </div>
        <div
          v-if="
            report.source_status?.manual_defect === 'unavailable' ||
            report.source_status?.review === 'unavailable'
          "
          class="notice"
        >
          部分来源暂不可用，相关指标显示“不可用”。
        </div>
      </section>

      <section class="distribution" aria-label="分布">
        <h2>分布</h2>
        <div class="distribution-grid">
          <div v-if="report.score_standard.status === 'configured'" class="data-panel">
            <h3>等级分布</h3>
            <div
              v-for="item in report.grade_distribution || []"
              :key="item.grade || 'unknown'"
              class="data-row"
            >
              <span>{{ item.grade || '未分级' }}</span
              ><strong>{{ item.count }}</strong>
            </div>
            <p v-if="!report.grade_distribution?.length" class="empty">暂无数据</p>
          </div>
          <div v-if="report.score_standard.status === 'configured'" class="data-panel">
            <h3>得分分布</h3>
            <div
              v-for="item in report.score_distribution || []"
              :key="item.bucket"
              class="data-row"
            >
              <span>{{ item.bucket }}</span
              ><strong>{{ item.count }}</strong>
            </div>
            <p v-if="!report.score_distribution?.length" class="empty">暂无数据</p>
          </div>
          <div class="data-panel">
            <h3>缺陷等级</h3>
            <template v-if="report.defect_level_distribution"
              ><div
                v-for="item in report.defect_level_distribution"
                :key="item.name"
                class="data-row"
              >
                <span>{{ item.name }}</span
                ><strong>{{ item.defect_total }}</strong>
              </div>
              <p v-if="!report.defect_level_distribution.length" class="empty">
                暂无数据
              </p></template
            >
            <p v-else class="empty">不可用</p>
          </div>
          <div class="data-panel">
            <h3>文书分布</h3>
            <template v-if="report.document_distribution"
              ><button
                v-for="item in report.document_distribution"
                :key="item.name"
                class="data-row row-button"
                type="button"
                @click="openDrilldown({ document: item.name }, `文书：${item.name}`)"
              >
                <span>{{ item.name }}</span
                ><strong>{{ item.defect_total }}</strong>
              </button>
              <p v-if="!report.document_distribution.length" class="empty">暂无数据</p></template
            >
            <p v-else class="empty">不可用</p>
          </div>
        </div>
        <div class="top-panel">
          <div class="top-head">
            <h3>缺陷 Top 20</h3>
            <div class="segmented">
              <button
                v-for="tab in topTabs"
                :key="tab.key"
                type="button"
                :class="{ active: activeTop === tab.key }"
                @click="activeTop = tab.key"
              >
                {{ tab.label }}
              </button>
            </div>
          </div>
          <p v-if="activeTopRows === null" class="empty">不可用</p>
          <p v-else-if="!activeTopRows.length" class="empty">暂无数据</p>
          <div v-else class="top-grid">
            <button
              v-for="(item, index) in activeTopRows"
              :key="`${item.name}-${index}`"
              type="button"
              class="top-row"
              @click="openTop(item)"
            >
              <span class="rank">{{ index + 1 }}</span
              ><span class="top-name">{{ item.rule_name || item.name }}</span
              ><strong>{{ item.defect_total }}</strong>
            </button>
          </div>
        </div>
      </section>

      <section class="details" aria-label="明细">
        <div class="section-head">
          <h2>明细</h2>
          <div class="head-actions">
            <label class="column-picker"
              ><Columns3 :size="16" />显示列<select
                v-model="columnPreset"
                @change="applyColumnPreset"
              >
                <option value="all">全部</option>
                <option value="quality">质量</option>
                <option value="defects">缺陷</option>
              </select></label
            >
          </div>
        </div>
        <div class="column-options">
          <label v-for="column in optionalColumns" :key="column.key"
            ><input
              v-model="visibleColumns"
              type="checkbox"
              :value="column.key"
              @change="saveColumns"
            />{{ column.label }}</label
          >
        </div>
        <div class="table-panel">
          <div class="table-head">
            <h3>科室明细</h3>
            <span>{{ report.department_rows.length }} 个科室</span>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>科室</th>
                  <th v-for="column in shownColumns" :key="column.key">{{ column.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in report.department_rows" :key="row.name">
                  <td>
                    <button
                      class="link"
                      type="button"
                      @click="openDrilldown({ department: row.name }, `科室：${row.name}`)"
                    >
                      {{ row.name }}
                    </button>
                  </td>
                  <td v-for="column in shownColumns" :key="column.key">
                    {{ cellValue(row, column.key) }}
                  </td>
                </tr>
                <tr v-if="!report.department_rows.length">
                  <td :colspan="shownColumns.length + 1" class="empty">暂无数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="table-panel">
          <div class="table-head">
            <h3>医生明细</h3>
            <span>{{ report.doctor_rows.length }} 位医生</span>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>主治医师</th>
                  <th v-for="column in shownColumns" :key="column.key">{{ column.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in report.doctor_rows" :key="row.name">
                  <td>
                    <button
                      class="link"
                      type="button"
                      @click="openDrilldown({ doctor: row.name }, `医生：${row.name}`)"
                    >
                      {{ row.name }}
                    </button>
                  </td>
                  <td v-for="column in shownColumns" :key="column.key">
                    {{ cellValue(row, column.key) }}
                  </td>
                </tr>
                <tr v-if="!report.doctor_rows.length">
                  <td :colspan="shownColumns.length + 1" class="empty">暂无数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
      <section class="unavailable">
        <h2>暂未接入的维度</h2>
        <p v-for="item in report.unavailable_dimensions" :key="item.key">
          {{ item.label }}：{{ unavailableReason(item.reason_code) }}
        </p>
      </section>
    </template>

    <a-drawer v-model:open="drawerOpen" :title="drilldownTitle" :width="900" destroy-on-close>
      <div class="drawer-actions">
        <span>{{ recordsPage ? `共 ${recordsPage.total} 份病历` : '病例明细' }}</span
        ><button
          class="secondary"
          type="button"
          :disabled="!recordsPage || exporting !== null"
          @click="download('records')"
        >
          <Download :size="16" />导出病例 CSV
        </button>
      </div>
      <p v-if="recordsError" class="status error" role="alert">{{ recordsError }}</p>
      <p v-else-if="recordsLoading" class="status">正在读取病例…</p>
      <div v-else-if="recordsPage" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>患者 / 就诊号</th>
              <th>科室 / 医生</th>
              <th>完成时间</th>
              <th>得分 / 等级</th>
              <th>自动 / 人工缺陷</th>
              <th>审核状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in recordsPage.items"
              :key="`${row.institute_id}/${row.patient_id}/${row.visit_id}`"
            >
              <td>
                <strong>{{ row.patient_name || '姓名未知' }}</strong
                ><small>{{ row.visit_id }}</small>
              </td>
              <td>
                {{ row.department || '未知' }}<small>{{ row.doctor || '未知' }}</small>
              </td>
              <td>{{ formatTime(row.completed_at) }}</td>
              <td>{{ scoreText(row.score) }} / {{ row.grade || '未分级' }}</td>
              <td>
                {{ numberText(row.auto_defect_total) }} / {{ numberText(row.manual_defect_total) }}
              </td>
              <td>{{ reviewText(row.review_state) }}</td>
            </tr>
            <tr v-if="!recordsPage.items.length">
              <td colspan="6" class="empty">暂无病例</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="recordsPage && recordsPage.total > recordsPage.page_size" class="pager">
        <button
          class="secondary"
          type="button"
          :disabled="recordsPage.page <= 1 || recordsLoading"
          @click="changePage(recordsPage.page - 1)"
        >
          上一页</button
        ><span
          >{{ recordsPage.page }} / {{ Math.ceil(recordsPage.total / recordsPage.page_size) }}</span
        ><button
          class="secondary"
          type="button"
          :disabled="
            recordsPage.page * recordsPage.page_size >= recordsPage.total || recordsLoading
          "
          @click="changePage(recordsPage.page + 1)"
        >
          下一页
        </button>
      </div>
    </a-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { CircleAlert, Columns3, Download, RefreshCw, Search } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import {
  exportRecordQualityReport,
  getRecordQualityRecords,
  getRecordQualityReport,
} from '@/api/qualityReports'
import type {
  DefectSource,
  RecordDrilldownFilters,
  RecordQualityFilters,
  RecordQualityRecordsPage,
  RecordQualityReport,
  ReportDistributionItem,
  ReportGroupRow,
  ReportScene,
  ReportSheet,
} from '@/api/qualityReports'

type ColumnKey =
  | 'record_total'
  | 'qc_ready_total'
  | 'average_score'
  | 'top_grade_rate'
  | 'review_approved_total'
  | 'auto_defect_total'
  | 'manual_defect_total'
  | 'veto_defect_total'
  | 'records_with_defect'
const optionalColumns: Array<{ key: ColumnKey; label: string }> = [
  { key: 'record_total', label: '病历数' },
  { key: 'qc_ready_total', label: '已质控' },
  { key: 'average_score', label: '平均分' },
  { key: 'top_grade_rate', label: '首档率' },
  { key: 'review_approved_total', label: '审核通过' },
  { key: 'auto_defect_total', label: '自动缺陷' },
  { key: 'manual_defect_total', label: '人工缺陷' },
  { key: 'veto_defect_total', label: '单否缺陷' },
  { key: 'records_with_defect', label: '有缺陷病历' },
]
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const scene = computed<ReportScene>(() => (route.query.scene === 'final' ? 'final' : 'running'))
const draft = ref({
  department: '',
  doctor: '',
  completed_from: '',
  completed_to: '',
  defect_source: 'all' as DefectSource,
})
const filters = ref<RecordQualityFilters>({ scene: scene.value, defect_source: 'all' })
const report = ref<RecordQualityReport | null>(null)
const loading = ref(false)
const loadError = ref('')
const exporting = ref<ReportSheet | null>(null)
const activeTop = ref<'rules' | 'departments' | 'doctors' | 'documents'>('rules')
const topTabs = [
  { key: 'rules', label: '规则' },
  { key: 'departments', label: '科室' },
  { key: 'doctors', label: '医生' },
  { key: 'documents', label: '文书' },
] as const
const columnPreset = ref('all')
const storageKey = computed(
  () => `medqc:record-quality-columns:${authStore.user?.id || 'anonymous'}`,
)
const visibleColumns = ref<ColumnKey[]>(optionalColumns.map((column) => column.key))
const shownColumns = computed(() =>
  optionalColumns.filter((column) => visibleColumns.value.includes(column.key)),
)
const drawerOpen = ref(false)
const drilldownTitle = ref('病例明细')
const drilldown = ref<Partial<RecordDrilldownFilters>>({})
const recordsPage = ref<RecordQualityRecordsPage | null>(null)
const recordsLoading = ref(false)
const recordsError = ref('')
let reportRequest = 0
let recordsRequest = 0

const topLists = computed(() => ({
  rules: report.value?.top_rules,
  departments: report.value?.top_departments,
  doctors: report.value?.top_doctors,
  documents: report.value?.top_documents,
}))
const activeTopRows = computed(() => topLists.value[activeTop.value] ?? null)
const scoreAvailability = computed(() =>
  report.value?.score_standard.status === 'no_standard' ? '未配置评分标准' : '不可用',
)
const kpiCards = computed(() => {
  const k = report.value?.kpis
  if (!k) return []
  return [
    { label: '病历总数', value: numberText(k.record_total), note: '当前筛选范围' },
    { label: '已完成质控', value: numberText(k.qc_ready_total), note: '每份病历最新已完成结果' },
    {
      label: '平均分',
      value: k.average_score == null ? scoreAvailability.value : k.average_score.toFixed(2),
      note: `已计分 ${numberText(k.scored_total)} 份`,
    },
    {
      label: '首档率',
      value: rateText(k.top_grade_rate, scoreAvailability.value),
      note: k.top_grade_name || '最高等级',
    },
    { label: '审核通过', value: numberText(k.review_approved_total), note: '病历级审核' },
    { label: '自动缺陷', value: numberText(k.auto_defect_total), note: '确认缺陷' },
    {
      label: '人工缺陷',
      value: numberText(k.manual_defect_total),
      note: `驳回 ${numberText(k.manual_defect_rejected_total)} 条`,
    },
    {
      label: '单否缺陷',
      value: numberText(k.veto_defect_total),
      note: `涉及 ${numberText(k.veto_record_total)} 份病历`,
    },
  ]
})

function numberText(value: number | null | undefined): string {
  return value == null ? '不可用' : String(value)
}
function scoreText(value: number | null | undefined): string {
  return value == null ? scoreAvailability.value : value.toFixed(2)
}
function rateText(value: number | null | undefined, fallback = '不可用'): string {
  return value == null ? fallback : `${(value * 100).toFixed(1)}%`
}
function cellValue(row: ReportGroupRow, key: ColumnKey): string {
  const value = row[key]
  if (key === 'average_score') return value == null ? scoreAvailability.value : value.toFixed(2)
  if (key === 'top_grade_rate') return rateText(value, scoreAvailability.value)
  return numberText(value)
}
function reviewText(value: string | null): string {
  return (
    (
      {
        approved: '已通过',
        pending_review: '待初审',
        pending_recheck: '待复审',
        doubtful: '存疑',
      } as Record<string, string>
    )[value || ''] || '未知'
  )
}
function formatTime(value: string): string {
  if (!value) return '未知'
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime())
    ? '未知'
    : new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(parsed)
}
function unavailableReason(code: string): string {
  return (
    (
      {
        remediation_owner_undefined: '未接入（整改状态归属尚未定义）',
        core_system_classification_missing: '未接入（缺核心制度归类）',
      } as Record<string, string>
    )[code] || '未接入'
  )
}

async function loadReport(): Promise<void> {
  const request = ++reportRequest
  ++recordsRequest
  drawerOpen.value = false
  drilldown.value = {}
  recordsPage.value = null
  recordsError.value = ''
  loading.value = true
  loadError.value = ''
  report.value = null
  const result = await getRecordQualityReport(filters.value)
  if (request !== reportRequest) return
  loading.value = false
  if (result.success && result.data) report.value = result.data
  else
    loadError.value =
      result.code === 'archive_scope_unverified'
        ? '终末归档范围尚未核实，暂不能生成终末质量报表。'
        : result.message || '病历质量报表暂不可用'
}
function applyFilters(): void {
  if (
    draft.value.completed_from &&
    draft.value.completed_to &&
    draft.value.completed_from > draft.value.completed_to
  ) {
    message.error('完成时间起不能晚于完成时间止')
    return
  }
  filters.value = { scene: scene.value, ...draft.value }
  void loadReport()
}
function resetFilters(): void {
  draft.value = {
    department: '',
    doctor: '',
    completed_from: '',
    completed_to: '',
    defect_source: 'all',
  }
  applyFilters()
}
function setScene(next: ReportScene): void {
  if (scene.value !== next) void router.push({ query: { ...route.query, scene: next } })
}
watch(scene, (next) => {
  filters.value = { ...filters.value, scene: next }
  drawerOpen.value = false
  void loadReport()
})
watch(storageKey, restoreColumns)
function restoreColumns(): void {
  visibleColumns.value = optionalColumns.map((column) => column.key)
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey.value) || 'null') as unknown
    if (Array.isArray(saved)) {
      const valid = saved.filter(
        (key): key is ColumnKey =>
          typeof key === 'string' && optionalColumns.some((column) => column.key === key),
      )
      if (valid.length) visibleColumns.value = valid
    }
  } catch {
    visibleColumns.value = optionalColumns.map((column) => column.key)
  }
}
function saveColumns(): void {
  if (!visibleColumns.value.length) visibleColumns.value = ['record_total']
  try {
    localStorage.setItem(storageKey.value, JSON.stringify(visibleColumns.value))
  } catch {
    /* 私密模式仍可在本次会话使用列选择 */
  }
}
function applyColumnPreset(): void {
  visibleColumns.value =
    columnPreset.value === 'quality'
      ? [
          'record_total',
          'qc_ready_total',
          'average_score',
          'top_grade_rate',
          'review_approved_total',
        ]
      : columnPreset.value === 'defects'
        ? [
            'record_total',
            'auto_defect_total',
            'manual_defect_total',
            'veto_defect_total',
            'records_with_defect',
          ]
        : optionalColumns.map((column) => column.key)
  saveColumns()
}
async function loadRecords(page = 1): Promise<void> {
  const request = ++recordsRequest
  recordsLoading.value = true
  recordsError.value = ''
  recordsPage.value = null
  const result = await getRecordQualityRecords({
    ...filters.value,
    ...drilldown.value,
    page,
    page_size: 20,
  })
  if (request !== recordsRequest) return
  recordsLoading.value = false
  if (result.success && result.data) recordsPage.value = result.data
  else recordsError.value = result.message || '病例明细暂不可用'
}
function openDrilldown(dimensions: Partial<RecordDrilldownFilters>, title: string): void {
  drilldown.value = dimensions
  drilldownTitle.value = title
  drawerOpen.value = true
  void loadRecords()
}
function openTop(item: ReportDistributionItem): void {
  if (activeTop.value === 'rules')
    openDrilldown({ rule_id: item.rule_id || item.name }, `规则：${item.rule_name || item.name}`)
  else if (activeTop.value === 'departments')
    openDrilldown({ department: item.name }, `科室：${item.name}`)
  else if (activeTop.value === 'doctors') openDrilldown({ doctor: item.name }, `医生：${item.name}`)
  else openDrilldown({ document: item.name }, `文书：${item.name}`)
}
function changePage(page: number): void {
  void loadRecords(page)
}
async function download(sheet: ReportSheet): Promise<void> {
  exporting.value = sheet
  const result = await exportRecordQualityReport(
    { ...filters.value, ...(sheet === 'records' ? drilldown.value : {}) },
    sheet,
  )
  exporting.value = null
  if (!result.success || !result.data) {
    message.error(result.message || '导出失败')
    return
  }
  const url = URL.createObjectURL(result.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `病历质量分析-${scene.value}-${sheet}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
onMounted(() => {
  restoreColumns()
  void loadReport()
})
</script>

<style scoped>
.report-page {
  min-height: 100%;
  padding: 24px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
  font-size: 14px;
  line-height: 22px;
}
.page-head,
.section-head,
.table-head,
.top-head,
.drawer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-head {
  margin-bottom: 18px;
}
.page-head h1 {
  font-size: 24px;
  line-height: 31px;
  font-weight: 600;
  margin: 0;
}
.page-head p {
  margin: 4px 0 0;
  color: #62666d;
}
.head-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.primary,
.secondary {
  height: 36px;
  border-radius: 8px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
  cursor: pointer;
}
.primary {
  background: #007aff;
  color: white;
  border: 1px solid #007aff;
}
.secondary {
  background: white;
  color: #30343b;
  border: 1px solid #d9dee5;
}
.primary:disabled,
.secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
  padding: 16px 18px;
  margin-bottom: 20px;
  background: white;
  border: 1px solid #e4e7eb;
  border-radius: 8px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 128px;
}
.field label {
  color: #5e6670;
}
.field input,
.field select,
.column-picker select {
  height: 36px;
  border: 1px solid #d9dee5;
  border-radius: 8px;
  background: white;
  padding: 0 10px;
  color: #1d1d1f;
  min-width: 0;
}
.field input[type='datetime-local'] {
  min-width: 180px;
}
.segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 8px;
  background: #eceef1;
  gap: 2px;
}
.segmented button {
  height: 30px;
  border: 0;
  background: transparent;
  border-radius: 6px;
  padding: 0 10px;
  cursor: pointer;
  white-space: nowrap;
  color: #535b66;
}
.segmented button.active {
  background: white;
  color: #007aff;
  box-shadow: 0 1px 3px #00000015;
}
.status {
  padding: 22px;
  background: white;
  border: 1px solid #e5e8ed;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #62666d;
}
.status.error {
  color: #b42318;
  background: #fff9f8;
  border-color: #ffd8d2;
}
section {
  margin-bottom: 22px;
}
h2 {
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
  margin: 0 0 12px;
}
h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.metric {
  background: white;
  border: 1px solid #e5e8ed;
  border-radius: 8px;
  padding: 14px;
  min-height: 100px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.metric span {
  color: #62666d;
}
.metric strong {
  font-size: 22px;
  line-height: 28px;
  font-weight: 600;
  color: #1d1d1f;
  overflow-wrap: anywhere;
}
.metric small {
  color: #7e858d;
  font-size: 12px;
}
.notice {
  margin-top: 10px;
  color: #8b5a14;
  background: #fff9ec;
  padding: 9px 12px;
  border-radius: 6px;
}
.distribution-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.data-panel,
.top-panel,
.table-panel,
.unavailable {
  background: white;
  border: 1px solid #e5e8ed;
  border-radius: 8px;
}
.data-panel {
  padding: 14px;
  min-height: 180px;
}
.data-panel h3 {
  margin-bottom: 10px;
}
.data-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 0;
  border-top: 1px solid #f0f1f3;
  width: 100%;
}
.data-row strong,
.top-row strong {
  font-weight: 600;
}
.row-button {
  border-left: 0;
  border-right: 0;
  border-bottom: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.row-button:hover,
.top-row:hover {
  color: #007aff;
}
.empty {
  padding: 22px;
  text-align: center;
  color: #8b919a;
}
.top-panel {
  margin-top: 10px;
  padding: 14px;
}
.top-head {
  margin-bottom: 12px;
}
.top-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 24px;
}
.top-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 36px;
  padding: 6px 0;
  border: 0;
  border-bottom: 1px solid #f0f1f3;
  background: white;
  text-align: left;
  cursor: pointer;
}
.rank {
  width: 24px;
  color: #8b919a;
}
.top-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.details .section-head h2 {
  margin: 0;
}
.column-picker {
  display: flex;
  align-items: center;
  gap: 6px;
}
.column-options {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 12px 0;
}
.column-options label {
  white-space: nowrap;
  color: #535b66;
}
.column-options input {
  margin-right: 5px;
}
.table-panel {
  margin-top: 10px;
  overflow: hidden;
}
.table-head {
  padding: 12px 14px;
  border-bottom: 1px solid #e5e8ed;
}
.table-head span {
  color: #7e858d;
}
.table-scroll {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  white-space: nowrap;
}
th,
td {
  text-align: left;
  padding: 11px 14px;
  border-bottom: 1px solid #edf0f2;
}
th {
  background: #f8f9fb;
  color: #62666d;
  font-weight: 400;
}
td strong,
td small {
  display: block;
}
td small {
  font-size: 12px;
  color: #7e858d;
}
.link {
  background: none;
  border: 0;
  color: #007aff;
  padding: 0;
  cursor: pointer;
}
.unavailable {
  padding: 14px;
}
.unavailable p {
  margin: 5px 0;
  color: #62666d;
}
.drawer-actions {
  margin-bottom: 12px;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 16px;
}
.pager .secondary {
  height: 32px;
}
@media (max-width: 1100px) {
  .metrics,
  .distribution-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .report-page {
    padding: 14px;
  }
  .page-head,
  .top-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .metrics,
  .distribution-grid,
  .top-grid {
    grid-template-columns: 1fr;
  }
  .field {
    flex: 1 1 150px;
  }
  .field input[type='datetime-local'] {
    min-width: 0;
  }
}
</style>
