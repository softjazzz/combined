<template>
  <main class="mq-page report-page special-report">
    <header class="page-head mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">统计分析 · 质量报表</span>
        <h1 class="mq-page-title">特殊病历报表</h1>
        <p>按出院日期统计八类特殊病历的来源、专用评分与确认缺陷</p>
      </div>
      <div class="head-actions mq-page-head__actions">
        <button class="mq-btn" type="button" :disabled="loading" title="刷新报表" @click="load">
          <MqIcon name="sync" :size="16" />刷新
        </button>
        <button
          class="mq-btn"
          type="button"
          :disabled="!report || loading || exporting"
          @click="download()"
        >
          <MqIcon name="download" :size="16" />下载报表
        </button>
        <button
          class="mq-btn"
          type="button"
          :disabled="!report || loading || exporting"
          @click="download('defects')"
        >
          <MqIcon name="download" :size="16" />下载缺陷明细
        </button>
        <button
          v-if="canConfigure"
          class="mq-btn"
          type="button"
          :disabled="!draft.institute_id"
          @click="configOpen = true"
        >
          <MqIcon name="settings" :size="16" />机构代码配置
        </button>
      </div>
    </header>
    <form class="filters mq-card mq-card--padded" aria-label="报表筛选" @submit.prevent="apply">
      <div class="field mq-field">
        <label for="sr-type">特殊类型</label
        ><a-select
          id="sr-type"
          v-model:value="draft.record_type"
          :options="typeOptions"
          class="type-select"
        />
      </div>
      <div class="field mq-field">
        <label for="sr-state">来源状态</label
        ><a-select
          id="sr-state"
          v-model:value="draft.record_type_state"
          :options="[
            { value: 'positive', label: '已知命中' },
            { value: 'unknown', label: '未知来源' },
            { value: 'negative', label: '明确非该类型' },
          ]"
          class="type-select"
        />
      </div>
      <div class="field mq-field">
        <label for="sr-institute">机构</label
        ><input
          id="sr-institute"
          v-model="draft.institute_id"
          class="mq-input"
          placeholder="授权范围内机构"
        />
      </div>
      <div class="field mq-field">
        <label for="sr-department">科室</label
        ><input
          id="sr-department"
          v-model="draft.department"
          class="mq-input"
          placeholder="全部科室"
        />
      </div>
      <div class="field mq-field">
        <label for="sr-from">出院日期起（上海）</label
        ><input
          id="sr-from"
          v-model="draft.discharged_from"
          class="mq-input"
          type="date"
          required
        />
      </div>
      <div class="field mq-field">
        <label for="sr-to">出院日期止（上海）</label
        ><input id="sr-to" v-model="draft.discharged_to" class="mq-input" type="date" required />
      </div>
      <div class="filter-actions">
        <button class="mq-btn mq-btn--primary" type="submit">
          <MqIcon name="search" :size="16" />查询
        </button>
        <button class="mq-btn" type="button" @click="reset">重置</button>
      </div>
    </form>
    <p v-if="filterError" role="alert" class="status error">
      <MqIcon name="issue" :size="18" />{{ filterError }}
    </p>
    <div v-if="loading" role="status" class="status">正在读取特殊病历报表…</div>
    <div v-else-if="error" role="alert" class="status error">
      <MqIcon name="issue" :size="18" />{{ error }}
    </div>
    <template v-else-if="report">
      <p class="notice archive-notice">
        <MqIcon name="issue" :size="16" />八类可重叠；缺失来源单列未知。已出院病例未核验归档。
      </p>
      <section class="metrics" aria-label="病例概览">
        <div class="metric mq-card">
          <span class="metric-label"><MqIcon name="pool" :size="20" />范围病例</span
          ><strong>{{ report.summary.cohort_total }}</strong>
        </div>
        <div class="metric mq-card">
          <span class="metric-label"><MqIcon name="doc" :size="20" />选中类型病例</span
          ><strong>{{ report.summary.record_total }}</strong>
        </div>
        <div class="metric mq-card">
          <span class="metric-label"><MqIcon name="issue" :size="20" />范围内结果不可用</span
          ><strong>{{ report.summary.unavailable_result_total }}</strong>
        </div>
        <div class="metric metric--text mq-card">
          <span class="metric-label"><MqIcon name="rules" :size="20" />专用评分标准</span
          ><strong class="standard-name">{{ standardName }}</strong
          ><small
            >{{ report.score_standard.standard_id || '未知' }} / 版本
            {{ report.score_standard.standard_version_seq ?? '未知' }}</small
          >
        </div>
      </section>
      <section class="mq-card mq-card--padded" aria-label="八类来源边界">
        <div class="mq-card__head">
          <div>
            <h2 class="mq-card__title">类型来源</h2>
            <p class="mq-card__desc">点击类型查看已知命中，点击“未知”查看来源缺失病例</p>
          </div>
        </div>
        <div class="type-summary">
          <div
            v-for="item in report.types"
            :key="item.key"
            class="type-item mq-inset"
            :class="{ 'is-active': applied.record_type === item.key }"
          >
            <button
              type="button"
              class="type-main"
              :aria-pressed="
                applied.record_type === item.key && applied.record_type_state === 'positive'
              "
              @click="selectType(item.key)"
            >
              <span class="type-label">{{ item.label }}</span
              ><strong class="type-count">{{ item.count ?? '未知' }}</strong>
            </button>
            <small
              >已知命中 {{ item.known_positive_total }} ·
              <button
                type="button"
                class="link type-unknown"
                :aria-pressed="
                  applied.record_type === item.key && applied.record_type_state === 'unknown'
                "
                @click="selectType(item.key, 'unknown')"
              >
                未知 {{ item.unknown_total }}
              </button></small
            >
          </div>
        </div>
      </section>
      <section class="mq-card mq-card--padded" aria-label="专题分析">
        <div class="mq-card__head section-head">
          <div>
            <h2 class="mq-card__title">{{ activeTypeLabel }}分析</h2>
            <p class="mq-card__desc">
              等级比例分母：已计分 {{ report.summary.graded_total }} 例；未计分
              {{ report.summary.ungraded_total }}
              例。缺陷占比分母为已确认自动缺陷，人工缺陷未纳入；已知结果
              {{ report.summary.known_result_total }} 例，结果不可用
              {{ report.summary.selected_unavailable_result_total }} 例。
            </p>
          </div>
          <div class="mq-segmented" role="group" aria-label="分析视图">
            <button
              v-for="option in modeOptions"
              :key="option.value"
              type="button"
              class="mq-segmented__item"
              :class="{ 'is-active': mode === option.value }"
              :aria-pressed="mode === option.value"
              @click="mode = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
        <SpecialReportCharts
          v-if="mode === 'charts'"
          :departments="report.top_departments || []"
          :grades="report.grade_distribution || []"
          :defects="report.top_defects || []"
        />
        <div v-if="mode === 'charts'" class="analysis-grid">
          <section class="data-panel mq-inset">
            <h3>科室数量 Top5</h3>
            <p v-if="report.top_departments === null" class="empty">数量来源未知</p>
            <p v-else-if="!report.top_departments.length" class="empty">无已知命中病例</p>
            <button
              v-for="item in report.top_departments || []"
              :key="item.name"
              type="button"
              class="data-row row-button"
              @click="drill({ department: item.name })"
            >
              <span>{{ item.name || '未知科室' }}</span
              ><strong>{{ item.count }}</strong>
            </button>
          </section>
          <section class="data-panel mq-inset">
            <h3>专用评分等级比例</h3>
            <p v-if="report.grade_distribution === null" class="empty">等级未知或无可评分病例</p>
            <button
              v-for="item in report.grade_distribution || []"
              :key="item.grade"
              type="button"
              class="data-row row-button"
              @click="drill({ grade: item.grade })"
            >
              <span>{{ item.grade }}</span
              ><strong>{{ item.count }} · {{ (item.ratio * 100).toFixed(1) }}%</strong>
            </button>
          </section>
          <section class="data-panel mq-inset">
            <h3>缺陷 Top10</h3>
            <p v-if="report.top_defects === null" class="empty">缺陷来源不可用</p>
            <p v-else-if="!report.top_defects.length" class="empty">暂无确认缺陷</p>
            <button
              v-for="item in report.top_defects || []"
              :key="defectKey(item)"
              type="button"
              class="data-row row-button"
              @click="drill({ rule_id: item.rule_id })"
            >
              <span>{{ item.name }}</span
              ><strong>{{ item.count }}</strong>
            </button>
          </section>
        </div>
        <div v-else-if="defectsLoading" role="status" class="status">正在读取缺陷明细…</div>
        <p v-else-if="defectsError" role="alert" class="status error">
          <MqIcon name="issue" :size="18" />{{ defectsError }}
        </p>
        <div v-else-if="defects" class="table-panel mq-inset">
          <div class="table-scroll">
            <table class="mq-table">
              <thead>
                <tr>
                  <th>缺陷名称</th>
                  <th>提醒等级</th>
                  <th>大类</th>
                  <th>类型</th>
                  <th>文书</th>
                  <th>单否</th>
                  <th class="num">数量</th>
                  <th class="num">占比</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in defects.items" :key="defectKey(item)">
                  <td>
                    <button type="button" class="link" @click="drill({ rule_id: item.rule_id })">
                      {{ item.name }}
                    </button>
                  </td>
                  <td>{{ item.severity ?? '未知' }}</td>
                  <td>{{ item.category ?? '未知' }}</td>
                  <td>{{ item.type ?? '未知' }}</td>
                  <td>{{ item.document ?? '未知' }}</td>
                  <td>{{ item.is_veto === null ? '未知' : item.is_veto ? '是' : '否' }}</td>
                  <td class="num">
                    {{ item.count }}
                  </td>
                  <td class="num">{{ (item.ratio * 100).toFixed(1) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="!defects.items.length" class="empty">暂无确认缺陷</p>
          <nav class="pager" aria-label="缺陷分页">
            <button
              class="mq-btn"
              type="button"
              :disabled="defects.page === 1"
              title="上一页"
              @click="loadDefects(defects.page - 1)"
            >
              上一页</button
            ><span>第 {{ defects.page }} 页 · {{ defects.total }} 项</span
            ><button
              class="mq-btn"
              type="button"
              :disabled="defects.page * defects.page_size >= defects.total"
              title="下一页"
              @click="loadDefects(defects.page + 1)"
            >
              下一页
            </button>
          </nav>
        </div>
      </section>
      <section class="mq-card mq-card--padded" aria-label="病例下钻">
        <div class="mq-card__head section-head">
          <div>
            <h2 class="mq-card__title">病例明细</h2>
            <p class="mq-card__desc">点击科室、等级或缺陷可下钻；导出按当前下钻条件</p>
          </div>
          <div class="head-actions">
            <button
              class="mq-btn"
              type="button"
              :disabled="exporting || !records"
              @click="download('records')"
            >
              <MqIcon name="download" :size="16" />下载病例</button
            ><button class="mq-btn" type="button" :disabled="recordsLoading" @click="drill({})">
              清除下钻
            </button>
          </div>
        </div>
        <p v-if="drillLabel" class="drill-chip">
          <span class="mq-status mq-status--info">当前下钻</span>{{ drillLabel }}
        </p>
        <div v-if="recordsLoading" class="status" role="status">正在读取病例明细…</div>
        <p v-else-if="recordsError" role="alert" class="status error">
          <MqIcon name="issue" :size="18" />{{ recordsError }}
        </p>
        <div v-else-if="records" class="table-panel mq-inset">
          <div class="table-scroll">
            <table class="mq-table">
              <thead>
                <tr>
                  <th>病例身份</th>
                  <th>科室</th>
                  <th>出院日期</th>
                  <th>类型事实</th>
                  <th>报表专用分 / 等级</th>
                  <th>标准版本</th>
                  <th>历史分 / 等级</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in records.items"
                  :key="`${row.institute_id}:${row.patient_id}:${row.visit_id}`"
                >
                  <td>
                    <strong>{{ row.patient_name || '未登记姓名' }}</strong
                    ><small class="mq-mono"
                      >{{ row.institute_id }} / {{ row.patient_id }} / {{ row.visit_id }}</small
                    >
                  </td>
                  <td>{{ row.department || '未知科室' }}</td>
                  <td class="mq-mono">
                    {{ row.discharged_at || '未知' }}
                  </td>
                  <td>
                    <span
                      class="mq-status"
                      :class="factClass(row.types[applied.record_type || 'death'])"
                      >{{ factLabel(row.types[applied.record_type || 'death']) }}</span
                    >
                  </td>
                  <td>
                    {{
                      row.report_score_status === 'scored'
                        ? `${row.report_score ?? '未知'} / ${row.report_grade ?? '未知'}`
                        : '未知'
                    }}<small>{{ row.reason_code || '' }}</small>
                  </td>
                  <td class="mq-mono">
                    {{ row.standard_id || '未知' }} / {{ row.standard_version_seq ?? '未知' }}
                  </td>
                  <td>
                    {{ row.historical_score ?? '未知' }} / {{ row.historical_grade ?? '未知' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="!records.items.length" class="empty">无匹配病例</p>
          <nav class="pager" aria-label="病例分页">
            <button
              class="mq-btn"
              type="button"
              :disabled="records.page === 1"
              title="上一页"
              @click="loadRecords(records.page - 1)"
            >
              上一页</button
            ><span>第 {{ records.page }} 页 · {{ records.total }} 例</span
            ><button
              class="mq-btn"
              type="button"
              :disabled="records.page * records.page_size >= records.total"
              title="下一页"
              @click="loadRecords(records.page + 1)"
            >
              下一页
            </button>
          </nav>
        </div>
      </section>
    </template>
    <p v-if="exportError" role="alert" class="status error">
      <MqIcon name="issue" :size="18" />{{ exportError }}
    </p>
    <SpecialReportConfigDrawer
      v-if="canConfigure"
      :open="configOpen"
      :institute-id="draft.institute_id"
      @close="configOpen = false"
      @saved="configurationSaved"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
import {
  getSpecialRecordReport,
  getSpecialReportRecords,
  getSpecialReportDefects,
  exportSpecialRecordReport,
  sameSpecialReportVersions,
} from '@/api/specialRecordReports'
import type {
  SpecialRecordFilters,
  SpecialRecordReport,
  SpecialReportRecords,
  SpecialRecordType,
  SpecialTypeFact,
  SpecialDefectsPage,
} from '@/api/specialRecordReports'
import SpecialReportConfigDrawer from './SpecialReportConfigDrawer.vue'
import SpecialReportCharts from './SpecialReportCharts.vue'

const typeOptions = [
  { value: 'death', label: '死亡' },
  { value: 'critical', label: '危重' },
  { value: 'difficult', label: '疑难' },
  { value: 'consultation', label: '会诊' },
  { value: 'transfusion', label: '输血' },
  { value: 'surgery', label: '手术' },
  { value: 'surgery_ge3', label: '3级及以上手术' },
  { value: 'surgery_ge4', label: '4级及以上手术' },
]
const auth = useAuthStore()
const canConfigure = computed(() => auth.hasRole('admin') || auth.hasRole('qc_manager'))
const configOpen = ref(false)
function initial(): SpecialRecordFilters {
  const today = new Date(new Date().toLocaleDateString('en-US', { timeZone: 'Asia/Shanghai' }))
  const date = (value: Date) =>
    `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  const start = new Date(today)
  start.setDate(start.getDate() - 29)
  return {
    institute_id: auth.user?.institute_id || '',
    department: '',
    discharged_from: date(start),
    discharged_to: date(today),
    record_type: 'death',
    record_type_state: 'positive',
  }
}
const draft = ref<SpecialRecordFilters>(initial())
const applied = ref<SpecialRecordFilters>(initial())
const drillFilters = ref<Partial<SpecialRecordFilters>>({})
const modeOptions = [
  { value: 'charts', label: '图表' },
  { value: 'details', label: '明细' },
] as const
const mode = ref<'charts' | 'details'>('charts')
const report = ref<SpecialRecordReport | null>(null)
const records = ref<SpecialReportRecords | null>(null)
const defects = ref<SpecialDefectsPage | null>(null)
const defectsLoading = ref(false)
const defectsError = ref('')
const loading = ref(false)
const recordsLoading = ref(false)
const exporting = ref(false)
const error = ref('')
const filterError = ref('')
const recordsError = ref('')
const exportError = ref('')
let nonce = 0
let recordsNonce = 0
let defectsNonce = 0
const standardName = computed(() =>
  report.value?.score_standard.status === 'configured'
    ? report.value.score_standard.standard_name || '已配置'
    : report.value?.score_standard.status === 'no_standard'
      ? '未配置'
      : '不可用',
)
const activeTypeLabel = computed(
  () => typeOptions.find((item) => item.value === applied.value.record_type)?.label || '特殊病历',
)
const drillLabel = computed(() =>
  Object.entries(drillFilters.value)
    .map(
      ([key, value]) =>
        `${({ department: '科室', grade: '等级', rule_id: '缺陷' } as Record<string, string>)[key] || key}：${value}`,
    )
    .join(' · '),
)
const message = (cause: unknown) => (cause instanceof Error ? cause.message : '读取失败，请重试')
function defectKey(item: import('@/api/specialRecordReports').SpecialDefectRow) {
  return JSON.stringify([
    item.rule_id,
    item.name,
    item.severity,
    item.category,
    item.type,
    item.document,
    item.is_veto,
  ])
}
function factLabel(fact: SpecialTypeFact) {
  return fact.state === 'positive'
    ? '命中'
    : fact.state === 'negative'
      ? '明确非该类型'
      : `未知（${fact.reason_code || '来源缺失'}）`
}
function factClass(fact: SpecialTypeFact) {
  // 只有明确命中用语义色；未知/非该类型保持中性，不暗示结论
  return fact.state === 'positive' ? 'mq-status--info' : ''
}
async function load() {
  if (!applied.value.institute_id) {
    filterError.value = '请填写授权范围内的机构'
    return
  }
  const ticket = ++nonce
  recordsNonce++
  defectsNonce++
  defects.value = null
  defectsLoading.value = false
  report.value = null
  records.value = null
  loading.value = true
  recordsLoading.value = false
  exporting.value = false
  error.value = ''
  exportError.value = ''
  try {
    const result = await getSpecialRecordReport(applied.value)
    if (ticket !== nonce) return
    report.value = result
    void loadRecords()
    void loadDefects()
  } catch (cause) {
    if (ticket === nonce) error.value = message(cause)
  } finally {
    if (ticket === nonce) loading.value = false
  }
}
async function loadDefects(page = 1) {
  const ticket = ++defectsNonce
  const scopeTicket = nonce
  defectsLoading.value = true
  defects.value = null
  defectsError.value = ''
  try {
    const result = await getSpecialReportDefects(applied.value, page)
    if (ticket === defectsNonce && scopeTicket === nonce) {
      if (!report.value || !sameSpecialReportVersions(report.value, result))
        throw new Error('机构分类或评分标准版本已变化，请刷新报表')
      defects.value = result
    }
  } catch (cause) {
    if (ticket === defectsNonce && scopeTicket === nonce) defectsError.value = message(cause)
  } finally {
    if (ticket === defectsNonce && scopeTicket === nonce) defectsLoading.value = false
  }
}
async function loadRecords(page = 1) {
  const ticket = ++recordsNonce
  const scopeTicket = nonce
  recordsLoading.value = true
  records.value = null
  recordsError.value = ''
  try {
    const result = await getSpecialReportRecords({ ...applied.value, ...drillFilters.value }, page)
    if (ticket === recordsNonce && scopeTicket === nonce) {
      if (!report.value || !sameSpecialReportVersions(report.value, result))
        throw new Error('机构分类或评分标准版本已变化，请刷新报表')
      records.value = result
    }
  } catch (cause) {
    if (ticket === recordsNonce && scopeTicket === nonce) recordsError.value = message(cause)
  } finally {
    if (ticket === recordsNonce && scopeTicket === nonce) recordsLoading.value = false
  }
}
function apply() {
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(draft.value.discharged_from) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(draft.value.discharged_to) ||
    draft.value.discharged_from > draft.value.discharged_to
  ) {
    filterError.value = '请选择顺序正确的出院日期范围'
    return
  }
  filterError.value = ''
  applied.value = { ...draft.value }
  drillFilters.value = {}
  void load()
}
function configurationSaved() {
  configOpen.value = false
  apply()
}
function reset() {
  nonce++
  recordsNonce++
  defectsNonce++
  configOpen.value = false
  report.value = null
  records.value = null
  defects.value = null
  loading.value = false
  recordsLoading.value = false
  defectsLoading.value = false
  exporting.value = false
  error.value = ''
  recordsError.value = ''
  defectsError.value = ''
  exportError.value = ''
  draft.value = initial()
  mode.value = 'charts'
  apply()
}
function selectType(type: SpecialRecordType, state: 'positive' | 'unknown' = 'positive') {
  draft.value = { ...applied.value, record_type: type, record_type_state: state }
  apply()
}
function drill(value: Partial<SpecialRecordFilters>) {
  drillFilters.value = value
  void loadRecords()
}
async function download(kind: 'records' | 'defects' | 'summary' = 'summary') {
  if (!report.value || loading.value || exporting.value) return
  const ticket = nonce
  const drillTicket = recordsNonce
  exporting.value = true
  exportError.value = ''
  try {
    const blob = await exportSpecialRecordReport(
      kind === 'records' ? { ...applied.value, ...drillFilters.value } : applied.value,
      kind,
      report.value,
    )
    if (ticket !== nonce || (kind === 'records' && drillTicket !== recordsNonce)) return
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `special-record-${kind}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    if (ticket === nonce && (kind !== 'records' || drillTicket === recordsNonce)) {
      exportError.value = message(cause)
    }
  } finally {
    if (ticket === nonce) exporting.value = false
  }
}
watch(() => auth.user?.id, reset)
onMounted(reset)
onBeforeUnmount(() => {
  nonce++
  recordsNonce++
  defectsNonce++
})
</script>

<style scoped src="./reportPage.css"></style>
<style scoped src="./styles/special-record-report.css"></style>
