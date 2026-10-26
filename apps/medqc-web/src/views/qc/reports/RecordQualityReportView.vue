<template>
  <main class="mq-page report-page">
    <header class="page-head mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">统计分析 · 质量报表</span>
        <h1 class="mq-page-title">病历质量分析</h1>
        <p>
          {{
            scene === 'running'
              ? '当前在院病历的已完成质控结果'
              : '已出院且有已完成质控结果的病历（未核验归档）'
          }}
        </p>
      </div>
      <div class="head-actions mq-page-head__actions">
        <div class="mq-segmented" role="tablist" aria-label="报表专题">
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': reportTab === 'quality' }"
            role="tab"
            :aria-selected="reportTab === 'quality'"
            @click="reportTab = 'quality'"
          >
            病历质量分析
          </button>
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': reportTab === 'core' }"
            role="tab"
            :aria-selected="reportTab === 'core'"
            data-testid="core-tab"
            @click="reportTab = 'core'"
          >
            18项核心制度
          </button>
        </div>
        <button
          v-if="reportTab === 'quality'"
          class="secondary mq-btn"
          type="button"
          :disabled="loading"
          @click="loadReport"
        >
          <MqIcon name="sync" :size="16" />刷新
        </button>
        <button
          v-if="reportTab === 'quality'"
          class="secondary mq-btn"
          type="button"
          :disabled="!report || exporting !== null"
          @click="download('departments')"
        >
          <MqIcon name="download" :size="16" />科室 CSV
        </button>
        <button
          v-if="reportTab === 'quality'"
          class="secondary mq-btn"
          type="button"
          :disabled="!report || exporting !== null"
          @click="download('doctors')"
        >
          <MqIcon name="download" :size="16" />医生 CSV
        </button>
      </div>
    </header>
    <CoreSystemReportPanel v-if="reportTab === 'core'" :initial-filters="filters" />
    <div v-show="reportTab === 'quality'">
      <section class="filters mq-card mq-card--padded" aria-label="报表筛选">
        <div class="field mq-field scene-field">
          <label>场景</label>
          <div class="segmented mq-segmented" role="group" aria-label="质控场景">
            <button
              type="button"
              class="mq-segmented__item"
              :class="{ active: scene === 'running', 'is-active': scene === 'running' }"
              :aria-pressed="scene === 'running'"
              @click="setScene('running')"
            >
              运行病历</button
            ><button
              type="button"
              class="mq-segmented__item"
              :class="{ active: scene === 'final', 'is-active': scene === 'final' }"
              :aria-pressed="scene === 'final'"
              @click="setScene('final')"
            >
              终末病历
            </button>
          </div>
        </div>
        <div class="field mq-field">
          <label for="report-department">科室</label
          ><input
            id="report-department"
            v-model.trim="draft.department"
            class="mq-input"
            placeholder="全部科室"
          />
        </div>
        <div class="field mq-field">
          <label for="report-doctor">主治医师</label
          ><input
            id="report-doctor"
            v-model.trim="draft.doctor"
            class="mq-input"
            placeholder="全部医生"
          />
        </div>
        <div class="field mq-field">
          <label for="report-from">完成时间起</label
          ><input
            id="report-from"
            v-model="draft.completed_from"
            class="mq-input"
            type="datetime-local"
          />
        </div>
        <div class="field mq-field">
          <label for="report-to">完成时间止</label
          ><input
            id="report-to"
            v-model="draft.completed_to"
            class="mq-input"
            type="datetime-local"
          />
        </div>
        <div class="field mq-field">
          <label for="report-source">质控类型</label
          ><select id="report-source" v-model="draft.defect_source" class="mq-input">
            <option value="all">全部</option>
            <option value="auto">自动缺陷</option>
            <option value="manual">人工缺陷</option>
          </select>
        </div>
        <button class="primary mq-btn mq-btn--primary" type="button" @click="applyFilters">
          <MqIcon name="search" :size="16" />查询
        </button>
        <button class="secondary mq-btn" type="button" @click="resetFilters">重置</button>
      </section>

      <div v-if="loading" class="status" role="status">正在读取病历质量报表…</div>
      <div v-else-if="loadError" class="status error" role="alert" data-testid="report-error">
        <MqIcon name="issue" :size="18" />{{ loadError }}
      </div>
      <template v-else-if="report">
        <div
          v-if="report.scope.archive_status === 'unverified'"
          class="notice archive-notice"
          role="note"
          data-testid="archive-unverified"
        >
          <MqIcon
            name="issue"
            :size="16"
          />终末口径：已出院且有已完成质控结果的病历。医院归档标记尚未接入，
          统计范围未按“已归档”核验，可能包含尚未归档的病历。
        </div>
        <section class="overview" aria-label="总览">
          <h2>总览</h2>
          <div class="metrics">
            <div
              v-for="item in kpiCards"
              :key="item.label"
              class="metric mq-card"
              :class="{ 'metric--text': /[\u4e00-\u9fff]/.test(item.value) }"
            >
              <span class="metric-label"><MqIcon name="stats" :size="20" />{{ item.label }}</span
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
            <div v-if="report.score_standard.status === 'configured'" class="data-panel mq-card">
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
            <div v-if="report.score_standard.status === 'configured'" class="data-panel mq-card">
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
            <div class="data-panel mq-card">
              <h3>缺陷等级</h3>
              <template v-if="report.defect_level_distribution">
                <div
                  v-for="item in report.defect_level_distribution"
                  :key="item.name"
                  class="data-row"
                >
                  <span>{{ item.name }}</span
                  ><strong>{{ item.defect_total }}</strong>
                </div>
                <p v-if="!report.defect_level_distribution.length" class="empty">暂无数据</p>
              </template>
              <p v-else class="empty">不可用</p>
            </div>
            <div class="data-panel mq-card">
              <h3>缺陷类型分布</h3>
              <template v-if="report.defect_type_distribution">
                <button
                  v-for="item in report.defect_type_distribution"
                  :key="item.name"
                  class="data-row row-button"
                  type="button"
                  @click="openDrilldown({ defect_type: item.name }, `缺陷类型：${item.name}`)"
                >
                  <span>{{ item.name }}</span
                  ><strong>{{ item.defect_total }}</strong>
                </button>
                <p v-if="!report.defect_type_distribution.length" class="empty">暂无已分类缺陷</p>
              </template>
              <p v-else class="empty">不可用</p>
            </div>
            <div class="data-panel mq-card">
              <h3>文书分布</h3>
              <template v-if="report.document_distribution">
                <button
                  v-for="item in report.document_distribution"
                  :key="item.name"
                  class="data-row row-button"
                  type="button"
                  @click="openDrilldown({ document: item.name }, `文书：${item.name}`)"
                >
                  <span>{{ item.name }}</span
                  ><strong>{{ item.defect_total }}</strong>
                </button>
                <p v-if="!report.document_distribution.length" class="empty">暂无数据</p>
              </template>
              <p v-else class="empty">不可用</p>
            </div>
          </div>
          <div class="top-panel mq-card">
            <div class="top-head">
              <h3>缺陷 Top 20</h3>
              <div class="segmented mq-segmented">
                <button
                  v-for="tab in topTabs"
                  :key="tab.key"
                  type="button"
                  class="mq-segmented__item"
                  :class="{ active: activeTop === tab.key, 'is-active': activeTop === tab.key }"
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
            <p v-if="activeTop === 'veto'" class="notice">
              单否按评分标准的自动缺陷计分结果统计；人工缺陷单否归属未知。
            </p>
            <div v-if="report.classification_unknown" class="notice">
              <button
                v-for="dimension in classificationDimensions"
                :key="dimension.key"
                type="button"
                class="link"
                :disabled="report.classification_unknown[dimension.key] == null"
                @click="
                  openDrilldown(
                    { unknown_classification: dimension.key },
                    `${dimension.label}未知的病例`,
                  )
                "
              >
                {{ dimension.label }}未知：{{
                  numberText(report.classification_unknown[dimension.key])
                }}
              </button>
            </div>
          </div>
        </section>

        <section class="details" aria-label="明细">
          <div class="section-head">
            <h2>明细</h2>
            <div class="head-actions mq-page-head__actions">
              <label class="column-picker"
                ><MqIcon name="settings" :size="16" />显示列<select
                  v-model="columnPreset"
                  class="mq-input"
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
                class="mq-input"
                type="checkbox"
                :value="column.key"
                @change="saveColumns"
              />{{ column.label }}</label
            >
          </div>
          <div class="table-panel mq-card">
            <div class="table-head">
              <h3>科室明细</h3>
              <span>{{ report.department_rows.length }} 个科室</span>
            </div>
            <div class="table-scroll">
              <table class="mq-table">
                <thead>
                  <tr>
                    <th>科室</th>
                    <th v-for="column in shownColumns" :key="column.key">
                      {{ column.label }}
                    </th>
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
          <div class="table-panel mq-card">
            <div class="table-head">
              <h3>医生明细</h3>
              <span>{{ report.doctor_rows.length }} 位医生</span>
            </div>
            <div class="table-scroll">
              <table class="mq-table">
                <thead>
                  <tr>
                    <th>主治医师</th>
                    <th v-for="column in shownColumns" :key="column.key">
                      {{ column.label }}
                    </th>
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
        <RecordRemediationAnalysisPanel :filters="filters" />
        <section class="unavailable mq-card">
          <h2>暂未接入的维度</h2>
          <p v-for="item in report.unavailable_dimensions" :key="item.key">
            {{ item.label }}：{{ unavailableReason(item.reason_code) }}
          </p>
          <button class="link" type="button" @click="reportTab = 'core'">
            核心制度自动缺陷分析
          </button>
        </section>
      </template>

      <a-drawer
        v-model:open="drawerOpen"
        :title="drilldownTitle"
        width="min(900px, 100vw)"
        :root-style="{ zIndex: 1100 }"
        destroy-on-close
      >
        <div class="drawer-actions">
          <span>{{ recordsPage ? `共 ${recordsPage.total} 份病历` : '病例明细' }}</span
          ><button
            class="secondary mq-btn"
            type="button"
            :disabled="!recordsPage || exporting !== null"
            @click="download('records')"
          >
            <MqIcon name="download" :size="16" />导出病例 CSV
          </button>
        </div>
        <p v-if="recordsError" class="status error" role="alert">
          <MqIcon name="issue" :size="18" />{{ recordsError }}
        </p>
        <p v-else-if="recordsLoading" class="status" role="status">正在读取病例…</p>
        <div v-else-if="recordsPage" class="table-scroll">
          <table class="mq-table">
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
                  {{ numberText(row.auto_defect_total) }} /
                  {{ numberText(row.manual_defect_total) }}
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
            class="secondary mq-btn"
            type="button"
            :disabled="recordsPage.page <= 1 || recordsLoading"
            @click="changePage(recordsPage.page - 1)"
          >
            上一页</button
          ><span
            >{{ recordsPage.page }} /
            {{ Math.ceil(recordsPage.total / recordsPage.page_size) }}</span
          ><button
            class="secondary mq-btn"
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
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
import CoreSystemReportPanel from './CoreSystemReportPanel.vue'
import RecordRemediationAnalysisPanel from './RecordRemediationAnalysisPanel.vue'
const reportTab = ref('quality')
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
  | 'veto_record_total'
  | 'records_with_defect'
  | 'reviewed_total'
  | 'top_grade_total'
  | 'defect_total'
  | 'average_defect_total'
  | `grade_rate:${string}`
const baseColumns: Array<{ key: ColumnKey; label: string }> = [
  { key: 'record_total', label: '病历数' },
  { key: 'qc_ready_total', label: '已质控' },
  { key: 'average_score', label: '平均分' },
  { key: 'top_grade_rate', label: '首档率' },
  { key: 'review_approved_total', label: '审核通过' },
  { key: 'reviewed_total', label: '已审核' },
  { key: 'top_grade_total', label: '首档病历数' },
  { key: 'defect_total', label: '缺陷总数' },
  { key: 'average_defect_total', label: '平均缺陷数（每份已质控病历）' },
  { key: 'auto_defect_total', label: '自动缺陷' },
  { key: 'manual_defect_total', label: '人工缺陷' },
  { key: 'veto_defect_total', label: '单否缺陷' },
  { key: 'veto_record_total', label: '单否病历数' },
  { key: 'records_with_defect', label: '有缺陷病历' },
]
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const authKey = computed(() =>
  JSON.stringify([
    authStore.user?.id,
    authStore.user?.institute_id,
    authStore.user?.department,
    authStore.user?.roles || authStore.user?.role,
  ]),
)
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
const optionalColumns = computed<Array<{ key: ColumnKey; label: string }>>(() => [
  ...baseColumns.map((column) => ({
    ...column,
    label:
      column.key === 'top_grade_total' && report.value?.kpis.top_grade_name
        ? `${report.value.kpis.top_grade_name}病历数`
        : column.label,
  })),
  ...(report.value?.grade_distribution || [])
    .filter((item) => item.grade !== null)
    .map((item) => ({
      key: `grade_rate:${item.grade}` as ColumnKey,
      label: `${item.grade}占比`,
    })),
])
const loading = ref(false)
const loadError = ref('')
const exporting = ref<ReportSheet | null>(null)
const activeTop = ref<'categories' | 'types' | 'documents' | 'veto' | 'rules'>('categories')
const topTabs = [
  { key: 'categories', label: '大类' },
  { key: 'types', label: '类型' },
  { key: 'documents', label: '文书' },
  { key: 'veto', label: '单否' },
  { key: 'rules', label: '规则' },
] as const
const classificationDimensions = [
  { key: 'defect_category', label: '大类' },
  { key: 'defect_type', label: '类型' },
] as const
const columnPreset = ref('all')
const storageKey = computed(
  () => `medqc:record-quality-columns:${authStore.user?.id || 'anonymous'}`,
)
const visibleColumns = ref<ColumnKey[]>(baseColumns.map((column) => column.key))
const shownColumns = computed(() =>
  optionalColumns.value.filter((column) => visibleColumns.value.includes(column.key)),
)
const drawerOpen = ref(false)
const drilldownTitle = ref('病例明细')
const drilldown = ref<Partial<RecordDrilldownFilters>>({})
const recordsPage = ref<RecordQualityRecordsPage | null>(null)
const recordsLoading = ref(false)
const recordsError = ref('')
let reportRequest = 0
let recordsRequest = 0
let exportRequest = 0
const exportScope = computed(() =>
  JSON.stringify([scene.value, filters.value, draft.value, drilldown.value, shownColumns.value]),
)
function invalidateExport(): void {
  ++exportRequest
  exporting.value = null
}
watch([authKey, exportScope], invalidateExport, { flush: 'sync' })
watch(authKey, () => {
  ++reportRequest
  ++recordsRequest
  report.value = null
  recordsPage.value = null
  drawerOpen.value = false
  loading.value = false
  recordsLoading.value = false
  if (authStore.user?.id) void loadReport()
})

const topLists = computed(() => ({
  rules: report.value?.top_rules,
  categories: report.value?.top_categories,
  types: report.value?.top_types,
  veto: report.value?.top_veto_rules,
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
  if (key.startsWith('grade_rate:'))
    return rateText(row.grade_rates?.[key.slice('grade_rate:'.length)], scoreAvailability.value)
  const value = row[key as Exclude<ColumnKey, `grade_rate:${string}`>]
  if (key === 'average_score' || key === 'average_defect_total')
    return value == null ? '不可用' : value.toFixed(2)
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
        core_system_classification_missing:
          '人工缺陷未接入冻结制度归类；自动缺陷可查看核心制度专题',
      } as Record<string, string>
    )[code] || '未接入'
  )
}

async function loadReport(): Promise<void> {
  invalidateExport()
  const request = ++reportRequest
  const identity = authKey.value
  ++recordsRequest
  drawerOpen.value = false
  drilldown.value = {}
  recordsPage.value = null
  recordsError.value = ''
  loading.value = true
  loadError.value = ''
  report.value = null
  const result = await getRecordQualityReport(filters.value)
  if (request !== reportRequest || identity !== authKey.value) return
  loading.value = false
  if (result.success && result.data) {
    report.value = result.data
    restoreColumns()
  } else loadError.value = result.message || '病历质量报表暂不可用'
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
  visibleColumns.value = optionalColumns.value.map((column) => column.key)
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey.value) || 'null') as unknown
    if (Array.isArray(saved)) {
      const valid = saved.filter(
        (key): key is ColumnKey =>
          typeof key === 'string' && optionalColumns.value.some((column) => column.key === key),
      )
      if (valid.length) visibleColumns.value = valid
    }
  } catch {
    visibleColumns.value = optionalColumns.value.map((column) => column.key)
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
        : optionalColumns.value.map((column) => column.key)
  saveColumns()
}
async function loadRecords(page = 1): Promise<void> {
  const request = ++recordsRequest
  const identity = authKey.value
  recordsLoading.value = true
  recordsError.value = ''
  recordsPage.value = null
  const result = await getRecordQualityRecords({
    ...filters.value,
    ...drilldown.value,
    page,
    page_size: 20,
  })
  if (request !== recordsRequest || identity !== authKey.value) return
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
  else if (activeTop.value === 'categories')
    openDrilldown({ defect_category: item.name }, `大类：${item.name}`)
  else if (activeTop.value === 'types')
    openDrilldown({ defect_type: item.name }, `类型：${item.name}`)
  else if (activeTop.value === 'veto')
    openDrilldown(
      { defect_source: 'auto', rule_id: item.rule_id || item.name, has_veto: true },
      `单否：${item.rule_name || item.name}`,
    )
  else openDrilldown({ document: item.name }, `文书：${item.name}`)
}
function changePage(page: number): void {
  void loadRecords(page)
}
async function download(sheet: ReportSheet): Promise<void> {
  if (!report.value || !authStore.user?.id) return
  const request = ++exportRequest
  const identity = authKey.value
  const scope = exportScope.value
  const query = { ...filters.value, ...(sheet === 'records' ? drilldown.value : {}) }
  const columns = sheet === 'records' ? undefined : shownColumns.value.map((column) => column.key)
  const filename = `病历质量分析-${query.scene}-${sheet}.csv`
  const current = () =>
    request === exportRequest && identity === authKey.value && scope === exportScope.value
  exporting.value = sheet
  try {
    const result = await exportRecordQualityReport(query, sheet, columns)
    if (!current()) return
    if (!result.success || !result.data) {
      message.error(result.message || '导出失败')
      return
    }
    const url = URL.createObjectURL(result.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch {
    if (current()) message.error('导出失败')
  } finally {
    if (request === exportRequest) exporting.value = null
  }
}
onBeforeUnmount(() => {
  ++reportRequest
  ++recordsRequest
  invalidateExport()
})
onMounted(() => {
  restoreColumns()
  void loadReport()
})
</script>

<style scoped src="./reportPage.css"></style>
