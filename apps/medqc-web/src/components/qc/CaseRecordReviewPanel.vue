<template>
  <RecordReviewDecisionBlock
    v-if="!forbidden"
    data-testid="case-record-review"
    :controller="review"
    blocked-message="当前病历结果不允许提交审核。"
  >
    <template #history-meta="{ entry }">
      <span>{{ contextLabel(entry) }}</span>
    </template>
  </RecordReviewDecisionBlock>
</template>

<script setup lang="ts">
/**
 * 运行/终末列表病例上下文的病历审核：身份为 institute_id/patient_id/visit_id 三坐标，
 * 当前结果对象由服务端单病历最新 ready 结果决定；展示与交互复用共享块。
 * 无审核权限（GET 403）时整块不渲染，并通知父级。
 */
import { computed, watch } from 'vue'
import { getCaseRecordReview, submitCaseRecordReview } from '@/api/recordReviews'
import type {
  CaseRecordReviewSubmitPayload,
  CaseRecordReviewView,
  RecordReviewDecision,
  RecordReviewEntryBase,
} from '@/api/recordReviews'
import { useRecordReviewDecision } from '@/composables/useRecordReviewDecision'
import RecordReviewDecisionBlock from './RecordReviewDecisionBlock.vue'

const props = defineProps<{
  instituteId: string
  patientId: string
  visitId: string
  /** 调用方正在展示的结果 job；给定时审核视图必须指向同一结果，避免审核用户未看到的结果。 */
  jobId?: string
  userId?: string
}>()

const emit = defineEmits<{
  'review-submitted': [decision: RecordReviewDecision]
  forbidden: []
}>()

const contextKey = computed(() => JSON.stringify([
  props.instituteId, props.patientId, props.visitId, props.jobId ?? '', props.userId ?? '',
]))

function isOwnedView(data: CaseRecordReviewView | undefined): data is CaseRecordReviewView {
  return !!data && data.review_context === 'workspace'
    && data.institute_id === props.instituteId && data.patient_id === props.patientId
    && data.visit_id === props.visitId && Array.isArray(data.history) && !!data.result
    && (!props.jobId || data.result.job_id === null || data.result.job_id === props.jobId)
}

/** 历史行来源：病例上下文会合并任务与列表两类决定。 */
function contextLabel(entry: RecordReviewEntryBase) {
  const context = 'review_context' in entry ? entry.review_context : undefined
  if (context === 'workspace') return '来源：病历列表'
  if (context === 'task') return '来源：质控任务'
  return '来源未知'
}

const review = useRecordReviewDecision<CaseRecordReviewView, CaseRecordReviewSubmitPayload>({
  contextKey,
  fetchView: () => getCaseRecordReview({
    institute_id: props.instituteId, patient_id: props.patientId, visit_id: props.visitId,
  }),
  isOwnedView,
  submit: (payload) => submitCaseRecordReview(payload),
  buildPayload: (fields, view) => ({
    institute_id: props.instituteId,
    patient_id: props.patientId,
    visit_id: props.visitId,
    job_id: view.result.job_id as string,
    envelope_id: fields.envelope_id,
    decision: fields.decision,
    reason: fields.reason,
    request_id: fields.request_id,
  }),
  isReusablePayload: (pending, view) => pending.job_id === view.result.job_id
    && pending.institute_id === props.instituteId && pending.patient_id === props.patientId
    && pending.visit_id === props.visitId,
  canSubmitView: (view) => !!view.result.job_id,
  onSubmitted: (decision) => emit('review-submitted', decision),
})

const forbidden = computed(() => review.loadStatus === 403)

watch(forbidden, (value) => {
  if (value) emit('forbidden')
})
</script>
