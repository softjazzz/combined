<template>
  <RecordReviewDecisionBlock
    data-testid="task-record-review"
    :controller="review"
    blocked-message="当前任务或病历状态不允许提交审核。"
  />
</template>

<script setup lang="ts">
/** 任务受领上下文的病历审核：身份为 任务 + 受领记录 + 运行轮次，展示与交互复用共享块。 */
import { computed } from 'vue'
import { getTaskRecordReview, submitTaskRecordReview } from '@/api/recordReviews'
import type {
  RecordReviewDecision,
  RecordReviewSubmitPayload,
  RecordReviewView,
} from '@/api/recordReviews'
import { useRecordReviewDecision } from '@/composables/useRecordReviewDecision'
import RecordReviewDecisionBlock from './RecordReviewDecisionBlock.vue'

const props = defineProps<{
  taskId: string
  taskRecordId: string
  runNumber: number
  jobId: string
  userId: string
}>()

const emit = defineEmits<{ 'review-submitted': [decision: RecordReviewDecision] }>()

const contextKey = computed(() => JSON.stringify([
  props.taskId, props.taskRecordId, props.runNumber, props.jobId, props.userId,
]))

function isOwnedView(data: RecordReviewView | undefined): data is RecordReviewView {
  return !!data && data.task_id === props.taskId && data.task_record_id === props.taskRecordId
    && data.run_number === props.runNumber && Array.isArray(data.history)
    && !!data.result && (data.result.job_id === null || data.result.job_id === props.jobId)
}

const review = useRecordReviewDecision<RecordReviewView, RecordReviewSubmitPayload>({
  contextKey,
  fetchView: () => getTaskRecordReview(props.taskId, props.taskRecordId, props.runNumber),
  isOwnedView,
  submit: (payload) => submitTaskRecordReview(props.taskId, props.taskRecordId, payload),
  buildPayload: (fields) => ({
    run_number: props.runNumber,
    decision: fields.decision,
    reason: fields.reason,
    request_id: fields.request_id,
    envelope_id: fields.envelope_id,
  }),
  isReusablePayload: (pending) => pending.run_number === props.runNumber,
  onSubmitted: (decision) => emit('review-submitted', decision),
})
</script>
