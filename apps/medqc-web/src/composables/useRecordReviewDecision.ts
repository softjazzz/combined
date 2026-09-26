/**
 * 病历审核（通过/存疑）的上下文无关交互状态机。
 *
 * 任务上下文与病例上下文共用：读取 → 弹窗填写 → 提交 → 以服务端 GET 复核。
 * 上下文差异（请求地址、身份校验、载荷字段）由调用方通过适配器注入；
 * 状态、阶段、原因码均由服务端推导，这里只搬运和展示，不重新判定。
 */

import { computed, reactive, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type {
  RecordReviewApiResult,
  RecordReviewDecision,
  RecordReviewEntryBase,
  RecordReviewStage,
  RecordReviewState,
  RecordReviewViewBase,
} from '@/api/recordReviews'

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

export function isPendingReviewState(state: RecordReviewState) {
  return state === 'pending_review' || state === 'pending_recheck'
}

export function reviewStateLabel(state: RecordReviewState) {
  return STATE_LABELS[state] || '未知'
}

export function reviewStateColor(state: RecordReviewState) {
  if (state === 'approved') return 'success'
  if (state === 'doubtful') return 'warning'
  if (state === 'unavailable') return 'default'
  return 'processing'
}

export function reviewStageLabel(stage: RecordReviewStage | null) {
  if (stage === 'initial') return '初审'
  if (stage === 'recheck') return '复审'
  return '未知阶段'
}

export function reviewDecisionLabel(decision: RecordReviewDecision) {
  return decision === 'approved' ? '通过' : decision === 'doubtful' ? '存疑' : '未知'
}

export function reviewUnavailableReason(code: string | null) {
  if (!code) return '原因未知'
  return REASON_LABELS[code] || `原因未知（${code}）`
}

export function reviewConflictMessage(code: string | undefined) {
  return code ? CONFLICT_MESSAGES[code] : undefined
}

export function formatReviewTime(value: string | null | undefined) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { hour12: false })
}

/** 各上下文载荷都包含的决定字段。 */
export interface RecordReviewDecisionFields {
  decision: RecordReviewDecision
  reason?: string | null
  request_id: string
  envelope_id: string
}

export interface RecordReviewDecisionAdapter<
  V extends RecordReviewViewBase,
  P extends RecordReviewDecisionFields,
> {
  /** 上下文身份键；变化即丢弃在途请求并重置状态。 */
  contextKey: Ref<string>
  fetchView: () => Promise<RecordReviewApiResult<V>>
  /** 校验响应确属当前上下文，防止串病例/串运行。 */
  isOwnedView: (data: V | undefined) => data is V
  submit: (payload: P) => Promise<RecordReviewApiResult<{ request_id: string }>>
  /** 由公共决定字段与当前视图组装上下文载荷。 */
  buildPayload: (fields: RecordReviewDecisionFields, view: V) => P
  /** 结果不确定时保留的原载荷是否仍属于当前上下文（可复用原 request_id）。 */
  isReusablePayload: (pending: P, view: V) => boolean
  /** 上下文额外的可提交前提（如病例上下文需要 job_id）。 */
  canSubmitView?: (view: V) => boolean
  onSubmitted?: (decision: RecordReviewDecision) => void
}

export function useRecordReviewDecision<
  V extends RecordReviewViewBase,
  P extends RecordReviewDecisionFields,
>(adapter: RecordReviewDecisionAdapter<V, P>) {
  const view = ref<V | null>(null) as Ref<V | null>
  const loading = ref(false)
  const loadError = ref('')
  /** 最近一次读取失败的 HTTP 状态；成功或网络异常时为 undefined。 */
  const loadStatus = ref<number | undefined>(undefined)
  const submitting = ref(false)
  const actionError = ref('')
  const successMessage = ref('')
  const decisionOpen = ref(false)
  const activeDecision = ref<RecordReviewDecision>('approved')
  const reason = ref('')
  const reasonError = ref('')
  /** 结果不确定（网络/5xx）时保留原请求，重试沿用同一 request_id 保证幂等。 */
  const pendingPayload = ref<P | null>(null) as Ref<P | null>
  let sequence = 0

  function isSubmittable(current: V | null): current is V {
    return !!current && current.can_submit && isPendingReviewState(current.state)
      && !!current.result.envelope_id && (adapter.canSubmitView ? adapter.canSubmitView(current) : true)
  }

  const canAct = computed(() => isSubmittable(view.value) && !submitting.value && !loading.value)

  function isCurrent(key: string, token: number) {
    return key === adapter.contextKey.value && token === sequence
  }

  /** 读取审核状态；返回 false 表示读取失败或已过期。 */
  async function load(key: string, token: number): Promise<boolean> {
    loading.value = true
    loadError.value = ''
    loadStatus.value = undefined
    try {
      const response = await adapter.fetchView()
      if (!isCurrent(key, token)) return false
      if (!response.success || !adapter.isOwnedView(response.data)) {
        loadStatus.value = response.success ? undefined : response.status
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
    const key = adapter.contextKey.value
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

  function setReason(text: string | undefined) {
    reason.value = text ?? ''
  }

  function closeDecision() {
    if (submitting.value) return
    decisionOpen.value = false
    reasonError.value = ''
  }

  function resolvePayload(decision: RecordReviewDecision, text: string | null, envelopeId: string, current: V): P {
    const pending = pendingPayload.value
    if (pending && pending.decision === decision && (pending.reason || null) === text
      && pending.envelope_id === envelopeId && adapter.isReusablePayload(pending, current)) {
      return pending
    }
    return adapter.buildPayload({
      decision,
      reason: text,
      request_id: crypto.randomUUID(),
      envelope_id: envelopeId,
    }, current)
  }

  async function confirmDecision() {
    if (submitting.value) return
    const current = view.value
    if (!isSubmittable(current)) {
      decisionOpen.value = false
      return
    }
    const envelopeId = current.result.envelope_id as string
    const decision = activeDecision.value
    const text = reason.value.trim() || null
    if (decision === 'doubtful' && !text) {
      reasonError.value = '请填写存疑原因'
      return
    }
    reasonError.value = ''
    const payload = resolvePayload(decision, text, envelopeId, current)
    pendingPayload.value = payload
    const key = adapter.contextKey.value
    const token = ++sequence
    submitting.value = true
    actionError.value = ''
    successMessage.value = ''
    let outcome: 'saved' | 'conflict' | 'rejected' | 'uncertain' = 'uncertain'
    let failureMessage = ''
    try {
      const response = await adapter.submit(payload)
      if (!isCurrent(key, token)) return
      if (response.success && response.data?.request_id === payload.request_id) {
        outcome = 'saved'
      } else if (response.status === 409) {
        outcome = 'conflict'
        failureMessage = reviewConflictMessage(response.code) || response.message || '审核状态已变化，已刷新'
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
      adapter.onSubmitted?.(decision)
      return
    }
    if (outcome === 'saved') {
      actionError.value = ok ? '审核已提交但状态未确认，请刷新核对' : '审核已提交，但刷新状态失败，请稍后刷新核对'
      return
    }
    actionError.value = failureMessage || '审核提交未完成'
  }

  watch(adapter.contextKey, () => {
    sequence += 1
    view.value = null
    loading.value = false
    loadError.value = ''
    loadStatus.value = undefined
    submitting.value = false
    actionError.value = ''
    successMessage.value = ''
    decisionOpen.value = false
    reason.value = ''
    reasonError.value = ''
    pendingPayload.value = null
    void refresh()
  }, { immediate: true })

  return reactive({
    view,
    loading,
    loadError,
    loadStatus,
    submitting,
    actionError,
    successMessage,
    decisionOpen,
    activeDecision,
    reason,
    reasonError,
    canAct,
    refresh,
    openDecision,
    setReason,
    closeDecision,
    confirmDecision,
  })
}

/** 共享展示组件接收的控制器（已解包的响应式对象）。 */
export type RecordReviewDecisionController = ReturnType<
  typeof useRecordReviewDecision<RecordReviewViewBase<RecordReviewEntryBase>, RecordReviewDecisionFields>
>
