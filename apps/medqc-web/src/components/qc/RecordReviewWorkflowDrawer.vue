<template>
  <a-drawer
    :open="open"
    width="min(760px, 100vw)"
    :root-style="{ zIndex: 1400 }"
    :closable="!saving"
    :mask-closable="!saving"
    @close="emit('close')"
  >
    <template #title>
      <div class="review-heading">
        <MqIconTile
          name="rule_validation"
          tone="brand"
          :size="36"
        />
        <div>
          <span class="review-heading__eyebrow">{{
            reviewId ? '质量管理 · 审核历史' : '质量管理 · 审核工作台'
          }}</span>
          <h2>病历初审 / 复审</h2>
        </div>
      </div>
    </template>
    <section
      class="record-review-workflow"
      aria-label="病历审核"
    >
      <template v-if="!reviewId">
        <div
          class="review-counts mq-soft"
          aria-label="审核待办概况"
        >
          <div>
            <MqIcon
              name="rule_validation"
              :size="20"
            /><span>待初审 <strong>{{ initialCount ?? '未知' }}</strong></span>
          </div>
          <div>
            <MqIcon
              name="history"
              :size="20"
            /><span>待复审 <strong>{{ recheckCount ?? '未知' }}</strong></span>
          </div>
        </div>
        <div class="review-filters">
          <label class="mq-field"><span class="mq-field__label">场景</span><select
            v-model="scene"
            class="mq-input"
            :disabled="saving"
            @change="query"
          >
            <option value="">全部场景</option>
            <option value="running">运行</option>
            <option value="final">终末</option>
          </select></label>
          <label class="mq-field"><span class="mq-field__label">审核状态</span><select
            v-model="state"
            class="mq-input"
            :disabled="saving"
            @change="query"
          >
            <option value="open">待处理</option>
            <option value="history">审核历史</option>
            <option
              v-for="(label, key) in labels"
              :key="key"
              :value="key"
            >{{ label }}</option>
          </select></label>
          <button
            type="button"
            class="mq-btn"
            :disabled="saving || loading"
            @click="refresh"
          >
            <MqIcon
              name="sync"
              :size="16"
            />刷新核对
          </button>
        </div>
      </template>
      <div
        v-else
        class="review-history-context"
      >
        <span class="mq-status">历史记录 · 只读</span>
        <button
          type="button"
          class="mq-btn"
          :disabled="saving || loading"
          @click="refresh"
        >
          <MqIcon
            name="sync"
            :size="16"
          />刷新核对
        </button>
      </div>
      <p
        v-if="error"
        class="review-message review-message--error"
        role="alert"
      >
        <MqIcon
          name="history"
          :size="18"
        />{{ error }}
      </p>
      <p
        v-if="notice"
        class="review-message review-message--success"
        role="status"
      >
        <MqIcon
          name="rule_validation"
          :size="18"
        />{{ notice }}
      </p>
      <p
        v-if="loading"
        class="review-message"
        role="status"
      >
        <MqIcon
          name="sync"
          :size="18"
        />正在核对审核来源…
      </p>
      <template v-else-if="!reviewId">
        <ul class="review-list">
          <li
            v-for="(row, index) in items"
            :key="`${row.envelope_id}-${row.review_id || index}`"
          >
            <button
              type="button"
              class="review-row"
              :class="{ 'is-selected': selected?.envelope_id === row.envelope_id }"
              :aria-pressed="selected?.envelope_id === row.envelope_id"
              :disabled="saving"
              @click="show(row)"
            >
              <MqIconTile
                :name="row.scene === 'running' ? 'running' : 'final'"
                :size="32"
                tone="brand"
              />
              <span class="review-row__copy"><strong>{{ row.visit_id }}</strong><span>{{ row.scene === 'running' ? '运行' : '终末' }} ·
                {{ row.case_department || '科室未知' }}</span></span>
              <span
                class="mq-status"
                :class="statusClass(row.state)"
              >{{ labels[row.state] }}</span>
            </button>
          </li>
        </ul>
        <div
          v-if="!error && !items.length && !selected"
          class="review-empty mq-soft"
        >
          <MqIconTile
            name="rule_validation"
            :size="44"
          />
          <strong>没有符合条件的病历审核</strong>
        </div>
        <nav
          v-if="total"
          class="review-pagination"
          aria-label="审核分页"
        >
          <button
            type="button"
            class="mq-btn"
            :disabled="page === 1 || saving"
            @click="move(-1)"
          >
            上一页
          </button><span>第 {{ page }} 页 / {{ total }} 条</span><button
            type="button"
            class="mq-btn"
            :disabled="page * 10 >= total || saving"
            @click="move(1)"
          >
            下一页
          </button>
        </nav>
      </template>
      <article
        v-if="selected"
        class="review-detail"
        aria-label="审核详情"
      >
        <div class="review-object mq-soft">
          <div class="review-object__head">
            <MqIconTile
              :name="selected.scene === 'running' ? 'running' : 'final'"
              :size="40"
              tone="brand"
            />
            <div class="review-object__copy">
              <span class="review-label">{{ historyView ? '历史审核病历' : '当前审核病历' }}</span>
              <h3>{{ selected.visit_id }}</h3>
            </div>
            <span
              class="mq-status"
              :class="statusClass(selected.state)"
            >{{
              labels[selected.state]
            }}</span>
          </div>
          <div class="review-object__meta">
            <span>{{ selected.scene === 'running' ? '运行病历' : '终末病历' }}</span><span>{{ selected.case_department || '科室未知' }}</span><span>规则版本 {{ selected.rule_set_version }}</span>
          </div>
          <details class="review-source">
            <summary>保存结果来源</summary>
            <dl>
              <div>
                <dt>机构</dt>
                <dd>{{ selected.institute_id }}</dd>
              </div>
              <div>
                <dt>患者</dt>
                <dd>{{ selected.patient_id }}</dd>
              </div>
              <div>
                <dt>就诊</dt>
                <dd>{{ selected.visit_id }}</dd>
              </div>
              <div>
                <dt>任务</dt>
                <dd>{{ selected.root_job_id }}</dd>
              </div>
              <div>
                <dt>保存结果</dt>
                <dd>{{ selected.envelope_id }}</dd>
              </div>
              <div>
                <dt>规则集</dt>
                <dd>{{ selected.rule_set_key }} · {{ selected.rule_set_version }}</dd>
              </div>
            </dl>
          </details>
        </div>
        <form
          v-if="selected.can_submit && reviewer"
          class="review-form"
          @submit.prevent
        >
          <label class="mq-field"><span class="mq-field__label">审核意见</span><textarea
            v-model="reason"
            class="mq-input"
            rows="3"
            maxlength="2000"
            :disabled="saving || uncertain"
          />
          </label>
          <div class="review-actions">
            <button
              type="button"
              class="mq-btn mq-btn--primary"
              :disabled="saving || uncertain"
              @click="decide('approved')"
            >
              <MqIcon
                name="rule_validation"
                :size="16"
              />
              审核通过
            </button><button
              type="button"
              class="mq-btn"
              :disabled="saving || uncertain || !reason.trim()"
              @click="decide('doubtful')"
            >
              <MqIcon
                name="history"
                :size="16"
              />
              标记存疑
            </button>
          </div>
        </form>
        <div class="review-section-head">
          <h4>
            <MqIcon
              name="history"
              :size="18"
            />审核历史
          </h4>
          <span>{{ selected.history.length }} 条记录</span>
        </div>
        <ul class="review-history">
          <li
            v-for="event in selected.history"
            :key="event.id"
            :class="{ 'is-viewing': historyView && event.id === selected.current_review?.id }"
          >
            <div class="review-history__head">
              <strong>{{ event.stage === 'initial' ? '初审' : '复审' }}</strong><span
                class="mq-status"
                :class="statusClass(event.decision)"
              >{{
                labels[event.decision]
              }}</span><span
                v-if="historyView && event.id === selected.current_review?.id"
                class="review-history__viewing"
              >当前查看</span><time :datetime="event.created_at">{{ formatReviewTime(event.created_at) }}</time>
            </div>
            <p class="review-history__reason">
              {{ event.reason || '无附加意见' }}
            </p>
            <details class="review-source">
              <summary>审核人及结果来源</summary>
              <dl>
                <div>
                  <dt>审核人ID</dt>
                  <dd>{{ event.reviewer_id }}</dd>
                </div>
                <div>
                  <dt>任务</dt>
                  <dd>{{ event.root_job_id }}</dd>
                </div>
                <div>
                  <dt>保存结果</dt>
                  <dd>{{ event.envelope_id }}</dd>
                </div>
              </dl>
            </details>
          </li>
        </ul>
        <p
          v-if="!selected.history.length"
          class="review-history__empty"
        >
          暂无审核记录
        </p>
      </article>
    </section>
  </a-drawer>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { useAuthStore } from '@/stores/auth'
import { effectiveRoles } from '@/utils/effectiveRoles'
import {
  getRecordReviewCurrent,
  getRecordReviewHistory,
  listRecordReviews,
  submitRecordReview,
  type RecordReviewDetail,
  type RecordReviewItem,
  type RecordReviewSource,
  type ReviewDecision,
  type ReviewState,
} from '@/api/recordReviews'

const props = defineProps<{
  open: boolean
  source?: RecordReviewSource | null
  reviewId?: string
}>()
const emit = defineEmits<{ close: []; changed: [] }>()
const auth = useAuthStore()
const effectiveUserRoles = computed(() => {
  const raw = Array.isArray(auth.userRoles)
    ? auth.userRoles
    : Array.isArray(auth.user?.roles)
      ? auth.user.roles
      : auth.user?.role
        ? [auth.user.role]
        : []
  return effectiveRoles(raw)
})
const reviewer = computed(() =>
  ['admin', 'qc_manager', 'qc_staff', 'sync_admin', 'super_admin'].some(
    (role) =>
      effectiveUserRoles.value.includes(role) ||
      (typeof auth.hasRole === 'function' && auth.hasRole(role)),
  ),
)
const labels: Record<ReviewState, string> = {
  pending_review: '待初审',
  pending_recheck: '待复审',
  approved: '已通过',
  doubtful: '存疑',
}
const statusClass = (value: ReviewState) => ({
  'mq-status--success': value === 'approved',
  'mq-status--warning': value === 'doubtful',
  'mq-status--info': value === 'pending_review' || value === 'pending_recheck',
})
function formatReviewTime(value: string) {
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}
const scene = ref<'' | 'running' | 'final'>(''),
  state = ref<ReviewState | 'open' | 'history'>('open')
const historyView = computed(() => !!props.reviewId || state.value === 'history')
const items = ref<RecordReviewItem[]>([]),
  selected = ref<RecordReviewDetail | null>(null)
const initialCount = ref<number | null>(null),
  recheckCount = ref<number | null>(null),
  total = ref(0),
  page = ref(1)
const reason = ref(''),
  error = ref(''),
  notice = ref(''),
  loading = ref(false),
  saving = ref(false),
  uncertain = ref(false)
let epoch = 0,
  queryToken = 0,
  detailToken = 0
const message = (err: unknown) =>
  err instanceof Error ? err.message : '审核服务暂不可用，请刷新核对'
const sourceOf = (row: RecordReviewSource): RecordReviewSource => ({
  institute_id: row.institute_id,
  patient_id: row.patient_id,
  visit_id: row.visit_id,
  scene: row.scene,
  root_job_id: row.root_job_id,
  envelope_id: row.envelope_id,
  rule_set_key: row.rule_set_key,
  rule_set_version: row.rule_set_version,
})

async function load() {
  const ownEpoch = epoch,
    token = ++queryToken
  loading.value = true
  try {
    const result = await listRecordReviews(state.value, scene.value || undefined, page.value)
    if (ownEpoch !== epoch || token !== queryToken) return
    items.value = result.items
    total.value = result.total
    initialCount.value = result.initial_count
    recheckCount.value = result.recheck_count
  } catch (err) {
    if (ownEpoch !== epoch || token !== queryToken) return
    items.value = []
    total.value = 0
    initialCount.value = null
    recheckCount.value = null
    selected.value = null
    uncertain.value = true
    error.value = message(err)
  } finally {
    if (ownEpoch === epoch && token === queryToken) loading.value = false
  }
}
async function show(row: RecordReviewSource & { review_id?: string | null }, history = false) {
  const ownEpoch = epoch,
    token = ++detailToken
  selected.value = null
  reason.value = ''
  error.value = ''
  try {
    const result =
      row.review_id && (history || state.value === 'history')
        ? await getRecordReviewHistory(row.review_id)
        : await getRecordReviewCurrent(sourceOf(row))
    if (ownEpoch !== epoch || token !== detailToken) return
    selected.value = result
  } catch (err) {
    if (ownEpoch === epoch && token === detailToken) error.value = message(err)
  }
}
async function refresh() {
  error.value = ''
  notice.value = ''
  const previous = selected.value
  const ownEpoch = epoch
  await load()
  if (ownEpoch !== epoch) return
  const listError = error.value
  if (props.reviewId) {
    const token = ++detailToken
    selected.value = null
    try {
      const result = await getRecordReviewHistory(props.reviewId)
      if (ownEpoch === epoch && token === detailToken) selected.value = result
    } catch (err) {
      if (ownEpoch === epoch && token === detailToken) error.value = message(err)
    }
  } else if (!listError && (props.source || previous)) await show(props.source || previous!)
  if (listError) error.value = listError
  if (ownEpoch === epoch && !error.value) uncertain.value = false
}
async function decide(decision: ReviewDecision) {
  const current = selected.value
  if (!current?.can_submit || saving.value || uncertain.value || !reviewer.value) return
  if (decision === 'doubtful' && !reason.value.trim()) return
  const ownEpoch = epoch
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    await submitRecordReview(
      sourceOf(current),
      current.state,
      decision,
      reason.value,
      crypto.randomUUID(),
    )
    if (ownEpoch !== epoch) return
    emit('changed')
    await refresh()
    if (ownEpoch === epoch && !error.value) notice.value = '审核已保存'
  } catch (err) {
    if (ownEpoch !== epoch) return
    uncertain.value = true
    selected.value = null
    error.value = `${message(err)}。提交结果未核实，请刷新核对。`
  } finally {
    if (ownEpoch === epoch) saving.value = false
  }
}
function query() {
  page.value = 1
  error.value = ''
  selected.value = null
  detailToken++
  void load()
}
function move(delta: number) {
  page.value += delta
  selected.value = null
  detailToken++
  void load()
}
watch(
  () => [
    props.open,
    props.source ? JSON.stringify(sourceOf(props.source)) : '',
    props.reviewId,
    auth.user?.id,
    JSON.stringify(auth.user?.roles || []),
    JSON.stringify(effectiveUserRoles.value),
    auth.user?.role,
    auth.user?.institute_id,
    auth.user?.department,
    reviewer.value,
  ],
  () => {
    epoch++
    queryToken++
    detailToken++
    items.value = []
    selected.value = null
    initialCount.value = null
    recheckCount.value = null
    page.value = 1
    total.value = 0
    saving.value = false
    uncertain.value = false
    error.value = ''
    notice.value = ''
    if (props.open && reviewer.value) void refresh()
  },
  { immediate: true },
)
onUnmounted(() => {
  epoch++
})
</script>
<style scoped src="./styles/record-review-workflow.css"></style>
