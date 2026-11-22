<template>
  <section
    class="qc-result-analysis"
    aria-label="质控结果分析"
  >
    <header class="qc-result-analysis__command-bar">
      <div
        class="qc-result-analysis__filters"
        aria-label="结果分析筛选"
      >
        <label>
          <span>质控完成日期</span>
          <input
            v-model="completedFrom"
            type="date"
            aria-label="质控完成开始日期"
          >
        </label>
        <span class="qc-result-analysis__date-separator">至</span>
        <label class="qc-result-analysis__date-end">
          <span class="sr-only">质控完成结束日期</span>
          <input
            v-model="completedTo"
            type="date"
            aria-label="质控完成结束日期"
          >
        </label>
        <label>
          <span>科室</span>
          <select
            v-model="department"
            aria-label="分析科室筛选"
          >
            <option value="">全部科室</option>
            <option
              v-for="item in departmentOptions"
              :key="item"
              :value="item"
            >{{ item }}</option>
          </select>
        </label>
        <label>
          <span>主治医师</span>
          <select
            v-model="doctor"
            aria-label="分析主治医师筛选"
          >
            <option value="">全部医师</option>
            <option
              v-for="item in physicianOptions"
              :key="item"
              :value="item"
            >{{ item }}</option>
          </select>
        </label>
        <button
          type="button"
          class="qc-result-analysis__query"
          :disabled="loading"
          @click="void queryAnalysis()"
        >
          <Search
            :size="15"
            aria-hidden="true"
          />
          查询
        </button>
        <button
          type="button"
          class="qc-result-analysis__reset"
          :disabled="loading"
          @click="void resetFilters()"
        >
          <RotateCcw
            :size="14"
            aria-hidden="true"
          />
          重置
        </button>
      </div>
    </header>

    <nav
      class="qc-result-analysis__status-nav"
      aria-label="按质控结论筛选"
    >
      <button
        v-for="item in statusNavigator"
        :key="item.key"
        type="button"
        :class="[
          'qc-result-analysis__status-button',
          `is-${item.key}`,
          { 'is-active': activeStatus === item.key },
        ]"
        :aria-pressed="activeStatus === item.key"
        @click="void selectStatus(item.key)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ loading || error ? '—' : item.count }}</strong>
      </button>
    </nav>

    <section
      v-if="error"
      class="qc-result-analysis__state qc-result-analysis__state--error"
      role="status"
    >
      <div>
        <strong>结果分析暂时无法加载</strong>
        <span>{{ error }}</span>
      </div>
      <button
        type="button"
        @click="void queryAnalysis()"
      >
        重试
      </button>
    </section>
    <section
      v-else-if="loading"
      class="qc-result-analysis__state"
      aria-live="polite"
    >
      <LoaderCircle
        :size="22"
        class="qc-result-analysis__spin"
        aria-hidden="true"
      />
      <div>
        <strong>正在汇总最新质控结果</strong>
        <span>只读取当前范围内已交付的 Canonical 结果。</span>
      </div>
    </section>

    <template v-else-if="payload">
      <section
        class="qc-result-analysis__summary"
        aria-label="当前分析范围"
      >
        <span><strong>{{ payload.kpis.scoped_record_total }}</strong> 份纳入病历</span>
        <i aria-hidden="true" />
        <span><strong>{{ payload.kpis.ready_record_total }}</strong> 份已完成质控</span>
        <i aria-hidden="true" />
        <span>当前范围：{{ carePhaseLabel }}</span>
        <span
          v-if="department"
          class="qc-result-analysis__scope-chip"
        >科室：{{ department }}</span>
        <span
          v-if="doctor"
          class="qc-result-analysis__scope-chip"
        >医师：{{ doctor }}</span>
      </section>

      <div class="qc-result-analysis__content-grid">
        <article class="qc-result-analysis__rules-panel">
          <header class="qc-result-analysis__panel-heading">
            <div>
              <span>质控点 → 科室 / 医师 → 病历</span>
              <h2>{{ selectedRule ? '已筛选质控点' : '按质控点规则查看' }}</h2>
            </div>
            <button
              v-if="selectedRule"
              type="button"
              class="qc-result-analysis__clear-rule"
              @click="void clearRule()"
            >
              清除质控点
            </button>
          </header>

          <div
            v-if="payload.rule_distribution.length"
            class="qc-result-analysis__rule-table-wrap"
          >
            <table class="qc-result-analysis__rule-table">
              <thead>
                <tr>
                  <th scope="col">
                    质控点
                  </th>
                  <th scope="col">
                    确定问题
                  </th>
                  <th scope="col">
                    资料待核实
                  </th>
                  <th scope="col">
                    待判断
                  </th>
                  <th scope="col">
                    已核对
                  </th>
                  <th
                    scope="col"
                    aria-label="展开科室"
                  />
                </tr>
              </thead>
              <tbody>
                <template
                  v-for="rule in payload.rule_distribution"
                  :key="rule.rule_id"
                >
                  <tr
                    :class="{ 'is-selected': selectedRuleId === rule.rule_id }"
                    @click="void selectRule(rule.rule_id)"
                  >
                    <td>
                      <span class="qc-result-analysis__rule-code">{{ rule.rule_id }}</span>
                      <strong>{{ rule.rule_name }}</strong>
                    </td>
                    <td>
                      <span class="qc-result-analysis__count is-danger">{{
                        rule.non_compliant_count
                      }}</span>
                    </td>
                    <td>
                      <span class="qc-result-analysis__count is-warning">{{
                        rule.data_gap_count
                      }}</span>
                    </td>
                    <td>
                      <span class="qc-result-analysis__count is-neutral">{{
                        rule.uncertain_count
                      }}</span>
                    </td>
                    <td>{{ rule.evaluated_count }}</td>
                    <td>
                      <button
                        type="button"
                        class="qc-result-analysis__expand"
                        :aria-label="`展开${rule.rule_id}的科室分布`"
                        :aria-expanded="expandedRuleId === rule.rule_id"
                        @click.stop="toggleExpandedRule(rule.rule_id)"
                      >
                        <ChevronDown
                          v-if="expandedRuleId === rule.rule_id"
                          :size="16"
                          aria-hidden="true"
                        />
                        <ChevronRight
                          v-else
                          :size="16"
                          aria-hidden="true"
                        />
                      </button>
                    </td>
                  </tr>
                  <tr
                    v-if="expandedRuleId === rule.rule_id"
                    class="qc-result-analysis__department-row"
                  >
                    <td colspan="6">
                      <div
                        v-if="rule.department_distribution.length"
                        class="qc-result-analysis__department-list"
                      >
                        <button
                          v-for="departmentItem in rule.department_distribution"
                          :key="departmentItem.department"
                          type="button"
                          @click="void selectDepartment(departmentItem.department)"
                        >
                          <span>{{ departmentItem.department }}</span>
                          <small>{{ departmentItem.record_total }} 份病历</small>
                          <strong>
                            <em v-if="departmentItem.non_compliant_count">确定 {{ departmentItem.non_compliant_count }}</em>
                            <em v-if="departmentItem.data_gap_count">待核实 {{ departmentItem.data_gap_count }}</em>
                            <em v-if="departmentItem.uncertain_count">待判断 {{ departmentItem.uncertain_count }}</em>
                            <template
                              v-if="
                                !departmentItem.non_compliant_count &&
                                  !departmentItem.data_gap_count &&
                                  !departmentItem.uncertain_count
                              "
                            >无重点问题</template>
                          </strong>
                        </button>
                      </div>
                      <p v-else>
                        当前筛选下没有可归属的科室结果。
                      </p>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <div
            v-else
            class="qc-result-analysis__empty"
          >
            当前筛选下暂无可交付的质控结论。
          </div>
        </article>

        <aside
          class="qc-result-analysis__insights"
          aria-label="筛选结果概览"
        >
          <section>
            <header class="qc-result-analysis__panel-heading">
              <div>
                <span>筛选结果概览</span>
                <h2>结论结构</h2>
              </div>
              <strong>{{ totalStatusCount }} 条</strong>
            </header>
            <ul class="qc-result-analysis__status-list">
              <li
                v-for="item in visibleStatusItems"
                :key="item.key"
              >
                <span :class="`is-${item.key}`" />
                <strong>{{ item.label }}</strong>
                <i><b :style="{ width: `${item.percent}%` }" /></i>
                <em>{{ item.count }}</em>
              </li>
            </ul>
          </section>
          <section>
            <header class="qc-result-analysis__panel-heading">
              <div>
                <span>按当前筛选统计</span>
                <h2>主治医师 Top 5</h2>
              </div>
              <span class="qc-result-analysis__panel-note">点击筛选</span>
            </header>
            <ol
              v-if="topPhysicians.length"
              class="qc-result-analysis__physician-list"
            >
              <li
                v-for="(item, index) in topPhysicians"
                :key="item.physician"
              >
                <button
                  type="button"
                  @click="void selectPhysician(item.physician)"
                >
                  <span>{{ String(index + 1).padStart(2, '0') }}</span>
                  <strong>{{ item.physician }}</strong>
                  <small>
                    <em v-if="item.non_compliant_count">确定 {{ item.non_compliant_count }}</em>
                    <em v-if="item.data_gap_count">待核实 {{ item.data_gap_count }}</em>
                    <em v-if="item.uncertain_count">待判断 {{ item.uncertain_count }}</em>
                    <template
                      v-if="
                        !item.non_compliant_count && !item.data_gap_count && !item.uncertain_count
                      "
                    >已核对 {{ item.record_total }}</template>
                  </small>
                </button>
              </li>
            </ol>
            <p
              v-else
              class="qc-result-analysis__empty-inline"
            >
              暂无可归属的主治医师结果。
            </p>
          </section>
        </aside>
      </div>

      <section class="qc-result-analysis__drilldown">
        <header class="qc-result-analysis__panel-heading">
          <div>
            <span>病历下钻</span>
            <h2>
              {{
                selectedRule
                  ? `${selectedRule.rule_id} · ${selectedRule.rule_name}`
                  : '请选择一个质控点'
              }}
            </h2>
          </div>
          <span
            v-if="selectedRule"
            class="qc-result-analysis__panel-note"
          >{{ payload.record_page.total }} 份匹配病历</span>
        </header>
        <div
          v-if="!selectedRule"
          class="qc-result-analysis__drilldown-empty"
        >
          请在上方选择一个质控点，查看对应科室、医师和病历结果。
        </div>
        <div
          v-else-if="payload.record_page.items.length"
          class="qc-result-analysis__record-table-wrap"
        >
          <table class="qc-result-analysis__record-table">
            <thead>
              <tr>
                <th scope="col">
                  患者 / 住院号
                </th>
                <th scope="col">
                  科室
                </th>
                <th scope="col">
                  主治医师
                </th>
                <th scope="col">
                  本项结论
                </th>
                <th scope="col">
                  最近质控
                </th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="record in payload.record_page.items"
                :key="record.record_key"
              >
                <td>
                  <strong>{{ record.patient_name || '患者信息待核实' }}</strong>
                  <span>住院号 {{ record.visit_id }}</span>
                </td>
                <td>{{ record.department }}</td>
                <td>{{ record.attending_physician }}</td>
                <td>
                  <span :class="['qc-result-analysis__result-tag', `is-${record.status}`]">{{
                    statusLabel(record.status)
                  }}</span>
                </td>
                <td>{{ formatQcCompletedAt(record.completed_at) }}</td>
                <td>
                  <button
                    type="button"
                    class="qc-result-analysis__open"
                    @click="emit('open-result', record)"
                  >
                    查看结果 <ExternalLink
                      :size="14"
                      aria-hidden="true"
                    />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-else
          class="qc-result-analysis__drilldown-empty"
        >
          当前筛选下没有对应病历。
        </div>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  LoaderCircle,
  RotateCcw,
  Search,
} from 'lucide-vue-next'
import {
  getLuxianQcResultAnalysis,
  type LuxianQcAnalysisCarePhase,
  type LuxianQcAnalysisRecordItem,
  type LuxianQcAnalysisStatus,
  type LuxianQcResultAnalysisPayload,
} from '@/services/luxian-qc-result-analysis-service'
import { QC_RESULT_STATUS_LABELS } from '../../utils/qcResultStatusLabels'
import { formatQcCompletedAt } from './latestQcSummaryPresentation'

const props = defineProps<{ carePhase: LuxianQcAnalysisCarePhase }>()
const emit = defineEmits<{ (event: 'open-result', record: LuxianQcAnalysisRecordItem): void }>()

type StatusNavigatorKey = 'all' | LuxianQcAnalysisStatus

const STATUS_META: Array<{ key: LuxianQcAnalysisStatus; label: string }> = [
  { key: 'non_compliant', label: QC_RESULT_STATUS_LABELS.non_compliant },
  { key: 'data_gap', label: QC_RESULT_STATUS_LABELS.data_gap },
  { key: 'uncertain', label: QC_RESULT_STATUS_LABELS.uncertain },
  { key: 'compliant', label: '合规' },
  { key: 'not_applicable', label: '不适用' },
  { key: 'not_executed', label: '未执行' },
]

const loading = ref(false)
const error = ref('')
const payload = ref<LuxianQcResultAnalysisPayload | null>(null)
const completedFrom = ref('')
const completedTo = ref('')
const department = ref('')
const doctor = ref('')
const activeStatus = ref<StatusNavigatorKey>('all')
const selectedRuleId = ref('')
const expandedRuleId = ref('')
let activeRequest = 0

const carePhaseLabel = computed(() => (props.carePhase === 'inpatient' ? '在院病历' : '已出院病历'))
const selectedRule = computed(() => payload.value?.selected_rule || null)
const departmentOptions = computed(() =>
  [
    ...new Set(
      payload.value?.rule_distribution.flatMap((item) =>
        item.department_distribution.map((row) => row.department),
      ) || [],
    ),
  ].sort((left, right) => left.localeCompare(right, 'zh-CN')),
)
const physicianOptions = computed(() =>
  (payload.value?.physician_distribution || [])
    .map((item) => item.physician)
    .filter((item) => item && item !== '未登记主治医师')
    .sort((left, right) => left.localeCompare(right, 'zh-CN')),
)
const totalStatusCount = computed(() =>
  (payload.value?.status_distribution || []).reduce(
    (total, item) => total + Number(item.count || 0),
    0,
  ),
)
const statusNavigator = computed(() => {
  const counts = new Map(
    (payload.value?.status_distribution || []).map((item) => [item.status, item.count]),
  )
  return [
    { key: 'all' as const, label: '全部', count: totalStatusCount.value },
    ...STATUS_META.map((item) => ({ ...item, count: Number(counts.get(item.key) || 0) })),
  ]
})
const visibleStatusItems = computed(() =>
  statusNavigator.value
    .filter((item) => item.key !== 'all' && item.count > 0)
    .map((item) => ({
      ...item,
      percent: totalStatusCount.value
        ? Math.max((item.count / totalStatusCount.value) * 100, 3)
        : 0,
    })),
)
const topPhysicians = computed(() => (payload.value?.physician_distribution || []).slice(0, 5))

function statusLabel(status: LuxianQcAnalysisStatus): string {
  return STATUS_META.find((item) => item.key === status)?.label || '结果待核实'
}

async function queryAnalysis(options: { resetRule?: boolean } = {}) {
  if (options.resetRule) selectedRuleId.value = ''
  const request = ++activeRequest
  loading.value = true
  error.value = ''
  try {
    const nextPayload = await getLuxianQcResultAnalysis({
      carePhase: props.carePhase,
      department: department.value,
      doctor: doctor.value,
      ruleId: selectedRuleId.value,
      resultStatus: activeStatus.value === 'all' ? undefined : activeStatus.value,
      completedFrom: completedFrom.value,
      completedTo: completedTo.value,
    })
    if (request !== activeRequest) return
    payload.value = nextPayload
    if (selectedRuleId.value && !nextPayload.selected_rule) selectedRuleId.value = ''
    if (
      expandedRuleId.value &&
      !nextPayload.rule_distribution.some((item) => item.rule_id === expandedRuleId.value)
    ) {
      expandedRuleId.value = ''
    }
  } catch (reason) {
    if (request !== activeRequest) return
    error.value = reason instanceof Error ? reason.message : '请稍后重试'
    payload.value = null
  } finally {
    if (request === activeRequest) loading.value = false
  }
}

async function selectStatus(status: StatusNavigatorKey) {
  if (activeStatus.value === status) return
  activeStatus.value = status
  await queryAnalysis()
}

async function selectRule(ruleId: string) {
  selectedRuleId.value = ruleId
  await queryAnalysis()
}

function toggleExpandedRule(ruleId: string) {
  expandedRuleId.value = expandedRuleId.value === ruleId ? '' : ruleId
}

async function clearRule() {
  selectedRuleId.value = ''
  await queryAnalysis()
}

async function selectDepartment(value: string) {
  department.value = value
  await queryAnalysis()
}

async function selectPhysician(value: string) {
  doctor.value = value
  await queryAnalysis()
}

async function resetFilters() {
  completedFrom.value = ''
  completedTo.value = ''
  department.value = ''
  doctor.value = ''
  activeStatus.value = 'all'
  selectedRuleId.value = ''
  expandedRuleId.value = ''
  await queryAnalysis()
}

watch(
  () => props.carePhase,
  async () => {
    await resetFilters()
  },
)

onMounted(() => {
  void queryAnalysis()
})
</script>

<style scoped>
.qc-result-analysis {
  padding: 12px 0 0;
  background: rgba(255, 255, 255, 0.96);
}
.qc-result-analysis__command-bar,
.qc-result-analysis__summary,
.qc-result-analysis__drilldown,
.qc-result-analysis__rules-panel,
.qc-result-analysis__insights {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: #fff;
}
.qc-result-analysis__command-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 0 16px;
  border: 0;
  border-bottom: 1px solid #e7edf4;
  border-radius: 0;
}
.qc-result-analysis__command-copy {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
  color: #0a6cff;
}
.qc-result-analysis__command-copy strong,
.qc-result-analysis h2 {
  color: #1d1d1f;
}
.qc-result-analysis__command-copy strong {
  display: block;
  font-size: 15px;
  line-height: 20px;
}
.qc-result-analysis__command-copy span {
  display: block;
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 18px;
}
.qc-result-analysis__filters {
  display: flex;
  align-items: flex-end;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}
.qc-result-analysis__filters label {
  display: grid;
  gap: 4px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 11px;
  font-weight: 600;
}
.qc-result-analysis__filters input,
.qc-result-analysis__filters select {
  width: 132px;
  height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  padding: 0 8px;
  background: #fff;
  color: rgba(29, 29, 31, 0.82);
  font: inherit;
  font-size: 13px;
}
.qc-result-analysis__filters select {
  width: 136px;
}
.qc-result-analysis__date-separator {
  padding: 0 1px 9px;
  color: rgba(29, 29, 31, 0.4);
  font-size: 12px;
}
.qc-result-analysis__filters button,
.qc-result-analysis__clear-rule,
.qc-result-analysis__open {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border-radius: 8px;
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}
.qc-result-analysis__query {
  height: 34px;
  border: 1px solid #0a6cff;
  padding: 0 11px;
  background: #0a6cff;
  color: #fff;
}
.qc-result-analysis__reset,
.qc-result-analysis__clear-rule {
  height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  padding: 0 10px;
  background: #fff;
  color: rgba(29, 29, 31, 0.72);
}
.qc-result-analysis__filters button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.qc-result-analysis__status-nav {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  margin: 14px 0;
  padding: 4px;
  background: #f3f6fa;
  border-radius: 9px;
  scrollbar-width: thin;
}
.qc-result-analysis__status-button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  border: 1px solid transparent;
  border-radius: 9px;
  padding: 0 11px;
  background: transparent;
  color: rgba(29, 29, 31, 0.64);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.qc-result-analysis__status-button strong {
  min-width: 18px;
  text-align: center;
  color: inherit;
  font-size: 13px;
}
.qc-result-analysis__status-button.is-active {
  border-color: #d5e3f3;
  background: #fff;
  color: #0a6cff;
  box-shadow: 0 1px 3px rgba(25, 49, 80, 0.07);
}
.qc-result-analysis__status-button.is-non_compliant:not(.is-active) {
  color: #59677a;
}
.qc-result-analysis__status-button.is-data_gap:not(.is-active) {
  color: #59677a;
}
.qc-result-analysis__status-button.is-uncertain:not(.is-active) {
  color: #526276;
}
.qc-result-analysis__status-button.is-compliant:not(.is-active) {
  color: #59677a;
}
.qc-result-analysis__status-button:hover {
  color: #0a6cff;
  background: #eaf1f9;
}
.qc-result-analysis__status-button:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: -2px;
}
.qc-result-analysis__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 250px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  color: rgba(29, 29, 31, 0.72);
}
.qc-result-analysis__state strong,
.qc-result-analysis__state span {
  display: block;
}
.qc-result-analysis__state span {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.54);
  font-size: 13px;
}
.qc-result-analysis__state--error {
  justify-content: space-between;
  padding: 0 20px;
}
.qc-result-analysis__state--error button {
  border: 0;
  background: transparent;
  color: #0a6cff;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}
.qc-result-analysis__spin {
  animation: qc-result-analysis-spin 1s linear infinite;
  color: #0a6cff;
}
.qc-result-analysis__summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding: 0 2px;
  border: 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}
.qc-result-analysis__scope-chip {
  padding: 3px 8px;
  border-radius: 5px;
  background: #eff5fc;
  color: #486c94;
}
.qc-result-analysis__rule-table th:not(:first-child),
.qc-result-analysis__rule-table td:not(:first-child) {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.qc-result-analysis__rule-table tbody > tr.is-selected td:first-child {
  box-shadow: inset 3px 0 #0a6cff;
}
.qc-result-analysis__summary strong {
  color: #1d1d1f;
  font-size: 13px;
}
.qc-result-analysis__summary i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(29, 29, 31, 0.3);
}
.qc-result-analysis__content-grid {
  display: grid;
  align-items: start;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
}
.qc-result-analysis__rules-panel,
.qc-result-analysis__insights,
.qc-result-analysis__drilldown {
  overflow: hidden;
}
.qc-result-analysis__panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}
.qc-result-analysis__panel-heading > div > span {
  display: block;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.01em;
}
.qc-result-analysis h2 {
  margin: 3px 0 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
}
.qc-result-analysis__panel-heading > strong {
  color: #0a6cff;
  font-size: 14px;
}
.qc-result-analysis__panel-note {
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  line-height: 18px;
}
.qc-result-analysis__rule-table-wrap,
.qc-result-analysis__record-table-wrap {
  overflow-x: auto;
}
.qc-result-analysis table {
  width: 100%;
  border-collapse: collapse;
}
.qc-result-analysis th {
  padding: 10px 12px;
  background: rgba(245, 245, 247, 0.86);
  color: #637084;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}
.qc-result-analysis td {
  padding: 13px 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
}
.qc-result-analysis__rule-table tbody > tr:not(.qc-result-analysis__department-row) {
  cursor: pointer;
  transition: background 0.2s ease;
}
.qc-result-analysis__rule-table tbody > tr:not(.qc-result-analysis__department-row):hover,
.qc-result-analysis__rule-table tbody > tr.is-selected {
  background: rgba(10, 108, 255, 0.045);
}
.qc-result-analysis__rule-table td:first-child {
  min-width: 260px;
}
.qc-result-analysis__rule-table td:first-child strong {
  display: block;
  margin-top: 3px;
  color: #1d1d1f;
  font-weight: 600;
  line-height: 21px;
}
.qc-result-analysis__rule-code {
  color: #8190a2;
  font-size: 12px;
  font-weight: 400;
}
.qc-result-analysis__count {
  display: inline-flex;
  min-width: 24px;
  justify-content: center;
  font-weight: 700;
}
.qc-result-analysis__count.is-danger {
  color: #b74b50;
}
.qc-result-analysis__count.is-warning {
  color: #667487;
}
.qc-result-analysis__count.is-neutral {
  color: #526276;
}
.qc-result-analysis__expand {
  display: inline-grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #0a6cff;
  cursor: pointer;
}
.qc-result-analysis__expand:hover {
  background: rgba(10, 108, 255, 0.08);
}
.qc-result-analysis__department-row > td {
  padding: 0;
  background: rgba(245, 245, 247, 0.62);
}
.qc-result-analysis__department-list {
  padding: 8px 12px;
}
.qc-result-analysis__department-list button {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) 80px minmax(175px, 1.4fr);
  width: 100%;
  align-items: center;
  gap: 12px;
  border: 0;
  padding: 9px 7px;
  background: transparent;
  color: inherit;
  text-align: left;
  font: inherit;
  cursor: pointer;
}
.qc-result-analysis__department-list button:hover {
  background: rgba(10, 108, 255, 0.055);
}
.qc-result-analysis__department-list small {
  color: rgba(29, 29, 31, 0.48);
  font-size: 11px;
}
.qc-result-analysis__department-list strong {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 600;
}
.qc-result-analysis__department-list em,
.qc-result-analysis__physician-list em {
  font-style: normal;
}
.qc-result-analysis__department-list em,
.qc-result-analysis__physician-list em {
  color: #667487;
}
.qc-result-analysis__department-row p {
  margin: 0;
  padding: 14px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
}
.qc-result-analysis__insights {
  align-self: start;
}
.qc-result-analysis__insights > section + section {
  border-top: 1px solid rgba(0, 0, 0, 0.07);
}
.qc-result-analysis__status-list,
.qc-result-analysis__physician-list {
  margin: 0;
  padding: 10px 16px 16px;
  list-style: none;
}
.qc-result-analysis__status-list li {
  display: grid;
  grid-template-columns: 8px 76px minmax(40px, 1fr) 34px;
  align-items: center;
  gap: 8px;
  min-height: 32px;
}
.qc-result-analysis__status-list li > span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}
.qc-result-analysis__status-list li > span.is-non_compliant {
  background: #b74b50;
}
.qc-result-analysis__status-list li > span.is-data_gap {
  background: #91a4bb;
}
.qc-result-analysis__status-list li > span.is-uncertain {
  background: #64748b;
}
.qc-result-analysis__status-list li > span.is-compliant {
  background: #a7b8c9;
}
.qc-result-analysis__status-list strong {
  color: rgba(29, 29, 31, 0.68);
  font-size: 13px;
  font-weight: 400;
}
.qc-result-analysis__status-list i {
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.06);
}
.qc-result-analysis__status-list b {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #9eb3cc;
}
.qc-result-analysis__status-list li:has(.is-non_compliant) b {
  background: #b74b50;
}
.qc-result-analysis__status-list li:has(.is-data_gap) b {
  background: #91a4bb;
}
.qc-result-analysis__status-list li:has(.is-uncertain) b {
  background: #64748b;
}
.qc-result-analysis__status-list li:has(.is-compliant) b {
  background: #a7b8c9;
}
.qc-result-analysis__status-list em {
  font-variant-numeric: tabular-nums;
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  font-style: normal;
  text-align: right;
}
.qc-result-analysis__physician-list {
  display: grid;
  gap: 1px;
}
.qc-result-analysis__physician-list button {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 2px 8px;
  width: 100%;
  border: 0;
  border-radius: 8px;
  padding: 9px 5px;
  background: transparent;
  color: inherit;
  text-align: left;
  font: inherit;
  cursor: pointer;
}
.qc-result-analysis__physician-list button:hover {
  background: rgba(10, 108, 255, 0.055);
}
.qc-result-analysis__physician-list span {
  grid-row: span 2;
  color: rgba(29, 29, 31, 0.35);
  font-size: 11px;
  font-weight: 700;
}
.qc-result-analysis__physician-list strong {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qc-result-analysis__physician-list small {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
}
.qc-result-analysis__empty,
.qc-result-analysis__empty-inline {
  padding: 26px 16px;
  color: rgba(29, 29, 31, 0.5);
  font-size: 13px;
  text-align: center;
}
.qc-result-analysis__empty-inline {
  margin: 0;
}
.qc-result-analysis__drilldown {
  margin-top: 16px;
}
.qc-result-analysis__drilldown-empty {
  padding: 28px 16px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 13px;
  text-align: center;
}
.qc-result-analysis__record-table td:first-child strong,
.qc-result-analysis__record-table td:first-child span {
  display: block;
}
.qc-result-analysis__record-table td:first-child strong {
  color: #1d1d1f;
  font-weight: 650;
}
.qc-result-analysis__record-table td:first-child span {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.45);
  font-size: 12px;
}
.qc-result-analysis__result-tag {
  display: inline-flex;
  border-radius: 5px;
  padding: 3px 8px;
  background: rgba(148, 163, 184, 0.12);
  color: #526276;
  font-size: 12px;
  font-weight: 500;
}
.qc-result-analysis__result-tag.is-non_compliant {
  background: rgba(239, 68, 68, 0.1);
  color: #b74b50;
}
.qc-result-analysis__result-tag.is-data_gap {
  background: #f1f4f8;
  color: #667487;
}
.qc-result-analysis__result-tag.is-compliant {
  background: #f1f4f8;
  color: #667487;
}
.qc-result-analysis__open {
  border: 0;
  padding: 5px 0;
  background: transparent;
  color: #0a6cff;
  white-space: nowrap;
}
@keyframes qc-result-analysis-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1240px) {
  .qc-result-analysis__command-bar {
    align-items: flex-start;
    flex-direction: column;
  }
  .qc-result-analysis__filters {
    justify-content: flex-start;
  }
  .qc-result-analysis__content-grid {
    grid-template-columns: 1fr;
  }
  .qc-result-analysis__insights {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    display: grid;
  }
  .qc-result-analysis__insights > section + section {
    border-top: 0;
    border-left: 1px solid rgba(0, 0, 0, 0.07);
  }
}
@media (max-width: 780px) {
  .qc-result-analysis {
    padding: 14px;
  }
  .qc-result-analysis__filters {
    width: 100%;
  }
  .qc-result-analysis__filters label {
    flex: 1 1 132px;
  }
  .qc-result-analysis__filters input,
  .qc-result-analysis__filters select {
    width: 100%;
  }
  .qc-result-analysis__date-end {
    flex: 1 1 132px;
  }
  .qc-result-analysis__insights {
    grid-template-columns: 1fr;
  }
  .qc-result-analysis__insights > section + section {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
    border-left: 0;
  }
  .qc-result-analysis__department-list button {
    grid-template-columns: 1fr;
    gap: 3px;
  }
  .qc-result-analysis__rule-table td:first-child {
    min-width: 200px;
  }
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
