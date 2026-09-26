<template>
  <section
    class="record-review"
    aria-label="病历审核"
    data-testid="task-record-review"
  >
    <div class="record-review__heading">
      <div class="record-review__title">
        <h4>病历审核</h4>
        <a-tag
          v-if="view"
          :color="stateColor(view.state)"
          data-testid="record-review-state"
        >
          {{ stateLabel(view.state) }}
        </a-tag>
      </div>
      <a-button
        size="small"
        :loading="loading"
        :disabled="submitting"
        data-testid="record-review-refresh"
        @click="void refresh()"
      >
        <RotateCw
          :size="14"
          aria-hidden="true"
        />刷新
      </a-button>
    </div>

    <p
      v-if="loading && !view"
      class="record-review__muted"
    >
      正在读取审核状态…
    </p>
    <p
      v-else-if="loadError && !view"
      class="record-review__error"
      role="alert"
    >
      {{ loadError }}
    </p>
    <template v-else-if="view">
      <p
        v-if="view.state === 'unavailable'"
        class="record-review__muted"
        data-testid="record-review-unavailable"
      >
        不可审核：{{ unavailableReason(view.reason_code) }}
      </p>
      <p
        v-else-if="view.current"
        class="record-review__muted"
      >
        {{ stageLabel(view.current.stage) }}结论：{{ decisionLabel(view.current.decision) }}（决定不可修改，如需推翻请重新质控）
      </p>
      <p
        v-else-if="view.state === 'pending_recheck'"
        class="record-review__muted"
      >
        上一次结果审核存疑，本次重质控结果待复审。
      </p>

      <div
        v-if="isPending(view.state)"
        class="record-review__actions"
      >
        <a-button
          type="primary"
          :disabled="!canAct"
          :loading="submitting && activeDecision === 'approved'"
          data-testid="record-review-approve"
          @click="openDecision('approved')"
        >
          审核通过
        </a-button>
        <a-button
          danger
          :disabled="!canAct"
          :loading="submitting && activeDecision === 'doubtful'"
          data-testid="record-review-doubt"
          @click="openDecision('doubtful')"
        >
          审核存疑
        </a-button>
      </div>
      <p
        v-if="isPending(view.state) && !view.can_submit"
        class="record-review__muted"
      >
        当前任务或病历状态不允许提交审核。
      </p>
    </template>

    <p
      v-if="actionError"
      class="record-review__error"
      role="alert"
      data-testid="record-review-error"
    >
      {{ actionError }}
    </p>
    <p
      v-if="successMessage"
      class="record-review__success"
      role="status"
    >
      {{ successMessage }}
    </p>

    <div
      v-if="view && view.history.length"
      class="record-review__history"
    >
      <h5>审核历史</h5>
      <ul>
        <li
          v-for="entry in view.history"
          :key="entry.id"
          data-testid="record-review-history-item"
        >
          <div class="record-review__history-heading">
            <span>{{ formatTime(entry.created_at) }}</span>
            <span>{{ stageLabel(entry.stage) }}</span>
            <a-tag :color="entry.decision === 'approved' ? 'success' : 'warning'">
              {{ decisionLabel(entry.decision) }}
            </a-tag>
            <span>审核人 {{ entry.reviewer_id || '未知' }}</span>
          </div>
          <p v-if="entry.reason">
            原因：{{ entry.reason }}
          </p>
        </li>
      </ul>
    </div>

    <a-modal
      :open="decisionOpen"
      :title="activeDecision === 'doubtful' ? '审核存疑' : '审核通过'"
      :confirm-loading="submitting"
      ok-text="提交"
      cancel-text="取消"
      @ok="void confirmDecision()"
      @cancel="closeDecision()"
    >
      <p class="record-review__muted">
        审核决定提交后不可修改。
      </p>
      <label for="record-review-reason">{{ activeDecision === 'doubtful' ? '存疑原因（必填）' : '备注（可选）' }}</label>
      <a-textarea
        id="record-review-reason"
        v-model:value="reason"
        :maxlength="2000"
        :rows="3"
        :disabled="submitting"
      />
      <p
        v-if="reasonError"
        class="record-review__error"
        role="alert"
      >
        {{ reasonError }}
      </p>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RotateCw } from 'lucide-vue-next'
import { getTaskRecordReview, submitTaskRecordReview } from '@/api/recordReviews'
import type {
  RecordReviewDecision,
  RecordReviewStage,
  RecordReviewState,
  RecordReviewSubmitPayload,
  RecordReviewView,
} from '@/api/recordReviews'

const props = defineProps<{
  taskId: string
  taskRecordId: string
  runNumber: number
  jobId: string
  userId: string
}>()

const emit = defineEmits<{ 'review-submitted': [decision: RecordReviewDecision] }>()

const view = ref<RecordReviewView | null>(null)
const loading = ref(false)
const loadError = ref('')
const submitting = ref(false)
const actionError = ref('')
const successMessage = ref('')
const decisionOpen = ref(false)
const activeDecision = ref<RecordReviewDecision>('approved')
const reason = ref('')
const reasonError = ref('')
/** 结果不确定（网络/5xx）时保留原请求，重试沿用同一 request_id 保证幂等。 */
const pendingPayload = ref<RecordReviewSubmitPayload | null>(null)
let sequence = 0

const contextKey = computed(() => JSON.stringify([
  props.taskId, props.taskRecordId, props.runNumber, props.jobId, props.userId,
]))
const canAct = computed(() => !!view.value && view.value.can_submit && isPending(view.value.state)
  && !!view.value.result.envelope_id && !submitting.value && !loading.value)

const STATE_LABELS: Record<RecordReviewState, string> = {
  pending_review: '待审核',
  pending_recheck: '待复审',
  approved: '审核通过',
  doubtful: '审核存疑',
  unavailable: '不可审核',
}

const REASON_LABELS: Record<string, string> = {
  identity_incomplete: '病历缺少完整三坐标',
  unsupported_rule_set: '当前规则集不支持病历审核',
  result_invalid: '本次质控结果无效',
  result_pending: '本次质控结果尚未生成',
  result_unavailable: '本次质控结果不可用',
  result_unknown: '本次质控结果状态未知',
  envelope_missing: '质控结果对象缺失',
  envelope_ambiguous: '质控结果对象不唯一',
}

const CONFLICT_MESSAGES: Record<string, string> = {
  result_changed: '质控结果已被替换，已刷新为最新状态，请重新审核',
  already_decided: '该结果已有审核决定，已刷新为最新状态',
  idempotency_conflict: '请求编号冲突，已刷新状态，请重新提交',
  result_unavailable: '本次质控结果不可用于审核',
  unsupported_rule_set: '当前规则集不支持病历审核',
  state_conflict: '任务或病历当前状态不允许审核',
}

function isPending(state: RecordReviewState) {
  return state === 'pending_review' || state === 'pending_recheck'
}

function stateLabel(state: RecordReviewState) {
  return STATE_LABELS[state] || '未知'
}

function stateColor(state: RecordReviewState) {
  if (state === 'approved') return 'success'
  if (state === 'doubtful') return 'warning'
  if (state === 'unavailable') return 'default'
  return 'processing'
}

function stageLabel(stage: RecordReviewStage | null) {
  if (stage === 'initial') return '初审'
  if (stage === 'recheck') return '复审'
  return '未知阶段'
}

function decisionLabel(decision: RecordReviewDecision) {
  return decision === 'approved' ? '通过' : decision === 'doubtful' ? '存疑' : '未知'
}

function unavailableReason(code: string | null) {
  if (!code) return '原因未知'
  return REASON_LABELS[code] || `原因未知（${code}）`
}

function formatTime(value: string | null | undefined) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { hour12: false })
}

function isCurrent(key: string, token: number) {
  return key === contextKey.value && token === sequence
}

function isOwnedView(data: RecordReviewView | undefined): data is RecordReviewView {
  return !!data && data.task_id === props.taskId && data.task_record_id === props.taskRecordId
    && data.run_number === props.runNumber && Array.isArray(data.history)
    && !!data.result && (data.result.job_id === null || data.result.job_id === props.jobId)
}

/** 读取审核状态；返回 false 表示读取失败或已过期。 */
async function load(key: string, token: number): Promise<boolean> {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getTaskRecordReview(props.taskId, props.taskRecordId, props.runNumber)
    if (!isCurrent(key, token)) return false
    if (!response.success || !isOwnedView(response.data)) {
      loadError.value = response.success ? '审核状态身份校验失败，请刷新' : response.message || '读取病历审核状态失败'
      return false
    }
    view.value = response.data
    return true
  } catch {
    if (isCurrent(key, token)) loadError.value = '网络异常或服务器不可用'
    return false
  } finally {
    if (isCurrent(key, token)) loading.value = false
  }
}

async function refresh() {
  if (submitting.value) return
  const key = contextKey.value
  const token = ++sequence
  actionError.value = ''
  successMessage.value = ''
  const ok = await load(key, token)
  if (!ok && isCurrent(key, token) && view.value) actionError.value = loadError.value
}

function openDecision(decision: RecordReviewDecision) {
  if (!canAct.value) return
  activeDecision.value = decision
  const pending = pendingPayload.value
  reason.value = pending && pending.decision === decision ? pending.reason || '' : ''
  reasonError.value = ''
  decisionOpen.value = true
}

function closeDecision() {
  if (submitting.value) return
  decisionOpen.value = false
  reasonError.value = ''
}

function buildPayload(decision: RecordReviewDecision, text: string | null, envelopeId: string): RecordReviewSubmitPayload {
  const pending = pendingPayload.value
  if (pending && pending.decision === decision && (pending.reason || null) === text
    && pending.envelope_id === envelopeId && pending.run_number === props.runNumber) {
    return pending
  }
  return {
    run_number: props.runNumber,
    decision,
    reason: text,
    request_id: crypto.randomUUID(),
    envelope_id: envelopeId,
  }
}

async function confirmDecision() {
  if (submitting.value) return
  const current = view.value
  const envelopeId = current?.result.envelope_id
  if (!current || !current.can_submit || !isPending(current.state) || !envelopeId) {
    decisionOpen.value = false
    return
  }
  const decision = activeDecision.value
  const text = reason.value.trim() || null
  if (decision === 'doubtful' && !text) {
    reasonError.value = '请填写存疑原因'
    return
  }
  reasonError.value = ''
  const payload = buildPayload(decision, text, envelopeId)
  pendingPayload.value = payload
  const key = contextKey.value
  const token = ++sequence
  submitting.value = true
  actionError.value = ''
  successMessage.value = ''
  let outcome: 'saved' | 'conflict' | 'rejected' | 'uncertain' = 'uncertain'
  let failureMessage = ''
  try {
    const response = await submitTaskRecordReview(props.taskId, props.taskRecordId, payload)
    if (!isCurrent(key, token)) return
    if (response.success && response.data?.request_id === payload.request_id) {
      outcome = 'saved'
    } else if (response.status === 409) {
      outcome = 'conflict'
      failureMessage = (response.code && CONFLICT_MESSAGES[response.code]) || response.message || '审核状态已变化，已刷新'
    } else if (response.status && response.status >= 400 && response.status < 500 && response.status !== 408) {
      outcome = 'rejected'
      failureMessage = response.message || '审核提交被拒绝'
    } else {
      failureMessage = response.success
        ? '提交响应未确认，正在重新查询'
        : `${response.message || '网络异常或服务暂不可用'}，可重试（沿用原请求编号）`
    }
  } catch {
    if (!isCurrent(key, token)) return
    failureMessage = '网络异常，可重试（沿用原请求编号）'
  } finally {
    if (isCurrent(key, token)) submitting.value = false
  }
  if (!isCurrent(key, token)) return
  if (outcome !== 'uncertain') pendingPayload.value = null
  decisionOpen.value = false

  // 任何结果都以服务端 GET 为准，不做乐观更新。
  const ok = await load(key, token)
  if (!isCurrent(key, token)) return
  const confirmed = ok && view.value?.current?.request_id === payload.request_id
  if (confirmed) {
    pendingPayload.value = null
    reason.value = ''
    successMessage.value = decision === 'approved' ? '审核通过已保存并确认' : '审核存疑已保存并确认'
    emit('review-submitted', decision)
    return
  }
  if (outcome === 'saved') {
    actionError.value = ok ? '审核已提交但状态未确认，请刷新核对' : '审核已提交，但刷新状态失败，请稍后刷新核对'
    return
  }
  actionError.value = failureMessage || '审核提交未完成'
}

watch(contextKey, () => {
  sequence += 1
  view.value = null
  loading.value = false
  loadError.value = ''
  submitting.value = false
  actionError.value = ''
  successMessage.value = ''
  decisionOpen.value = false
  reason.value = ''
  reasonError.value = ''
  pendingPayload.value = null
  void refresh()
}, { immediate: true })
</script>

<style scoped>
.record-review { margin-top: 18px; padding-top: 16px; border-top: 1px solid rgba(0, 0, 0, .08); }
.record-review__heading, .record-review__title, .record-review__actions, .record-review__history-heading { display: flex; align-items: center; gap: 10px; }
.record-review__heading { justify-content: space-between; }
.record-review__heading h4, .record-review__history h5 { margin: 0; font-size: 14px; font-weight: 600; }
.record-review__heading button { display: inline-flex; align-items: center; gap: 5px; }
.record-review__actions { margin-top: 10px; }
.record-review__muted { margin: 8px 0 0; color: rgba(29, 29, 31, .6); font-size: 13px; }
.record-review__error { margin: 8px 0 0; color: #b42318; }
.record-review__success { margin: 8px 0 0; color: #067647; }
.record-review__history { margin-top: 14px; }
.record-review__history ul { margin: 8px 0 0; padding: 0; list-style: none; }
.record-review__history li { padding: 10px 0; border-bottom: 1px solid rgba(0, 0, 0, .06); }
.record-review__history-heading { flex-wrap: wrap; color: rgba(29, 29, 31, .7); font-size: 13px; }
.record-review__history li p { margin: 6px 0 0; line-height: 22px; overflow-wrap: anywhere; }
</style>
