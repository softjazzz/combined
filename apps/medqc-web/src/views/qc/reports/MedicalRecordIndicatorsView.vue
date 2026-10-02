<template>
  <main class="report-page indicator-page">
    <header class="page-head">
      <div>
        <h1>病案管理 27 项指标</h1>
        <p>国家口径逐项展示；缺少权威来源的指标明确标记为不可计算。</p>
      </div>
      <div class="head-actions">
        <button class="secondary" type="button" :disabled="loading" @click="loadReport">
          刷新
        </button>
        <button
          class="primary"
          type="button"
          :disabled="!report || exporting"
          @click="exportReport"
        >
          导出指标清单
        </button>
      </div>
    </header>

    <section class="filters" aria-label="报表筛选">
      <div class="field">
        <label for="indicator-from">出院日期起</label>
        <input id="indicator-from" v-model="filters.discharged_from" type="date" />
      </div>
      <div class="field">
        <label for="indicator-to">出院日期止</label>
        <input id="indicator-to" v-model="filters.discharged_to" type="date" />
      </div>
      <div class="field">
        <label for="indicator-department">科室</label>
        <input id="indicator-department" v-model.trim="filters.department" placeholder="全部科室" />
      </div>
      <div class="field">
        <label for="indicator-doctor">医生</label>
        <input id="indicator-doctor" v-model.trim="filters.doctor" placeholder="全部医生" />
      </div>
      <button class="primary" type="button" :disabled="loading" @click="loadReport">查询</button>
      <button class="secondary" type="button" :disabled="loading" @click="resetFilters">
        重置
      </button>
    </section>

    <div v-if="loading" class="status">正在读取病案管理指标...</div>
    <div v-else-if="error" class="status error">
      {{ error }}
    </div>
    <template v-else-if="report">
      <section class="metrics">
        <article class="metric">
          <span>指标总数</span><strong>{{ report.summary.indicator_total }}</strong
          ><small>国家 2021 年版</small>
        </article>
        <article class="metric">
          <span>已接真实来源</span><strong>{{ report.summary.partial_total }}</strong
          ><small>仅展示已核实子集率</small>
        </article>
        <article class="metric">
          <span>阻塞指标</span><strong>{{ report.summary.blocked_total }}</strong
          ><small>缺失源逐项列明</small>
        </article>
        <article class="metric">
          <span>出院队列病例</span><strong>{{ report.summary.cohort_total }}</strong
          ><small>三坐标去重</small>
        </article>
      </section>

      <p class="notice scope-notice">
        {{ report.scope.description }}；归档状态未核验。官方率不会用已核实子集率替代。
      </p>

      <section>
        <div class="section-head">
          <h2>指标口径与计算状态</h2>
        </div>
        <div class="table-panel">
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>指标</th>
                  <th>计算状态</th>
                  <th>公式与数据源</th>
                  <th>已核实结果</th>
                  <th>缺口</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in report.indicators" :key="item.code">
                  <td>
                    <strong>{{ item.code }}</strong
                    ><small>{{ item.name }}</small>
                  </td>
                  <td>
                    <span class="state-tag" :class="item.calculation_status">{{
                      statusLabel(item.calculation_status)
                    }}</span>
                  </td>
                  <td class="contract-cell">
                    <strong>{{ item.formula }}</strong
                    ><small>{{ item.data_source }}</small>
                  </td>
                  <td>
                    <strong>{{ rateText(item.verified_subset_rate) }}</strong>
                    <small
                      >分子 {{ countText(item.numerator_total) }} / 已核实分母
                      {{ countText(item.eligible_total) }} / 未知 {{ item.unknown_total }}</small
                    >
                  </td>
                  <td class="gap-cell">
                    {{ item.blocker || '无' }}
                  </td>
                  <td>
                    <button class="link" type="button" @click="selectIndicator(item)">
                      查看下钻
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section v-if="selected" class="details">
        <div class="section-head">
          <div>
            <h2>{{ selected.code }} {{ selected.name }}</h2>
            <p class="detail-note">官方率：不可计算；下方仅为已核实子集。</p>
          </div>
          <div class="segmented">
            <button
              type="button"
              :class="{ active: dimension === 'department' }"
              @click="setDimension('department')"
            >
              按科室
            </button>
            <button
              type="button"
              :class="{ active: dimension === 'doctor' }"
              @click="setDimension('doctor')"
            >
              按医生
            </button>
          </div>
        </div>
        <div class="distribution-grid">
          <article v-for="item in breakdown" :key="item.name" class="data-panel compact-panel">
            <h3>{{ item.name }}</h3>
            <div class="data-row">
              <span>已核实子集率</span><strong>{{ rateText(item.verified_subset_rate) }}</strong>
            </div>
            <div class="data-row">
              <span>已核实 / 未知</span
              ><strong>{{ countText(item.eligible_total) }} / {{ item.unknown_total }}</strong>
            </div>
          </article>
          <div v-if="!breakdown.length" class="empty">暂无维度数据</div>
        </div>

        <div class="table-panel case-panel">
          <div class="table-head">
            <h3>病例明细</h3>
            <select v-model="caseState" aria-label="病例状态" @change="loadCases(1)">
              <option value="">全部状态</option>
              <option value="compliant">符合</option>
              <option value="non_compliant">不符合</option>
              <option value="not_applicable">不适用</option>
              <option value="unknown">未知/未执行</option>
            </select>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>病例</th>
                  <th>科室/医生</th>
                  <th>状态</th>
                  <th>来源值</th>
                  <th>质控完成时间</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in cases"
                  :key="`${item.institute_id}/${item.patient_id}/${item.visit_id}`"
                >
                  <td>
                    <strong>{{ item.patient_name || '未登记姓名' }}</strong
                    ><small
                      >{{ item.institute_id }} / {{ item.patient_id }} / {{ item.visit_id }}</small
                    >
                  </td>
                  <td>{{ item.department }} / {{ item.doctor }}</td>
                  <td>{{ stateLabel(item.state) }}</td>
                  <td>{{ item.source_value || '未知' }}</td>
                  <td>{{ item.qc_completed_at || '未执行' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!cases.length" class="empty">暂无病例</div>
          <div class="pager">
            <button
              class="secondary"
              type="button"
              :disabled="casePage <= 1"
              @click="loadCases(casePage - 1)"
            >
              上一页</button
            ><span>第 {{ casePage }} 页，共 {{ caseTotal }} 例</span
            ><button
              class="secondary"
              type="button"
              :disabled="casePage * 20 >= caseTotal"
              @click="loadCases(casePage + 1)"
            >
              下一页
            </button>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  exportMedicalRecordIndicators,
  getMedicalRecordIndicatorBreakdown,
  getMedicalRecordIndicatorCases,
  getMedicalRecordIndicators,
  type IndicatorDimension,
  type IndicatorState,
  type MedicalRecordIndicator,
  type MedicalRecordIndicatorReport,
  type IndicatorCase,
} from '@/api/medicalRecordIndicators'

const filters = reactive({ department: '', doctor: '', discharged_from: '', discharged_to: '' })
const report = ref<MedicalRecordIndicatorReport | null>(null)
const selected = ref<MedicalRecordIndicator | null>(null)
const breakdown = ref<Array<MedicalRecordIndicator & { name: string }>>([])
const cases = ref<IndicatorCase[]>([])
const dimension = ref<IndicatorDimension>('department')
const caseState = ref<IndicatorState | ''>('')
const casePage = ref(1)
const caseTotal = ref(0)
const loading = ref(false)
const exporting = ref(false)
const error = ref('')

function queryFilters() {
  return {
    department: filters.department || undefined,
    doctor: filters.doctor || undefined,
    discharged_from: filters.discharged_from || undefined,
    discharged_to: filters.discharged_to || undefined,
  }
}
function statusLabel(status: string) {
  return (
    (
      { partial: '部分可计算', blocked: '缺来源', unavailable: '当前不可计算' } as Record<
        string,
        string
      >
    )[status] || '未知'
  )
}
function stateLabel(state: IndicatorState) {
  return {
    compliant: '符合',
    non_compliant: '不符合',
    not_applicable: '不适用',
    unknown: '未知/未执行',
  }[state]
}
function rateText(value: number | null) {
  return value === null ? '不可计算' : `${value.toFixed(2)}%`
}
function countText(value: number | null) {
  return value === null ? '未知' : String(value)
}

async function loadReport() {
  loading.value = true
  error.value = ''
  const result = await getMedicalRecordIndicators(queryFilters())
  loading.value = false
  if (!result.success || !result.data) {
    error.value = result.message || '病案管理指标报表暂不可用'
    return
  }
  report.value = result.data
  const preferred =
    result.data.indicators.find((item) => item.calculation_status === 'partial') ||
    result.data.indicators[0]
  if (preferred) await selectIndicator(preferred)
}
async function selectIndicator(item: MedicalRecordIndicator) {
  selected.value = item
  caseState.value = ''
  await Promise.all([loadBreakdown(), loadCases(1)])
}
async function setDimension(value: IndicatorDimension) {
  dimension.value = value
  await loadBreakdown()
}
async function loadBreakdown() {
  if (!selected.value) return
  const result = await getMedicalRecordIndicatorBreakdown(
    queryFilters(),
    selected.value.code,
    dimension.value,
  )
  breakdown.value = result.success && result.data ? result.data.items : []
}
async function loadCases(page: number) {
  if (!selected.value) return
  const result = await getMedicalRecordIndicatorCases(
    queryFilters(),
    selected.value.code,
    caseState.value || undefined,
    page,
  )
  if (result.success && result.data) {
    cases.value = result.data.items
    casePage.value = result.data.page
    caseTotal.value = result.data.total
  } else {
    cases.value = []
    caseTotal.value = 0
  }
}
function resetFilters() {
  filters.department = ''
  filters.doctor = ''
  filters.discharged_from = ''
  filters.discharged_to = ''
  void loadReport()
}
async function exportReport() {
  exporting.value = true
  const result = await exportMedicalRecordIndicators(queryFilters())
  exporting.value = false
  if (!result.success || !result.data) {
    error.value = result.message || '导出失败'
    return
  }
  const url = URL.createObjectURL(result.data)
  const link = document.createElement('a')
  link.href = url
  link.download = '病案管理27项指标.csv'
  link.click()
  URL.revokeObjectURL(url)
}
onMounted(loadReport)
</script>

<style src="./reportPage.css"></style>
<style scoped>
.contract-cell {
  min-width: 360px;
  white-space: normal;
}
.gap-cell {
  min-width: 260px;
  max-width: 380px;
  white-space: normal;
  color: #62666d;
}
.state-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: #f1f3f5;
  color: #62666d;
}
.state-tag.partial {
  background: #eaf2ff;
  color: #007aff;
}
.state-tag.blocked,
.state-tag.unavailable {
  background: #fff4e5;
  color: #9a5b00;
}
.scope-notice {
  margin: 0 0 22px;
}
.detail-note {
  margin: 4px 0 0;
  color: #7e858d;
}
.compact-panel {
  min-height: 112px;
}
.case-panel {
  margin-top: 16px;
}
.table-head select {
  height: 34px;
  border: 1px solid #d9dee5;
  border-radius: 8px;
  padding: 0 8px;
  background: white;
}
</style>
