<template>
  <main
    class="mq-page rule-validation-page"
    data-testid="rule-validation-detail"
  >
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">
          <router-link :to="{ name: 'WorkstationV4RuleValidation' }">规则验收</router-link>
          <template v-if="detail"> · {{ detail.rule.source_document }}</template>
        </span>
        <h1 class="mq-page-title rv-title">
          <span class="mq-mono">{{ ruleId }}</span>
          <span v-if="detail">{{ detail.rule.name }}</span>
        </h1>
      </div>
      <div class="mq-page-head__actions">
        <span
          v-if="detail"
          :class="statusClass(STAGES[detail.stage].tone)"
          data-testid="rule-stage"
        >{{ STAGES[detail.stage].label }}</span>
        <router-link
          class="mq-btn"
          :to="{ name: 'WorkstationV4RuleValidation' }"
        >
          返回列表
        </router-link>
      </div>
    </header>

    <a-alert
      v-if="error"
      type="error"
      :message="error"
      show-icon
    />

    <a-spin
      :spinning="loading && !detail"
      class="rule-validation-page"
    >
      <template v-if="detail">
        <section
          class="mq-card rv-steps"
          aria-label="验收进度"
        >
          <div
            v-for="(step, i) in steps"
            :key="step.title"
            class="rv-step"
            :class="{ 'is-done': step.state === 'done', 'is-current': step.state === 'current' }"
          >
            <span class="rv-step__no">{{ i + 1 }}</span>
            <div class="rv-step__copy">
              <b>{{ step.title }}</b>
              <small class="rv-muted">{{ step.note }}</small>
            </div>
            <span
              v-if="i < steps.length - 1"
              class="rv-step__line"
            />
          </div>
        </section>

        <section class="rv-grid-2">
          <div class="mq-card mq-card--padded rv-section">
            <h2 class="mq-card__title">
              规则口径
            </h2>
            <div class="mq-soft rv-policy">
              {{ detail.rule.policy_summary || '（规则目录未填写业务口径）' }}
            </div>
            <div class="rv-facts">
              <div class="mq-inset rv-fact">
                <small class="rv-muted">发布范围</small><b>{{ detail.rule.release_scope === 'default' ? '已上线' : '待验收' }}</b>
              </div>
              <div class="mq-inset rv-fact">
                <small class="rv-muted">影响范围</small><b>{{ detail.rule.impact_class || '未声明' }}</b>
              </div>
              <div class="mq-inset rv-fact">
                <small class="rv-muted">规则族</small><b>{{ detail.rule.source_document }}</b>
              </div>
            </div>
            <small class="rv-muted">影响范围（独立判定 / 共享抽取批次 / 修改共享抽取）由代码声明，共享抽取规则需额外做同族回归。</small>
          </div>
          <div class="mq-card mq-card--padded rv-section">
            <div class="mq-card__head">
              <h2 class="mq-card__title">
                覆盖矩阵
              </h2>
              <span class="rv-tag rv-tag--blue">独立验收集 {{ detail.coverage.acceptance_cases }} 例</span>
            </div>
            <div class="rv-scroll">
              <table class="mq-table">
                <thead>
                  <tr>
                    <th>预期状态</th>
                    <th class="rv-num">
                      合成病例
                    </th>
                    <th class="rv-num">
                      真实病例副本
                    </th>
                    <th class="rv-num">
                      合计
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="status in EXPECTED_STATUSES"
                    :key="status"
                  >
                    <td>
                      {{ STATUS[status].label }}
                      <span
                        v-if="detail.coverage.gaps.includes(status)"
                        class="mq-status mq-status--warning"
                      >缺口</span>
                    </td>
                    <td class="rv-num">
                      {{ detail.coverage.counts[status].synthetic }}
                    </td>
                    <td class="rv-num">
                      {{ detail.coverage.counts[status].real_copy }}
                    </td>
                    <td class="rv-num rv-strong">
                      {{ detail.coverage.counts[status].synthetic + detail.coverage.counts[status].real_copy }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <small class="rv-muted">合成病例只验证程序行为，不能替代客户真实病例验收；缺少的类别在验收结论时须逐项说明。</small>
          </div>
        </section>

        <!-- ① 测试病例与预期 -->
        <section class="mq-card mq-card--padded rv-section">
          <div class="mq-card__head">
            <div>
              <div class="rv-section__title">
                <span
                  class="rv-step__no"
                  :class="stepNoClass(0)"
                >1</span>
                <h2 class="mq-card__title">
                  测试病例与预期
                </h2>
              </div>
              <p class="mq-card__desc">
                每个病例按本规则单独标注预期；病例创建后内容与评价时间点固定，需修改请复制为新病例。
              </p>
            </div>
            <div class="mq-page-head__actions">
              <button
                type="button"
                class="mq-btn"
                data-testid="link-case"
                @click="openAnswer(null)"
              >
                关联已有病例
              </button>
              <router-link
                class="mq-btn"
                data-testid="new-case"
                :to="{ name: 'WorkstationV4RuleValidationNewCase', params: { ruleId } }"
              >
                新建测试病例
              </router-link>
            </div>
          </div>
          <div class="rv-scroll">
            <table class="mq-table">
              <thead>
                <tr>
                  <th>病例</th>
                  <th>来源</th>
                  <th>用途</th>
                  <th>评价时间点</th>
                  <th>预期</th>
                  <th>人工依据</th>
                  <th>修订</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in detail.cases"
                  :key="item.item_id"
                  data-testid="case-row"
                >
                  <td class="rv-strong">
                    {{ item.case_title }}
                  </td>
                  <td><span :class="['rv-tag', item.source_kind === 'real_copy' ? 'rv-tag--blue' : '']">{{ SOURCE_KINDS[item.source_kind] }}</span></td>
                  <td>{{ PURPOSES[item.purpose] }}</td>
                  <td>
                    <span
                      v-if="item.evaluation_as_of_date"
                      class="mq-mono"
                    >{{ item.evaluation_as_of_date }}</span>
                    <span
                      v-else
                      class="mq-status mq-status--warning"
                    >未固定</span>
                  </td>
                  <td><span :class="statusClass(STATUS[item.expected_status].tone)">{{ STATUS[item.expected_status].label }}</span></td>
                  <td class="rv-reason">
                    {{ item.human_reason }}
                  </td>
                  <td><span class="mq-mono">r{{ item.answer_revision }}</span></td>
                  <td class="rv-right rv-row-actions">
                    <router-link
                      class="mq-btn"
                      :to="{ name: 'WorkstationV4RuleValidationNewCase', params: { ruleId }, query: { copyFrom: item.item_id } }"
                    >
                      复制
                    </router-link>
                    <button
                      type="button"
                      class="mq-btn"
                      @click="openAnswer(item)"
                    >
                      编辑预期
                    </button>
                  </td>
                </tr>
                <tr v-if="!detail.cases.length">
                  <td
                    colspan="8"
                    class="rv-empty"
                  >
                    还没有关联测试病例。请关联已有病例，或新建测试病例后回到这里标注预期。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- ② 运行验证 -->
        <section class="mq-card mq-card--padded rv-section">
          <div class="mq-card__head">
            <div>
              <div class="rv-section__title">
                <span
                  class="rv-step__no"
                  :class="stepNoClass(1)"
                >2</span>
                <h2 class="mq-card__title">
                  运行验证
                </h2>
              </div>
              <p class="mq-card__desc">
                只运行本规则，走正式执行、保存和读取链路；人工预期不进入任务。新运行会使旧结论和批准失效。
              </p>
            </div>
            <button
              type="button"
              class="mq-btn mq-btn--primary"
              data-testid="start-run"
              :disabled="!detail.cases.length || starting || runInProgress"
              @click="startRun"
            >
              {{ starting ? '正在创建运行…' : runInProgress ? '运行中…' : `运行本规则（${detail.cases.length} 例）` }}
            </button>
          </div>
          <div
            v-if="detail.runs.length"
            class="rv-runs"
          >
            <div
              v-for="(run, i) in detail.runs"
              :key="run.id"
              class="mq-inset rv-run"
              :class="{ 'is-stale': i > 0 }"
            >
              <span :class="statusClass(runState(run, i).tone)">{{ runState(run, i).label }}</span>
              <b>{{ formatTime(run.created_at) }}</b>
              <span>{{ run.cases.length }} 例</span>
              <span class="rv-tag">{{ buildLabel(run) }}</span>
              <span class="rv-run__note">{{ i === 0 ? '当前运行 · 比较与复核基于此次' : '已被后续运行取代' }}</span>
              <span class="mq-mono rv-muted">{{ run.job_id || '—' }}</span>
            </div>
          </div>
          <p
            v-else
            class="rv-muted"
          >
            尚未运行。
          </p>
        </section>

        <!-- ③ 对照复核 -->
        <section class="mq-card mq-card--padded rv-section">
          <div class="mq-card__head">
            <div>
              <div class="rv-section__title">
                <span
                  class="rv-step__no"
                  :class="stepNoClass(2)"
                >3</span>
                <h2 class="mq-card__title">
                  对照复核
                </h2>
              </div>
              <p class="mq-card__desc">
                状态一致只代表结论相同，仍需逐例核对原文、证据和修改建议。
              </p>
            </div>
            <div
              v-if="rows.length"
              class="rv-summary-pills"
            >
              <span class="mq-status mq-status--success">一致 {{ countBy('same') }}</span>
              <span
                v-if="rows.length - countBy('same') - countBy('pending')"
                class="mq-status mq-status--danger"
              >异常 {{ rows.length - countBy('same') - countBy('pending') }}</span>
              <span class="mq-status mq-status--info">已核对 {{ reviewedCount }} / {{ rows.length }}</span>
            </div>
          </div>
          <div
            v-if="rows.length"
            class="rv-scroll"
          >
            <table class="mq-table">
              <thead>
                <tr>
                  <th>病例</th>
                  <th>预期</th>
                  <th>实际</th>
                  <th>比较</th>
                  <th>逐例核对</th>
                  <th>核对意见</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, i) in rows"
                  :key="row.item_id"
                  data-testid="compare-row"
                >
                  <td class="rv-strong">
                    {{ row.case_title }}
                  </td>
                  <td>{{ STATUS[row.expected_status].label }}</td>
                  <td>{{ statusLabel(row.actual_status).label }}</td>
                  <td><span :class="statusClass(COMPARISONS[row.comparison].tone)">{{ COMPARISONS[row.comparison].label }}</span></td>
                  <td>
                    <span :class="statusClass(reviewOf(row.item_id).tone)">{{ reviewOf(row.item_id).label }}</span>
                  </td>
                  <td class="rv-reason">
                    {{ latestReview(row.item_id)?.note || '—' }}
                  </td>
                  <td class="rv-right">
                    <button
                      type="button"
                      class="mq-btn"
                      :disabled="row.comparison === 'pending'"
                      @click="reviewIndex = i"
                    >
                      核对证据
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p
            v-else
            class="rv-muted"
          >
            运行完成后在这里逐例对照。
          </p>
        </section>

        <!-- ④ 验收结论与批准 -->
        <section class="mq-card mq-card--padded rv-conclusion">
          <div class="rv-checks">
            <div class="rv-section__title">
              <span
                class="rv-step__no"
                :class="stepNoClass(3)"
              >4</span>
              <h2 class="mq-card__title">
                验收结论与批准
              </h2>
            </div>
            <p class="mq-card__desc">
              以下条件全部满足才能验收通过；不满足时仍可记录“不通过”。
            </p>
            <div
              v-for="check in checks"
              :key="check.label"
              class="rv-check"
            >
              <span
                class="rv-check__mark"
                :class="`is-${check.state}`"
              >{{ check.state === 'ok' ? '✓' : check.state === 'no' ? '✕' : '!' }}</span>
              <div>
                {{ check.label }}
                <div
                  v-if="check.note"
                  class="rv-muted"
                >
                  {{ check.note }}
                </div>
              </div>
            </div>
            <ul
              v-if="decisions.length"
              class="rv-history"
            >
              <li
                v-for="event in decisions"
                :key="event.id"
              >
                <span :class="statusClass(['accepted', 'approved'].includes(event.decision) ? 'success' : 'danger')">{{ decisionLabel(event) }}</span>
                <span>{{ event.note }}</span>
                <span class="rv-muted">{{ event.actor }} · {{ formatTime(event.created_at) }}</span>
              </li>
            </ul>
          </div>
          <div class="rv-form">
            <label class="mq-field">
              <span class="mq-field__label">验收意见</span>
              <a-textarea
                v-model:value="conclusionNote"
                aria-label="验收意见"
                :rows="4"
                :maxlength="4000"
                placeholder="说明核对范围、结论依据"
              />
            </label>
            <label
              v-if="detail.coverage.gaps.length"
              class="mq-field"
            >
              <span class="mq-field__label">覆盖缺口说明<span class="mq-field__required">*</span></span>
              <a-textarea
                v-model:value="gapAck"
                aria-label="覆盖缺口说明"
                :rows="2"
                :maxlength="4000"
                :placeholder="`缺少：${detail.coverage.gaps.map((s) => STATUS[s].label).join('、')}；逐项说明为何可接受`"
              />
            </label>
            <a-alert
              v-if="actionError"
              type="error"
              :message="actionError"
              show-icon
            />
            <div class="rv-actions">
              <button
                type="button"
                class="mq-btn"
                :disabled="!canConclude || busy || !conclusionNote.trim()"
                @click="conclude('rejected')"
              >
                记录不通过
              </button>
              <button
                type="button"
                class="mq-btn mq-btn--primary"
                data-testid="accept-rule"
                :disabled="!canAccept || busy || !conclusionNote.trim() || (detail.coverage.gaps.length > 0 && !gapAck.trim())"
                @click="conclude('accepted')"
              >
                验收通过
              </button>
            </div>
            <div class="mq-soft rv-approval">
              <div>
                <b>{{ approval?.decision === 'approved' ? '已批准，待开发发布' : '批准上线' }}</b>
                <div class="rv-muted">
                  {{ approval?.decision === 'approved' ? '按发布单修改规则目录并随版本部署，部署后复验' : '验收通过后由批准人审阅，生成发布单交开发修改规则目录' }}
                </div>
              </div>
              <button
                type="button"
                class="mq-btn"
                data-testid="open-approval"
                :disabled="!['pending_approval', 'approved_pending_release'].includes(detail.stage)"
                @click="approvalOpen = true"
              >
                {{ approval?.decision === 'approved' ? '查看发布单' : '批准…' }}
              </button>
            </div>
          </div>
        </section>
      </template>
    </a-spin>

    <CaseAnswerModal
      :open="answerOpen"
      :rule-id="ruleId"
      :current="answerTarget"
      @close="answerOpen = false"
      @saved="onAnswerSaved"
    />
    <CaseReviewDrawer
      v-if="latestRun"
      :run-id="latestRun.id"
      :run-time="formatTime(latestRun.created_at)"
      :rows="rows"
      :index="reviewIndex"
      :reviews="latestRunReviews"
      @close="reviewIndex = -1"
      @navigate="(i) => (reviewIndex = i)"
      @reviewed="load"
    />
    <ApprovalModal
      v-if="detail"
      :open="approvalOpen"
      :detail="detail"
      :approval="approval"
      @close="approvalOpen = false"
      @done="onApprovalDone"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { concludeRule, getValidationRule, startValidationRun } from '@/services/rule-validation-service'
import type { Comparison, RuleDetail, ValidationCase, ValidationEvent, ValidationRun } from '@/services/rule-validation-service'
import CaseAnswerModal from './CaseAnswerModal.vue'
import CaseReviewDrawer from './CaseReviewDrawer.vue'
import ApprovalModal from './ApprovalModal.vue'
import {
  COMPARISONS,
  EXPECTED_STATUSES,
  PURPOSES,
  SOURCE_KINDS,
  STAGES,
  STATUS,
  buildLabel,
  formatTime,
  statusClass,
  statusLabel,
} from './presentation'
import type { Labeled } from './presentation'

const POLL_MS = 5000

const route = useRoute()
const ruleId = computed(() => String(route.params.ruleId || ''))
const detail = ref<RuleDetail | null>(null)
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const busy = ref(false)
const starting = ref(false)
const answerOpen = ref(false)
const answerTarget = ref<ValidationCase | null>(null)
const reviewIndex = ref(-1)
const approvalOpen = ref(false)
const conclusionNote = ref('')
const gapAck = ref('')
let pollTimer: ReturnType<typeof setTimeout> | undefined

const latestRun = computed<ValidationRun | null>(() => detail.value?.runs[0] ?? null)
const rows = computed(() => detail.value?.latest_run_rows ?? [])
const runInProgress = computed(
  () => latestRun.value?.state === 'creating' || rows.value.some((r) => r.comparison === 'pending'),
)
const latestRunReviews = computed(() =>
  (detail.value?.events ?? []).filter((e) => e.kind === 'case_review' && e.run_id === latestRun.value?.id),
)
const decisions = computed(() =>
  (detail.value?.events ?? []).filter((e) => e.kind !== 'case_review' && e.run_id === latestRun.value?.id),
)
const approval = computed<ValidationEvent | null>(
  () => [...decisions.value].reverse().find((e) => e.kind === 'approval') ?? null,
)
const reviewedCount = computed(() => rows.value.filter((r) => latestReview(r.item_id)).length)
const canConclude = computed(() =>
  Boolean(detail.value && ['pending_conclusion', 'reviewing'].includes(detail.value.stage) && !runInProgress.value),
)
const canAccept = computed(
  () => detail.value?.stage === 'pending_conclusion' && detail.value.acceptance_blockers.length === 0,
)

function latestReview(itemId: string): ValidationEvent | undefined {
  return [...latestRunReviews.value].reverse().find((e) => e.item_id === itemId)
}
function reviewOf(itemId: string): Labeled {
  const review = latestReview(itemId)
  if (!review) return { label: '待核对', tone: '' }
  return review.decision === 'confirmed' ? { label: '已确认', tone: 'success' } : { label: '有问题', tone: 'danger' }
}
function countBy(comparison: Comparison) {
  return rows.value.filter((r) => r.comparison === comparison).length
}
function runState(run: ValidationRun, index: number): Labeled {
  if (index > 0) return { label: '已失效', tone: '' }
  if (run.state === 'creation_failed') return { label: '创建失败', tone: 'danger' }
  if (runInProgress.value) return { label: '运行中', tone: 'info' }
  if (rows.value.some((r) => r.comparison === 'failed')) return { label: '执行失败', tone: 'danger' }
  return { label: '已完成', tone: 'success' }
}
function decisionLabel(event: ValidationEvent) {
  if (event.kind === 'conclusion') return event.decision === 'accepted' ? '验收通过' : '验收不通过'
  return event.decision === 'approved' ? '已批准' : '已驳回'
}

type StepState = 'done' | 'current' | 'todo'
const steps = computed<{ title: string; note: string; state: StepState }[]>(() => {
  const d = detail.value
  if (!d) return []
  const cases = d.cases.length
  const runDone = Boolean(latestRun.value) && !runInProgress.value && latestRun.value?.state === 'bound'
  const reviewDone = runDone && rows.value.length > 0 && reviewedCount.value === rows.value.length
  const approved = approval.value?.decision === 'approved'
  const released = d.stage === 'released'
  const done = [cases > 0, runDone, reviewDone, approved || released, released]
  const firstTodo = done.indexOf(false)
  const notes = [
    cases ? `${cases} 例 · ${d.coverage.gaps.length ? `缺 ${d.coverage.gaps.length} 类` : '四类已覆盖'}` : '尚未关联',
    latestRun.value ? `${formatTime(latestRun.value.created_at)} ${runInProgress.value ? '运行中' : runDone ? '已完成' : ''}` : '尚未运行',
    rows.value.length ? `已核对 ${reviewedCount.value} / ${rows.value.length}` : '等待运行',
    approved ? '已批准' : STAGES[d.stage].label,
    '开发按发布单执行',
  ]
  const titles = ['测试病例与预期', '运行验证', '对照复核', '结论与批准', '代码发布']
  return titles.map((title, i) => ({
    title,
    note: notes[i],
    state: done[i] ? 'done' : i === firstTodo ? 'current' : 'todo',
  }))
})
function stepNoClass(i: number) {
  const state = steps.value[i]?.state
  return { 'is-done': state === 'done', 'is-current': state === 'current' }
}

const checks = computed(() => {
  const d = detail.value
  if (!d || !latestRun.value) return [{ label: '尚未运行', note: '关联病例并运行后显示验收条件', state: 'no' as const }]
  const abnormal = rows.value.filter((r) => r.comparison !== 'same' && r.comparison !== 'pending')
  const unconfirmed = rows.value.filter((r) => latestReview(r.item_id)?.decision !== 'confirmed')
  const unpinned = rows.value.filter((r) => !r.evaluation_as_of_date)
  const release = latestRun.value.build_kind === 'release'
  return [
    { label: '最近一次运行已完成', note: `${formatTime(latestRun.value.created_at)} · ${rows.value.length} 例`, state: runInProgress.value ? 'no' : 'ok' },
    { label: '全部病例状态一致', note: abnormal.map((r) => `${r.case_title}：${COMPARISONS[r.comparison].label}`).join('；'), state: abnormal.length ? 'no' : 'ok' },
    { label: '全部病例已逐例确认', note: unconfirmed.length ? `还有 ${unconfirmed.length} 例未确认` : '', state: unconfirmed.length ? 'no' : 'ok' },
    { label: '评价时间点均已固定', note: unpinned.length ? `${unpinned.length} 例为未固定的历史病例` : '', state: unpinned.length ? 'no' : 'ok' },
    {
      label: `执行版本：${buildLabel(latestRun.value)}`,
      note: release ? '' : '开发环境可批准并在发布单标注；客户环境须在正式构建上重跑',
      state: release ? 'ok' : 'warn',
    },
    {
      label: d.coverage.gaps.length ? '存在覆盖缺口' : '四类预期均有病例覆盖',
      note: d.coverage.gaps.length ? `缺少：${d.coverage.gaps.map((s) => STATUS[s].label).join('、')}，通过时须逐项说明` : '',
      state: d.coverage.gaps.length ? 'warn' : 'ok',
    },
  ] as { label: string; note: string; state: 'ok' | 'no' | 'warn' }[]
})

async function load() {
  if (!ruleId.value) return
  loading.value = true
  const response = await getValidationRule(ruleId.value)
  loading.value = false
  if (!response.success) {
    error.value = response.error || '规则验收详情加载失败'
    return
  }
  error.value = ''
  detail.value = response.data
  schedulePoll()
}

function schedulePoll() {
  clearTimeout(pollTimer)
  if (runInProgress.value) pollTimer = setTimeout(() => void load(), POLL_MS)
}

function openAnswer(item: ValidationCase | null) {
  answerTarget.value = item
  answerOpen.value = true
}
async function onAnswerSaved() {
  answerOpen.value = false
  message.success('预期已保存')
  await load()
}

async function startRun() {
  starting.value = true
  actionError.value = ''
  const response = await startValidationRun(ruleId.value)
  starting.value = false
  if (!response.success) {
    // 超时不代表失败：任务可能已在后台建成，刷新后以服务端记录为准，避免重复创建
    const timedOut = /timeout/i.test(response.error || '')
    actionError.value = timedOut
      ? '创建运行超时，可能仍在后台完成；已刷新详情，请勿重复点击运行'
      : response.error || '运行创建失败'
    if (timedOut) await load()
    return
  }
  message.success('已创建验收运行')
  await load()
}

async function conclude(decision: 'accepted' | 'rejected') {
  if (!latestRun.value) return
  busy.value = true
  actionError.value = ''
  const response = await concludeRule(ruleId.value, {
    run_id: latestRun.value.id,
    decision,
    note: conclusionNote.value.trim(),
    gap_ack: gapAck.value.trim(),
  })
  busy.value = false
  if (!response.success) {
    actionError.value = response.error || '提交验收结论失败'
    return
  }
  conclusionNote.value = ''
  gapAck.value = ''
  message.success(decision === 'accepted' ? '已记录验收通过' : '已记录验收不通过')
  await load()
}

async function onApprovalDone() {
  await load()
}

watch(ruleId, () => {
  detail.value = null
  reviewIndex.value = -1
  void load()
}, { immediate: true })
onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<style scoped src="./styles/rule-validation.css"></style>
<style scoped>
.rv-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 14px;
}

.rv-title .mq-mono {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-20);
}
</style>
