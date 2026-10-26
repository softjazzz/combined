<template>
  <section class="core-report" aria-label="核心制度专题报表">
    <header class="core-head">
      <div>
        <h2 class="mq-card__title">18项核心制度专题</h2>
        <p class="mq-card__desc">按院科、医师与完成时间统计各项制度已配置质控点的问题病例</p>
      </div>
      <button
        class="mq-btn"
        type="button"
        :disabled="!report || loading || exporting"
        @click="download"
      >
        <MqIcon name="download" :size="16" />导出 CSV
      </button>
    </header>
    <form class="core-filters mq-card mq-card--padded" @submit.prevent="apply">
      <label class="mq-field"
        ><span class="mq-field__label">场景</span
        ><select v-model="draft.scene" class="mq-input">
          <option value="running">运行病历</option>
          <option value="final">终末病历</option>
        </select></label
      >
      <label class="mq-field"
        ><span class="mq-field__label">机构</span
        ><input v-model.trim="draft.institute_id" class="mq-input" placeholder="授权范围内机构"
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">科室</span
        ><input v-model.trim="draft.department" class="mq-input" placeholder="全部科室"
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">主治医师</span
        ><input v-model.trim="draft.doctor" class="mq-input" placeholder="全部医生"
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">完成时间起（上海）</span
        ><input v-model="draft.completed_from" class="mq-input" type="datetime-local" step="any"
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">完成时间止（上海）</span
        ><input v-model="draft.completed_to" class="mq-input" type="datetime-local" step="any"
      /></label>
      <label class="mq-field"
        ><span class="mq-field__label">明细制度</span
        ><select v-model="draft.system_id" class="mq-input">
          <option value="">全部制度</option>
          <option value="unknown">未知覆盖</option>
          <option v-for="system in report?.systems || []" :key="system.id" :value="system.id">
            {{ system.name }}
          </option>
        </select></label
      >
      <label class="mq-field"
        ><span class="mq-field__label">明细质控点</span
        ><input v-model.trim="draft.rule_id" class="mq-input" placeholder="质控点编号"
      /></label>
      <div class="core-actions">
        <label class="checkbox"
          ><input v-model="draft.problems_only" type="checkbox" />仅问题病例</label
        >
        <button class="mq-btn mq-btn--primary" type="submit">
          <MqIcon name="search" :size="16" />查询</button
        ><button class="mq-btn" type="button" @click="reset">重置</button>
      </div>
    </form>
    <p class="core-notice mq-soft">
      <MqIcon name="issue" :size="16" />仅统计自动质控确认问题，人工缺陷未纳入；多制度归属可重叠。
    </p>
    <div v-if="loading" class="core-status" role="status">正在读取核心制度报表…</div>
    <div v-else-if="error" class="core-status is-error" role="alert">
      <MqIcon name="issue" :size="18" />{{ error }}
    </div>
    <template v-else-if="report">
      <div class="core-contract">
        <p>{{ report.contract }}</p>
        <small>{{ report.scope.scope_label }} · 生成时间 {{ formatTime(report.as_of) }}</small>
      </div>
      <div class="core-metrics">
        <div class="core-metric mq-card">
          <span class="core-metric__label">范围病例</span>
          <strong>{{ report.summary.candidate_records }}</strong>
        </div>
        <div class="core-metric mq-card">
          <span class="core-metric__label">未知分类病例</span>
          <strong>{{ report.summary.unknown_records }}</strong>
        </div>
        <div class="core-metric mq-card">
          <span class="core-metric__label">未知分类质控点</span>
          <strong>{{ report.summary.unknown_points }}</strong>
        </div>
        <div class="core-metric mq-card">
          <span class="core-metric__label">未知分类确认缺陷</span>
          <strong>{{ report.summary.unknown_defects ?? '未知' }}</strong>
        </div>
        <div class="core-metric core-metric--action mq-card">
          <span class="core-metric__label">结果不可用</span>
          <button class="mq-btn" type="button" @click="drill('unknown')">
            结果不可用 {{ report.summary.unavailable_records }} / 未知覆盖
          </button>
        </div>
      </div>
      <section class="core-card mq-card mq-card--padded">
        <h3>核心制度缺陷 Top20</h3>
        <div class="core-chips" data-testid="core-defect-top">
          <button
            v-for="system in report.top_systems || []"
            :key="system.id"
            class="mq-btn"
            type="button"
            @click="drill(system.id, '', true)"
          >
            {{ system.name }} · {{ system.defect_total }} 条
          </button>
          <span v-if="report.top_systems === undefined" class="core-empty">缺陷分布来源未接入</span>
          <span v-else-if="!report.top_systems.length" class="core-empty"
            >暂无已核验分类的确认缺陷</span
          >
        </div>
      </section>
      <section class="core-card core-card--table mq-card">
        <h3 class="core-table-title">制度汇总（院科、医师与完成时间范围）</h3>
        <div class="table-scroll">
          <table class="mq-table">
            <thead>
              <tr>
                <th>制度</th>
                <th class="num">已配置点范围病例</th>
                <th class="num">问题病例</th>
                <th class="num">确认缺陷</th>
                <th class="num">问题率</th>
                <th class="num">质控点</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="system in report.systems" :key="system.id">
                <td class="name">
                  {{ system.name }}
                </td>
                <td class="num">
                  {{ display(system.record_count) }}
                </td>
                <td class="num">
                  {{ display(system.problem_records) }}
                </td>
                <td class="num">
                  {{ system.defect_total == null ? '未知或无配置数据' : system.defect_total }}
                </td>
                <td class="num">
                  {{
                    system.problem_rate === null
                      ? '无配置数据'
                      : `${(system.problem_rate * 100).toFixed(1)}%`
                  }}
                </td>
                <td class="num">
                  {{ system.points.length }}
                </td>
                <td class="ops">
                  <button class="link" type="button" @click="openSystem(system.id)">
                    原文与缺陷点</button
                  ><button
                    class="link"
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
      </section>
      <section class="core-card core-card--table mq-card">
        <h3 class="core-table-title">病例明细（{{ report.total }}）</h3>
        <div class="table-scroll">
          <table class="mq-table">
            <thead>
              <tr>
                <th>病例身份</th>
                <th>科室 / 医师</th>
                <th>冻结结果</th>
                <th>覆盖</th>
                <th class="num">问题</th>
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
                  }}<small class="mq-mono"
                    >{{ row.institute_id }} / {{ row.patient_id }} / {{ row.visit_id }}</small
                  >
                </td>
                <td>{{ row.department || '未知科室' }} / {{ row.doctor || '未知医师' }}</td>
                <td>
                  <span class="mq-mono"
                    >{{ row.rule_set_key || '未知' }} / {{ row.rule_set_version || '未知' }}</span
                  ><small>{{ formatTime(row.completed_at) }}</small>
                </td>
                <td>
                  <span class="mq-status" :class="coverageClass(row.coverage)">{{
                    coverage(row.coverage)
                  }}</span>
                </td>
                <td class="num">
                  {{
                    row.coverage === 'unavailable'
                      ? '未知'
                      : row.points.filter((p) => p.is_confirmed_issue).length
                  }}
                </td>
                <td class="ops">
                  <button class="link" type="button" @click="selectedCase = row">详情</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!report.items.length" class="core-empty">无匹配病例</p>
        </div>
        <nav class="core-pager" aria-label="病例分页">
          <button
            class="mq-btn"
            type="button"
            :disabled="report.page === 1"
            @click="load(report.page - 1)"
          >
            上一页</button
          ><span>第{{ report.page }}页 / {{ report.total }}例</span
          ><button
            class="mq-btn"
            type="button"
            :disabled="report.page * report.page_size >= report.total"
            @click="load(report.page + 1)"
          >
            下一页
          </button>
        </nav>
      </section>
    </template>
    <a-drawer
      :open="!!selectedSystem"
      width="min(720px, 100vw)"
      :root-style="{ zIndex: 1100 }"
      title="制度原文与缺陷点"
      @close="selectedSystem = ''"
    >
      <template v-if="activeSystem && report">
        <h3 class="drawer-title">
          {{ activeSystem.name }}
        </h3>
        <div class="drawer-summary mq-soft">
          <p>{{ report.reference.reference_note }}</p>
          <a :href="report.reference.source_url" target="_blank" rel="noopener noreferrer"
            >国家卫生健康委员会原文（{{ report.reference.reference_date }}）</a
          >
        </div>
        <pre class="reference-text">{{ activeReference?.text }}</pre>
        <h3 class="drawer-title">实际返回的已配置质控点</h3>
        <p v-if="!activeSystem.points.length" class="core-empty">
          无已配置返回点，不能判定该制度合规。
        </p>
        <div
          v-for="point in activeSystem.points"
          :key="`${point.rule_set_key}:${point.rule_set_version}:${point.rule_id}`"
          class="point mq-inset"
        >
          <div>
            <strong>{{ point.rule_name }}</strong>
            <p class="mq-mono">
              {{ point.rule_id }} · {{ point.rule_set_key }}/{{ point.rule_set_version }}
            </p>
            <p>病例{{ point.record_count }} · 问题病例{{ point.problem_records }}</p>
          </div>
          <button class="mq-btn" type="button" @click="drill(activeSystem.id, point.rule_id)">
            病例下钻
          </button>
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
        <h3 class="drawer-title">
          {{ selectedCase.patient_name || '未登记姓名' }}
        </h3>
        <div class="drawer-summary mq-soft">
          <p class="mq-mono">
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
          <span class="mq-status" :class="coverageClass(selectedCase.coverage)">{{
            coverage(selectedCase.coverage)
          }}</span>
        </div>
        <div v-for="point in selectedCase.points" :key="point.rule_id" class="point mq-inset">
          <div>
            <strong>{{ point.rule_name }}</strong>
            <p>
              <span class="mq-mono">{{ point.rule_id }}</span> · {{ point.status }} ·
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
        </div>
      </template>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
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
// 覆盖状态只做展示映射：已核验保持中性，分类未知为warning，结果不可用为danger
function coverageClass(value: string) {
  return value === 'unknown'
    ? 'mq-status--warning'
    : value === 'unavailable'
      ? 'mq-status--danger'
      : ''
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
