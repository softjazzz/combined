<template>
  <section
    class="qc-result-feedback"
    :class="{ 'is-compact': Boolean(feedback) && !editing }"
    data-testid="qc-result-feedback"
  >
    <p
      v-if="loading"
      class="feedback-loading"
      data-testid="qc-result-feedback-loading"
    >
      正在读取你的反馈…
    </p>
    <div
      v-else-if="feedback && !editing"
      class="feedback-submitted"
      data-testid="qc-result-feedback-submitted"
    >
      <div class="feedback-submitted-copy">
        <span class="feedback-label">你的反馈</span>
        <strong>{{ feedbackTypeLabel(feedback.feedback_type) }}</strong>
        <span v-if="feedback.expected_status">
          期望结果：{{ expectedStatusLabel(feedback.expected_status) }}
        </span>
        <span
          v-if="feedback.comment"
          class="feedback-comment"
        >{{ feedback.comment }}</span>
      </div>
      <button
        type="button"
        class="feedback-edit-button"
        data-testid="qc-result-feedback-edit"
        @click="startEditingFromButton"
      >
        修改反馈
      </button>
    </div>

    <template v-else>
      <div class="feedback-prompt">
        <span>这个质控结果准确吗？</span>
        <div
          class="feedback-actions"
          role="group"
          aria-label="质控结果反馈"
        >
          <button
            type="button"
            class="feedback-action is-correct"
            data-testid="qc-result-feedback-correct"
            :disabled="saving"
            @click="submitCorrect"
          >
            准确
          </button>
          <button
            type="button"
            class="feedback-action is-incorrect"
            data-testid="qc-result-feedback-incorrect"
            :disabled="saving"
            @click="startIncorrectEditing"
          >
            有误
          </button>
          <button
            type="button"
            class="feedback-action is-note"
            data-testid="qc-result-feedback-note"
            :disabled="saving"
            @click="startNoteEditing"
          >
            补充说明
          </button>
        </div>
      </div>

      <form
        v-if="editing"
        class="feedback-form"
        data-testid="qc-result-feedback-form"
        @submit.prevent="submit"
      >
        <div class="feedback-form-title">
          <strong>{{ selectedType === 'note' ? '补充说明' : '指出结果问题' }}</strong>
          <span>仅用于演示反馈，不会修改本次质控结果。</span>
        </div>

        <label
          v-if="selectedType === 'incorrect'"
          class="feedback-field"
        >
          <span>期望结果</span>
          <select
            v-model="expectedStatus"
            data-testid="qc-result-feedback-expected-status"
          >
            <option value="">请选择</option>
            <option
              v-for="option in expectedStatusOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label
          v-if="selectedType === 'incorrect'"
          class="feedback-field"
        >
          <span>问题类型</span>
          <select
            v-model="errorCategory"
            data-testid="qc-result-feedback-error-category"
          >
            <option value="">请选择</option>
            <option
              v-for="option in errorCategoryOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="feedback-field">
          <span>{{ selectedType === 'note' ? '说明' : '补充说明' }}</span>
          <textarea
            v-model="comment"
            maxlength="500"
            rows="3"
            :placeholder="selectedType === 'note' ? '请填写需要补充的情况' : '请说明结果哪里不准确'"
            data-testid="qc-result-feedback-comment"
          />
        </label>

        <p
          v-if="errorMessage"
          class="feedback-error"
          data-testid="qc-result-feedback-error"
        >
          {{ errorMessage }}
        </p>

        <div class="feedback-form-actions">
          <button
            type="button"
            class="feedback-cancel"
            :disabled="saving"
            @click="cancelEditing"
          >
            取消
          </button>
          <button
            type="submit"
            class="feedback-submit"
            :disabled="saving || !canSubmit"
            data-testid="qc-result-feedback-submit"
          >
            {{ saving ? '保存中…' : '保存反馈' }}
          </button>
        </div>
      </form>

      <p
        v-else-if="errorMessage"
        class="feedback-error"
        data-testid="qc-result-feedback-error"
      >
        {{ errorMessage }}
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  QcResultExpectedStatus,
  QcResultFeedbackErrorCategory,
  QcResultFeedbackRecord,
  QcResultFeedbackType,
  SaveQcResultFeedbackInput,
} from '@/api/qc-result-feedback-demo'

const props = withDefaults(
  defineProps<{
    feedback?: QcResultFeedbackRecord | null
    loading?: boolean
    saving?: boolean
    errorMessage?: string
  }>(),
  { feedback: null, loading: false, saving: false, errorMessage: '' },
)

const emit = defineEmits<{
  (event: 'submit', input: SaveQcResultFeedbackInput): void
}>()

const selectedType = ref<QcResultFeedbackType | ''>('')
const expectedStatus = ref<QcResultExpectedStatus | ''>('')
const errorCategory = ref<QcResultFeedbackErrorCategory | ''>('')
const comment = ref('')
const editing = ref(false)

const expectedStatusOptions: Array<{ value: QcResultExpectedStatus; label: string }> = [
  { value: 'non_compliant', label: '不合规' },
  { value: 'compliant', label: '合规' },
  { value: 'data_gap', label: '数据不足' },
  { value: 'not_applicable', label: '不适用' },
  { value: 'evaluation_unknown', label: '待确认' },
  { value: 'not_executed', label: '未执行' },
]

const errorCategoryOptions: Array<{ value: QcResultFeedbackErrorCategory; label: string }> = [
  { value: 'wrong_status', label: '判定结果不正确' },
  { value: 'wrong_reason', label: '结论或原因不正确' },
  { value: 'wrong_evidence', label: '证据引用不正确' },
  { value: 'missing_data_read', label: '已读取资料未被正确识别' },
  { value: 'wrong_suggestion', label: '处理建议不合适' },
  { value: 'rule_definition', label: '质控点口径需要调整' },
  { value: 'other', label: '其他' },
]

const canSubmit = computed(() => {
  if (selectedType.value === 'correct') return true
  if (!comment.value.trim()) return false
  if (selectedType.value === 'note') return true
  return Boolean(expectedStatus.value && errorCategory.value)
})

function feedbackTypeLabel(type: QcResultFeedbackType) {
  return type === 'correct' ? '结果准确' : type === 'incorrect' ? '结果有误' : '补充说明'
}

function expectedStatusLabel(status: QcResultExpectedStatus) {
  return expectedStatusOptions.find((option) => option.value === status)?.label || status
}

function resetDraft(feedback?: QcResultFeedbackRecord | null) {
  selectedType.value = feedback?.feedback_type || ''
  expectedStatus.value = feedback?.expected_status || ''
  errorCategory.value = feedback?.error_category || ''
  comment.value = feedback?.comment || ''
}

function startEditing(type?: QcResultFeedbackType) {
  resetDraft(props.feedback)
  if (type) selectedType.value = type
  editing.value = true
}

function startEditingFromButton() {
  startEditing()
}

function startIncorrectEditing() {
  startEditing('incorrect')
}

function startNoteEditing() {
  startEditing('note')
}

function cancelEditing() {
  editing.value = false
  resetDraft(props.feedback)
}

function submitCorrect() {
  if (props.saving) return
  emit('submit', { feedback_type: 'correct' })
}

function submit() {
  if (!canSubmit.value || !selectedType.value || props.saving) return
  const input: SaveQcResultFeedbackInput = {
    feedback_type: selectedType.value,
  }
  if (expectedStatus.value) input.expected_status = expectedStatus.value
  if (errorCategory.value) input.error_category = errorCategory.value
  if (comment.value.trim()) input.comment = comment.value.trim()
  emit('submit', input)
}

watch(
  () => props.feedback,
  (feedback, previousFeedback) => {
    // 父层只有在接口成功后才会更新 feedback；失败时保持原值，让表单继续可编辑。
    if (editing.value && feedback && feedback !== previousFeedback) {
      editing.value = false
    }
    if (!editing.value) resetDraft(feedback)
  },
  { immediate: true },
)
</script>

<style scoped>
.qc-result-feedback {
  margin-top: 16px;
  padding: 12px 0 0;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  line-height: 18px;
}

.feedback-loading {
  margin: 0;
  color: rgba(29, 29, 31, 0.46);
  font-size: 11px;
}

.feedback-prompt,
.feedback-submitted,
.feedback-form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.feedback-prompt > span,
.feedback-label {
  color: rgba(29, 29, 31, 0.58);
  font-weight: 600;
}

.feedback-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.feedback-action,
.feedback-edit-button,
.feedback-cancel,
.feedback-submit {
  min-height: 29px;
  padding: 4px 10px;
  border-radius: 7px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  transition: 180ms ease;
}

.feedback-action {
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: #fff;
  color: rgba(29, 29, 31, 0.72);
}

.feedback-action:hover:not(:disabled),
.feedback-edit-button:hover:not(:disabled),
.feedback-cancel:hover:not(:disabled) {
  border-color: rgba(0, 102, 204, 0.25);
  background: rgba(0, 102, 204, 0.05);
  color: #0066cc;
}

.feedback-action.is-correct {
  color: #087443;
}

.feedback-action.is-incorrect {
  color: #c24136;
}

.feedback-action.is-note {
  color: #7c5a00;
}

.feedback-action:disabled,
.feedback-cancel:disabled,
.feedback-submit:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.feedback-submitted {
  align-items: flex-start;
}

.feedback-submitted-copy {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  min-width: 0;
}

.feedback-submitted-copy strong {
  color: #0066cc;
  font-size: 12px;
}

.feedback-comment {
  width: 100%;
  color: rgba(29, 29, 31, 0.7);
  white-space: pre-wrap;
  word-break: break-word;
}

.feedback-edit-button,
.feedback-cancel {
  flex: none;
  border: 1px solid rgba(0, 0, 0, 0.09);
  background: transparent;
  color: #0066cc;
}

.feedback-form {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  padding: 11px;
  border-radius: 9px;
  background: rgba(0, 102, 204, 0.035);
}

.feedback-form-title {
  display: grid;
  gap: 2px;
}

.feedback-form-title strong {
  color: rgba(29, 29, 31, 0.82);
  font-size: 13px;
}

.feedback-form-title span {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
}

.feedback-field {
  display: grid;
  gap: 4px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 11px;
  font-weight: 600;
}

.feedback-field select,
.feedback-field textarea {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 7px;
  background: #fff;
  color: rgba(29, 29, 31, 0.82);
  font: inherit;
  font-weight: 500;
  outline: none;
}

.feedback-field select {
  min-height: 30px;
  padding: 4px 7px;
}

.feedback-field textarea {
  min-height: 64px;
  padding: 7px;
  line-height: 18px;
  resize: vertical;
}

.feedback-field select:focus,
.feedback-field textarea:focus {
  border-color: rgba(0, 102, 204, 0.32);
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.08);
}

.feedback-form-actions {
  justify-content: flex-end;
}

.feedback-submit {
  border: 1px solid #0066cc;
  background: #0066cc;
  color: #fff;
  box-shadow: 0 2px 6px rgba(0, 102, 204, 0.18);
}

.feedback-submit:hover:not(:disabled) {
  background: #005bb8;
}

.feedback-error {
  margin: 8px 0 0;
  color: #b42318;
  font-size: 11px;
  line-height: 17px;
}

@media (max-width: 520px) {
  .feedback-prompt,
  .feedback-submitted {
    align-items: flex-start;
    flex-direction: column;
  }

  .feedback-actions {
    justify-content: flex-start;
  }
}
</style>
