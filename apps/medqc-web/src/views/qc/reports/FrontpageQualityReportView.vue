<template>
  <main class="report-page">
    <header class="page-head">
      <div>
        <h1>病案首页统计分析</h1>
        <p>每份病案首页质控与编码质控的最新一次结果（已核验病例身份）</p>
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
      </div>
    </header>

    <section class="filters" aria-label="报表筛选">
      <div class="field">
        <label for="fp-department">科室</label
        ><input id="fp-department" v-model.trim="draft.department" placeholder="全部科室" />
      </div>
      <div class="field">
        <label for="fp-doctor">主治医师</label
        ><input id="fp-doctor" v-model.trim="draft.doctor" placeholder="全部医生" />
      </div>
      <div class="field">
        <label for="fp-from">质控时间起</label
        ><input id="fp-from" v-model="draft.analyzed_from" type="datetime-local" />
      </div>
      <div class="field">
        <label for="fp-to">质控时间止</label
        ><input id="fp-to" v-model="draft.analyzed_to" type="datetime-local" />
      </div>
      <button class="primary" type="button" @click="applyFilters"><Search :size="16" />查询</button>
      <button class="secondary" type="button" @click="resetFilters">重置</button>
    </section>

    <div v-if="loading" class="status" role="status">正在读取病案首页统计…</div>
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
      </section>

      <section class="distribution" aria-label="分布">
        <div class="section-head">
          <h2>缺陷分布</h2>
          <div class="segmented">
            <button
              v-for="source in report.sources"
              :key="source.source_key"
              type="button"
              :class="{ active: activeSource === source.source_key }"
              @click="activeSource = source.source_key"
            >
              {{ source.label }}
            </button>
          </div>
        </div>
        <template v-if="currentSource">
          <div class="distribution-grid">
            <div class="data-panel">
              <h3>严重度</h3>
              <div
                v-for="item in currentSource.severity_distribution"
                :key="item.severity"
                class="data-row"
              >
                <span>{{ severityText(item.severity) }}</span
                ><strong>{{ item.defect_total }}</strong>
              </div>
              <p v-if="!currentSource.severity_distribution.length" class="empty">暂无缺陷</p>
            </div>
            <div class="data-panel">
              <h3>缺陷分类</h3>
              <div
                v-for="item in currentSource.category_distribution"
                :key="item.category"
                class="data-row"
              >
                <span>{{ categoryText(item.category) }}</span
                ><strong>{{ item.defect_total }}</strong>
              </div>
              <p v-if="!currentSource.category_distribution.length" class="empty">暂无缺陷</p>
            </div>
          </div>
          <div class="top-panel">
            <div class="top-head">
              <h3>{{ currentSource.label }} 规则 Top 20</h3>
            </div>
            <p v-if="!currentSource.top_rules.length" class="empty">暂无缺陷</p>
            <div v-else class="top-grid">
              <button
                v-for="(item, index) in currentSource.top_rules"
                :key="item.rule_code"
                type="button"
                class="top-row"
                @click="openRule(item.rule_code, item.rule_name)"
              >
                <span class="rank">{{ index + 1 }}</span
                ><span class="top-name">{{ item.rule_code }} {{ item.rule_name }}</span
                ><strong>{{ item.defect_total }}</strong>
              </button>
            </div>
          </div>
        </template>
      </section>

      <section class="details" aria-label="科室明细">
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
                  <th>病案数</th>
                  <th>问题病案数</th>
                  <th>问题病案率</th>
                  <th>非编码缺陷</th>
                  <th>编码缺陷</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in report.department_rows" :key="row.department">
                  <td>
                    <button
                      class="link"
                      type="button"
                      @click="
                        openDrilldown({ department: row.department }, `科室：${row.department}`)
                      "
                    >
                      {{ row.department }}
                    </button>
                  </td>
                  <td>{{ row.case_total }}</td>
                  <td>
                    <button
                      class="link"
                      type="button"
                      @click="
                        openDrilldown(
                          { department: row.department, problem_only: true },
                          `科室问题病案：${row.department}`,
                        )
                      "
                    >
                      {{ row.problem_case_total }}
                    </button>
                  </td>
                  <td>{{ rateText(row.problem_rate) }}</td>
                  <td>{{ row.noncoding_defect_total }}</td>
                  <td>{{ row.coding_defect_total }}</td>
                </tr>
                <tr v-if="!report.department_rows.length">
                  <td colspan="6" class="empty">当前范围内没有首页或编码质控结果</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>

    <a-drawer v-model:open="drawerOpen" :title="drilldownTitle" :width="900" destroy-on-close>
      <div class="drawer-actions">
        <span>{{ recordsPage ? `共 ${recordsPage.total} 份病案` : '病案明细' }}</span
        ><button
          class="secondary"
          type="button"
          :disabled="!recordsPage || exporting !== null"
          @click="download('records')"
        >
          <Download :size="16" />导出病案 CSV
        </button>
      </div>
      <p v-if="recordsError" class="status error" role="alert">
        {{ recordsError }}
      </p>
      <p v-else-if="recordsLoading" class="status">正在读取病案…</p>
      <div v-else-if="recordsPage" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>患者 / 就诊号</th>
              <th>科室 / 医生</th>
              <th>首页质控</th>
              <th>编码质控</th>
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
              <td>
                {{ defectText(row.frontpage_defect_total)
                }}<small>{{ formatTime(row.frontpage_analysis_date) }}</small>
              </td>
              <td>
                {{ defectText(row.coding_defect_total)
                }}<small>{{ formatTime(row.coding_analysis_date) }}</small>
              </td>
            </tr>
            <tr v-if="!recordsPage.items.length">
              <td colspan="4" class="empty">暂无病案</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="recordsPage && recordsPage.total > recordsPage.page_size" class="pager">
        <button
          class="secondary"
          type="button"
          :disabled="recordsPage.page <= 1 || recordsLoading"
          @click="loadRecords(recordsPage.page - 1)"
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
          @click="loadRecords(recordsPage.page + 1)"
        >
          下一页
        </button>
      </div>
    </a-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { CircleAlert, Download, RefreshCw, Search } from 'lucide-vue-next'
import {
  exportFrontpageQualityReport,
  getFrontpageQualityRecords,
  getFrontpageQualityReport,
} from '@/api/frontpageQualityReport'
import type {
  FrontpageDrilldownFilters,
  FrontpageQualityFilters,
  FrontpageQualityReport,
  FrontpageRecordsPage,
  FrontpageSheet,
  FrontpageSourceKey,
} from '@/api/frontpageQualityReport'

const SOURCE_FILTER: Record<FrontpageSourceKey, 'frontpage' | 'coding'> = {
  frontpage_formal_qc: 'frontpage',
  coding_qc: 'coding',
}
const draft = ref({ department: '', doctor: '', analyzed_from: '', analyzed_to: '' })
const filters = ref<FrontpageQualityFilters>({})
const report = ref<FrontpageQualityReport | null>(null)
const loading = ref(false)
const loadError = ref('')
const exporting = ref<FrontpageSheet | null>(null)
const activeSource = ref<FrontpageSourceKey>('frontpage_formal_qc')
const drawerOpen = ref(false)
const drilldownTitle = ref('病案明细')
const drilldown = ref<Partial<FrontpageDrilldownFilters>>({})
const recordsPage = ref<FrontpageRecordsPage | null>(null)
const recordsLoading = ref(false)
const recordsError = ref('')
let reportRequest = 0
let recordsRequest = 0

const currentSource = computed(
  () => report.value?.sources.find((item) => item.source_key === activeSource.value) ?? null,
)
const kpiCards = computed(() => {
  const k = report.value?.kpis
  if (!k) return []
  return [
    { label: '病案数', value: String(k.case_total), note: '有首页或编码质控结果' },
    {
      label: '问题病案数',
      value: String(k.problem_case_total),
      note: `问题病案率 ${rateText(k.problem_rate)}`,
    },
    {
      label: '非编码缺陷',
      value: String(k.noncoding_defect_total),
      note: `首页质控 ${k.frontpage_case_total} 份，问题 ${k.noncoding_problem_case_total} 份`,
    },
    {
      label: '编码缺陷',
      value: String(k.coding_defect_total),
      note: `编码质控 ${k.coding_case_total} 份，问题 ${k.coding_problem_case_total} 份`,
    },
  ]
})

function rateText(value: number | null | undefined): string {
  return value == null ? '无病案' : `${(value * 100).toFixed(1)}%`
}
function defectText(value: number | null): string {
  return value == null ? '未质控' : `${value} 条缺陷`
}
function severityText(value: string): string {
  return (
    ({ critical: '严重', error: '错误', warning: '警告', info: '提示' } as Record<string, string>)[
      value
    ] || value
  )
}
function categoryText(value: string): string {
  return (
    (
      {
        required: '必填',
        format: '格式',
        logic: '值域/逻辑',
        consistency: '一致性',
        existence: '存在性',
        bidding: '招标场景',
        semantic: '语义',
      } as Record<string, string>
    )[value] || value
  )
}
function formatTime(value: string | null): string {
  if (!value) return '无结果'
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
        hour12: false,
      }).format(parsed)
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
  const result = await getFrontpageQualityReport(filters.value)
  if (request !== reportRequest) return
  loading.value = false
  if (result.success && result.data) report.value = result.data
  else
    loadError.value =
      result.code === 'schema_unavailable'
        ? '首页质控数据源未部署：业务库尚未执行现代身份迁移，暂不能统计。'
        : result.message || '病案首页统计暂不可用'
}
function applyFilters(): void {
  if (
    draft.value.analyzed_from &&
    draft.value.analyzed_to &&
    draft.value.analyzed_from > draft.value.analyzed_to
  ) {
    message.error('质控时间起不能晚于质控时间止')
    return
  }
  filters.value = { ...draft.value }
  void loadReport()
}
function resetFilters(): void {
  draft.value = { department: '', doctor: '', analyzed_from: '', analyzed_to: '' }
  applyFilters()
}
async function loadRecords(page = 1): Promise<void> {
  const request = ++recordsRequest
  recordsLoading.value = true
  recordsError.value = ''
  recordsPage.value = null
  const result = await getFrontpageQualityRecords({
    ...filters.value,
    ...drilldown.value,
    page,
    page_size: 20,
  })
  if (request !== recordsRequest) return
  recordsLoading.value = false
  if (result.success && result.data) recordsPage.value = result.data
  else recordsError.value = result.message || '病案明细暂不可用'
}
function openDrilldown(dimensions: Partial<FrontpageDrilldownFilters>, title: string): void {
  drilldown.value = dimensions
  drilldownTitle.value = title
  drawerOpen.value = true
  void loadRecords()
}
function openRule(ruleCode: string, ruleName: string): void {
  openDrilldown(
    { source: SOURCE_FILTER[activeSource.value], rule_code: ruleCode },
    `规则：${ruleCode} ${ruleName}`,
  )
}
async function download(sheet: FrontpageSheet): Promise<void> {
  exporting.value = sheet
  const result = await exportFrontpageQualityReport(
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
  anchor.download = `病案首页统计-${sheet}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
onMounted(() => {
  void loadReport()
})
</script>

<style scoped src="./reportPage.css"></style>
