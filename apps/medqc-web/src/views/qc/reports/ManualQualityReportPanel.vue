<template>
  <section class="manual-report" aria-label="人工质控报表">
    <details class="manual-assumption mq-soft" data-testid="manual-assumption">
      <summary><MqIcon name="rules" :size="16" />统计口径</summary>
      <p>
        {{
          report?.assumption ||
          '已确认统计口径：按上海自然日的缺陷创建日期计录入量，审核与整改分别展示当前状态；支持机构、科室、录入人、任务及场景筛选；同缺陷多次操作只计一条，来源不完整或错配时相关信息为未知。'
        }}
      </p>
    </details>
    <form class="manual-filters mq-card mq-card--padded" @submit.prevent="query">
      <label class="mq-field"
        ><span class="mq-field__label">开始日期</span
        ><input v-model="draft.start_date" class="mq-input" type="date" required
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">结束日期</span
        ><input v-model="draft.end_date" class="mq-input" type="date" required
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">机构</span
        ><select v-model="draft.institute_id" class="mq-input" @change="draft.department = ''">
          <option value="">全部可见机构</option>
          <option v-for="id in options.institutes" :key="id">{{ id }}</option>
        </select></label
      >
      <label class="mq-field"
        ><span class="mq-field__label">科室</span
        ><select v-model="draft.department" class="mq-input">
          <option value="">全部科室</option>
          <option
            v-for="item in options.departments.filter(
              (item) => item.institute_id === draft.institute_id,
            )"
            :key="item.department"
          >
            {{ item.department }}
          </option>
        </select></label
      >
      <label class="mq-field"
        ><span class="mq-field__label">录入人</span
        ><select v-model="draft.creator_id" class="mq-input">
          <option value="">全部可见人员</option>
          <option v-for="item in options.creators" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select></label
      >
      <label class="mq-field"
        ><span class="mq-field__label">任务</span
        ><select v-model="draft.task_id" class="mq-input">
          <option value="">全部可信任务</option>
          <option v-for="item in options.tasks" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select></label
      >
      <label class="mq-field"
        ><span class="mq-field__label">冻结场景</span
        ><select v-model="draft.scene" class="mq-input">
          <option value="all">全部场景</option>
          <option value="running">运行</option>
          <option value="final">终末</option>
          <option value="outpatient_emergency">门急诊</option>
        </select></label
      >
      <div class="manual-actions">
        <button class="mq-btn mq-btn--primary" type="submit" :disabled="loading">
          <MqIcon name="search" :size="16" />查询
        </button>
        <button class="mq-btn" type="button" :disabled="loading" @click="reset">重置</button>
        <button
          class="mq-btn"
          type="button"
          :disabled="!report || loading || exporting"
          @click="download"
        >
          <MqIcon name="download" :size="16" />导出 CSV
        </button>
      </div>
    </form>
    <p v-if="error" class="manual-error" role="alert">
      <MqIcon name="issue" :size="16" />{{ error }}
    </p>
    <a-spin :spinning="loading">
      <template v-if="report">
        <div class="manual-summary">
          <div class="summary-card mq-card mq-card--padded">
            <span class="summary-label"><MqIcon name="doc" :size="18" />人工缺陷录入</span>
            <h3 class="summary-total">录入 {{ report.summary.entered }} 条</h3>
            <small>统计读取时间 {{ report.as_of }} · 日期口径 {{ report.timezone }}</small>
          </div>
          <section class="summary-card mq-card mq-card--padded">
            <h3>当前审核状态</h3>
            <div class="status-list">
              <span
                v-for="(count, key) in report.summary.review"
                :key="key"
                class="mq-status"
                :class="statusClass(reviewTones, key, count)"
                >{{ reviewLabels[key] || key }} {{ count }}</span
              >
            </div>
          </section>
          <section class="summary-card mq-card mq-card--padded">
            <h3>当前现代整改状态</h3>
            <div class="status-list">
              <span
                v-for="(count, key) in report.summary.rectification"
                :key="key"
                class="mq-status"
                :class="statusClass(rectificationTones, key, count)"
                >{{ rectificationLabels[key] || key }} {{ count }}</span
              >
            </div>
          </section>
        </div>
        <div class="manual-table mq-card">
          <a-table
            :data-source="report.items"
            :columns="columns"
            row-key="id"
            :pagination="false"
            :scroll="{ x: 1000 }"
          >
            <template #bodyCell="{ column, record, text }">
              <span
                v-if="column.key === 'review_status'"
                class="mq-status"
                :class="statusClass(reviewTones, record.review_status)"
                >{{ reviewLabels[record.review_status] || '未知' }}</span
              >
              <span
                v-else-if="column.key === 'rectification_status'"
                class="mq-status"
                :class="statusClass(rectificationTones, record.rectification_status)"
                >{{ rectificationLabels[record.rectification_status] || '未知' }}</span
              >
              <button
                v-else-if="column.key === 'detail'"
                class="link"
                type="button"
                @click="selectDetail(record.id)"
              >
                查看明细
              </button>
              <template v-else>
                {{ text ?? '未知' }}
              </template>
            </template>
          </a-table>
          <div class="manual-pager">
            <a-pagination
              :current="page"
              :total="report.total"
              :page-size="20"
              :show-size-changer="false"
              @change="loadPage"
            />
          </div>
        </div>
      </template>
    </a-spin>
    <a-drawer
      :open="!!selected"
      title="人工缺陷统计明细"
      width="min(560px, 100vw)"
      @close="selected = null"
    >
      <a-descriptions v-if="selected" :column="1" bordered size="small">
        <a-descriptions-item v-for="field in detailFields" :key="field.key" :label="field.label">
          {{ detailValue(field.key) }}
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { onUnmounted, reactive, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
import {
  getManualQualityReport,
  exportManualQualityReport,
  type ManualReport,
  type ManualReportFilters,
  type ManualReportRow,
} from '@/api/manualQualityReport'
const auth = useAuthStore()
const today = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date())
const defaults = () => ({
  start_date: `${today.slice(0, 7)}-01`,
  end_date: today,
  institute_id: '',
  department: '',
  creator_id: '',
  task_id: '',
  scene: 'all' as ManualReportFilters['scene'],
})
const draft = reactive(defaults())
const applied = ref<ManualReportFilters>({
  start_date: draft.start_date,
  end_date: draft.end_date,
  scene: 'all',
})
const report = ref<ManualReport | null>(null),
  selected = ref<ManualReportRow | null>(null)
const loading = ref(false),
  exporting = ref(false),
  error = ref(''),
  page = ref(1)
let token = 0,
  exportToken = 0
const options = ref<ManualReport['filter_options']>({
  institutes: [],
  departments: [],
  creators: [],
  tasks: [],
})
const reviewLabels: Record<string, string> = {
  pending: '待审核',
  approved: '审核通过',
  rejected: '审核驳回',
  unknown: '未知',
}
const rectificationLabels: Record<string, string> = {
  pending: '待整改',
  submitted: '待验收',
  approved: '验收通过',
  rejected: '整改驳回',
  unassigned: '未派发',
  unknown: '未知',
}
// 状态到语义色只做展示映射；未知/未派发保持中性，计数为0时不着色
type Tone = 'success' | 'warning' | 'danger' | 'info'
const reviewTones: Record<string, Tone> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}
const rectificationTones: Record<string, Tone> = {
  pending: 'warning',
  submitted: 'info',
  approved: 'success',
  rejected: 'danger',
}
function statusClass(tones: Record<string, Tone>, key: unknown, count?: number) {
  const tone = tones[String(key)]
  return tone && count !== 0 ? `mq-status--${tone}` : ''
}
const columns = [
  { title: '机构', dataIndex: 'institute_id' },
  { title: '科室', dataIndex: 'department' },
  { title: '录入人', dataIndex: 'creator_name' },
  { title: '任务', dataIndex: 'task_name' },
  { title: '缺陷', dataIndex: 'rule_name' },
  { title: '创建日期', dataIndex: 'created_at' },
  { title: '审核', key: 'review_status' },
  { title: '整改', key: 'rectification_status' },
  { title: '操作', key: 'detail' },
]
const detailFields: Array<{ key: keyof ManualReportRow; label: string }> = [
  { key: 'id', label: '缺陷 ID' },
  { key: 'institute_id', label: '机构' },
  { key: 'patient_id', label: '患者号' },
  { key: 'visit_id', label: '就诊号' },
  { key: 'department', label: '抽样科室' },
  { key: 'creator_name', label: '录入人' },
  { key: 'task_id', label: '任务 ID' },
  { key: 'task_record_id', label: '任务病例 ID' },
  { key: 'run_number', label: '冻结运行号' },
  { key: 'scene', label: '冻结场景' },
  { key: 'review_status', label: '当前审核' },
  { key: 'rectification_status', label: '当前整改' },
  { key: 'source_verified', label: '冻结来源核验' },
]
function selectDetail(id: unknown) {
  selected.value = report.value?.items.find((item) => item.id === id) ?? null
}
function detailValue(key: keyof ManualReportRow) {
  if (!selected.value) return '未知'
  const value = selected.value[key]
  if (key === 'review_status') return reviewLabels[String(value)] || '未知'
  if (key === 'rectification_status') return rectificationLabels[String(value)] || '未知'
  if (key === 'source_verified') return value ? '已核验' : '来源不完整或错配'
  return value ?? '未知'
}
async function loadPage(value = 1) {
  const request = ++token
  ++exportToken
  loading.value = true
  error.value = ''
  report.value = null
  selected.value = null
  exporting.value = false
  try {
    const result = await getManualQualityReport(applied.value, value)
    if (request !== token) return
    if (!applied.value.institute_id && !applied.value.creator_id && !applied.value.task_id)
      options.value = result.filter_options
    else if (!options.value.institutes.length) options.value = result.filter_options
    report.value = result
    page.value = value
  } catch (e) {
    if (request === token) error.value = e instanceof Error ? e.message : '人工质控报表不可用'
  } finally {
    if (request === token) loading.value = false
  }
}
function query() {
  if (!draft.start_date || !draft.end_date || draft.start_date > draft.end_date) {
    error.value = '请选择正序完整日期窗口'
    return
  }
  applied.value = {
    start_date: draft.start_date,
    end_date: draft.end_date,
    scene: draft.scene,
    institute_id: draft.institute_id || undefined,
    department: draft.department || undefined,
    creator_id: draft.creator_id || undefined,
    task_id: draft.task_id || undefined,
  }
  void loadPage()
}
function reset() {
  Object.assign(draft, defaults())
  query()
}
async function download() {
  if (!report.value || exporting.value) return
  const request = ++exportToken
  exporting.value = true
  try {
    const blob = await exportManualQualityReport(applied.value)
    if (request !== exportToken) return
    const url = URL.createObjectURL(blob),
      link = document.createElement('a')
    link.href = url
    link.download = 'manual-quality-report.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    if (request === exportToken) error.value = e instanceof Error ? e.message : '导出失败'
  } finally {
    if (request === exportToken) exporting.value = false
  }
}
watch(
  () => [auth.user?.id, auth.user?.roles],
  () => {
    ++token
    ++exportToken
    report.value = null
    selected.value = null
    loading.value = false
    exporting.value = false
    options.value = { institutes: [], departments: [], creators: [], tasks: [] }
    if (auth.user?.id) void loadPage()
  },
  { immediate: true, deep: true },
)
onUnmounted(() => {
  ++token
  ++exportToken
})
</script>
<style scoped src="./styles/manual-quality-report.css"></style>
