<template>
  <section class="core-report" aria-label="核心制度专题报表">
    <header>
      <h2>18项核心制度专题</h2>
      <button
        class="mq-btn"
        type="button"
        :disabled="!report || loading || exporting"
        @click="download"
      >
        <Download :size="16" /> CSV
      </button>
    </header>
    <form class="core-filters mq-card mq-card--padded" @submit.prevent="apply">
      <label
        >场景<select v-model="draft.scene" class="mq-input">
          <option value="running">运行病历</option>
          <option value="final">终末病历</option>
        </select></label
      >
      <label>机构<input v-model.trim="draft.institute_id" class="mq-input" /></label>
      <label>科室<input v-model.trim="draft.department" class="mq-input" /></label>
      <label>主治医师<input v-model.trim="draft.doctor" class="mq-input" /></label>
      <label
        >完成时间起（上海）<input
          v-model="draft.completed_from"
          class="mq-input"
          type="datetime-local"
          step="any"
      /></label>
      <label
        >完成时间止（上海）<input
          v-model="draft.completed_to"
          class="mq-input"
          type="datetime-local"
          step="any"
      /></label>
      <label
        >明细制度<select v-model="draft.system_id" class="mq-input">
          <option value="">全部制度</option>
          <option value="unknown">未知覆盖</option>
          <option v-for="system in report?.systems || []" :key="system.id" :value="system.id">
            {{ system.name }}
          </option>
        </select></label
      >
      <label>明细质控点<input v-model.trim="draft.rule_id" class="mq-input" /></label>
      <label class="checkbox"
        ><input v-model="draft.problems_only" class="mq-input" type="checkbox" />仅问题病例</label
      >
      <button class="mq-btn" type="submit"><Search :size="16" />查询</button
      ><button class="mq-btn" type="button" @click="reset"><RotateCcw :size="16" />重置</button>
    </form>
    <p>仅统计自动质控确认问题，人工缺陷未纳入；多制度归属可重叠。</p>
    <div v-if="loading" role="status">正在读取核心制度报表…</div>
    <div v-else-if="error" role="alert">
      {{ error }}
    </div>
    <template v-else-if="report">
      <p class="contract">
        {{ report.contract }}
      </p>
      <p>{{ report.scope.scope_label }} · 生成时间 {{ formatTime(report.as_of) }}</p>
      <div class="core-summary">
        <span
          >范围病例 <strong>{{ report.summary.candidate_records }}</strong></span
        ><span
          >未知分类病例 <strong>{{ report.summary.unknown_records }}</strong></span
        ><span
          >未知分类质控点 <strong>{{ report.summary.unknown_points }}</strong></span
        ><span
          >未知分类确认缺陷 <strong>{{ report.summary.unknown_defects ?? '未知' }}</strong></span
        ><button class="mq-btn" type="button" @click="drill('unknown')">
          结果不可用 {{ report.summary.unavailable_records }} / 未知覆盖
        </button>
      </div>
      <h3>核心制度缺陷 Top20</h3>
      <div class="core-summary" data-testid="core-defect-top">
        <button
          v-for="system in report.top_systems || []"
          :key="system.id"
          class="mq-btn"
          type="button"
          @click="drill(system.id, '', true)"
        >
          {{ system.name }} · {{ system.defect_total }} 条
        </button>
        <span v-if="report.top_systems === undefined">缺陷分布来源未接入</span>
        <span v-else-if="!report.top_systems.length">暂无已核验分类的确认缺陷</span>
      </div>
      <h3>制度汇总（院科、医师与完成时间范围）</h3>
      <div class="table-scroll">
        <table class="mq-table">
          <thead>
            <tr>
              <th>制度</th>
              <th>已配置点范围病例</th>
              <th>问题病例</th>
              <th>确认缺陷</th>
              <th>问题率</th>
              <th>质控点</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="system in report.systems" :key="system.id">
              <td>{{ system.name }}</td>
              <td>{{ display(system.record_count) }}</td>
              <td>{{ display(system.problem_records) }}</td>
              <td>{{ system.defect_total == null ? '未知或无配置数据' : system.defect_total }}</td>
              <td>
                {{
                  system.problem_rate === null
                    ? '无配置数据'
                    : `${(system.problem_rate * 100).toFixed(1)}%`
                }}
              </td>
              <td>{{ system.points.length }}</td>
              <td>
                <button class="mq-btn" type="button" @click="openSystem(system.id)">
                  原文与缺陷点</button
                ><button
                  class="mq-btn"
                  type="button"
                  :disabled="system.record_count === null"
                  @click="drill(system.id)"
                >
                  病例明细
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <h3>病例明细（{{ report.total }}）</h3>
      <div class="table-scroll">
        <table class="mq-table">
          <thead>
            <tr>
              <th>病例身份</th>
              <th>科室 / 医师</th>
              <th>冻结结果</th>
              <th>覆盖</th>
              <th>问题</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in report.items"
              :key="`${row.institute_id}:${row.patient_id}:${row.visit_id}`"
            >
              <td>
                {{ row.patient_name || '未登记姓名'
                }}<small>{{ row.institute_id }} / {{ row.patient_id }} / {{ row.visit_id }}</small>
              </td>
              <td>{{ row.department || '未知科室' }} / {{ row.doctor || '未知医师' }}</td>
              <td>
                {{ row.rule_set_key || '未知' }} / {{ row.rule_set_version || '未知'
                }}<small>{{ formatTime(row.completed_at) }}</small>
              </td>
              <td>{{ coverage(row.coverage) }}</td>
              <td>
                {{
                  row.coverage === 'unavailable'
                    ? '未知'
                    : row.points.filter((p) => p.is_confirmed_issue).length
                }}
              </td>
              <td>
                <button class="mq-btn" type="button" @click="selectedCase = row">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!report.items.length">无匹配病例</p>
      </div>
      <nav aria-label="病例分页">
        <button class="mq-btn" :disabled="report.page === 1" @click="load(report.page - 1)">
          <ChevronLeft :size="16" /></button
        ><span>第{{ report.page }}页 / {{ report.total }}例</span
        ><button
          class="mq-btn"
          :disabled="report.page * report.page_size >= report.total"
          @click="load(report.page + 1)"
        >
          <ChevronRight :size="16" />
        </button>
      </nav>
    </template>
    <a-drawer
      :open="!!selectedSystem"
      width="min(720px, 100vw)"
      :root-style="{ zIndex: 1100 }"
      title="制度原文与缺陷点"
      @close="selectedSystem = ''"
    >
      <template v-if="activeSystem && report">
        <h3>{{ activeSystem.name }}</h3>
        <p>{{ report.reference.reference_note }}</p>
        <a :href="report.reference.source_url" target="_blank" rel="noopener noreferrer"
          >国家卫生健康委员会原文（{{ report.reference.reference_date }}）</a
        >
        <pre class="reference-text">{{ activeReference?.text }}</pre>
        <h3>实际返回的已配置质控点</h3>
        <p v-if="!activeSystem.points.length">无已配置返回点，不能判定该制度合规。</p>
        <div
          v-for="point in activeSystem.points"
          :key="`${point.rule_set_key}:${point.rule_set_version}:${point.rule_id}`"
          class="point"
        >
          <strong>{{ point.rule_name }}</strong>
          <p>{{ point.rule_id }} · {{ point.rule_set_key }}/{{ point.rule_set_version }}</p>
          <p>病例{{ point.record_count }} · 问题病例{{ point.problem_records }}</p>
          <button class="mq-btn" @click="drill(activeSystem.id, point.rule_id)">病例下钻</button>
        </div>
      </template>
    </a-drawer>
    <a-drawer
      :open="!!selectedCase"
      width="min(720px, 100vw)"
      :root-style="{ zIndex: 1100 }"
      title="病例质控点详情"
      @close="selectedCase = null"
    >
      <template v-if="selectedCase">
        <h3>{{ selectedCase.patient_name || '未登记姓名' }}</h3>
        <p>
          {{ selectedCase.institute_id }} / {{ selectedCase.patient_id }} /
          {{ selectedCase.visit_id }}
        </p>
        <p>
          运行 {{ selectedCase.root_job_id || '未知' }} · 结果
          {{ selectedCase.envelope_id || '未知' }}
        </p>
        <p>
          冻结版本 {{ selectedCase.rule_set_key || '未知' }}/{{
            selectedCase.rule_set_version || '未知'
          }}
        </p>
        <p>{{ coverage(selectedCase.coverage) }}</p>
        <div v-for="point in selectedCase.points" :key="point.rule_id" class="point">
          <strong>{{ point.rule_name }}</strong>
          <p>
            {{ point.rule_id }} · {{ point.status }} ·
            {{ point.is_confirmed_issue ? '确认问题' : '非确认问题' }}
          </p>
          <p>
            {{
              point.system_ids === null
                ? '制度归属未知'
                : point.system_ids.length
                  ? point.system_ids.join(' / ')
                  : '明确非核心制度'
            }}
          </p>
        </div>
      </template>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Download, RotateCcw, Search } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { getCoreSystemReport, exportCoreSystemReport } from '@/api/coreSystemReports'
import type { CoreReportFilters, CoreReportRow, CoreSystemReport } from '@/api/coreSystemReports'
import type { RecordQualityFilters } from '@/api/qualityReports'

const auth = useAuthStore()
const props = withDefaults(
  defineProps<{ initialScene?: 'running' | 'final'; initialFilters?: RecordQualityFilters }>(),
  {
    initialScene: 'running',
  },
)
const initial = () => ({
  scene: props.initialFilters?.scene ?? props.initialScene,
  institute_id: '',
  department: props.initialFilters?.department ?? '',
  doctor: props.initialFilters?.doctor ?? '',
  completed_from: localDate(props.initialFilters?.completed_from),
  completed_to: localDate(props.initialFilters?.completed_to),
  system_id: '',
  rule_id: '',
  problems_only: false,
})
const draft = ref<CoreReportFilters>(initial())
let applied: CoreReportFilters = initial()
const report = ref<CoreSystemReport | null>(null)
const loading = ref(false)
const error = ref('')
const exporting = ref(false)
const selectedSystem = ref('')
const selectedCase = ref<CoreReportRow | null>(null)
const activeSystem = computed(() =>
  report.value?.systems.find((s) => s.id === selectedSystem.value),
)
const activeReference = computed(() =>
  report.value?.reference.systems.find((s) => s.id === selectedSystem.value),
)
let nonce = 0
function localDate(value?: string) {
  if (!value) return ''
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}+08:00`
  const date = new Date(normalized)
  return Number.isFinite(date.getTime())
    ? new Date(date.getTime() + 8 * 60 * 60 * 1000).toISOString().slice(0, -1)
    : value
}
function formatTime(value: string | null) {
  return value
    ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) +
        ' 上海'
    : '未知时间'
}
function display(value: number | null) {
  return value === null ? '无配置数据' : value
}
function coverage(value: string) {
  return (
    (
      { known: '已核验分类', unknown: '分类未知', unavailable: '结果不可用' } as Record<
        string,
        string
      >
    )[value] || '未知'
  )
}
async function load(page = 1) {
  const ticket = ++nonce
  exporting.value = false
  loading.value = true
  error.value = ''
  report.value = null
  selectedCase.value = null
  try {
    const result = await getCoreSystemReport(applied, page)
    if (ticket === nonce) report.value = result
  } catch (cause) {
    if (ticket === nonce) error.value = cause instanceof Error ? cause.message : '读取失败，请重试'
  } finally {
    if (ticket === nonce) loading.value = false
  }
}
function apply() {
  const start = draft.value.completed_from
    ? new Date(`${draft.value.completed_from}+08:00`)
    : undefined
  const end = draft.value.completed_to ? new Date(`${draft.value.completed_to}+08:00`) : undefined
  if (
    (start && !Number.isFinite(start.getTime())) ||
    (end && !Number.isFinite(end.getTime())) ||
    (start && end && start > end)
  ) {
    error.value = '请选择有效且顺序正确的上海时间窗口'
    return
  }
  applied = {
    ...draft.value,
    completed_from: start?.toISOString(),
    completed_to: end?.toISOString(),
  }
  void load()
}
function reset() {
  nonce++
  report.value = null
  selectedCase.value = null
  loading.value = false
  exporting.value = false
  draft.value = initial()
  selectedSystem.value = ''
  apply()
}
function openSystem(id: string) {
  selectedSystem.value = id
}
function drill(id: string, rule = '', problemsOnly = applied.problems_only) {
  draft.value.system_id = id
  draft.value.rule_id = rule
  draft.value.problems_only = problemsOnly ?? false
  selectedSystem.value = ''
  applied = { ...applied, system_id: id, rule_id: rule || undefined, problems_only: problemsOnly }
  void load()
}
async function download() {
  if (!report.value || loading.value || exporting.value) return
  const ticket = nonce
  exporting.value = true
  try {
    const blob = await exportCoreSystemReport(applied)
    if (ticket !== nonce) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'core-system-report.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    if (ticket === nonce) error.value = cause instanceof Error ? cause.message : '导出失败'
  } finally {
    if (ticket === nonce) exporting.value = false
  }
}
watch(() => [props.initialFilters, props.initialScene, auth.user?.id], reset, { deep: true })
onMounted(() => {
  reset()
})
onBeforeUnmount(() => {
  nonce++
})
</script>

<style scoped src="@/views/qc/reports/styles/core-system-report.css"></style>
