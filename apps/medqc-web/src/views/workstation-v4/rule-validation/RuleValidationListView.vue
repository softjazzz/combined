<template>
  <main
    class="mq-page rule-validation-page"
    data-testid="rule-validation-list"
  >
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">规则 · 规则验收</span>
        <h1 class="mq-page-title">
          规则验收
        </h1>
      </div>
      <div class="mq-page-head__actions">
        <div
          class="mq-segmented"
          role="tablist"
          aria-label="规则范围"
        >
          <button
            v-for="tab in scopeTabs"
            :key="tab.key"
            type="button"
            role="tab"
            class="mq-segmented__item"
            :class="{ 'is-active': scope === tab.key }"
            :aria-selected="scope === tab.key"
            :data-testid="`scope-${tab.key}`"
            @click="scope = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>
    </header>

    <a-alert
      v-if="error"
      type="error"
      :message="error"
      show-icon
    />

    <section class="rv-hero">
      <div class="rv-hero__copy">
        <span class="rv-hero__eyebrow">泸县0609规则集 · luxian_0609_qc_v1</span>
        <strong class="rv-hero__title">{{ pendingCount }} 条规则待验收</strong>
        <p>
          准备测试病例并标注人工预期 → 运行 → 逐例核对证据与建议 → 验收结论与批准。批准后生成发布单，由开发修改规则目录并随版本上线；平台不直接改变执行范围。
        </p>
      </div>
      <div class="rv-hero__stats">
        <div>
          <span>已批准待发布</span>
          <b>{{ stageCount(['approved_pending_release']) }}</b>
        </div>
        <div>
          <span>测试病例</span>
          <b>{{ totalCases }}</b>
        </div>
      </div>
    </section>

    <section class="rv-metrics">
      <article
        v-for="metric in metrics"
        :key="metric.label"
        class="mq-card rv-metric"
      >
        <div class="rv-metric__head">
          <span>{{ metric.label }}</span>
          <span :class="statusClass(metric.tone)">{{ metric.tag }}</span>
        </div>
        <b>{{ metric.value }}</b>
        <small>{{ metric.desc }}</small>
      </article>
    </section>

    <section class="mq-card mq-card--padded rv-table-card">
      <div class="rv-toolbar">
        <div
          class="rv-chips"
          role="group"
          aria-label="规则族"
        >
          <button
            v-for="family in families"
            :key="family"
            type="button"
            class="rv-chip"
            :class="{ 'is-active': familyFilter === family }"
            @click="familyFilter = family"
          >
            {{ family || '全部规则族' }}
          </button>
        </div>
        <a-input
          v-model:value="keyword"
          allow-clear
          aria-label="搜索规则"
          placeholder="搜索编号或规则名称"
          class="rv-search"
        />
      </div>
      <a-spin :spinning="loading">
        <div class="rv-scroll">
          <table class="mq-table rv-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>规则</th>
                <th>阶段</th>
                <th>测试病例</th>
                <th>覆盖（合/不/适/缺）</th>
                <th>最近运行</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in visibleRows"
                :key="row.rule_id"
                data-testid="rule-row"
              >
                <td><span class="mq-mono">{{ row.rule_id }}</span></td>
                <td>
                  <div class="rv-strong">
                    {{ row.name }}
                  </div>
                  <small class="rv-muted">{{ row.source_document }}{{ row.impact ? ` · ${row.impact.label}` : '' }}</small>
                </td>
                <td><span :class="statusClass(STAGES[row.stage].tone)">{{ STAGES[row.stage].label }}</span></td>
                <td>
                  <div>{{ row.case_count }} 例</div>
                  <small class="rv-muted">{{ caseNote(row) }}</small>
                </td>
                <td>
                  <div
                    class="rv-dots"
                    :aria-label="coverageLabel(row)"
                  >
                    <span
                      v-for="status in EXPECTED_STATUSES"
                      :key="status"
                      class="rv-dot"
                      :class="{ 'is-on': covered(row, status) }"
                      :title="STATUS[status].label"
                    />
                    <small class="rv-muted">{{ row.coverage.gaps.length ? `缺 ${row.coverage.gaps.length} 类` : '4/4' }}</small>
                  </div>
                </td>
                <td>
                  <template v-if="row.latest_run">
                    <div>{{ formatTime(row.latest_run.created_at) }}</div>
                    <small class="rv-muted">{{ buildLabel(row.latest_run) }}</small>
                  </template>
                  <span
                    v-else
                    class="rv-muted"
                  >尚未运行</span>
                </td>
                <td class="rv-right">
                  <router-link
                    :to="detailLink(row.rule_id)"
                    class="rv-link"
                  >
                    进入验收
                  </router-link>
                </td>
              </tr>
              <tr v-if="!loading && !visibleRows.length">
                <td
                  colspan="7"
                  class="rv-empty"
                >
                  {{ scope === 'pending' ? '当前没有待验收规则' : '没有符合条件的规则' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </a-spin>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { listValidationRules } from '@/services/rule-validation-service'
import type { ExpectedStatus, RuleListItem, ValidationStage } from '@/services/rule-validation-service'
import { EXPECTED_STATUSES, STAGES, STATUS, buildLabel, formatTime, statusClass } from './presentation'
import type { StatusTone } from './presentation'

type Scope = 'pending' | 'released' | 'all'
const scopeTabs: { key: Scope; label: string }[] = [
  { key: 'pending', label: '待验收' },
  { key: 'released', label: '已上线' },
  { key: 'all', label: '全部' },
]

const rows = ref<RuleListItem[]>([])
const loading = ref(false)
const error = ref('')
const scope = ref<Scope>('pending')
const familyFilter = ref('')
const keyword = ref('')

const pendingRows = computed(() => rows.value.filter((r) => r.release_scope === 'acceptance_only'))
const pendingCount = computed(() => pendingRows.value.length)
const totalCases = computed(() => pendingRows.value.reduce((sum, r) => sum + r.case_count, 0))
const scopedRows = computed(() => {
  if (scope.value === 'pending') return pendingRows.value
  if (scope.value === 'released') return rows.value.filter((r) => r.release_scope === 'default')
  return rows.value
})
const families = computed(() => ['', ...new Set(scopedRows.value.map((r) => r.source_document))])
const visibleRows = computed(() => {
  const word = keyword.value.trim().toUpperCase()
  return scopedRows.value.filter(
    (r) =>
      (!familyFilter.value || r.source_document === familyFilter.value) &&
      (!word || r.rule_id.toUpperCase().includes(word) || r.name.toUpperCase().includes(word)),
  )
})

function stageCount(stages: ValidationStage[]) {
  return pendingRows.value.filter((r) => stages.includes(r.stage)).length
}
const metrics = computed<{ label: string; tag: string; tone: StatusTone; value: number; desc: string }[]>(() => [
  { label: '待准备', tag: '缺病例或未运行', tone: '', value: stageCount(['preparing', 'ready_to_run']), desc: '关联测试病例并标注预期后运行' },
  { label: '验证与复核中', tag: '进行中', tone: 'info', value: stageCount(['running', 'reviewing', 'pending_conclusion']), desc: '运行中或逐例核对未完成' },
  { label: '待批准', tag: '待批准', tone: 'warning', value: stageCount(['pending_approval']), desc: '验收结论已通过，等待批准' },
  { label: '验收不通过', tag: '需修正', tone: 'danger', value: stageCount(['rejected']), desc: '修正规则后须用新病例重新验收' },
])

function covered(row: RuleListItem, status: ExpectedStatus) {
  return !row.coverage.gaps.includes(status)
}
function coverageLabel(row: RuleListItem) {
  return EXPECTED_STATUSES.map((s) => `${STATUS[s].label}${covered(row, s) ? '有' : '缺'}`).join('，')
}
function caseNote(row: RuleListItem) {
  const real = EXPECTED_STATUSES.reduce((sum, s) => sum + row.coverage.counts[s].real_copy, 0)
  if (!row.case_count) return '尚未关联'
  if (!real) return '全部为合成病例'
  return `真实副本 ${real} · 验收集 ${row.coverage.acceptance_cases}`
}
function detailLink(ruleId: string) {
  return { name: 'WorkstationV4RuleValidationDetail', params: { ruleId } }
}

async function load() {
  loading.value = true
  error.value = ''
  const response = await listValidationRules(scope.value !== 'pending')
  loading.value = false
  if (!response.success) {
    error.value = response.error || '规则验收列表加载失败'
    return
  }
  rows.value = response.data.items
}

watch(scope, () => {
  familyFilter.value = ''
  void load()
})
onMounted(load)
</script>

<style scoped src="./styles/rule-validation.css"></style>
