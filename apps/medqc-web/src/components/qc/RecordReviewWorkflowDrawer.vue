<template>
  <a-drawer
    :open="open"
    title="病历初审 / 复审"
    width="min(760px, 100vw)"
    :root-style="{ zIndex: 1400 }"
    :closable="!saving"
    :mask-closable="!saving"
    @close="emit('close')"
  >
    <section
      class="record-review-workflow"
      aria-label="病历审核"
    >
      <div class="review-toolbar">
        <strong>待初审 {{ initialCount ?? '未知' }} · 待复审 {{ recheckCount ?? '未知' }}</strong>
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
        class="review-error"
        role="alert"
      >
        {{ error }}
      </p>
      <p
        v-if="notice"
        role="status"
      >
        {{ notice }}
      </p>
      <p
        v-if="loading"
        role="status"
      >
        正在核对审核来源…
      </p>
      <template v-else>
        <ul class="review-list">
          <li
            v-for="(row, index) in items"
            :key="`${row.envelope_id}-${row.review_id || index}`"
          >
            <button
              class="review-row"
              :disabled="saving"
              @click="show(row)"
            >
              <span>{{ row.scene === 'running' ? '运行' : '终末' }} · {{ row.visit_id }} ·
                {{ row.case_department || '科室未知' }}</span><span class="mq-status">{{ labels[row.state] }}</span>
            </button>
          </li>
        </ul>
        <p v-if="!error && !items.length">
          没有符合条件的病历审核
        </p>
        <nav
          v-if="total"
          class="review-toolbar"
          aria-label="审核分页"
        >
          <button
            class="mq-btn"
            :disabled="page === 1 || saving"
            @click="move(-1)"
          >
            上一页
          </button><span>第 {{ page }} 页 / {{ total }} 条</span><button
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
        <h3 class="mq-card__title">
          {{ selected.visit_id }} · {{ labels[selected.state] }}
        </h3>
        <p class="mq-mono review-identity">
          {{ selected.institute_id }} / {{ selected.patient_id }} / {{ selected.visit_id }}
        </p>
        <p class="mq-mono review-identity">
          {{ selected.root_job_id }} / {{ selected.envelope_id }}
        </p>
        <p>规则版本：{{ selected.rule_set_key }} · {{ selected.rule_set_version }}</p>
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
          <div class="review-toolbar">
            <button
              class="mq-btn mq-btn--primary"
              :disabled="saving || uncertain"
              @click="decide('approved')"
            >
              审核通过
            </button><button
              class="mq-btn"
              :disabled="saving || uncertain || !reason.trim()"
              @click="decide('doubtful')"
            >
              标记存疑
            </button>
          </div>
        </form>
        <h4>审核历史</h4>
        <ul class="review-history">
          <li
            v-for="event in selected.history"
            :key="event.id"
          >
            <strong>{{ event.stage === 'initial' ? '初审' : '复审' }} ·
              {{ labels[event.decision] }}</strong><span>{{ event.reviewer_id }} · {{ event.reason || '无附加意见' }}</span><time class="mq-mono">{{ event.created_at }}</time><span class="mq-mono review-identity">{{ event.root_job_id }} / {{ event.envelope_id }}</span>
          </li>
        </ul>
      </article>
    </section>
  </a-drawer>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
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
const reviewer = computed(() =>
  ['admin', 'qc_manager', 'qc_staff'].some((role) => auth.hasRole(role)),
)
const labels: Record<ReviewState, string> = {
  pending_review: '待初审',
  pending_recheck: '待复审',
  approved: '已通过',
  doubtful: '存疑',
}
const scene = ref<'' | 'running' | 'final'>(''),
  state = ref<ReviewState | 'open' | 'history'>('open')
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
<style scoped>
.record-review-workflow {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.review-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
}
.review-list,
.review-history {
  list-style: none;
  margin: 0;
  padding: 0;
}
.review-row {
  width: 100%;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 0;
  border: 0;
  border-bottom: 1px solid var(--mq-border, #dce3eb);
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.review-detail {
  border-top: 1px solid var(--mq-border, #dce3eb);
  padding-top: 16px;
  min-width: 0;
}
.review-form {
  display: grid;
  gap: 12px;
  margin: 16px 0;
}
.review-identity {
  overflow-wrap: anywhere;
}
.review-error {
  color: var(--mq-danger, #c43c40);
}
.review-history li {
  display: grid;
  gap: 6px;
  padding: 12px 0;
  border-bottom: 1px solid var(--mq-border, #dce3eb);
}
.mq-field {
  min-width: 120px;
}
textarea {
  width: 100%;
  resize: vertical;
}
</style>
